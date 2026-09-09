from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Any

from fastapi import HTTPException
from pydantic import StringConstraints
from sqlalchemy import func, select, update, and_, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from business_layer.schemas.enums import (
    BusinessDefinitionStatus,
    BusinessRelationCardinality,
)

from business_layer.schemas.models import (
    BusinessModel,
    BusinessModelRevision,
    BusinessEntity,
    BusinessEntityField,
    BusinessEntityRelation, BusinessObject, BusinessObjectField, BusinessObjectFieldValue, BusinessEntityFieldVersion,
    BusinessEntityVersion,
)

from business_layer.schemas.models.dtos import (
    BusinessModelAdd,
    BusinessModelRevisionAdd,

    BusinessEntityFilter,
    BusinessEntityAdd,

    BusinessEntityVersionFilter,
    BusinessEntityVersionAdd,
    BusinessEntityVersionUpdate,

    BusinessEntityFieldFilter,
    BusinessEntityFieldAdd,

    BusinessEntityFieldVersionFilter,
    BusinessEntityFieldVersionAdd,
    BusinessEntityFieldVersionUpdate,

    BusinessEntityRelationAdd,

    BusinessEntityRelationVersionFilter,
    BusinessEntityRelationVersionAdd,
    BusinessEntityRelationVersionUpdate, CreateObjectResponse, BusinessObjectRead, BusinessObjectFieldRead,
    BusinessObjectFieldValueRead,
)

from business_layer.services.repositories import (
    BusinessModelRepository,
    BusinessModelRevisionsRepository,

    BusinessEntityRepository,
    BusinessEntityVersionsRepository,

    BusinessEntityFieldsRepository,
    BusinessEntityFieldVersionsRepository,

    BusinessEntityRelationsRepository,
    BusinessEntityRelationVersionsRepository,
)

from business_layer.services.schema_language import Sema

# ============================================================
# Revision metadata
# ============================================================

SCHEMA_METADATA_KEY = "schema"
SCHEMA_HASH_METADATA_KEY = "schema_hash"
SCHEMA_HASH_VERSION_METADATA_KEY = "schema_hash_version"

SCHEMA_HASH_VERSION = 1

SYSTEM_ID_FIELD = "id"


class BusinessObjectNotFound(Exception):
    pass


class BusinessObjectFieldNotFound(Exception):
    pass


class BusinessObjectFieldMismatch(Exception):
    pass


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

        return (
            f"Applied {len(self.changes)} "
            f"schema change(s)"
        )


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

