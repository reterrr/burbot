from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from business_layer.schemas.enums import (
    BusinessDefinitionStatus,
    BusinessRelationCardinality,
)
from business_layer.schemas.models import (
    BusinessEntity,
    BusinessEntityField,
    BusinessEntityFieldVersion,
    BusinessEntityRelationVersion,
    BusinessEntityVersion,
    BusinessModel,
    BusinessModelRevision,
)
from business_layer.services.schema_language import Sema
from business_layer.services.transactions import transaction
from business_layer.services.value_history import aware

if TYPE_CHECKING:
    from business_layer.services.schema_parser import Program


# ============================================================
# Revision metadata
# ============================================================

SCHEMA_METADATA_KEY = "schemas"
SCHEMA_HASH_METADATA_KEY = "schema_hash"
SCHEMA_HASH_VERSION_METADATA_KEY = "schema_hash_version"

SCHEMA_HASH_VERSION = 3

SYSTEM_ID_FIELD = "id"


# ============================================================
# Diff result
# ============================================================


@dataclass(slots=True, frozen=True)
class SchemaChange:
    action: str
    # create | update | delete

    resource: str
    # entity | field | relation

    entity: str

    field: str | None = None


@dataclass(slots=True, frozen=True)
class RegisterResult:
    changed: bool

    revision_id: int | None

    changes: list[SchemaChange]

    @property
    def message(self) -> str:
        if not self.changed:
            return "Nothing to change"

        return f"Applied {len(self.changes)} schemas change(s)"


# ============================================================
# Semantic relation
# ============================================================


@dataclass(slots=True, frozen=True)
class _RelationSpec:
    source_table: str
    source_entity: str
    source_field: str

    target_table: str
    target_entity: str

    cardinality: BusinessRelationCardinality

    required: bool


# ============================================================
# Persistence result
# ============================================================


@dataclass(slots=True)
class _WrittenEntity:
    identity: BusinessEntity

    # Includes system "id".
    fields: dict[str, BusinessEntityField]


# ============================================================
# BusinessService
# ============================================================


