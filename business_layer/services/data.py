"""Object identities, field slots, validation, lifecycle, and value history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy import and_, delete, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from business_layer.schemas.enums import BusinessDefinitionStatus
from business_layer.schemas.execution import SeedResult
from business_layer.schemas.models import (
    BusinessEntity,
    BusinessEntityField,
    BusinessEntityFieldVersion,
    BusinessEntityRelationVersion,
    BusinessEntityVersion,
    BusinessModel,
    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)
from business_layer.schemas.models.dtos import (
    BusinessObjectFieldRead,
    BusinessObjectFieldValueRead,
    BusinessObjectRead,
    CreateObjectResponse,
)
from business_layer.services.transactions import transaction
from business_layer.services.validation import validate_value
from business_layer.services.value_history import (
    accept_value,
    aware,
    history_predicates,
    temporal_predicates,
)

if TYPE_CHECKING:
    from business_layer.services.schema_parser import Program


def current(model, at):
    return (
        model.valid_from <= at,
        or_(model.valid_to.is_(None), model.valid_to > at),
        model.transaction_to.is_(None),
    )


class DataService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        from business_layer.services.collections import CollectionsService

        self.collections = CollectionsService(session, self)

    async def _lock_entity(self, entity_id: int):
        entity = await self._session.get(BusinessEntity, entity_id)
        if entity is None:
            raise HTTPException(404, "Business entity not found")
        # Model lock also serializes schema revisions and unique-value checks.
        await self._session.scalar(
            select(BusinessModel)
            .where(BusinessModel.id == entity.business_model_id)
            .with_for_update()
        )
        return await self._session.scalar(
            select(BusinessEntity)
            .where(BusinessEntity.id == entity_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def _lock_object(self, object_id: int, *, allow_archived=False):
        entity_id = await self._session.scalar(
            select(BusinessObject.business_entity_id).where(BusinessObject.id == object_id)
        )
        if entity_id is None:
            raise HTTPException(404, "Business object not found")
        await self._lock_entity(entity_id)
        obj = await self._session.scalar(
            select(BusinessObject)
            .where(BusinessObject.id == object_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if obj is None:
            raise HTTPException(404, "Business object not found")
        if obj.archived_at is not None and not allow_archived:
            raise HTTPException(409, "Business object is archived")
        return obj

    async def _active_fields(self, entity_id: int, at: datetime):
        active = await self._session.scalar(
            select(BusinessEntityVersion.id).where(
                BusinessEntityVersion.business_entity_id == entity_id,
                BusinessEntityVersion.status == BusinessDefinitionStatus.ACTIVE,
                *current(BusinessEntityVersion, at),
            )
        )
        if active is None:
            raise HTTPException(409, "Business entity has no active definition")
        rows = (
            await self._session.execute(
                select(
                    BusinessEntityField.id,
                    BusinessEntityFieldVersion,
                )
                .join(
                    BusinessEntityFieldVersion,
                    BusinessEntityFieldVersion.business_entity_field_id == BusinessEntityField.id,
                )
                .where(
                    BusinessEntityField.business_entity_id == entity_id,
                    BusinessEntityFieldVersion.status == BusinessDefinitionStatus.ACTIVE,
                    *current(BusinessEntityFieldVersion, at),
                )
                .order_by(BusinessEntityField.id)
            )
        ).all()
        return dict(rows)

    async def _sync_slots(self, obj, fields):
        slots = dict(
            (
                await self._session.execute(
                    select(
                        BusinessObjectField.business_entity_field_id,
                        BusinessObjectField.id,
                    ).where(BusinessObjectField.business_object_id == obj.id)
                )
            ).all()
        )
        for field_id in fields.keys() - slots.keys():
            slot = BusinessObjectField(business_object_id=obj.id, business_entity_field_id=field_id)
            self._session.add(slot)
            await self._session.flush()
            slots[field_id] = slot.id
        return slots

    async def create_object(
        self, entity_id: int, values: dict[int, Any] | None = None, *, apply_defaults: bool = True
    ):
        """Initial values are keyed by entity-field ID, before object slots exist."""
        async with transaction(self._session):
            await self._lock_entity(entity_id)
            now = datetime.now(UTC)
            fields = await self._active_fields(entity_id, now)
            unknown = set(values or {}) - fields.keys()
            if unknown:
                raise HTTPException(422, f"Unknown or inactive entity fields: {sorted(unknown)}")
            obj = BusinessObject(business_entity_id=entity_id)
            self._session.add(obj)
            await self._session.flush()
            slots = await self._sync_slots(obj, fields)
            initial = dict(values or {})
            for field_id, version in fields.items():
                definition = version.definition_json
                if definition.get("system"):
                    if field_id in initial:
                        raise HTTPException(422, "System fields are read-only")
                    initial[field_id] = obj.id
                elif field_id not in initial:
                    if apply_defaults and (definition.get("has_default") or "default" in definition):
                        initial[field_id] = definition.get("default")
                    elif not definition.get("nullable", True):
                        raise HTTPException(422, f"Required field missing: {version.key}")
            await self._write_values(obj, slots, fields, initial, now, now, allow_system=True)
            response = CreateObjectResponse(object_id=obj.id, object_fields=slots)
        return response

    async def sync_object_fields(self, object_id: int):
        """Add slots for new fields without discarding retired slots or their history."""
        async with transaction(self._session):
            obj = await self._lock_object(object_id)
            fields = await self._active_fields(obj.business_entity_id, datetime.now(UTC))
            slots = await self._sync_slots(obj, fields)
            return CreateObjectResponse(object_id=obj.id, object_fields=slots)

    async def _validate_link(self, value, definition, field_id, at):
        """Shared scalar/collection reference and Source integrity policy."""
        if value is None:
            return
        if definition["type"] == "reference":
            target_entity = definition.get("reference_entity_id")
            if target_entity is None:
                relation = await self._session.scalar(
                    select(BusinessEntityRelationVersion).where(
                        BusinessEntityRelationVersion.from_field_id == field_id,
                        BusinessEntityRelationVersion.status == BusinessDefinitionStatus.ACTIVE,
                        *current(BusinessEntityRelationVersion, at),
                    )
                )
                target_entity = relation.to_entity_id if relation else None
            target = await self._session.get(BusinessObject, value, populate_existing=True)
            if target is None or target.business_entity_id != target_entity:
                raise HTTPException(422, "Invalid reference target")
            if target.archived_at is not None:
                raise HTTPException(422, "Reference target is archived")
        if definition["type"] == "source":
            from sources.schemas.models import Source

            source = await self._session.scalar(
                select(Source)
                .where(Source.id == value)
                .with_for_update(read=True, key_share=True)
                .execution_options(populate_existing=True)
            )
            if source is None:
                raise HTTPException(422, "Source does not exist")

    async def _write_values(
        self,
        obj,
        slots,
        fields,
        values,
        effective_at,
        now,
        *,
        allow_system=False,
        expected_collection_revisions=None,
        require_collection_revision=False,
        expected_value_ids=None,
    ):
        for field_id, value in values.items():
            version = fields.get(field_id)
            if version is None:
                raise HTTPException(409, f"Field {field_id} has no active definition")
            definition = version.definition_json
            if definition.get("system") and not allow_system:
                raise HTTPException(422, "System fields are read-only")
            try:
                validate_value(value, definition)
            except (ValueError, TypeError, OverflowError) as error:
                raise HTTPException(422, f"{version.key}: {error}") from error
            if definition["type"] == "list":
                try:
                    accepted = await self.collections.set_field_value(
                        slots[field_id],
                        value,
                        effective_at=effective_at,
                        recorded_at=now,
                        field_version=version,
                        require_revision=require_collection_revision,
                        has_value_precondition=slots[field_id] in (expected_value_ids or {}),
                        expected_revision=(expected_collection_revisions or {}).get(
                            slots[field_id]
                        ),
                    )
                    await self._session.execute(
                        update(BusinessObjectField)
                        .where(BusinessObjectField.id == slots[field_id])
                        .values(effective_value_id=accepted.id)
                    )
                except ValueError as error:
                    raise HTTPException(422, str(error)) from error
                continue
            await self._validate_link(value, definition, field_id, now)
            if definition.get("unique") and value is not None:
                conflict = await self._session.scalar(
                    select(BusinessObjectFieldValue.id)
                    .join(
                        BusinessObjectField,
                        BusinessObjectField.id == BusinessObjectFieldValue.business_object_field_id,
                    )
                    .where(
                        BusinessObjectField.business_entity_field_id == field_id,
                        BusinessObjectField.business_object_id != obj.id,
                        BusinessObjectFieldValue.transaction_to.is_(None),
                        or_(
                            BusinessObjectFieldValue.valid_to.is_(None),
                            BusinessObjectFieldValue.valid_to > effective_at,
                        ),
                        BusinessObjectFieldValue.value_json
                        == literal(
                            value, type_=BusinessObjectFieldValue.__table__.c.value_json.type
                        ),
                    )
                    .limit(1)
                )
                if conflict is not None:
                    raise HTTPException(409, f"{version.key}: value must be unique")
            try:
                accepted = await accept_value(
                    self._session,
                    slots[field_id],
                    value,
                    field_version=version,
                    effective_at=effective_at,
                    recorded_at=now,
                )
                await self._session.execute(
                    update(BusinessObjectField)
                    .where(
                        BusinessObjectField.id == slots[field_id],
                    )
                    .values(effective_value_id=accepted.id)
                )
            except ValueError as error:
                raise HTTPException(422, str(error)) from error

    async def assign_object_fields_values(
        self,
        object_id: int,
        dict_values: dict[int, Any],
        *,
        effective_at: datetime | None = None,
        expected_value_ids: dict[int, int | None] | None = None,
        expected_collection_revisions: dict[int, int] | None = None,
    ):
        try:
            effective_at = aware(effective_at) if effective_at is not None else None
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        async with transaction(self._session):
            obj = await self._lock_object(object_id)
            now = datetime.now(UTC)
            fields = await self._active_fields(obj.business_entity_id, now)
            slots = await self._sync_slots(obj, fields)
            reverse = {slots[field_id]: field_id for field_id in fields}
            unknown = set(dict_values) - reverse.keys()
            if unknown:
                raise HTTPException(422, f"Fields are not active on object: {sorted(unknown)}")
            if expected_value_ids is not None:
                if set(expected_value_ids) - set(dict_values):
                    raise HTTPException(422, "Expected value IDs must refer to assigned slots")
                current_values = dict(
                    (
                        await self._session.execute(
                            select(
                                BusinessObjectFieldValue.business_object_field_id,
                                BusinessObjectFieldValue.id,
                            ).where(
                                BusinessObjectFieldValue.business_object_field_id.in_(
                                    list(expected_value_ids)
                                ),
                                BusinessObjectFieldValue.transaction_to.is_(None),
                                BusinessObjectFieldValue.valid_to.is_(None),
                            )
                        )
                    ).all()
                )
                for slot_id, expected in expected_value_ids.items():
                    if current_values.get(slot_id) != expected:
                        raise HTTPException(409, f"Stale value for object field {slot_id}")
            values = {reverse[slot_id]: value for slot_id, value in dict_values.items()}
            if set(expected_collection_revisions or {}) - set(dict_values):
                raise HTTPException(422, "Collection revisions must refer to assigned slots")
            for slot_id, revision in (expected_collection_revisions or {}).items():
                if (
                    fields[reverse[slot_id]].definition_json["type"] != "list"
                    or type(revision) is not int
                    or revision < 0
                ):
                    raise HTTPException(422, "Invalid collection revision precondition")
            await self._write_values(
                obj,
                slots,
                fields,
                values,
                effective_at or now,
                now,
                require_collection_revision=True,
                expected_value_ids=expected_value_ids,
                expected_collection_revisions=expected_collection_revisions,
            )
        return await self.get_object(object_id)

    async def archive_object(self, object_id: int):
        async with transaction(self._session):
            obj = await self._lock_object(object_id, allow_archived=True)
            if obj.archived_at is None:
                obj.archived_at = datetime.now(UTC)
        return await self.get_object(object_id)

    async def restore_object(self, object_id: int):
        async with transaction(self._session):
            obj = await self._lock_object(object_id, allow_archived=True)
            await self._active_fields(obj.business_entity_id, datetime.now(UTC))
            obj.archived_at = None
        return await self.get_object(object_id)

    async def delete_object(self, object_id: int):
        async with transaction(self._session):
            await self._lock_object(object_id, allow_archived=True)
            slots = select(BusinessObjectField.id).where(
                BusinessObjectField.business_object_id == object_id
            )
            has_values = await self._session.scalar(
                select(BusinessObjectFieldValue.id)
                .where(
                    BusinessObjectFieldValue.business_object_field_id.in_(slots),
                )
                .limit(1)
            )
            if has_values is not None:
                raise HTTPException(409, "Object has value history; archive it instead")
            await self._session.execute(
                delete(BusinessObjectField).where(
                    BusinessObjectField.business_object_id == object_id,
                )
            )
            await self._session.execute(
                delete(BusinessObject).where(BusinessObject.id == object_id)
            )

    async def _read_objects(self, objects, *, at=None, known_at=None):
        now = datetime.now(UTC)
        try:
            at = aware(at) if at is not None else now
            known_at = aware(known_at) if known_at is not None else now
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        ids = [obj.id for obj in objects]
        if not ids:
            return []
        value = BusinessObjectFieldValue
        definition = BusinessEntityFieldVersion
        rows = (
            await self._session.execute(
                select(BusinessObjectField, value)
                .join(
                    definition,
                    and_(
                        definition.business_entity_field_id
                        == BusinessObjectField.business_entity_field_id,
                        definition.status == BusinessDefinitionStatus.ACTIVE,
                        *temporal_predicates(definition, at, known_at),
                    ),
                )
                .outerjoin(
                    value,
                    and_(
                        value.business_object_field_id == BusinessObjectField.id,
                        *temporal_predicates(value, at, known_at),
                    ),
                )
                .where(BusinessObjectField.business_object_id.in_(ids))
                .order_by(
                    BusinessObjectField.id,
                )
            )
        ).all()
        collection_ids = {
            version.collection_id
            for _, version in rows
            if version is not None and version.collection_id is not None
        }
        collections = await self.collections.materialize_fields(
            collection_ids, at=at, known_at=known_at
        )
        fields = {object_id: [] for object_id in ids}
        for slot, version in rows:
            collection = collections.get(version.collection_id) if version else None
            fields[slot.business_object_id].append(
                BusinessObjectFieldRead(
                    object_field_id=slot.id,
                    business_entity_field_id=slot.business_entity_field_id,
                    value_id=version.id if version else None,
                    validated_against_field_version_id=(
                        version.validated_against_field_version_id if version else None
                    ),
                    value=(
                        collection["value"]
                        if collection is not None
                        else version.value_json
                        if version
                        else None
                    ),
                    collection_id=version.collection_id if version else None,
                    collection_revision=collection["revision"] if collection is not None else None,
                    valid_from=version.valid_from if version else None,
                )
            )
        return [
            BusinessObjectRead(
                id=obj.id,
                business_entity_id=obj.business_entity_id,
                created_at=obj.created_at,
                archived_at=obj.archived_at,
                fields=fields[obj.id],
            )
            for obj in objects
        ]

    async def get_object(self, object_id: int, *, at=None, known_at=None):
        obj = await self._session.get(BusinessObject, object_id)
        if obj is None:
            raise HTTPException(404, "Business object not found")
        return (await self._read_objects([obj], at=at, known_at=known_at))[0]

    async def list_objects(
        self, entity_id: int, *, offset=0, limit=100, include_archived=False, at=None, known_at=None
    ):
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(422, "Invalid pagination")
        if await self._session.get(BusinessEntity, entity_id) is None:
            raise HTTPException(404, "Business entity not found")
        query = select(BusinessObject).where(BusinessObject.business_entity_id == entity_id)
        if not include_archived:
            query = query.where(BusinessObject.archived_at.is_(None))
        objects = list(
            (
                await self._session.scalars(
                    query.order_by(BusinessObject.id).offset(offset).limit(limit)
                )
            ).all()
        )
        return await self._read_objects(objects, at=at, known_at=known_at)

    async def get_object_field_value_history(
        self, object_field_id: int, *, at=None, known_at=None, offset=0, limit=100
    ):
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(422, "Invalid pagination")
        if await self._session.get(BusinessObjectField, object_field_id) is None:
            raise HTTPException(404, "Business object field not found")
        try:
            predicates = history_predicates(object_field_id, at=at, known_at=known_at)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        rows = (
            await self._session.scalars(
                select(BusinessObjectFieldValue)
                .where(
                    *predicates,
                )
                .order_by(
                    BusinessObjectFieldValue.transaction_from.desc(),
                    BusinessObjectFieldValue.valid_from.desc(),
                    BusinessObjectFieldValue.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [
            BusinessObjectFieldValueRead(
                id=row.id,
                business_object_field_id=row.business_object_field_id,
                validated_against_field_version_id=row.validated_against_field_version_id,
                value=(
                    [
                        item["value"]
                        for item in (
                            await self.collections.get_collection(
                                row.collection_id,
                                at=at or row.valid_from,
                                known_at=known_at or row.transaction_from,
                            )
                        )["items"]
                    ]
                    if row.collection_id is not None
                    else row.value_json
                ),
                collection_id=row.collection_id,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                transaction_from=row.transaction_from,
                transaction_to=row.transaction_to,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def seed_objects(self, model_id: int, program: Program) -> SeedResult:
        """Apply named seeds to registered definitions, without writing schemas.

        Names are local to this execution; each constructor creates a new object. The caller may
        compose this with EntitiesService.register_program in an outer transaction.
        """
        from business_layer.services.schema_parser import analyze_program

        plan = analyze_program(program.model_copy(deep=True))
        async with transaction(self._session):
            model = await self._session.scalar(
                select(BusinessModel)
                .where(
                    BusinessModel.id == model_id,
                )
                .with_for_update()
            )
            if model is None:
                raise LookupError("Business model not found")
            result = SeedResult()
            seeds = {seed.name: seed for seed in plan.objects}
            declared = {entity.name: entity for entity in plan.schema.entities}
            definitions = {}
            now = datetime.now(UTC)
            for name in plan.seed_order:
                seed = seeds[name]
                if seed.entity not in definitions:
                    entity_id = await self._session.scalar(
                        select(BusinessEntity.id)
                        .join(
                            BusinessEntityVersion,
                            BusinessEntityVersion.business_entity_id == BusinessEntity.id,
                        )
                        .where(
                            BusinessEntity.business_model_id == model_id,
                            BusinessEntity.table_name == declared[seed.entity].tablename,
                            BusinessEntityVersion.key == seed.entity,
                            BusinessEntityVersion.status == BusinessDefinitionStatus.ACTIVE,
                            *current(BusinessEntityVersion, now),
                        )
                    )
                    if entity_id is None:
                        raise HTTPException(
                            409, f"Entity '{seed.entity}' is not registered in this model"
                        )
                    fields = await self._active_fields(entity_id, now)
                    definitions[seed.entity] = (
                        entity_id,
                        {version.key: (field_id, version) for field_id, version in fields.items()},
                    )
                entity_id, fields = definitions[seed.entity]
                supplied = {}
                for key, value in seed.values.items():
                    if key not in fields:
                        raise HTTPException(409, f"Seed field '{key}' has no active definition")
                    field_id, version = fields[key]
                    kind = version.definition_json["type"]
                    is_reference = kind == "reference" or (
                        kind == "list" and version.definition_json["item"]["type"] == "reference"
                    )
                    if is_reference and value is not None:
                        references = value if kind == "list" else [value]
                        resolved = []
                        for reference in references:
                            identity = result.objects.get(reference["$ref"])
                            if identity is None:
                                raise HTTPException(422, f"Unresolved seed reference for '{key}'")
                            resolved.append(identity)
                        value = resolved if kind == "list" else resolved[0]
                    supplied[field_id] = value
                obj = await self.create_object(entity_id, supplied)
                result.created.append(name)
                result.objects[name] = obj.object_id
            return result