class BusinessService:
    def __init__(
            self,
            session: AsyncSession,

            model_repository: BusinessModelRepository,
            model_revision_repository: BusinessModelRevisionsRepository,

            entity_repository: BusinessEntityRepository,
            entity_version_repository: BusinessEntityVersionsRepository,

            field_repository: BusinessEntityFieldsRepository,
            field_version_repository: BusinessEntityFieldVersionsRepository,

            relation_repository: BusinessEntityRelationsRepository,
            relation_version_repository: BusinessEntityRelationVersionsRepository,
    ) -> None:
        self._session = session

        self._model_repository = model_repository
        self._model_revision_repository = (
            model_revision_repository
        )

        self._entity_repository = entity_repository
        self._entity_version_repository = (
            entity_version_repository
        )

        self._field_repository = field_repository
        self._field_version_repository = (
            field_version_repository
        )

        self._relation_repository = relation_repository
        self._relation_version_repository = (
            relation_version_repository
        )

    # ========================================================
    # Business models
    # ========================================================

    async def create_model(
            self,
            key: Annotated[
                str,
                StringConstraints(max_length=150),
            ],
            name: Annotated[
                str,
                StringConstraints(max_length=255),
            ],
            description: str | None = None,
            metadata_json: dict[str, Any] | None = None,
    ) -> BusinessModel:
        try:
            model_id = await self._model_repository.add(
                BusinessModelAdd(
                    key=key,
                    name=name,
                    description=description,
                    metadata_json=metadata_json,
                )
            )

            model = await self._model_repository.get(
                model_id
            )

            if model is None:
                raise RuntimeError(
                    "BusinessModel disappeared after insert"
                )

            await self._session.commit()

            return model

        except Exception:
            await self._session.rollback()
            raise

    async def get_model(
            self,
            model_id: int,
    ) -> BusinessModel:
        model = await self._model_repository.get(
            model_id
        )

        if model is None:
            raise LookupError(
                f"BusinessModel {model_id} not found"
            )

        return model

    async def get_revisions_count(
            self,
            model_id: int
    ) -> int:
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
            raise ValueError(
                "offset cannot be negative"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        models = await self._model_repository.list(
            offset=offset,
            limit=limit,
        )

        total = await self._model_repository.count()

        return models, total

    # ========================================================
    # Register complete schema
    # ========================================================

    async def register(
            self,
            model_id: int,
            reason: str | None,
            metadata_json: dict[str, Any] | None,
            scheme: Sema.Schema,
    ) -> RegisterResult:
        """
        Register a complete desired schema snapshot.

        Flow:

            validate desired schema
                ↓
            calculate canonical semantic hash
                ↓
            compare current revision hash
                ↓
            if different:
                load current schema from metadata_json["schema"]
                ↓
            compare Sema.Schema -> Sema.Schema
                ↓
            write complete new metadata revision
        """

        validated = Sema().validate(
            scheme
        )

        desired_hash = self._schema_hash(
            validated
        )

        try:
            # Serialize concurrent revisions for this model.
            model = await self._session.scalar(
                select(BusinessModel)
                .where(
                    BusinessModel.id == model_id
                )
                .with_for_update()
            )

            if model is None:
                raise LookupError(
                    f"BusinessModel {model_id} not found"
                )

            current_revision = (
                await self._get_current_revision(
                    model
                )
            )

            # =================================================
            # First revision
            # =================================================

            if current_revision is None:
                current_schema = Sema.Schema(
                    entities=[]
                )

                changes = self._find_changes(
                    current=current_schema,
                    desired=validated,
                )

            # =================================================
            # Existing revision
            # =================================================

            else:
                stored_hash = (
                    self._trusted_revision_hash(
                        current_revision
                    )
                )

                # Fast path.
                if stored_hash == desired_hash:
                    await self._session.commit()

                    return RegisterResult(
                        changed=False,
                        revision_id=None,
                        changes=[],
                    )

                current_schema = (
                    self._schema_from_revision(
                        current_revision
                    )
                )

                current_hash = self._schema_hash(
                    current_schema
                )

                # Covers old revisions which did not yet have
                # schema_hash metadata.
                if current_hash == desired_hash:
                    await self._session.commit()

                    return RegisterResult(
                        changed=False,
                        revision_id=None,
                        changes=[],
                    )

                changes = self._find_changes(
                    current=current_schema,
                    desired=validated,
                )

            # Defensive case, including an empty initial schema.
            if not changes:
                await self._session.commit()

                return RegisterResult(
                    changed=False,
                    revision_id=None,
                    changes=[],
                )

            revision_metadata = (
                self._revision_metadata(
                    metadata_json=metadata_json,
                    schema=validated,
                    schema_hash=desired_hash,
                )
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

            await self._session.commit()

            return RegisterResult(
                changed=True,
                revision_id=revision_id,
                changes=changes,
            )

        except Exception:
            await self._session.rollback()
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

        revision = (
            await self._model_revision_repository.get(
                revision_id
            )
        )

        if revision is None:
            raise RuntimeError(
                f"BusinessModel {self._require_id(model)} "
                f"points to missing revision {revision_id}"
            )

        model_id = self._require_id(
            model
        )

        if revision.business_model_id != model_id:
            raise RuntimeError(
                f"Revision {revision_id} does not belong "
                f"to BusinessModel {model_id}"
            )

        return revision

    # ========================================================
    # Current schema from revision metadata
    # ========================================================

    @staticmethod
    def _schema_from_revision(
            revision: BusinessModelRevision,
    ) -> Sema.Schema:
        metadata = revision.metadata_json or {}

        raw_schema = metadata.get(
            SCHEMA_METADATA_KEY
        )

        if raw_schema is None:
            raise RuntimeError(
                f"Revision {revision.id} has no "
                f"'{SCHEMA_METADATA_KEY}' metadata"
            )

        # Preferred format:
        #
        # {
        #   "schema": {
        #       "entities": [...]
        #   }
        # }
        if isinstance(raw_schema, dict):
            return Sema.Schema.model_validate(
                raw_schema
            )

        # Backwards compatibility:
        #
        # {
        #   "schema": "{\"entities\": [...]}"
        # }
        if isinstance(raw_schema, str):
            return Sema.Schema.model_validate_json(
                raw_schema
            )

        raise RuntimeError(
            f"Revision {revision.id} contains invalid "
            f"schema metadata type: "
            f"{type(raw_schema).__name__}"
        )

    # ========================================================
    # Schema hash
    # ========================================================

    def _schema_hash(
            self,
            schema: Sema.Schema,
    ) -> str:
        payload = self._canonical_schema_payload(
            schema
        )

        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return sha256(
            encoded
        ).hexdigest()

    @staticmethod
    def _canonical_schema_payload(
            schema: Sema.Schema,
    ) -> dict[str, Any]:
        """
        Canonical semantic representation.

        Source locations do not affect schema identity.

        Entity ordering and field ordering do not affect schema
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
                    key=lambda value: value.name,
                )
            ]

            entities.append(
                entity_data
            )

        return {
            "entities": entities,
        }

    @staticmethod
    def _trusted_revision_hash(
            revision: BusinessModelRevision,
    ) -> str | None:
        metadata = revision.metadata_json or {}

        version = metadata.get(
            SCHEMA_HASH_VERSION_METADATA_KEY
        )

        schema_hash = metadata.get(
            SCHEMA_HASH_METADATA_KEY
        )

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
        metadata = dict(
            metadata_json or {}
        )

        # Actual JSON object inside JSONB.
        metadata[
            SCHEMA_METADATA_KEY
        ] = schema.model_dump(
            mode="json"
        )

        metadata[
            SCHEMA_HASH_METADATA_KEY
        ] = schema_hash

        metadata[
            SCHEMA_HASH_VERSION_METADATA_KEY
        ] = SCHEMA_HASH_VERSION

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
            currently Field.name

        Relation identity:
            sources entity table + sources field
        """

        changes: list[SchemaChange] = []

        current_entities = {
            entity.tablename: entity
            for entity in current.entities
        }

        desired_entities = {
            entity.tablename: entity
            for entity in desired.entities
        }

        # ====================================================
        # Entities + fields
        # ====================================================

        for (
                table_name,
                desired_entity,
        ) in desired_entities.items():
            current_entity = current_entities.get(
                table_name
            )

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

            if (
                    self._entity_semantics(
                        current_entity
                    )
                    != self._entity_semantics(
                desired_entity
            )
            ):
                changes.append(
                    SchemaChange(
                        action="update",
                        resource="entity",
                        entity=desired_entity.name,
                    )
                )

            current_fields = {
                field.name: field
                for field in current_entity.fields
            }

            desired_fields = {
                field.name: field
                for field in desired_entity.fields
            }

            # ------------------------------------------------
            # Create / update fields
            # ------------------------------------------------

            for (
                    field_name,
                    desired_field,
            ) in desired_fields.items():
                current_field = current_fields.get(
                    field_name
                )

                if current_field is None:
                    changes.append(
                        SchemaChange(
                            action="create",
                            resource="field",
                            entity=desired_entity.name,
                            field=field_name,
                        )
                    )

                    continue

                if (
                        self._field_semantics(
                            current_field
                        )
                        != self._field_semantics(
                    desired_field
                )
                ):
                    changes.append(
                        SchemaChange(
                            action="update",
                            resource="field",
                            entity=desired_entity.name,
                            field=field_name,
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
                        field=field_name,
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

        current_relations = self._relations(
            current
        )

        desired_relations = self._relations(
            desired
        )

        # Create / update.
        for (
                relation_key,
                desired_relation,
        ) in desired_relations.items():
            current_relation = (
                current_relations.get(
                    relation_key
                )
            )

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
        entities_by_name = {
            entity.name: entity
            for entity in schema.entities
        }

        result: dict[
            tuple[str, str],
            _RelationSpec,
        ] = {}

        for source_entity in schema.entities:
            for field in source_entity.fields:
                if field.type != Sema.Type.REFERENCE:
                    continue

                if field.reference is None:
                    raise RuntimeError(
                        "Validated Reference field "
                        "has no reference target"
                    )

                target_entity = entities_by_name.get(
                    field.reference
                )

                if target_entity is None:
                    raise RuntimeError(
                        f"Reference target "
                        f"'{field.reference}' "
                        f"does not exist"
                    )

                relation_key = (
                    source_entity.tablename,
                    field.name,
                )

                result[
                    relation_key
                ] = _RelationSpec(
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
        now = datetime.now(
            UTC
        )

        model_id = self._require_id(
            model
        )

        # ----------------------------------------------------
        # Create revision row first.
        # ----------------------------------------------------

        revision_id = (
            await self._model_revision_repository.add(
                BusinessModelRevisionAdd(
                    business_model_id=model_id,
                    reason=reason,
                    metadata_json=metadata_json,
                )
            )
        )

        # ----------------------------------------------------
        # Close previous complete revision snapshot.
        # ----------------------------------------------------

        if previous_revision is not None:
            await self._close_revision_snapshot(
                revision_id=self._require_id(
                    previous_revision
                ),
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

            written_entities[
                entity.tablename
            ] = written

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
            entity_id = await self._entity_repository.add(
                BusinessEntityAdd(
                    business_model_id=model_id,

                    physical_name=entity.name,

                    table_name=entity.tablename,
                )
            )

            identity = await self._entity_repository.get(
                entity_id
            )

            if identity is None:
                raise RuntimeError(
                    "BusinessEntity disappeared "
                    "after insert"
                )

        entity_id = self._require_id(
            identity
        )

        # ====================================================
        # Entity version
        # ====================================================

        entity_payload = self._entity_payload(
            entity
        )

        await self._entity_version_repository.add(
            BusinessEntityVersionAdd(
                business_entity_id=entity_id,

                revision_id=revision_id,

                key=entity_payload[
                    "key"
                ],

                label=entity_payload[
                    "label"
                ],

                description=entity_payload[
                    "description"
                ],

                status=(
                    BusinessDefinitionStatus.ACTIVE
                ),

                definition_json=entity_payload[
                    "definition_json"
                ],

                valid_from=valid_from,

                valid_to=None,
            )
        )

        written_fields: dict[
            str,
            BusinessEntityField,
        ] = {}

        # ====================================================
        # System ID
        # ====================================================

        id_identity = (
            await self._get_or_create_field_identity(
                entity_id=entity_id,
                physical_name=SYSTEM_ID_FIELD,
            )
        )

        await self._field_version_repository.add(
            BusinessEntityFieldVersionAdd(
                business_entity_field_id=(
                    self._require_id(
                        id_identity
                    )
                ),

                revision_id=revision_id,

                key=SYSTEM_ID_FIELD,

                label="ID",

                description=(
                    "Burbot-managed primary identifier"
                ),

                status=(
                    BusinessDefinitionStatus.ACTIVE
                ),

                definition_json={
                    "type": (
                        Sema.Type.BIG_INTEGER.value
                    ),

                    "nullable": False,
                    "unique": True,
                    "index": False,
                    "primary_key": True,

                    "system": True,
                    "generated": True,
                },

                valid_from=valid_from,

                valid_to=None,
            )
        )

        written_fields[
            SYSTEM_ID_FIELD
        ] = id_identity

        # ====================================================
        # User fields
        # ====================================================

        for field in entity.fields:
            field_identity = (
                await self._get_or_create_field_identity(
                    entity_id=entity_id,
                    physical_name=field.name,
                )
            )

            field_payload = self._field_payload(
                field
            )

            await self._field_version_repository.add(
                BusinessEntityFieldVersionAdd(
                    business_entity_field_id=(
                        self._require_id(
                            field_identity
                        )
                    ),

                    revision_id=revision_id,

                    key=field_payload[
                        "key"
                    ],

                    label=field_payload[
                        "label"
                    ],

                    description=field_payload[
                        "description"
                    ],

                    status=(
                        BusinessDefinitionStatus.ACTIVE
                    ),

                    definition_json=field_payload[
                        "definition_json"
                    ],

                    valid_from=valid_from,

                    valid_to=None,
                )
            )

            written_fields[
                field.name
            ] = field_identity

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
        entities_by_name = {
            entity.name: entity
            for entity in schema.entities
        }

        for source_entity in schema.entities:
            source_state = entities[
                source_entity.tablename
            ]

            source_entity_id = self._require_id(
                source_state.identity
            )

            for field in source_entity.fields:
                if field.type != Sema.Type.REFERENCE:
                    continue

                if field.reference is None:
                    raise RuntimeError(
                        "Validated Reference field "
                        "has no target"
                    )

                target_entity = entities_by_name.get(
                    field.reference
                )

                if target_entity is None:
                    raise RuntimeError(
                        f"Reference target "
                        f"'{field.reference}' missing"
                    )

                target_state = entities[
                    target_entity.tablename
                ]

                target_entity_id = self._require_id(
                    target_state.identity
                )

                # --------------------------------------------
                # Source FK field
                # --------------------------------------------

                source_field_identity = (
                    source_state.fields[
                        field.name
                    ]
                )

                source_field_id = self._require_id(
                    source_field_identity
                )

                # --------------------------------------------
                # References always target Burbot ID
                # --------------------------------------------

                target_id_identity = (
                    target_state.fields[
                        SYSTEM_ID_FIELD
                    ]
                )

                target_id_field_id = self._require_id(
                    target_id_identity
                )

                # --------------------------------------------
                # Stable relation identity
                # --------------------------------------------

                relation_identity = (
                    await self
                    ._get_or_create_relation_identity(
                        model_id=model_id,
                        from_field_id=source_field_id,
                    )
                )

                relation_id = self._require_id(
                    relation_identity
                )

                cardinality = (
                    BusinessRelationCardinality.ONE_TO_ONE
                    if field.unique
                    else BusinessRelationCardinality.MANY_TO_ONE
                )

                await self._relation_version_repository.add(
                    BusinessEntityRelationVersionAdd(
                        business_entity_relation_id=(
                            relation_id
                        ),

                        revision_id=revision_id,

                        key=field.name,

                        label=(
                            f"{source_entity.name}."
                            f"{field.name} -> "
                            f"{target_entity.name}"
                        ),

                        description=None,

                        from_entity_id=(
                            source_entity_id
                        ),

                        to_entity_id=(
                            target_entity_id
                        ),

                        from_field_id=(
                            source_field_id
                        ),

                        to_field_id=(
                            target_id_field_id
                        ),

                        cardinality=cardinality,

                        status=(
                            BusinessDefinitionStatus.ACTIVE
                        ),

                        definition_json={
                            "required": (
                                not field.nullable
                            ),
                        },

                        valid_from=valid_from,

                        valid_to=None,
                    )
                )

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

        stmt = select(
            BusinessEntity
        ).where(
            BusinessEntity.business_model_id == model_id,
            BusinessEntity.table_name == table_name,
        )

        result = await self._session.execute(
            stmt
        )

        identities = list(
            result.scalars().all()
        )

        if len(identities) > 1:
            raise RuntimeError(
                f"Multiple BusinessEntity identities "
                f"for model={model_id}, "
                f"table_name={table_name!r}"
            )

        return (
            identities[0]
            if identities
            else None
        )

    # ========================================================
    # Stable field identity
    # ========================================================

    async def _get_or_create_field_identity(
            self,
            *,
            entity_id: int,
            physical_name: str,
    ) -> BusinessEntityField:
        result = await self._field_repository.search(
            [
                BusinessEntityFieldFilter(
                    business_entity_id=entity_id,

                    physical_name=physical_name,
                )
            ]
        )

        if len(result) > 1:
            raise RuntimeError(
                f"Multiple BusinessEntityField identities "
                f"for entity {entity_id}, "
                f"field '{physical_name}'"
            )

        if result:
            return result[0]

        field_id = await self._field_repository.add(
            BusinessEntityFieldAdd(
                business_entity_id=entity_id,

                physical_name=physical_name,
            )
        )

        identity = await self._field_repository.get(
            field_id
        )

        if identity is None:
            raise RuntimeError(
                "BusinessEntityField disappeared "
                "after insert"
            )

        return identity

    # ========================================================
    # Stable relation identity
    # ========================================================

    async def _get_or_create_relation_identity(
            self,
            *,
            model_id: int,
            from_field_id: int,
    ) -> BusinessEntityRelation:
        """
        One stable Reference field owns at most one stable
        outgoing BusinessEntityRelation identity.

        Changing:

            Recruitment.project_id -> Project

        into:

            Recruitment.project_id -> Geography

        produces another VERSION of the same relation identity.
        """

        versions = (
            await self
            ._relation_version_repository
            .search(
                [
                    BusinessEntityRelationVersionFilter(
                        from_field_id=from_field_id,
                    )
                ]
            )
        )

        relation_ids = {
            version.business_entity_relation_id
            for version in versions
        }

        if len(relation_ids) > 1:
            raise RuntimeError(
                f"Field {from_field_id} is associated "
                f"with multiple stable relation identities"
            )

        if relation_ids:
            relation_id = next(
                iter(relation_ids)
            )

            relation = (
                await self._relation_repository.get(
                    relation_id
                )
            )

            if relation is None:
                raise RuntimeError(
                    f"Relation identity "
                    f"{relation_id} disappeared"
                )

            if (
                    relation.business_model_id
                    != model_id
            ):
                raise RuntimeError(
                    f"Relation {relation_id} belongs "
                    f"to another BusinessModel"
                )

            return relation

        relation_id = (
            await self._relation_repository.add(
                BusinessEntityRelationAdd(
                    business_model_id=model_id,
                )
            )
        )

        relation = (
            await self._relation_repository.get(
                relation_id
            )
        )

        if relation is None:
            raise RuntimeError(
                "BusinessEntityRelation disappeared "
                "after insert"
            )

        return relation

    # ========================================================
    # Close previous snapshot
    # ========================================================

    async def _close_revision_snapshot(
            self,
            *,
            revision_id: int,
            timestamp: datetime,
    ) -> None:
        # ====================================================
        # Relations
        # ====================================================

        relation_versions = (
            await self
            ._relation_version_repository
            .search(
                [
                    BusinessEntityRelationVersionFilter(
                        revision_id=revision_id,
                    )
                ]
            )
        )

        for version in relation_versions:
            # A current revision version should have both NULL,
            # but this also safely handles a partially closed row.
            if (
                    version.valid_to is not None
                    and version.transaction_to is not None
            ):
                continue

            await self._relation_version_repository.update(
                self._require_id(
                    version
                ),

                BusinessEntityRelationVersionUpdate(
                    valid_to=(
                            version.valid_to
                            or timestamp
                    ),

                    transaction_to=(
                            version.transaction_to
                            or timestamp
                    ),
                ),
            )

        # ====================================================
        # Fields
        # ====================================================

        field_versions = (
            await self
            ._field_version_repository
            .search(
                [
                    BusinessEntityFieldVersionFilter(
                        revision_id=revision_id,
                    )
                ]
            )
        )

        for version in field_versions:
            if (
                    version.valid_to is not None
                    and version.transaction_to is not None
            ):
                continue

            await self._field_version_repository.update(
                self._require_id(
                    version
                ),

                BusinessEntityFieldVersionUpdate(
                    valid_to=(
                            version.valid_to
                            or timestamp
                    ),

                    transaction_to=(
                            version.transaction_to
                            or timestamp
                    ),
                ),
            )

        # ====================================================
        # Entities
        # ====================================================

        entity_versions = (
            await self
            ._entity_version_repository
            .search(
                [
                    BusinessEntityVersionFilter(
                        revision_id=revision_id,
                    )
                ]
            )
        )

        for version in entity_versions:
            if (
                    version.valid_to is not None
                    and version.transaction_to is not None
            ):
                continue

            await self._entity_version_repository.update(
                self._require_id(
                    version
                ),

                BusinessEntityVersionUpdate(
                    valid_to=(
                            version.valid_to
                            or timestamp
                    ),

                    transaction_to=(
                            version.transaction_to
                            or timestamp
                    ),
                ),
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

            "definition_json": (
                    definition
                    or None
            ),
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
        desired = Sema().validate(
            scheme
        )

        model = await self._model_repository.get(
            model_id
        )

        if model is None:
            raise LookupError(
                f"BusinessModel {model_id} not found"
            )

        current_revision = (
            await self._get_current_revision(
                model
            )
        )

        if current_revision is None:
            return self._find_changes(
                current=Sema.Schema(
                    entities=[]
                ),
                desired=desired,
            )

        desired_hash = self._schema_hash(
            desired
        )

        stored_hash = (
            self._trusted_revision_hash(
                current_revision
            )
        )

        if stored_hash == desired_hash:
            return []

        current = self._schema_from_revision(
            current_revision
        )

        if (
                self._schema_hash(
                    current
                )
                == desired_hash
        ):
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
            raise ValueError(
                "offset cannot be negative"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        # Verify model exists.
        model = await self._model_repository.get(
            model_id
        )

        if model is None:
            raise LookupError(
                f"BusinessModel {model_id} not found"
            )

        stmt = (
            select(
                BusinessModelRevision
            )
            .where(
                BusinessModelRevision.business_model_id
                == model_id
            )
            .order_by(
                BusinessModelRevision.id.desc()
            )
            .offset(
                offset
            )
            .limit(
                limit
            )
        )

        count_stmt = (
            select(
                func.count()
            )
            .select_from(
                BusinessModelRevision
            )
            .where(
                BusinessModelRevision.business_model_id
                == model_id
            )
        )

        result = await self._session.execute(
            stmt
        )

        count = await self._session.scalar(
            count_stmt
        )

        revisions = list(
            result.scalars().all()
        )

        return (
            revisions,
            int(count or 0),
        )

    async def get_revision(
            self,
            revision_id: int,
    ) -> BusinessModelRevision:
        revision = (
            await self
            ._model_revision_repository
            .get(
                revision_id
            )
        )

        if revision is None:
            raise LookupError(
                f"BusinessModelRevision "
                f"{revision_id} not found"
            )

        return revision

    async def get_object_field_value_history(
            self,
            object_field_id: int,
            *,
            offset: int = 0,
            limit: int = 100,
    ) -> list[BusinessObjectFieldValueRead]:
        field_exists = await self._session.scalar(
            select(BusinessObjectField.id)
            .where(
                BusinessObjectField.id == object_field_id,
            )
        )

        if field_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business object field {object_field_id} not found.",
            )

        values = list(
            (
                await self._session.scalars(
                    select(BusinessObjectFieldValue)
                    .where(
                        BusinessObjectFieldValue.business_object_field_id
                        == object_field_id,
                    )
                    .order_by(
                        BusinessObjectFieldValue.valid_from.desc(),
                        BusinessObjectFieldValue.transaction_from.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )

        return [
            BusinessObjectFieldValueRead(
                id=value.id,
                business_object_field_id=value.business_object_field_id,
                value=value.value_json,
                valid_from=value.valid_from,
                valid_to=value.valid_to,
                transaction_from=value.transaction_from,
                transaction_to=value.transaction_to,
                created_at=value.created_at,
            )
            for value in values
        ]

    async def delete_object(
            self,
            object_id: int,
    ) -> None:
        async with self._session.begin():
            object_exists = await self._session.scalar(
                select(BusinessObject.id)
                .where(BusinessObject.id == object_id)
                .with_for_update()
            )

            if object_exists is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Business object {object_id} not found.",
                )

            has_values = await self._session.scalar(
                select(
                    func.exists()
                    .where(
                        BusinessObjectFieldValue.business_object_field_id.in_(
                            select(BusinessObjectField.id)
                            .where(
                                BusinessObjectField.business_object_id
                                == object_id
                            )
                        )
                    )
                )
            )

            if has_values:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Business object cannot be deleted because "
                        "it already has value history."
                    ),
                )

            # RESTRICT FK means slots have to go first.
            await self._session.execute(
                delete(BusinessObjectField)
                .where(
                    BusinessObjectField.business_object_id == object_id,
                )
            )

            await self._session.execute(
                delete(BusinessObject)
                .where(
                    BusinessObject.id == object_id,
                )
            )

    async def assign_object_fields_values(
            self,
            object_id: int,
            dict_values: dict[int, Any],
    ) -> BusinessObjectRead:
        if not dict_values:
            return await self.get_object(object_id)

        field_ids = sorted(dict_values)
        effective_at = datetime.now(UTC)

        async with self._session.begin():
            # Serialization point for assign/delete operations.
            object_exists = await self._session.scalar(
                select(BusinessObject.id)
                .where(BusinessObject.id == object_id)
                .with_for_update()
            )

            if object_exists is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Business object {object_id} not found.",
                )

            # Lock all slots in a stable order.
            fields = (
                await self._session.execute(
                    select(
                        BusinessObjectField.id,
                        BusinessObjectField.business_object_id,
                    )
                    .where(
                        BusinessObjectField.id.in_(field_ids),
                    )
                    .order_by(BusinessObjectField.id)
                    .with_for_update()
                )
            ).all()

            found_ids = {
                field_id
                for field_id, _ in fields
            }

            missing_ids = set(field_ids) - found_ids

            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "message": "Business object fields not found.",
                        "field_ids": sorted(missing_ids),
                    },
                )

            foreign_field_ids = {
                field_id
                for field_id, field_object_id in fields
                if field_object_id != object_id
            }

            if foreign_field_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": (
                            "Some fields do not belong to this business object."
                        ),
                        "field_ids": sorted(foreign_field_ids),
                    },
                )

            # Close all previous current business values.
            await self._session.execute(
                update(BusinessObjectFieldValue)
                .where(
                    BusinessObjectFieldValue.business_object_field_id.in_(
                        field_ids
                    ),
                    BusinessObjectFieldValue.valid_to.is_(None),
                    BusinessObjectFieldValue.transaction_to.is_(None),
                )
                .values(
                    valid_to=effective_at,
                )
            )

            # Insert all replacements in one statement.
            await self._session.execute(
                insert(BusinessObjectFieldValue),
                [
                    {
                        "business_object_field_id": field_id,
                        "value_json": value,
                        "valid_from": effective_at,
                        "valid_to": None,
                        "transaction_from": effective_at,
                        "transaction_to": None,
                    }
                    for field_id, value in dict_values.items()
                ],
            )

        return await self.get_object(object_id)

    async def create_object(
            self,
            entity_id: int,
    ) -> CreateObjectResponse:
        effective_at = datetime.now(UTC)

        async with self._session.begin():
            entity_exists = await self._session.scalar(
                select(BusinessEntity.id)
                .where(BusinessEntity.id == entity_id)
            )

            if entity_exists is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Business entity {entity_id} not found.",
                )

            # Do not allow creating data for an entity whose current
            # definition is not ACTIVE.
            active_entity_version = await self._session.scalar(
                select(BusinessEntityVersion.id)
                .where(
                    BusinessEntityVersion.business_entity_id == entity_id,
                    BusinessEntityVersion.status == BusinessDefinitionStatus.ACTIVE,
                    BusinessEntityVersion.valid_from <= effective_at,
                    BusinessEntityVersion.transaction_from <= effective_at,
                    BusinessEntityVersion.valid_to.is_(None),
                    BusinessEntityVersion.transaction_to.is_(None),
                )
            )

            if active_entity_version is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Business entity {entity_id} has no active definition.",
                )

            # Get active schema fields.
            field_ids_result = await self._session.execute(
                select(BusinessEntityField.id)
                .join(
                    BusinessEntityFieldVersion,
                    BusinessEntityFieldVersion.business_entity_field_id
                    == BusinessEntityField.id,
                )
                .where(
                    BusinessEntityField.business_entity_id == entity_id,
                    BusinessEntityFieldVersion.status
                    == BusinessDefinitionStatus.ACTIVE,
                    BusinessEntityFieldVersion.valid_from <= effective_at,
                    BusinessEntityFieldVersion.transaction_from <= effective_at,
                    BusinessEntityFieldVersion.valid_to.is_(None),
                    BusinessEntityFieldVersion.transaction_to.is_(None),
                )
                .order_by(BusinessEntityField.id)
            )

            entity_field_ids = list(field_ids_result.scalars().all())

            object_id = await self._session.scalar(
                insert(BusinessObject)
                .values(
                    business_entity_id=entity_id,
                )
                .returning(BusinessObject.id)
            )

            if object_id is None:
                raise RuntimeError("Failed to create business object.")

            if not entity_field_ids:
                return CreateObjectResponse(
                    object_id=object_id,
                    object_fields={},
                )

            created_fields = (
                await self._session.execute(
                    insert(BusinessObjectField)
                    .values(
                        [
                            {
                                "business_object_id": object_id,
                                "business_entity_field_id": entity_field_id,
                            }
                            for entity_field_id in entity_field_ids
                        ]
                    )
                    .returning(
                        BusinessObjectField.id,
                        BusinessObjectField.business_entity_field_id,
                    )
                )
            ).all()

            return CreateObjectResponse(
                object_id=object_id,
                object_fields={
                    entity_field_id: object_field_id
                    for object_field_id, entity_field_id in created_fields
                },
            )

    async def get_object(
            self,
            object_id: int,
    ) -> BusinessObjectRead:
        business_object = (
            await self._session.execute(
                select(BusinessObject)
                .where(BusinessObject.id == object_id)
            )
        ).scalar_one_or_none()

        if business_object is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business object {object_id} not found.",
            )

        result = await self._session.execute(
            select(
                BusinessObjectField.id,
                BusinessObjectField.business_entity_field_id,

                BusinessObjectFieldValue.id,
                BusinessObjectFieldValue.value_json,
                BusinessObjectFieldValue.valid_from,
            )
            .outerjoin(
                BusinessObjectFieldValue,
                and_(
                    BusinessObjectFieldValue.business_object_field_id
                    == BusinessObjectField.id,

                    BusinessObjectFieldValue.valid_to.is_(None),
                    BusinessObjectFieldValue.transaction_to.is_(None),
                ),
            )
            .where(
                BusinessObjectField.business_object_id == object_id,
            )
            .order_by(BusinessObjectField.id)
        )

        fields = [
            BusinessObjectFieldRead(
                object_field_id=object_field_id,
                business_entity_field_id=entity_field_id,
                value_id=value_id,
                value=value_json,
                valid_from=valid_from,
            )
            for (
                object_field_id,
                entity_field_id,
                value_id,
                value_json,
                valid_from,
            ) in result.all()
        ]

        return BusinessObjectRead(
            id=business_object.id,
            business_entity_id=business_object.business_entity_id,
            created_at=business_object.created_at,
            fields=fields,
        )
        # ========================================================

    async def list_objects(
            self,
            entity_id: int,
            *,
            offset: int = 0,
            limit: int = 100,
    ) -> list[BusinessObjectRead]:
        entity_exists = await self._session.scalar(
            select(BusinessEntity.id)
            .where(BusinessEntity.id == entity_id)
        )

        if entity_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business entity {entity_id} not found.",
            )

        objects = list(
            (
                await self._session.scalars(
                    select(BusinessObject)
                    .where(
                        BusinessObject.business_entity_id == entity_id,
                    )
                    .order_by(BusinessObject.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )

        if not objects:
            return []

        object_ids = [
            obj.id
            for obj in objects
            if obj.id is not None
        ]

        values_result = await self._session.execute(
            select(
                BusinessObjectField.business_object_id,
                BusinessObjectField.id,
                BusinessObjectField.business_entity_field_id,

                BusinessObjectFieldValue.id,
                BusinessObjectFieldValue.value_json,
                BusinessObjectFieldValue.valid_from,
            )
            .outerjoin(
                BusinessObjectFieldValue,
                and_(
                    BusinessObjectFieldValue.business_object_field_id
                    == BusinessObjectField.id,

                    BusinessObjectFieldValue.valid_to.is_(None),
                    BusinessObjectFieldValue.transaction_to.is_(None),
                ),
            )
            .where(
                BusinessObjectField.business_object_id.in_(object_ids),
            )
            .order_by(
                BusinessObjectField.business_object_id,
                BusinessObjectField.id,
            )
        )

        fields_by_object: dict[int, list[BusinessObjectFieldRead]] = {
            object_id: []
            for object_id in object_ids
        }

        for (
                object_id,
                object_field_id,
                entity_field_id,
                value_id,
                value_json,
                valid_from,
        ) in values_result.all():
            fields_by_object[object_id].append(
                BusinessObjectFieldRead(
                    object_field_id=object_field_id,
                    business_entity_field_id=entity_field_id,
                    value_id=value_id,
                    value=value_json,
                    valid_from=valid_from,
                )
            )

        return [
            BusinessObjectRead(
                id=obj.id,
                business_entity_id=obj.business_entity_id,
                created_at=obj.created_at,
                fields=fields_by_object[obj.id],
            )
            for obj in objects
        ]

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
            raise RuntimeError(
                f"{type(model).__name__} "
                f"has no persisted id"
            )

        return model_id

    async def _commit(
            self,
    ) -> None:
        try:
            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise
