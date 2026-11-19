"""Universal collection operations; canonical pointers remain owned by DataService."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, select

from business_layer.schemas.models import (
    BusinessCollection,
    BusinessCollectionItem,
    BusinessCollectionItemVersion,
    BusinessEntityFieldVersion,
    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)
from business_layer.services.transactions import transaction
from business_layer.services.validation import validate_value
from business_layer.services.value_history import (
    accept_timeline,
    accept_value,
    aware,
    history_temporal_predicates,
    temporal_predicates,
)

ITEM_PAYLOAD = ("position", "value_json", "reference_object_id", "source_id", "present")
POINTER_PAYLOAD = ("value_json", "collection_id", "validated_against_field_version_id")


def covers(row, at):
    return row.valid_from <= at and (row.valid_to is None or at < row.valid_to)


def item_value(row):
    if row.reference_object_id is not None:
        return row.reference_object_id
    if row.source_id is not None:
        return row.source_id
    return row.value_json


def payload(position, value, definition):
    result = dict.fromkeys(ITEM_PAYLOAD)
    result.update(position=position, present=position is not None)
    if position is not None:
        channel = {"reference": "reference_object_id", "source": "source_id"}.get(
            definition["item"]["type"], "value_json"
        )
        result[channel] = value
    return result


class CollectionsService:
    def __init__(self, session, data_service=None):
        self.session = session
        self._data = data_service

    @property
    def data(self):
        if self._data is None:
            from business_layer.services.data import DataService

            self._data = DataService(self.session)
        return self._data

    async def _definition(self, slot, at, known_at):
        return await self.session.scalar(
            select(BusinessEntityFieldVersion).where(
                BusinessEntityFieldVersion.business_entity_field_id
                == slot.business_entity_field_id,
                *temporal_predicates(BusinessEntityFieldVersion, at, known_at),
            )
        )

    async def _pointer(self, slot_id, at, known_at):
        return await self.session.scalar(
            select(BusinessObjectFieldValue).where(
                BusinessObjectFieldValue.business_object_field_id == slot_id,
                *temporal_predicates(BusinessObjectFieldValue, at, known_at),
            )
        )

    async def _identity(self, collection_id):
        collection = await self.session.get(
            BusinessCollection, collection_id, populate_existing=True
        )
        if collection is None:
            raise HTTPException(404, "Collection not found")
        if collection.root_field_id is None:
            raise HTTPException(422, "UNSUPPORTED_NESTED_COLLECTION")
        return collection

    async def _lock(self, collection_id, expected_revision):
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 0
        ):
            raise HTTPException(422, "Invalid collection revision")
        collection = await self._identity(collection_id)
        slot = await self.session.get(BusinessObjectField, collection.root_field_id)
        await self.data._lock_object(slot.business_object_id)
        collection = await self.session.scalar(
            select(BusinessCollection)
            .where(BusinessCollection.id == collection_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if expected_revision is not None and expected_revision != collection.revision:
            raise HTTPException(409, "Collection changed; reload its latest revision")
        return collection, slot

    async def _snapshot(self, collection_ids, *, at=None, known_at=None):
        """Read ordered contents and their guard in one PostgreSQL snapshot.

        Current reads use statement time, not a timestamp captured before a
        concurrent writer committed. Explicit knowledge-time reads derive the
        guard from accepted decisions visible at that knowledge time.
        """
        if not collection_ids:
            return {}
        valid_at = at if at is not None else func.statement_timestamp()
        recorded_at = known_at if known_at is not None else func.statement_timestamp()
        query = select(BusinessCollection.id).select_from(BusinessCollection)
        if known_at is None:
            revision = BusinessCollection.revision
        else:
            decisions = (
                select(
                    BusinessCollectionItemVersion.collection_id,
                    func.count(func.distinct(BusinessCollectionItemVersion.transaction_from)).label(
                        "revision"
                    ),
                )
                .where(
                    BusinessCollectionItemVersion.collection_id.in_(collection_ids),
                    BusinessCollectionItemVersion.transaction_from <= known_at,
                )
                .group_by(BusinessCollectionItemVersion.collection_id)
                .subquery()
            )
            query = query.outerjoin(decisions, decisions.c.collection_id == BusinessCollection.id)
            revision = func.coalesce(decisions.c.revision, 0)
        query = (
            query.add_columns(revision, BusinessCollectionItemVersion)
            .outerjoin(
                BusinessCollectionItemVersion,
                and_(
                    BusinessCollectionItemVersion.collection_id == BusinessCollection.id,
                    BusinessCollectionItemVersion.present.is_(True),
                    *temporal_predicates(BusinessCollectionItemVersion, valid_at, recorded_at),
                ),
            )
            .where(BusinessCollection.id.in_(collection_ids))
            .order_by(BusinessCollection.id, BusinessCollectionItemVersion.position)
        )
        rows = (await self.session.execute(query)).all()
        result = {}
        for identity, token, row in rows:
            view = result.setdefault(identity, {"revision": token, "items": []})
            if row is not None:
                view["items"].append(
                    {
                        "id": row.item_id,
                        "version_id": row.id,
                        "position": row.position,
                        "value": item_value(row),
                        "valid_from": row.valid_from,
                    }
                )
        return result

    async def get_collection(self, collection_id, *, at=None, known_at=None):
        try:
            at = aware(at) if at is not None else None
            known_at = aware(known_at) if known_at is not None else None
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        collection = await self._identity(collection_id)
        if known_at is not None and collection.created_at > known_at:
            raise HTTPException(404, "Collection was not known at the requested time")
        snapshot = (await self._snapshot([collection_id], at=at, known_at=known_at))[collection_id]
        slot = await self.session.get(BusinessObjectField, collection.root_field_id)
        valid_at = at if at is not None else func.statement_timestamp()
        recorded_at = known_at if known_at is not None else func.statement_timestamp()
        pointer = await self._pointer(slot.id, valid_at, recorded_at)
        definition = await self._definition(slot, valid_at, recorded_at)
        return {
            "id": collection.id,
            "root_field_id": collection.root_field_id,
            "parent_item_id": collection.parent_item_id,
            "revision": snapshot["revision"],
            "created_at": collection.created_at,
            "active": bool(
                pointer
                and pointer.collection_id == collection_id
                and definition
                and definition.status == "ACTIVE"
            ),
            "items": snapshot["items"],
        }

    async def list_collection_items(self, collection_id, *, offset=0, limit=100, **times):
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(422, "Invalid pagination")
        result = await self.get_collection(collection_id, **times)
        return {
            "items": result["items"][offset : offset + limit],
            "total": len(result["items"]),
            "offset": offset,
            "limit": limit,
            "revision": result["revision"],
        }

    async def materialize_fields(self, collection_ids, *, at=None, known_at=None):
        """Batch the canonical reader with contents and revision guards kept together."""
        snapshots = await self._snapshot(collection_ids, at=at, known_at=known_at)
        return {
            identity: {
                "value": [item["value"] for item in snapshot["items"]],
                "revision": snapshot["revision"],
            }
            for identity, snapshot in snapshots.items()
        }

    async def item_history(
        self, collection_id, item_id, *, offset=0, limit=100, at=None, known_at=None
    ):
        await self._identity(collection_id)
        await self._member(collection_id, item_id)
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(422, "Invalid pagination")
        try:
            times = history_temporal_predicates(
                BusinessCollectionItemVersion, at=at, known_at=known_at
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        rows = (
            await self.session.scalars(
                select(BusinessCollectionItemVersion)
                .where(
                    BusinessCollectionItemVersion.item_id == item_id,
                    *times,
                )
                .order_by(
                    BusinessCollectionItemVersion.transaction_from.desc(),
                    BusinessCollectionItemVersion.valid_from.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [
            {
                "id": row.id,
                "item_id": item_id,
                "position": row.position,
                "present": row.present,
                "value": item_value(row),
                "valid_from": row.valid_from,
                "valid_to": row.valid_to,
                "transaction_from": row.transaction_from,
                "transaction_to": row.transaction_to,
            }
            for row in rows
        ]

    async def _member(self, collection_id, item_id):
        item = await self.session.get(BusinessCollectionItem, item_id)
        if item is None or item.collection_id != collection_id:
            raise HTTPException(404, "Item does not belong to this collection")
        return item

    async def _new_item(self, collection_id, now):
        item = BusinessCollectionItem(collection_id=collection_id, created_at=now)
        self.session.add(item)
        await self.session.flush()
        return item.id

    async def set_field_value(
        self,
        slot_id,
        value,
        *,
        effective_at,
        recorded_at,
        field_version,
        expected_revision=None,
        require_revision=False,
        has_value_precondition=False,
    ):
        """Called by DataService inside the existing owner/model transaction locks."""
        pointer = await self._pointer(slot_id, effective_at, recorded_at)
        if (
            pointer is not None
            and pointer.collection_id is not None
            and require_revision
            and (expected_revision is None or not has_value_precondition)
        ):
            raise HTTPException(
                422,
                "Existing collections require expected_value_ids and expected_collection_revisions",
            )
        if (
            pointer is not None
            and pointer.collection_id is not None
            and expected_revision is not None
        ):
            await self._lock(pointer.collection_id, expected_revision)
        if value is None:
            return await accept_value(
                self.session,
                slot_id,
                None,
                validated_against_field_version_id=field_version.id,
                effective_at=effective_at,
                recorded_at=recorded_at,
            )
        if pointer is not None and pointer.collection_id is not None:
            collection, _ = await self._lock(pointer.collection_id, expected_revision)
        else:
            collection = BusinessCollection(root_field_id=slot_id, created_at=recorded_at)
            self.session.add(collection)
            await self.session.flush()
        version = await accept_value(
            self.session,
            slot_id,
            None,
            collection_id=collection.id,
            validated_against_field_version_id=field_version.id,
            effective_at=effective_at,
            recorded_at=recorded_at,
        )
        await self._mutate_locked(
            collection,
            "replace",
            values=value,
            field_version=field_version,
            effective_at=effective_at,
            recorded_at=recorded_at,
        )
        return version

    async def create_collection(
        self, root_field_id, values=None, *, effective_at=None, expected_value_id=None
    ):
        async with transaction(self.session):
            slot = await self.session.get(BusinessObjectField, root_field_id)
            if slot is None:
                raise HTTPException(404, "Business object field not found")
            obj = await self.data._lock_object(slot.business_object_id)
            now = datetime.now(UTC)
            at = self._effective(effective_at, now)
            fields = await self.data._active_fields(obj.business_entity_id, now)
            definition = fields.get(slot.business_entity_field_id)
            if (
                not definition
                or definition.status != "ACTIVE"
                or definition.definition_json["type"] != "list"
            ):
                raise HTTPException(422, "Field does not have an active List definition")
            current = await self._pointer(slot.id, at, now)
            if (current.id if current else None) != expected_value_id:
                raise HTTPException(409, "Field value changed; reload it")
            if current and current.collection_id is not None:
                raise HTTPException(409, "Field already has a collection")
            version = await self.set_field_value(
                slot.id,
                values if values is not None else [],
                field_version=definition,
                effective_at=at,
                recorded_at=now,
            )
            slot.effective_value_id = version.id
            collection_id = version.collection_id
        return await self.get_collection(collection_id, at=at)

    @staticmethod
    def _effective(value, now):
        try:
            result = aware(value) if value is not None else now
            if result > now:
                raise ValueError("effective_at cannot be in the future")
            return result
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    async def _mutate(
        self, collection_id, operation, *, expected_revision=None, effective_at=None, **arguments
    ):
        async with transaction(self.session):
            collection, slot = await self._lock(collection_id, expected_revision)
            now = datetime.now(UTC)
            at = self._effective(effective_at, now)
            # The model lock held by _lock serializes this lookup with schema writes.
            owner = await self.session.get(BusinessObject, slot.business_object_id)
            fields = await self.data._active_fields(owner.business_entity_id, now)
            field_version = fields.get(slot.business_entity_field_id)
            if field_version is None or field_version.definition_json["type"] != "list":
                raise HTTPException(409, "Field does not have an active List definition")
            await self._mutate_locked(
                collection,
                operation,
                field_version=field_version,
                effective_at=at,
                recorded_at=now,
                **arguments,
            )
        return await self.get_collection(collection_id, at=at)

    async def _mutate_locked(
        self,
        collection,
        operation,
        *,
        effective_at,
        recorded_at,
        field_version,
        item_id=None,
        value=None,
        position=None,
        item_ids=None,
        values=None,
    ):
        """Transform every affected valid-time slice, preserving unrelated later edits.

        Each item's complete desired suffix is submitted once to the common
        bitemporal engine. This avoids overlapping decisions inside a reorder.
        """
        slot = await self.session.get(BusinessObjectField, collection.root_field_id)
        pointers = list(
            (
                await self.session.scalars(
                    select(BusinessObjectFieldValue).where(
                        BusinessObjectFieldValue.business_object_field_id == slot.id,
                        BusinessObjectFieldValue.transaction_to.is_(None),
                    )
                )
            ).all()
        )
        definitions = list(
            (
                await self.session.scalars(
                    select(BusinessEntityFieldVersion).where(
                        BusinessEntityFieldVersion.business_entity_field_id
                        == slot.business_entity_field_id,
                        BusinessEntityFieldVersion.transaction_to.is_(None),
                    )
                )
            ).all()
        )
        rows = list(
            (
                await self.session.scalars(
                    select(BusinessCollectionItemVersion).where(
                        BusinessCollectionItemVersion.collection_id == collection.id,
                        BusinessCollectionItemVersion.transaction_to.is_(None),
                    )
                )
            ).all()
        )

        def definition_at(at):
            return next((row for row in definitions if covers(row, at)), None)

        def active_at(at):
            pointer = next((row for row in pointers if covers(row, at)), None)
            definition = definition_at(at)
            return bool(
                pointer
                and pointer.collection_id == collection.id
                and definition
                and definition.status == "ACTIVE"
                and definition.definition_json["type"] == "list"
            )

        def state_at(at):
            return [
                (row.item_id, item_value(row))
                for row in sorted(
                    (row for row in rows if covers(row, at) and row.present),
                    key=lambda row: row.position,
                )
            ]

        if not active_at(effective_at):
            raise HTTPException(409, "Collection is not the active field value at effective_at")
        original = state_at(effective_at)
        original_ids = [identity for identity, _ in original]
        if item_id is not None:
            await self._member(collection.id, item_id)
        if operation in ("set", "move") and item_id not in original_ids:
            raise HTTPException(404, "Item is not present at effective_at")
        if operation == "move" and position is None:
            raise HTTPException(422, "Move requires a position")
        if position is not None and (
            type(position) is not int
            or position < 0
            or position > len(original) - (operation == "move")
        ):
            raise HTTPException(422, "Position is outside the collection")
        if operation == "reorder" and (
            len(item_ids) != len(set(item_ids)) or set(item_ids) != set(original_ids)
        ):
            raise HTTPException(422, "Reorder must contain every present item exactly once")
        allocated = []
        if operation == "insert":
            allocated = [await self._new_item(collection.id, recorded_at)]
        if operation == "replace":
            if not isinstance(values, list):
                raise HTTPException(422, "Expected a list")
            allocated = original_ids[: len(values)]
            while len(allocated) < len(values):
                allocated.append(await self._new_item(collection.id, recorded_at))
        if operation == "restore" and item_id in original_ids:
            raise HTTPException(409, "Item is already present")
        boundaries = {effective_at}
        for row in [*rows, *pointers, *definitions]:
            boundaries.update(
                time
                for time in (row.valid_from, row.valid_to)
                if time is not None and time > effective_at
            )
        starts = sorted(boundaries)
        identities = {row.item_id for row in rows} | set(allocated)
        if operation == "restore":
            identities.add(item_id)
        timelines = {identity: [] for identity in identities}
        pointer_timeline = []
        validated_links = set()
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else None
            state = state_at(start)
            definition_row = definition_at(start)
            definition = definition_row.definition_json if definition_row else None
            if active_at(start):
                if operation == "insert":
                    state.insert(
                        len(state) if position is None else min(position, len(state)),
                        (allocated[0], value),
                    )
                elif operation == "set":
                    state = [
                        (identity, value if identity == item_id else old) for identity, old in state
                    ]
                elif operation == "remove":
                    state = [(identity, old) for identity, old in state if identity != item_id]
                elif operation == "move":
                    moved = next((pair for pair in state if pair[0] == item_id), None)
                    if moved is not None:
                        state.remove(moved)
                        state.insert(min(position, len(state)), moved)
                elif operation == "reorder":
                    by_id = dict(state)
                    state = [
                        (identity, by_id[identity]) for identity in item_ids if identity in by_id
                    ] + [pair for pair in state if pair[0] not in item_ids]
                elif operation == "replace":
                    state = list(zip(allocated, values, strict=True))
                elif operation == "restore" and item_id not in dict(state):
                    state.insert(
                        len(state) if position is None else min(position, len(state)),
                        (item_id, value),
                    )
                try:
                    validate_value([old for _, old in state], definition)
                    # Backdated writes must also satisfy the active definition
                    # recorded as their validation provenance, just like scalars.
                    if definition_row.id != field_version.id:
                        validate_value([old for _, old in state], field_version.definition_json)
                except (ValueError, TypeError, OverflowError) as error:
                    raise HTTPException(422, str(error)) from error
                if definition["item"]["type"] in ("reference", "source"):
                    for _, old in state:
                        link = (
                            definition["item"]["type"],
                            definition["item"].get("reference_entity_id"),
                            old,
                        )
                        if link not in validated_links:
                            await self.data._validate_link(
                                old, definition["item"], slot.business_entity_field_id, start
                            )
                            validated_links.add(link)
            pointer = next((row for row in pointers if covers(row, start)), None)
            if pointer is not None:
                pointer_payload = {key: getattr(pointer, key) for key in POINTER_PAYLOAD}
                if active_at(start):
                    pointer_payload["validated_against_field_version_id"] = field_version.id
                pointer_timeline.append((start, end, pointer_payload))
            if active_at(start):
                desired = {
                    identity: payload(pos, old, definition)
                    for pos, (identity, old) in enumerate(state)
                }
            else:
                desired = {
                    row.item_id: {key: getattr(row, key) for key in ITEM_PAYLOAD}
                    for row in rows
                    if covers(row, start) and row.present
                }
            for identity in identities:
                old_row = next(
                    (row for row in rows if row.item_id == identity and covers(row, start)), None
                )
                if identity in desired:
                    timelines[identity].append((start, end, desired[identity]))
                elif old_row is not None:
                    timelines[identity].append((start, end, payload(None, None, None)))
        changed = False
        for identity, segments in timelines.items():
            changed |= await accept_timeline(
                self.session,
                BusinessCollectionItemVersion,
                {"item_id": identity, "collection_id": collection.id},
                segments,
                effective_at=effective_at,
                recorded_at=recorded_at,
            )
        if changed:
            collection.revision += 1
            await self.session.flush()
        # Ordinary item edits remain independent of canonical value history.
        # A new validating schema is a new canonical decision even if the
        # collection identity or contents are unchanged.
        if await accept_timeline(
            self.session,
            BusinessObjectFieldValue,
            {"business_object_field_id": slot.id},
            pointer_timeline,
            effective_at=effective_at,
            recorded_at=recorded_at,
        ):
            current = await self._pointer(slot.id, recorded_at, recorded_at)
            slot.effective_value_id = current.id if current else None
            await self.session.flush()

    async def append_item(self, collection_id, value, **options):
        return await self._mutate(collection_id, "insert", value=value, **options)

    async def insert_item(self, collection_id, position, value, **options):
        return await self._mutate(
            collection_id, "insert", value=value, position=position, **options
        )

    async def set_item_value(self, collection_id, item_id, value, **options):
        return await self._mutate(collection_id, "set", item_id=item_id, value=value, **options)

    async def move_item(self, collection_id, item_id, position, **options):
        return await self._mutate(
            collection_id, "move", item_id=item_id, position=position, **options
        )

    async def remove_item(self, collection_id, item_id, **options):
        return await self._mutate(collection_id, "remove", item_id=item_id, **options)

    async def reorder_items(self, collection_id, item_ids, **options):
        return await self._mutate(collection_id, "reorder", item_ids=item_ids, **options)

    async def replace_collection(self, collection_id, values, **options):
        return await self._mutate(collection_id, "replace", values=values, **options)

    async def clear_collection(self, collection_id, **options):
        return await self.replace_collection(collection_id, [], **options)

    async def restore_item(self, collection_id, item_id, value, *, position=None, **options):
        return await self._mutate(
            collection_id, "restore", item_id=item_id, value=value, position=position, **options
        )
