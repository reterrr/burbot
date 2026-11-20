"""Transactional SelectorTree persistence. The portable graph is the definition API."""

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from business_layer.schemas.models import BusinessEntityField, BusinessObjectField
from business_layer.services.transactions import transaction
from extraction.exceptions import ExtractionConflict, ExtractionNotFound, ExtractionValidationError
from extraction.schemas.selector import (
    Selector,
    SelectorEvaluation,
    SelectorLocator,
    SelectorPart,
    SelectorRecipe,
    SelectorVersion,
)
from extraction.schemas.selector_tree import (
    MAX_SAFE_INTEGER,
    SelectorDefinition,
    SelectorTree,
    SelectorVersionDefinition,
    validate_selector_transition,
)
from sources.schemas.models import Source, SourceSnapshot


def now_iso():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def drop_keys(data, *keys):
    return {key: value for key, value in data.items() if key not in keys}


class SelectorService:
    def __init__(self, session):
        self.session = session

    @asynccontextmanager
    async def write(self):
        try:
            async with transaction(self.session):
                yield
        except IntegrityError as error:
            raise ExtractionConflict("Selector UUID, ordering or ownership conflicts") from error

    async def selector(self, uuid, *, lock=False, required=True):
        query = select(Selector).where(Selector.uuid == uuid)
        query = query.with_for_update(read=not lock).execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        if row is None and required:
            raise ExtractionNotFound("Selector not found")
        return row

    async def version(self, selector_id, uuid):
        row = await self.session.scalar(
            select(SelectorVersion).where(
                SelectorVersion.selector_id == selector_id, SelectorVersion.uuid == uuid
            )
        )
        if row is None:
            raise ExtractionNotFound("Selector version not found")
        return row

    async def snapshots(self, row, tree, bindings):
        if not bindings:
            return {}
        referenced = {version.created_from_snapshot_uuid for version in tree.versions}
        result = {}
        for uuid, snapshot_id in bindings.items():
            if uuid not in referenced:
                raise ExtractionValidationError("Snapshot binding is absent from this tree")
            snapshot = await self.session.get(SourceSnapshot, snapshot_id)
            if snapshot is None:
                raise ExtractionNotFound("Source snapshot not found")
            if row.source_id is None or row.source_id != snapshot.source_id:
                raise ExtractionValidationError("Snapshot binding belongs to another source")
            result[uuid] = snapshot.id
        return result

    async def binding(self, binding):
        if binding is None:
            raise ExtractionValidationError("A new selector requires an explicit backend binding")
        values = binding.model_dump()
        if await self.session.get(BusinessEntityField, binding.business_entity_field_id) is None:
            raise ExtractionNotFound("Business entity field not found")
        if (
            binding.source_id is not None
            and await self.session.get(Source, binding.source_id) is None
        ):
            raise ExtractionNotFound("Source not found")
        if binding.business_object_field_id is not None:
            slot = await self.session.get(BusinessObjectField, binding.business_object_field_id)
            if slot is None:
                raise ExtractionNotFound("Business object field not found")
            if slot.business_entity_field_id != binding.business_entity_field_id:
                raise ExtractionValidationError("Object slot belongs to another entity field")
        return values

    async def definition(self, row, selector_uuid):
        return (await self._versions([row], selector_uuid))[0]

    async def tree(self, row):
        rows = list(
            await self.session.scalars(
                select(SelectorVersion)
                .where(SelectorVersion.selector_id == row.id)
                .order_by(SelectorVersion.version_no)
            )
        )
        header = {**row.metadata_json, "uuid": row.uuid}
        if row.active_version_id is not None:
            header["activeVersionUuid"] = next(
                version.uuid for version in rows if version.id == row.active_version_id
            )
        tree = SelectorTree.model_validate(
            {"selector": header, "versions": await self._versions(rows, row.uuid)}
        )
        return tree, rows

    async def _versions(self, rows, selector_uuid):
        async def children(model, key, parents):
            grouped = defaultdict(list)
            if parents:
                column = getattr(model, key)
                query = select(model).where(column.in_(parents)).order_by(column, model.position)
                for child in await self.session.scalars(query):
                    grouped[getattr(child, key)].append(child)
            return grouped

        recipes = await children(SelectorRecipe, "selector_version_id", [row.id for row in rows])
        parts = await children(
            SelectorPart, "recipe_id", [recipe.id for group in recipes.values() for recipe in group]
        )
        locators = await children(
            SelectorLocator, "part_id", [part.id for group in parts.values() for part in group]
        )
        result = []
        for row in rows:
            definition = {
                **row.metadata_json,
                "uuid": row.uuid,
                "selectorUuid": selector_uuid,
                "versionNo": row.version_no,
                "status": row.status,
                "recipes": [],
            }
            for recipe in recipes[row.id]:
                part_defs = []
                for part in parts[recipe.id]:
                    part_def = {
                        "uuid": part.uuid,
                        "order": part.position,
                        "extraction": part.extraction_json,
                        "locators": [
                            {
                                **locator.payload_json,
                                "uuid": locator.uuid,
                                "order": locator.position,
                                "kind": locator.kind,
                            }
                            for locator in locators[part.id]
                        ],
                    }
                    if part.join_with is not None:
                        part_def["joinWith"] = part.join_with
                    part_defs.append(part_def)
                definition["recipes"].append(
                    {"uuid": recipe.uuid, "order": recipe.position, "parts": part_defs}
                )
            result.append(SelectorVersionDefinition.model_validate(definition))
        return result

    async def page(self, offset, limit, source_id=None):
        query = select(Selector)
        if source_id is not None:
            query = query.where(Selector.source_id == source_id)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.session.execute(
            query.add_columns(SelectorVersion.uuid)
            .outerjoin(SelectorVersion, SelectorVersion.id == Selector.active_version_id)
            .order_by(Selector.id)
            .offset(offset)
            .limit(limit)
        )
        definitions = []
        for row, active_uuid in rows:
            header = {**row.metadata_json, "uuid": row.uuid}
            if active_uuid is not None:
                header["activeVersionUuid"] = active_uuid
            definitions.append(SelectorDefinition.model_validate(header))
        return definitions, total

    @staticmethod
    def _expect(row, revision):
        if revision is None:
            raise ExtractionValidationError("Send the selector ETag in If-Match")
        if revision != row.revision:
            raise ExtractionConflict("Selector changed; reload the current revision")

    async def import_tree(self, tree, binding=None, snapshots=None, revision=None, *, create=False):
        tree = tree.canonical_order()
        async with self.write():
            row = await self.selector(tree.selector.uuid, lock=True, required=False)
            if row is None:
                values = await self.binding(binding)
                if create and (len(tree.versions) != 1 or tree.versions[0].status != "draft"):
                    raise ExtractionValidationError("A new selector starts with one draft version")
                row = Selector(
                    uuid=tree.selector.uuid, metadata_json=self._metadata(tree), **values
                )
                self.session.add(row)
                await self.session.flush()
                snapshot_ids = await self.snapshots(row, tree, snapshots)
                await self._apply(row, None, [], tree, snapshot_ids)
            else:
                if create:
                    raise ExtractionConflict("Selector already exists; import or edit its draft")
                before, rows = await self.tree(row)
                migration = before.selector.migration
                if migration is not None:
                    if tree.selector.migration not in (None, migration):
                        raise ExtractionConflict("Legacy selector provenance cannot change")
                    tree.selector.migration = migration
                if binding is not None:
                    values = await self.binding(binding)
                    if any(getattr(row, key) != val for key, val in values.items()):
                        raise ExtractionConflict("Selector backend binding cannot change")
                snapshot_ids = await self.snapshots(row, tree, snapshots)
                mapped = {
                    version.created_from_snapshot_uuid: persisted.created_from_snapshot_id
                    for version, persisted in zip(before.versions, rows, strict=True)
                }
                if tree.portable() == before.portable() and all(
                    mapped.get(key) == val for key, val in snapshot_ids.items()
                ):
                    return before, row.revision
                self._expect(row, revision)
                await self._apply(row, before, rows, tree, snapshot_ids)
            return tree, row.revision

    async def draft(self, uuid, revision):
        async with self.write():
            row = await self.selector(uuid, lock=True)
            self._expect(row, revision)
            before, rows = await self.tree(row)
            active = before.selector.active_version_uuid
            source = next((v for v in before.versions if v.uuid == active), before.versions[-1])
            new_number = before.versions[-1].version_no + 1
            if new_number > MAX_SAFE_INTEGER:
                raise ExtractionConflict("Selector version numbers are exhausted")
            draft = drop_keys(source.portable(), "reviewedAt", "reviewedBy")
            draft.update(
                uuid=str(uuid4()), status="draft", versionNo=new_number, createdAt=now_iso()
            )
            for recipe in draft["recipes"]:
                recipe["uuid"] = str(uuid4())
                for part in recipe["parts"]:
                    part["uuid"] = str(uuid4())
                    for locator in part["locators"]:
                        locator["uuid"] = str(uuid4())
            payload = before.portable()
            payload["versions"].append(draft)
            after = SelectorTree.model_validate(payload)
            await self._apply(row, before, rows, after, {})
            return after, row.revision

    async def save_draft(self, uuid, version_uuid, version, revision):
        return await self._edit(uuid, version_uuid, revision, version=version)

    async def review(self, uuid, version_uuid, approve, reviewed_by, revision):
        return await self._edit(
            uuid, version_uuid, revision, approve=approve, reviewed_by=reviewed_by
        )

    async def _edit(
        self, uuid, version_uuid, revision, *, version=None, approve=None, reviewed_by=None
    ):
        async with self.write():
            row = await self.selector(uuid, lock=True)
            self._expect(row, revision)
            before, rows = await self.tree(row)
            payload = before.portable()
            draft = next((v for v in payload["versions"] if v["uuid"] == str(version_uuid)), None)
            if draft is None:
                raise ExtractionNotFound("Selector version not found")
            if draft["status"] != "draft":
                raise ExtractionConflict("Only a draft version can be edited or reviewed")
            if version is not None:
                if version.uuid != version_uuid or version.selector_uuid != uuid:
                    raise ExtractionValidationError(
                        "Draft identity or owner does not match the URL"
                    )
                if version.status != "draft":
                    raise ExtractionConflict("Review uses the approve or reject operation")
                payload["versions"][payload["versions"].index(draft)] = version.portable()
            else:
                if approve:
                    for other in payload["versions"]:
                        if other["status"] == "active":
                            other["status"] = "superseded"
                    payload["selector"]["activeVersionUuid"] = str(version_uuid)
                draft.update(status="active" if approve else "rejected", reviewedAt=now_iso())
                if reviewed_by is not None:
                    draft["reviewedBy"] = reviewed_by
            try:
                after = SelectorTree.model_validate(payload).canonical_order()
            except ValueError as error:
                raise ExtractionValidationError(str(error)) from error
            if after.portable() != before.portable():
                await self._apply(row, before, rows, after, {})
            return after, row.revision

    @staticmethod
    def _metadata(tree):
        header = drop_keys(tree.selector.portable(), "uuid")
        if tree.selector.active_version_uuid is not None:
            header.pop("activeVersionUuid", None)
        return header

    async def _apply(self, row, before, rows, after, snapshot_ids):
        existing = {item.uuid: item for item in rows}
        old = {item.uuid: item for item in before.versions} if before else {}
        if before:
            try:
                validate_selector_transition(before, after)
            except ValueError as error:
                raise ExtractionConflict(str(error)) from error
        # Close the former active row before inserting or approving any new one.
        for definition in after.versions:
            prior = existing.get(definition.uuid)
            if prior and prior.status == "active" and definition.status == "superseded":
                prior.status = "superseded"
        await self.session.flush()

        replaced = set()
        mapped_snapshots = {
            old[item.uuid].created_from_snapshot_uuid: item.created_from_snapshot_id
            for item in rows
            if item.created_from_snapshot_id is not None
        }
        mapped_snapshots.update(snapshot_ids)
        for definition in after.versions:
            prior = old.get(definition.uuid)
            if prior and prior.status == "draft" and prior.recipes != definition.recipes:
                stored = existing[definition.uuid]
                await self._clear_recipes(stored.id)
                replaced.add(definition.uuid)

        for definition in after.versions:
            stored = existing.get(definition.uuid)
            snapshot_id = mapped_snapshots.get(definition.created_from_snapshot_uuid)
            if stored is not None and old[definition.uuid].status != "draft":
                if definition.created_from_snapshot_uuid in snapshot_ids and (
                    stored.created_from_snapshot_id != snapshot_id
                ):
                    raise ExtractionConflict("An approved version's snapshot binding cannot change")
                continue
            attributes = drop_keys(
                definition.portable(), "uuid", "selectorUuid", "versionNo", "status", "recipes"
            )
            if stored is None:
                stored = SelectorVersion(
                    uuid=definition.uuid,
                    selector_id=row.id,
                    version_no=definition.version_no,
                    status="draft",
                    metadata_json=attributes,
                    created_from_snapshot_id=snapshot_id,
                )
                self.session.add(stored)
                await self.session.flush()
                existing[stored.uuid] = stored
                replaced.add(stored.uuid)
            else:
                stored.metadata_json = attributes
                stored.created_from_snapshot_id = snapshot_id
            if definition.uuid in replaced:
                await self._add_recipes(stored.id, definition.recipes)
            stored.status = definition.status
        row.active_version_id = (
            existing[after.selector.active_version_uuid].id
            if after.selector.active_version_uuid is not None
            else None
        )
        row.metadata_json = self._metadata(after)
        if before:
            row.revision += 1
        await self.session.flush()

    async def _clear_recipes(self, version_id):
        recipes = select(SelectorRecipe.id).where(SelectorRecipe.selector_version_id == version_id)
        parts = select(SelectorPart.id).where(SelectorPart.recipe_id.in_(recipes))
        await self.session.execute(
            delete(SelectorLocator).where(SelectorLocator.part_id.in_(parts))
        )
        await self.session.execute(delete(SelectorPart).where(SelectorPart.recipe_id.in_(recipes)))
        await self.session.execute(
            delete(SelectorRecipe).where(SelectorRecipe.selector_version_id == version_id)
        )
        # Mutable draft tests describe the previous definition, as in the extension.
        await self.session.execute(
            delete(SelectorEvaluation).where(
                SelectorEvaluation.selector_version_id == version_id,
                SelectorEvaluation.provenance == "client_reported",
            )
        )

    async def _add_recipes(self, version_id, recipes):
        for recipe in recipes:
            stored = SelectorRecipe(
                uuid=recipe.uuid, selector_version_id=version_id, position=recipe.order
            )
            self.session.add(stored)
            await self.session.flush()
            for part in recipe.parts:
                stored_part = SelectorPart(
                    uuid=part.uuid,
                    recipe_id=stored.id,
                    position=part.order,
                    extraction_json=part.extraction.portable(),
                    join_with=part.join_with,
                )
                self.session.add(stored_part)
                await self.session.flush()
                self.session.add_all(
                    [
                        SelectorLocator(
                            uuid=locator.uuid,
                            part_id=stored_part.id,
                            position=locator.order,
                            kind=locator.kind,
                            payload_json=drop_keys(locator.portable(), "uuid", "order", "kind"),
                        )
                        for locator in part.locators
                    ]
                )
        await self.session.flush()