class EntitiesService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ========================================================
    # Business models
    # ========================================================

    async def create_model(
        self,
        key: str,
        name: str,
        description: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> BusinessModel:
        async with transaction(self._session):
            model = BusinessModel(
                key=key, name=name, description=description, metadata_json=metadata_json
            )
            self._session.add(model)
            await self._session.flush()
        return model

    async def get_model(
        self,
        model_id: int,
    ) -> BusinessModel:
        model = await self._session.get(BusinessModel, model_id)

        if model is None:
            raise LookupError(f"BusinessModel {model_id} not found")

        return model

    async def get_revisions_count(self, model_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(BusinessModelRevision)
            .where(BusinessModelRevision.business_model_id == model_id)
        )

        count = await self._session.scalar(stmt)

        return count or 0

    async def get_models(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[BusinessModel], int]:
        if offset < 0:
            raise ValueError("offset cannot be negative")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        models = list(
            (
                await self._session.scalars(
                    select(BusinessModel).order_by(BusinessModel.id).offset(offset).limit(limit)
                )
            ).all()
        )
        total = await self._session.scalar(select(func.count()).select_from(BusinessModel))

        return models, total

    # ========================================================
    # Register complete schemas
    # ========================================================

    async def compile(self, model_id: int, code: str) -> Program:
        """Resolve source against this model's durable table names and current schema."""
        from business_layer.services.schema_parser import compile_source

        current = await self.get_schema(model_id)
        return compile_source(
            code,
            namespace=str(model_id),
            table_names={entity.name: entity.tablename for entity in current.entities},
            context_schema=current,
        )

    async def register_program(
        self,
        model_id: int,
        program: Program,
        *,
        reason: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> RegisterResult:
        """Register a program's definitions. DataService owns applying its seed objects."""
        from business_layer.services.schema_parser import analyze_program

        validated = analyze_program(program.model_copy(deep=True))
        return await self.register(model_id, reason, metadata_json, validated.schema)

    async def register(self, model_id, reason, metadata_json, scheme) -> RegisterResult:
        async with transaction(self._session):
            return await self._register(model_id, reason, metadata_json, scheme)

    async def _register(
        self,
        model_id: int,
        reason: str | None,
        metadata_json: dict[str, Any] | None,
        scheme: Sema.Schema,
    ) -> RegisterResult:
        """
        Register a complete desired schemas snapshot.

        Flow:

            validate desired schemas
                ↓
            calculate canonical semantic hash
                ↓
            compare current revision hash
                ↓
            if different:
                load current schemas from metadata_json["schemas"]
                ↓
            compare Sema.Schema -> Sema.Schema
                ↓
            write complete new metadata revision
        """

        validated = Sema().validate(scheme)

        desired_hash = self._schema_hash(validated)

        try:
            # Serialize concurrent revisions for this model.
            model = await self._session.scalar(
                select(BusinessModel).where(BusinessModel.id == model_id).with_for_update()
            )

            if model is None:
                raise LookupError(f"BusinessModel {model_id} not found")

            current_revision = await self._get_current_revision(model)

            # =================================================
            # First revision
            # =================================================

            if current_revision is None:
                current_schema = Sema.Schema(entities=[])

                changes = self._find_changes(
                    current=current_schema,
                    desired=validated,
                )

            # =================================================
            # Existing revision
            # =================================================

            else:
                stored_hash = self._trusted_revision_hash(current_revision)

                # Fast path.
                if stored_hash == desired_hash:
                    await self._session.flush()

                    return RegisterResult(
                        changed=False,
                        revision_id=None,
                        changes=[],
                    )

                current_schema = self._schema_from_revision(current_revision)

                current_hash = self._schema_hash(current_schema)

                # Covers old revisions which did not yet have
                # schema_hash metadata.
                if current_hash == desired_hash:
                    await self._session.flush()

                    return RegisterResult(
                        changed=False,
                        revision_id=None,
                        changes=[],
                    )

                changes = self._find_changes(
                    current=current_schema,
                    desired=validated,
                )

            # Defensive case, including an empty initial schemas.
            if not changes:
                await self._session.flush()

                return RegisterResult(
                    changed=False,
                    revision_id=None,
                    changes=[],
                )

            revision_metadata = self._revision_metadata(
                metadata_json=metadata_json,
                schema=validated,
                schema_hash=desired_hash,
            )

            revision_id = await self._write_revision(
                model=model,
                previous_revision=current_revision,
                desired=validated,
                reason=reason,
                metadata_json=revision_metadata,
            )

            # Only advance the pointer after the complete
            # revision snapshot was successfully written.
            model.current_revision_id = revision_id

            await self._session.flush()

            return RegisterResult(
                changed=True,
                revision_id=revision_id,
                changes=changes,
            )

        except Exception:
            raise

    # ========================================================
    # Current revision
    # ========================================================

    async def _get_current_revision(
        self,
        model: BusinessModel,
    ) -> BusinessModelRevision | None:
        revision_id = model.current_revision_id

        if revision_id is None:
            return None

        revision = await self._session.get(BusinessModelRevision, revision_id)

        if revision is None:
            raise RuntimeError(
                f"BusinessModel {self._require_id(model)} points to missing revision {revision_id}"
            )

        model_id = self._require_id(model)

        if revision.business_model_id != model_id:
            raise RuntimeError(
                f"Revision {revision_id} does not belong to BusinessModel {model_id}"
            )

        return revision

    # ========================================================
    # Current schemas from revision metadata
    # ========================================================

    @staticmethod
    def _schema_from_revision(
        revision: BusinessModelRevision,
    ) -> Sema.Schema:
        metadata = revision.metadata_json or {}

        raw_schema = metadata.get(SCHEMA_METADATA_KEY)

        if raw_schema is None:
            raise RuntimeError(f"Revision {revision.id} has no '{SCHEMA_METADATA_KEY}' metadata")

        # Preferred format:
        #
        # {
        #   "schemas": {
        #       "entities": [...]
        #   }
        # }
        if isinstance(raw_schema, dict):
            return Sema.Schema.model_validate(raw_schema)

        # Backwards compatibility:
        #
        # {
        #   "schemas": "{\"entities\": [...]}"
        # }
        if isinstance(raw_schema, str):
            return Sema.Schema.model_validate_json(raw_schema)

        raise RuntimeError(
            f"Revision {revision.id} contains invalid "
            f"schemas metadata type: "
            f"{type(raw_schema).__name__}"
        )

    # ========================================================
    # Schema hash
    # ========================================================

    def _schema_hash(
        self,
        schema: Sema.Schema,
    ) -> str:
        payload = self._canonical_schema_payload(schema)

        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return sha256(encoded).hexdigest()

    @staticmethod
    def _canonical_schema_payload(
        schema: Sema.Schema,
    ) -> dict[str, Any]:
        """
        Canonical semantic representation.

        Source locations do not affect schemas identity.

        Entity ordering and field ordering do not affect schemas
        identity either.
        """

        entities: list[dict[str, Any]] = []

        for entity in sorted(
            schema.entities,
            key=lambda value: value.tablename,
        ):
            entity_data = entity.model_dump(
                mode="json",
                exclude={
                    "location",
                    "fields",
                },
            )

            entity_data["fields"] = [
                field.model_dump(
                    mode="json",
                    exclude={
                        "location",
                    },
                )
                for field in sorted(
                    entity.fields,
                    key=lambda value: value.persistent_key,
                )
            ]

            entities.append(entity_data)

        return {
            "entities": entities,
            "enums": [
                {
                    "name": enum.name,
                    "members": sorted(
                        [{"name": member.name, "value": member.value} for member in enum.members],
                        key=lambda member: member["name"],
                    ),
                }
                for enum in sorted(schema.enums, key=lambda enum: enum.name)
            ],
        }

    @staticmethod
    def _trusted_revision_hash(
        revision: BusinessModelRevision,
    ) -> str | None:
        metadata = revision.metadata_json or {}

        version = metadata.get(SCHEMA_HASH_VERSION_METADATA_KEY)

        schema_hash = metadata.get(SCHEMA_HASH_METADATA_KEY)

        if version != SCHEMA_HASH_VERSION:
            return None

        if not isinstance(schema_hash, str):
            return None

        if len(schema_hash) != 64:
            return None

        return schema_hash

    # ========================================================
    # Revision metadata
    # ========================================================

    @staticmethod
    def _revision_metadata(
        *,
        metadata_json: dict[str, Any] | None,
        schema: Sema.Schema,
        schema_hash: str,
    ) -> dict[str, Any]:
        metadata = dict(metadata_json or {})

        # Actual JSON object inside JSONB.
        metadata[SCHEMA_METADATA_KEY] = schema.model_dump(mode="json")

        metadata[SCHEMA_HASH_METADATA_KEY] = schema_hash

        metadata[SCHEMA_HASH_VERSION_METADATA_KEY] = SCHEMA_HASH_VERSION

        return metadata

    # ========================================================
    # Semantic diff
    # ========================================================

    def _find_changes(
        self,
        *,
        current: Sema.Schema,
        desired: Sema.Schema,
    ) -> list[SchemaChange]:
        """
        Entity stable identity:
            Entity.tablename

        Entity logical name:
            Entity.name

        Field identity:
            Field.persistent_key

        Relation identity:
            sources entity table + sources field
        """

        changes: list[SchemaChange] = []

        current_enums = {
            enum.name: {member.name: member.value for member in enum.members}
            for enum in current.enums
        }
        desired_enums = {
            enum.name: {member.name: member.value for member in enum.members}
            for enum in desired.enums
        }
        for name in sorted(current_enums.keys() | desired_enums.keys()):
            if current_enums.get(name) != desired_enums.get(name):
                action = (
                    "delete"
                    if name not in desired_enums
                    else ("create" if name not in current_enums else "update")
                )
                changes.append(SchemaChange(action=action, resource="enum", entity=name))

        current_entities = {entity.tablename: entity for entity in current.entities}

        desired_entities = {entity.tablename: entity for entity in desired.entities}

        # ====================================================
        # Entities + fields
        # ====================================================

        for (
            table_name,
            desired_entity,
        ) in desired_entities.items():
            current_entity = current_entities.get(table_name)

            # ------------------------------------------------
            # Create entity
            # ------------------------------------------------

            if current_entity is None:
                changes.append(
                    SchemaChange(
                        action="create",
                        resource="entity",
                        entity=desired_entity.name,
                    )
                )

                for field in desired_entity.fields:
                    changes.append(
                        SchemaChange(
                            action="create",
                            resource="field",
                            entity=desired_entity.name,
                            field=field.name,
                        )
                    )

                continue

            # ------------------------------------------------
            # Entity update
            #
            # Same table_name + different name means a new
            # version of the SAME BusinessEntity.
            # ------------------------------------------------

            if self._entity_semantics(current_entity) != self._entity_semantics(desired_entity):
                changes.append(
                    SchemaChange(
                        action="update",
                        resource="entity",
                        entity=desired_entity.name,
                    )
                )

            current_fields = {field.persistent_key: field for field in current_entity.fields}

            desired_fields = {field.persistent_key: field for field in desired_entity.fields}

            # ------------------------------------------------
            # Create / update fields
            # ------------------------------------------------

            for (
                field_name,
                desired_field,
            ) in desired_fields.items():
                current_field = current_fields.get(field_name)

                if current_field is None:
                    changes.append(
                        SchemaChange(
                            action="create",
                            resource="field",
                            entity=desired_entity.name,
                            field=desired_field.name,
                        )
                    )

                    continue

                if self._field_semantics(current_field) != self._field_semantics(desired_field):
                    changes.append(
                        SchemaChange(
                            action="update",
                            resource="field",
                            entity=desired_entity.name,
                            field=desired_field.name,
                        )
                    )

            # ------------------------------------------------
            # Delete fields
            # ------------------------------------------------

            for field_name in current_fields:
                if field_name in desired_fields:
                    continue

                changes.append(
                    SchemaChange(
                        action="delete",
                        resource="field",
                        entity=desired_entity.name,
                        field=current_fields[field_name].name,
                    )
                )

        # ====================================================
        # Delete entities
        # ====================================================

        for (
            table_name,
            current_entity,
        ) in current_entities.items():
            if table_name in desired_entities:
                continue

            for field in current_entity.fields:
                changes.append(
                    SchemaChange(
                        action="delete",
                        resource="field",
                        entity=current_entity.name,
                        field=field.name,
                    )
                )

            changes.append(
                SchemaChange(
                    action="delete",
                    resource="entity",
                    entity=current_entity.name,
                )
            )

        # ====================================================
        # Relations
        # ====================================================

        current_relations = self._relations(current)

        desired_relations = self._relations(desired)

        # Create / update.
        for (
            relation_key,
            desired_relation,
        ) in desired_relations.items():
            current_relation = current_relations.get(relation_key)

            if current_relation is None:
                changes.append(
                    SchemaChange(
                        action="create",
                        resource="relation",
                        entity=desired_relation.source_entity,
                        field=desired_relation.source_field,
                    )
                )

                continue

            if current_relation != desired_relation:
                changes.append(
                    SchemaChange(
                        action="update",
                        resource="relation",
                        entity=desired_relation.source_entity,
                        field=desired_relation.source_field,
                    )
                )

        # Delete.
        for (
            relation_key,
            current_relation,
        ) in current_relations.items():
            if relation_key in desired_relations:
                continue

            changes.append(
                SchemaChange(
                    action="delete",
                    resource="relation",
                    entity=current_relation.source_entity,
                    field=current_relation.source_field,
                )
            )

        return changes

    # ========================================================
    # Semantic payloads
    # ========================================================

    @staticmethod
    def _entity_semantics(
        entity: Sema.Entity,
    ) -> dict[str, Any]:
        """
        tablename is stable identity and therefore excluded
        from semantic version comparison.

        fields are compared independently.
        """

        return entity.model_dump(
            mode="json",
            exclude={
                "tablename",
                "location",
                "fields",
            },
        )

    @staticmethod
    def _field_semantics(
        field: Sema.Field,
    ) -> dict[str, Any]:
        """
        Reference target is represented by the relation layer.

        Therefore changing:

            project_id -> Project

        to:

            project_id -> Geography

        is primarily a relation change.
        """

        return field.model_dump(
            mode="json",
            exclude={
                "location",
                "reference",
            },
        )

    # ========================================================
    # Semantic relations
    # ========================================================

    @staticmethod
    def _relations(
        schema: Sema.Schema,
    ) -> dict[
        tuple[str, str],
        _RelationSpec,
    ]:
        entities_by_name = {entity.name: entity for entity in schema.entities}

        result: dict[
            tuple[str, str],
            _RelationSpec,
        ] = {}

        for source_entity in schema.entities:
            for field in source_entity.fields:
                if field.type != Sema.Type.REFERENCE:
                    continue

                if field.reference is None:
                    raise RuntimeError("Validated Reference field has no reference target")

                target_entity = entities_by_name.get(field.reference)

                if target_entity is None:
                    raise RuntimeError(f"Reference target '{field.reference}' does not exist")

                relation_key = (
                    source_entity.tablename,
                    field.persistent_key,
                )

                result[relation_key] = _RelationSpec(
                    source_table=source_entity.tablename,
                    source_entity=source_entity.name,
                    source_field=field.name,
                    target_table=target_entity.tablename,
                    target_entity=target_entity.name,
                    cardinality=(
                        BusinessRelationCardinality.ONE_TO_ONE
                        if field.unique
                        else BusinessRelationCardinality.MANY_TO_ONE
                    ),
                    required=not field.nullable,
                )

        return result

    # ========================================================
    # Write complete revision
    # ========================================================

    async def _write_revision(
        self,
        *,
        model: BusinessModel,
        previous_revision: BusinessModelRevision | None,
        desired: Sema.Schema,
        reason: str | None,
        metadata_json: dict[str, Any],
    ) -> int:
        now = datetime.now(UTC)

        model_id = self._require_id(model)

        # ----------------------------------------------------
        # Create revision row first.
        # ----------------------------------------------------

        revision = BusinessModelRevision(
            business_model_id=model_id,
            reason=reason,
            metadata_json=metadata_json,
        )
        self._session.add(revision)
        await self._session.flush()
        revision_id = self._require_id(revision)

        # ----------------------------------------------------
        # Close previous complete revision snapshot.
        # ----------------------------------------------------

        if previous_revision is not None:
            await self._close_revision_snapshot(
                revision_id=self._require_id(previous_revision),
                timestamp=now,
            )

        # ----------------------------------------------------
        # Pass 1:
        #
        # entities
        # entity versions
        # system id field
        # user fields
        # field versions
        # ----------------------------------------------------

        # Logical names may be reused or swapped between stable table identities.
        await self._session.execute(
            update(BusinessEntity)
            .where(
                BusinessEntity.business_model_id == model_id,
            )
            .values(physical_name=None)
        )

        written_entities: dict[
            str,
            _WrittenEntity,
        ] = {}

        for entity in desired.entities:
            written = await self._write_entity_snapshot(
                model_id=model_id,
                revision_id=revision_id,
                entity=entity,
                valid_from=now,
            )

            written_entities[entity.tablename] = written

        # ----------------------------------------------------
        # Pass 2:
        #
        # All entity/field IDs now exist.
        # ----------------------------------------------------

        await self._write_relation_snapshot(
            model_id=model_id,
            revision_id=revision_id,
            schema=desired,
            entities=written_entities,
            valid_from=now,
        )

        return revision_id

    # ========================================================
    # Write entity snapshot
    # ========================================================

    async def _write_entity_snapshot(
        self,
        *,
        model_id: int,
        revision_id: int,
        entity: Sema.Entity,
        valid_from: datetime,
    ) -> _WrittenEntity:
        """
        BusinessEntity identity:

            physical_name = entity.name
            table_name    = entity.tablename

        Stable reconciliation uses table_name.

        Example:

        revision 1:
            physical_name = Project
            table_name    = e_xxx

        revision 2:
            logical entity becomes ClientProject
            table_name remains e_xxx

        -> same BusinessEntity identity
        """

        # ====================================================
        # Stable entity identity by TABLE NAME
        # ====================================================

        identity = await self._get_entity_identity(
            model_id=model_id,
            table_name=entity.tablename,
        )

        if identity is None:
            identity = BusinessEntity(
                business_model_id=model_id,
                physical_name=entity.name,
                table_name=entity.tablename,
            )
            self._session.add(identity)
            await self._session.flush()

        entity_id = self._require_id(identity)

        # ====================================================
        # Entity version
        # ====================================================

        entity_payload = self._entity_payload(entity)

        entity_version = BusinessEntityVersion(
            business_entity_id=entity_id,
            business_model_revision_id=revision_id,
            key=entity_payload["key"],
            label=entity_payload["label"],
            description=entity_payload["description"],
            status=BusinessDefinitionStatus.ACTIVE,
            definition_json=entity_payload["definition_json"],
            valid_from=valid_from,
            transaction_from=valid_from,
        )
        self._session.add(entity_version)
        await self._session.flush()
        identity.effective_business_entity_version_id = self._require_id(entity_version)
        # Identity names track the latest spelling, while stable IDs stay unchanged.
        identity.physical_name = entity.name

        written_fields: dict[
            str,
            BusinessEntityField,
        ] = {}

        # ====================================================
        # System ID
        # ====================================================

        id_identity = await self._get_or_create_field_identity(
            entity_id=entity_id,
            physical_name=SYSTEM_ID_FIELD,
            persistent_key=SYSTEM_ID_FIELD,
        )

        self._session.add(
            BusinessEntityFieldVersion(
                business_entity_field_id=self._require_id(id_identity),
                business_model_revision_id=revision_id,
                key=SYSTEM_ID_FIELD,
                label="ID",
                description="Burbot-managed primary identifier",
                status=BusinessDefinitionStatus.ACTIVE,
                definition_json={
                    "type": Sema.Type.BIG_INTEGER.value,
                    "nullable": False,
                    "unique": True,
                    "index": False,
                    "primary_key": True,
                    "system": True,
                    "generated": True,
                },
                valid_from=valid_from,
                transaction_from=valid_from,
            )
        )
        await self._session.flush()

        written_fields[SYSTEM_ID_FIELD] = id_identity

        # ====================================================
        # User fields
        # ====================================================

        for field in entity.fields:
            field_identity = await self._get_or_create_field_identity(
                entity_id=entity_id,
                physical_name=field.name,
                persistent_key=field.persistent_key,
            )

            field_payload = self._field_payload(field)

            self._session.add(
                BusinessEntityFieldVersion(
                    business_entity_field_id=self._require_id(field_identity),
                    business_model_revision_id=revision_id,
                    key=field_payload["key"],
                    label=field_payload["label"],
                    description=field_payload["description"],
                    status=BusinessDefinitionStatus.ACTIVE,
                    definition_json=field_payload["definition_json"],
                    valid_from=valid_from,
                    transaction_from=valid_from,
                )
            )
            await self._session.flush()

            written_fields[field.name] = field_identity

        return _WrittenEntity(
            identity=identity,
            fields=written_fields,
        )

    # ========================================================
    # Write relation snapshot
    # ========================================================

    async def _write_relation_snapshot(
        self,
        *,
        model_id: int,
        revision_id: int,
        schema: Sema.Schema,
        entities: dict[str, _WrittenEntity],
        valid_from: datetime,
    ) -> None:
        entities_by_name = {entity.name: entity for entity in schema.entities}

        for source_entity in schema.entities:
            source_state = entities[source_entity.tablename]

            source_entity_id = self._require_id(source_state.identity)

            for field in source_entity.fields:
                if field.type != Sema.Type.REFERENCE:
                    continue

                if field.reference is None:
                    raise RuntimeError("Validated Reference field has no target")

                target_entity = entities_by_name.get(field.reference)

                if target_entity is None:
                    raise RuntimeError(f"Reference target '{field.reference}' missing")

                target_state = entities[target_entity.tablename]

                target_entity_id = self._require_id(target_state.identity)

                # --------------------------------------------
                # Source FK field
                # --------------------------------------------

                source_field_identity = source_state.fields[field.name]

                source_field_id = self._require_id(source_field_identity)

                # --------------------------------------------
                # References always target Burbot ID
                # --------------------------------------------

                target_id_identity = target_state.fields[SYSTEM_ID_FIELD]

                target_id_field_id = self._require_id(target_id_identity)

                # --------------------------------------------
                # Stable relation identity
                # --------------------------------------------

                relation_id = await self._get_or_create_relation_identity(
                    model_id=model_id,
                    from_field_id=source_field_id,
                )

                cardinality = (
                    BusinessRelationCardinality.ONE_TO_ONE
                    if field.unique
                    else BusinessRelationCardinality.MANY_TO_ONE
                )

                self._session.add(
                    BusinessEntityRelationVersion(
                        relation_id=relation_id,
                        business_model_revision_id=revision_id,
                        key=field.name,
                        label=f"{source_entity.name}.{field.name} -> {target_entity.name}",
                        from_entity_id=source_entity_id,
                        to_entity_id=target_entity_id,
                        from_field_id=source_field_id,
                        to_field_id=target_id_field_id,
                        cardinality=cardinality,
                        status=BusinessDefinitionStatus.ACTIVE,
                        definition_json={"required": not field.nullable},
                        valid_from=valid_from,
                        transaction_from=valid_from,
                    )
                )
                await self._session.flush()

    # ========================================================
    # Stable entity identity
    # ========================================================

    async def _get_entity_identity(
        self,
        *,
        model_id: int,
        table_name: str,
    ) -> BusinessEntity | None:
        """
        table_name is the stable entity identity.

        physical_name must NOT be used for reconciliation.
        """

        stmt = select(BusinessEntity).where(
            BusinessEntity.business_model_id == model_id,
            BusinessEntity.table_name == table_name,
        )

        result = await self._session.execute(stmt)

        identities = list(result.scalars().all())

        if len(identities) > 1:
            raise RuntimeError(
                f"Multiple BusinessEntity identities "
                f"for model={model_id}, "
                f"table_name={table_name!r}"
            )

        return identities[0] if identities else None

    # ========================================================
    # Stable field identity
    # ========================================================

    async def _get_or_create_field_identity(
        self, *, entity_id: int, physical_name: str, persistent_key: str,
    ) -> BusinessEntityField:
        identity = await self._session.scalar(select(BusinessEntityField).where(
            BusinessEntityField.business_entity_id == entity_id,
            BusinessEntityField.persistent_key == persistent_key,
        ))
        if identity is not None:
            identity.physical_name = physical_name
            return identity
        identity = BusinessEntityField(
            business_entity_id=entity_id, physical_name=physical_name,
            persistent_key=persistent_key,
        )
        self._session.add(identity)
        await self._session.flush()
        return identity

    # ========================================================
    # Stable relation identity
    # ========================================================

    async def _get_or_create_relation_identity(
        self,
        *,
        model_id: int,
        from_field_id: int,
    ) -> UUID:
        relation_ids = set(
            (
                await self._session.scalars(
                    select(BusinessEntityRelationVersion.relation_id)
                    .where(
                        BusinessEntityRelationVersion.from_field_id == from_field_id,
                    )
                    .distinct()
                )
            ).all()
        )
        if len(relation_ids) > 1:
            raise RuntimeError(f"Field {from_field_id} has multiple relation identities")
        return next(iter(relation_ids)) if relation_ids else uuid4()

    # ========================================================
    # Close previous snapshot
    # ========================================================

    async def _close_revision_snapshot(self, *, revision_id: int, timestamp: datetime) -> None:
        # Preserve old valid intervals. Only transaction time may be closed in place.
        # Copy their earlier valid-time prefix into today's knowledge timeline.
        for model in (
            BusinessEntityRelationVersion,
            BusinessEntityFieldVersion,
            BusinessEntityVersion,
        ):
            versions = list(
                (
                    await self._session.scalars(
                        select(model).where(
                            model.business_model_revision_id == revision_id,
                            model.transaction_to.is_(None),
                            model.valid_to.is_(None),
                        )
                    )
                ).all()
            )
            for version in versions:
                if timestamp <= version.transaction_from:
                    raise ValueError("Schema revision time must advance")
                version.transaction_to = timestamp
            await self._session.flush()
            for version in versions:
                if version.valid_from < timestamp:
                    payload = version.model_dump(exclude={"id", "created_at"})
                    payload.update(
                        valid_to=timestamp, transaction_from=timestamp, transaction_to=None
                    )
                    self._session.add(model(**payload))
            await self._session.flush()
        entity_ids = select(BusinessEntityVersion.business_entity_id).where(
            BusinessEntityVersion.business_model_revision_id == revision_id,
        )
        await self._session.execute(
            update(BusinessEntity)
            .where(
                BusinessEntity.id.in_(entity_ids),
            )
            .values(effective_business_entity_version_id=None)
        )

    # ========================================================
    # Entity version payload
    # ========================================================

    @staticmethod
    def _entity_payload(
        entity: Sema.Entity,
    ) -> dict[str, Any]:
        label = (
            getattr(
                entity,
                "label",
                None,
            )
            or entity.name
        )

        description = getattr(
            entity,
            "description",
            None,
        )

        definition = entity.model_dump(
            mode="json",
            exclude={
                "name",
                "label",
                "description",
                # Stored on stable BusinessEntity.
                "tablename",
                "location",
                # Fields have their own identities/versions.
                "fields",
            },
            exclude_none=True,
        )

        return {
            "key": entity.name,
            "label": label,
            "description": description,
            "definition_json": (definition or None),
        }

    # ========================================================
    # Field version payload
    # ========================================================

    @staticmethod
    def _field_payload(
        field: Sema.Field,
    ) -> dict[str, Any]:
        label = (
            getattr(
                field,
                "label",
                None,
            )
            or field.name
        )

        description = getattr(
            field,
            "description",
            None,
        )

        definition = field.model_dump(
            mode="json",
            exclude={
                "name",
                "persistent_key",
                "label",
                "description",
                "location",
                # Relation target lives in
                # BusinessEntityRelationVersion.
                "reference",
            },
            exclude_none=True,
        )

        return {
            "key": field.name,
            "label": label,
            "description": description,
            "definition_json": definition,
        }

    # ========================================================
    # Diff endpoint
    # ========================================================

    async def find_changes(
        self,
        model_id: int,
        scheme: Sema.Schema,
    ) -> list[SchemaChange]:
        desired = Sema().validate(scheme)

        model = await self._session.get(BusinessModel, model_id)

        if model is None:
            raise LookupError(f"BusinessModel {model_id} not found")

        current_revision = await self._get_current_revision(model)

        if current_revision is None:
            return self._find_changes(
                current=Sema.Schema(entities=[]),
                desired=desired,
            )

        desired_hash = self._schema_hash(desired)

        stored_hash = self._trusted_revision_hash(current_revision)

        if stored_hash == desired_hash:
            return []

        current = self._schema_from_revision(current_revision)

        if self._schema_hash(current) == desired_hash:
            return []

        return self._find_changes(
            current=current,
            desired=desired,
        )

    # ========================================================
    # Revisions
    # ========================================================

    async def get_revisions(
        self,
        *,
        model_id: int,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[BusinessModelRevision], int]:
        if offset < 0:
            raise ValueError("offset cannot be negative")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        # Verify model exists.
        model = await self._session.get(BusinessModel, model_id)

        if model is None:
            raise LookupError(f"BusinessModel {model_id} not found")

        stmt = (
            select(BusinessModelRevision)
            .where(BusinessModelRevision.business_model_id == model_id)
            .order_by(BusinessModelRevision.id.desc())
            .offset(offset)
            .limit(limit)
        )

        count_stmt = (
            select(func.count())
            .select_from(BusinessModelRevision)
            .where(BusinessModelRevision.business_model_id == model_id)
        )

        result = await self._session.execute(stmt)

        count = await self._session.scalar(count_stmt)

        revisions = list(result.scalars().all())

        return (
            revisions,
            int(count or 0),
        )

    async def get_revision(
        self,
        revision_id: int,
    ) -> BusinessModelRevision:
        revision = await self._session.get(BusinessModelRevision, revision_id)

        if revision is None:
            raise LookupError(f"BusinessModelRevision {revision_id} not found")

        return revision

    # Helpers
    # ========================================================

    @staticmethod
    def _require_id(
        model: Any,
    ) -> int:
        model_id = getattr(
            model,
            "id",
            None,
        )

        if model_id is None:
            raise RuntimeError(f"{type(model).__name__} has no persisted id")

        return model_id

    async def get_schema(self, model_id: int, *, revision_id: int | None = None) -> Sema.Schema:
        model = await self.get_model(model_id)
        revision = (
            await self.get_revision(revision_id)
            if revision_id is not None
            else await self._get_current_revision(model)
        )
        if revision is None:
            return Sema.Schema(entities=[])
        if revision.business_model_id != model_id:
            raise LookupError("Revision does not belong to this business model")
        return self._schema_from_revision(revision)

    @staticmethod
    def _temporal(model, at, known_at):
        return (
            model.valid_from <= at,
            model.valid_to.is_(None) | (model.valid_to > at),
            model.transaction_from <= known_at,
            model.transaction_to.is_(None) | (model.transaction_to > known_at),
        )

    async def get_entity(self, entity_id: int, *, at=None, known_at=None):
        from business_layer.schemas.models.dtos import EntityDefinitionRead, FieldDefinitionRead

        now = datetime.now(UTC)
        at = aware(at) if at is not None else now
        known_at = aware(known_at) if known_at is not None else now
        entity = await self._session.get(BusinessEntity, entity_id)
        if entity is None:
            raise LookupError("Business entity not found")
        version = await self._session.scalar(
            select(BusinessEntityVersion).where(
                BusinessEntityVersion.business_entity_id == entity_id,
                *self._temporal(BusinessEntityVersion, at, known_at),
            )
        )
        if version is None:
            raise LookupError("No entity definition at the requested times")
        fields = (
            await self._session.execute(
                select(
                    BusinessEntityField.id,
                    BusinessEntityField.persistent_key,
                    BusinessEntityFieldVersion,
                )
                .join(
                    BusinessEntityFieldVersion,
                    BusinessEntityFieldVersion.business_entity_field_id == BusinessEntityField.id,
                )
                .where(
                    BusinessEntityField.business_entity_id == entity_id,
                    *self._temporal(BusinessEntityFieldVersion, at, known_at),
                )
                .order_by(BusinessEntityField.id)
            )
        ).all()
        return EntityDefinitionRead(
            entity_id=entity.id,
            model_id=entity.business_model_id,
            table_name=entity.table_name,
            version_id=version.id,
            key=version.key,
            label=version.label,
            status=version.status,
            fields=[
                FieldDefinitionRead(
                    field_id=field_id,
                    persistent_key=persistent_key,
                    entity_id=entity_id,
                    version_id=field.id,
                    key=field.key,
                    label=field.label,
                    status=field.status,
                    definition=field.definition_json,
                )
                for field_id, persistent_key, field in fields
            ],
        )

    async def list_entities(self, model_id: int, *, offset=0, limit=100, at=None, known_at=None):
        if offset < 0 or not 1 <= limit <= 500:
            raise ValueError("Invalid pagination")
        await self.get_model(model_id)
        now = datetime.now(UTC)
        at = aware(at) if at is not None else now
        known_at = aware(known_at) if known_at is not None else now
        ids = (
            await self._session.scalars(
                select(BusinessEntity.id)
                .join(
                    BusinessEntityVersion,
                    BusinessEntityVersion.business_entity_id == BusinessEntity.id,
                )
                .where(
                    BusinessEntity.business_model_id == model_id,
                    *self._temporal(BusinessEntityVersion, at, known_at),
                )
                .order_by(BusinessEntity.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [await self.get_entity(entity_id, at=at, known_at=known_at) for entity_id in ids]

    async def resolve_entity(self, business_model_id: int, key: str):
        now = datetime.now(UTC)
        entity_id = await self._session.scalar(
            select(BusinessEntity.id)
            .join(
                BusinessEntityVersion,
                BusinessEntityVersion.business_entity_id == BusinessEntity.id,
            )
            .where(
                BusinessEntity.business_model_id == business_model_id,
                BusinessEntityVersion.key == key,
                *self._temporal(BusinessEntityVersion, now, now),
            )
        )
        if entity_id is None:
            raise LookupError(f"Unknown entity: {key}")
        return await self.get_entity(entity_id)

    async def resolve_field(self, entity_id: int, key: str):
        entity = await self.get_entity(entity_id)
        for field in entity.fields:
            if field.key == key:
                return field
        raise LookupError(f"Unknown field: {key}")

    async def resolve_field_by_persistent_key(self, entity_id: int, persistent_key: str):
        entity = await self.get_entity(entity_id)
        for field in entity.fields:
            if field.persistent_key == persistent_key:
                return field
        raise LookupError(f"Unknown persistent field key: {persistent_key}")

    async def get_entity_history(self, entity_id: int, *, offset=0, limit=100):
        if await self._session.get(BusinessEntity, entity_id) is None:
            raise LookupError("Business entity not found")
        return await self._definition_history(
            BusinessEntityVersion,
            BusinessEntityVersion.business_entity_id == entity_id,
            offset=offset,
            limit=limit,
        )

    async def get_field_history(self, field_id: int, *, offset=0, limit=100):
        if await self._session.get(BusinessEntityField, field_id) is None:
            raise LookupError("Business entity field not found")
        return await self._definition_history(
            BusinessEntityFieldVersion,
            BusinessEntityFieldVersion.business_entity_field_id == field_id,
            offset=offset,
            limit=limit,
        )

    async def _definition_history(self, model, predicate, *, offset=0, limit=100):
        if offset < 0 or not 1 <= limit <= 500:
            raise ValueError("Invalid pagination")
        return list(
            (
                await self._session.scalars(
                    select(model)
                    .where(predicate)
                    .order_by(
                        model.transaction_from.desc(),
                        model.valid_from.desc(),
                        model.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )

    async def list_relations(self, entity_id: int, *, at=None, known_at=None):
        if await self._session.get(BusinessEntity, entity_id) is None:
            raise LookupError("Business entity not found")
        now = datetime.now(UTC)
        at = aware(at) if at is not None else now
        known_at = aware(known_at) if known_at is not None else now
        model = BusinessEntityRelationVersion
        return list(
            (
                await self._session.scalars(
                    select(model)
                    .where(
                        (model.from_entity_id == entity_id) | (model.to_entity_id == entity_id),
                        *self._temporal(model, at, known_at),
                    )
                    .order_by(model.id)
                )
            ).all()
        )

    async def update_model(self, model_id: int, changes: dict[str, Any]):
        allowed = {"name", "description", "metadata_json"}
        if set(changes) - allowed:
            raise ValueError("Only name, description, and metadata_json can be updated")
        if "name" in changes and (
            not isinstance(changes["name"], str) or not changes["name"].strip()
        ):
            raise ValueError("Model name cannot be empty")
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
            for name, value in changes.items():
                setattr(model, name, value)
            await self._session.flush()
        return model

    async def delete_model(self, model_id: int):
        from sqlalchemy import delete

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
            revisions = await self._session.scalar(
                select(BusinessModelRevision.id)
                .where(
                    BusinessModelRevision.business_model_id == model_id,
                )
                .limit(1)
            )
            entities = await self._session.scalar(
                select(BusinessEntity.id)
                .where(
                    BusinessEntity.business_model_id == model_id,
                )
                .limit(1)
            )
            if revisions is not None or entities is not None:
                from fastapi import HTTPException

                raise HTTPException(409, "Business model has schema history and cannot be deleted")
            await self._session.execute(delete(BusinessModel).where(BusinessModel.id == model_id))

    async def get_relation_history(self, relation_id: UUID, *, offset=0, limit=100):
        model = BusinessEntityRelationVersion
        exists = await self._session.scalar(
            select(model.id)
            .where(
                model.relation_id == relation_id,
            )
            .limit(1)
        )
        if exists is None:
            raise LookupError("Business relation not found")
        return await self._definition_history(
            model, model.relation_id == relation_id, offset=offset, limit=limit
        )
