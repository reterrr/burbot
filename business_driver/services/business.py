from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, or_, select

from business_driver.schemas.api import (
    BusinessEntityCreate,
    BusinessEntityFieldCreate,
    BusinessEntityFieldUpdate,
    BusinessEntityFieldValueSet,
    BusinessEntityRelationCreate,
    BusinessEntityStatePatch,
    BusinessEntityUpdate,
    RelationDirection,
)
from business_driver.schemas.entities import (
    BusinessEntity,
    BusinessEntityField,
    BusinessEntityFieldValue,
    BusinessEntityRelation,
    BusinessEntityRevision,
)
from business_driver.schemas.enums import (
    BusinessEntityFieldCardinality,
    BusinessEntityFieldDataType,
    ConfirmedBy,
)

_UNPROCESSABLE_CONTENT = 422


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(resource: str, identifier: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} {identifier} was not found.",
    )


def _normalize_machine_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=_UNPROCESSABLE_CONTENT,
            detail="Machine key cannot be empty.",
        )
    return normalized


def _persisted_id(identifier: int | None, resource: str) -> int:
    if identifier is None:
        raise RuntimeError(f"{resource} has not been persisted yet.")
    return identifier


def validate_field_value(field: BusinessEntityField, value: Any) -> None:
    """Validate the JSON value against the business field declaration.

    This intentionally stays conservative. It prevents obvious type errors
    while leaving domain-specific validation to a higher layer.
    """

    _validate_declared_value(
        data_type=field.data_type,
        cardinality=field.cardinality,
        required=field.required,
        key=field.key,
        value=value,
    )


def _validate_declared_value(
        *,
        data_type: BusinessEntityFieldDataType,
        cardinality: BusinessEntityFieldCardinality,
        required: bool,
        key: str,
        value: Any,
) -> None:
    if cardinality == BusinessEntityFieldCardinality.MANY:
        if not isinstance(value, list):
            raise HTTPException(
                status_code=_UNPROCESSABLE_CONTENT,
                detail=f"Field '{key}' expects a list because cardinality=MANY.",
            )
        if required and not value:
            raise HTTPException(
                status_code=_UNPROCESSABLE_CONTENT,
                detail=f"Required field '{key}' cannot store an empty list.",
            )
        for item in value:
            _validate_scalar(data_type, item, key)
        return

    if isinstance(value, list):
        raise HTTPException(
            status_code=_UNPROCESSABLE_CONTENT,
            detail=f"Field '{key}' expects one value, not a list.",
        )
    _validate_scalar(data_type, value, key)


def _validate_scalar(
        data_type: BusinessEntityFieldDataType,
        value: Any,
        key: str,
) -> None:
    if value is None:
        raise HTTPException(
            status_code=_UNPROCESSABLE_CONTENT,
            detail=f"Field '{key}' cannot store null as an accepted value.",
        )

    if data_type == BusinessEntityFieldDataType.TEXT:
        valid = isinstance(value, str)
    elif data_type == BusinessEntityFieldDataType.URL:
        valid = _is_http_url(value)
    elif data_type == BusinessEntityFieldDataType.INTEGER:
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif data_type in {
        BusinessEntityFieldDataType.DECIMAL,
        BusinessEntityFieldDataType.MONEY,
        BusinessEntityFieldDataType.PERCENTAGE,
    }:
        valid = (isinstance(value, int) and not isinstance(value, bool)) or (
                isinstance(value, float) and isfinite(value)
        )
    elif data_type == BusinessEntityFieldDataType.BOOLEAN:
        valid = isinstance(value, bool)
    elif data_type == BusinessEntityFieldDataType.DATE:
        valid = _is_iso_date(value)
    elif data_type == BusinessEntityFieldDataType.DATETIME:
        valid = _is_aware_iso_datetime(value)
    else:
        valid = True

    if not valid:
        raise HTTPException(
            status_code=_UNPROCESSABLE_CONTENT,
            detail=f"Value does not match field '{key}' data type {data_type.value}.",
        )


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        # Accessing hostname validates bracketed IPv6 hosts as well.
        hostname = parsed.hostname
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(hostname)


def _is_aware_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


class BusinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_entity(self, entity_id: int) -> BusinessEntity:
        result = await self.session.execute(
            select(BusinessEntity).where(col(BusinessEntity.id) == entity_id)
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            raise _not_found("Business entity", entity_id)
        return entity

    async def create_entity(self, payload: BusinessEntityCreate) -> BusinessEntity:
        entity = BusinessEntity(entity_type=_normalize_machine_key(payload.entity_type))
        self.session.add(entity)
        await self._commit()
        await self.session.refresh(entity)
        return entity

    async def list_entities(
            self,
            *,
            entity_type: str | None,
            offset: int,
            limit: int,
    ) -> list[BusinessEntity]:
        stmt = (
            select(BusinessEntity)
            .order_by(col(BusinessEntity.id))
            .offset(offset)
            .limit(limit)
        )
        if entity_type is not None:
            stmt = stmt.where(
                col(BusinessEntity.entity_type) == _normalize_machine_key(entity_type)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_entity(
            self,
            entity_id: int,
            payload: BusinessEntityUpdate,
    ) -> BusinessEntity:
        entity = await self.get_entity(entity_id)
        if payload.entity_type is not None:
            entity.entity_type = _normalize_machine_key(payload.entity_type)
        await self._commit()
        await self.session.refresh(entity)
        return entity

    async def create_field(
            self,
            entity_id: int,
            payload: BusinessEntityFieldCreate,
    ) -> BusinessEntityField:
        await self.get_entity(entity_id)
        field = BusinessEntityField(
            business_entity_id=entity_id,
            key=_normalize_machine_key(payload.key),
            label=payload.label,
            data_type=payload.data_type,
            cardinality=payload.cardinality,
            required=payload.required,
            description=payload.description,
        )
        self.session.add(field)
        await self._commit_conflict(
            "A field with this key already exists for the entity."
        )
        await self.session.refresh(field)
        return field

    async def get_field(
            self,
            field_id: int,
            *,
            include_deleted: bool = False,
            for_update: bool = False,
    ) -> BusinessEntityField:
        stmt = select(BusinessEntityField).where(
            col(BusinessEntityField.id) == field_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        field = result.scalar_one_or_none()
        if field is None or (field.deleted_at is not None and not include_deleted):
            raise _not_found("Business entity field", field_id)
        return field

    async def list_fields(
            self,
            entity_id: int,
            *,
            for_update: bool = False,
    ) -> list[BusinessEntityField]:
        await self.get_entity(entity_id)
        stmt = (
            select(BusinessEntityField)
            .where(
                col(BusinessEntityField.business_entity_id) == entity_id,
                col(BusinessEntityField.deleted_at).is_(None),
            )
            .order_by(col(BusinessEntityField.id))
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_field(
            self,
            field_id: int,
            payload: BusinessEntityFieldUpdate,
    ) -> BusinessEntityField:
        field = await self.get_field(field_id, for_update=True)
        data = payload.model_dump(exclude_unset=True)

        current = await self._get_current_value_row(field_id)
        if current is not None and any(
                key in data for key in ("data_type", "cardinality", "required")
        ):
            _validate_declared_value(
                data_type=data.get("data_type", field.data_type),
                cardinality=data.get("cardinality", field.cardinality),
                required=data.get("required", field.required),
                key=field.key,
                value=current.value_json,
            )

        for key, value in data.items():
            setattr(field, key, value)
        await self._commit()
        await self.session.refresh(field)
        return field

    async def delete_field(self, field_id: int) -> None:
        field = await self.get_field(field_id, for_update=True)
        now = _now()
        current = await self._get_current_value_row(field_id)
        if current is not None:
            current.valid_to = now
        field.deleted_at = now
        await self._commit()

    async def get_current_value(
            self,
            field_id: int,
    ) -> BusinessEntityFieldValue | None:
        await self.get_field(field_id)
        return await self._get_current_value_row(field_id)

    async def _get_current_value_row(
            self,
            field_id: int,
    ) -> BusinessEntityFieldValue | None:
        result = await self.session.execute(
            select(BusinessEntityFieldValue)
            .where(
                col(BusinessEntityFieldValue.business_entity_field_id) == field_id,
                col(BusinessEntityFieldValue.valid_to).is_(None),
            )
            .order_by(col(BusinessEntityFieldValue.valid_from).desc())
        )
        return result.scalar_one_or_none()

    async def get_value_history(
            self,
            field_id: int,
            *,
            offset: int,
            limit: int,
    ) -> list[BusinessEntityFieldValue]:
        await self.get_field(field_id, include_deleted=True)
        result = await self.session.execute(
            select(BusinessEntityFieldValue)
            .where(col(BusinessEntityFieldValue.business_entity_field_id) == field_id)
            .order_by(col(BusinessEntityFieldValue.valid_from).desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def set_current_value(
            self,
            field_id: int,
            payload: BusinessEntityFieldValueSet,
    ) -> BusinessEntityFieldValue:
        # The field row is the serialization point for every current-value
        # writer. This prevents two requests from both replacing the same
        # current row at once.
        field = await self.get_field(field_id, for_update=True)
        validate_field_value(field, payload.value)

        current = await self._get_current_value_row(field_id)
        if (
                current is not None
                and current.value_json == payload.value
                and current.confirmed_by == payload.confirmed_by
                and payload.reason is None
                and payload.revision_metadata is None
        ):
            await self._commit()
            return current

        revision = BusinessEntityRevision(
            business_entity_id=field.business_entity_id,
            reason=payload.reason,
            metadata_json=payload.revision_metadata,
        )
        self.session.add(revision)
        await self.session.flush()

        value = await self._replace_current_value(
            field=field,
            new_value=payload.value,
            confirmed_by=payload.confirmed_by,
            revision_id=_persisted_id(revision.id, "Business entity revision"),
            current=current,
        )
        await self._commit_conflict(
            "The field's current value was changed by another request."
        )
        await self.session.refresh(value)
        return value

    async def clear_current_value(self, field_id: int) -> None:
        field = await self.get_field(field_id, for_update=True)
        current = await self._get_current_value_row(field_id)
        if current is None:
            await self._commit()
            return
        if field.required:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Required field '{field.key}' cannot be cleared.",
            )
        current.valid_to = _now()
        await self._commit()

    async def get_state(
            self,
            entity_id: int,
    ) -> tuple[
        BusinessEntity,
        list[tuple[BusinessEntityField, BusinessEntityFieldValue | None]],
    ]:
        entity = await self.get_entity(entity_id)
        fields = await self.list_fields(entity_id)
        if not fields:
            return entity, []

        persisted_fields = [
            (field, _persisted_id(field.id, "Business entity field"))
            for field in fields
        ]
        field_ids = [field_id for _, field_id in persisted_fields]
        result = await self.session.execute(
            select(BusinessEntityFieldValue).where(
                col(BusinessEntityFieldValue.business_entity_field_id).in_(field_ids),
                col(BusinessEntityFieldValue.valid_to).is_(None),
            )
        )
        current_by_field = {
            value.business_entity_field_id: value for value in result.scalars().all()
        }
        return entity, [
            (field, current_by_field.get(field_id))
            for field, field_id in persisted_fields
        ]

    async def patch_state(
            self,
            entity_id: int,
            payload: BusinessEntityStatePatch,
    ) -> None:
        await self.get_entity(entity_id)
        # Lock in primary-key order so state patches and single-field writes
        # share the same serialization point without deadlocking each other.
        fields = await self.list_fields(entity_id, for_update=True)
        fields_by_key = {field.key: field for field in fields}

        missing = sorted(set(payload.values) - set(fields_by_key))
        if missing:
            raise HTTPException(
                status_code=_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Unknown field keys for this entity.",
                    "fields": missing,
                },
            )

        changed: list[
            tuple[
                BusinessEntityField,
                Any,
                BusinessEntityFieldValue | None,
            ]
        ] = []
        for key, value in payload.values.items():
            field = fields_by_key[key]
            validate_field_value(field, value)
            field_id = _persisted_id(field.id, "Business entity field")
            current = await self._get_current_value_row(field_id)
            if (
                    current is None
                    or current.value_json != value
                    or current.confirmed_by != payload.confirmed_by
            ):
                changed.append((field, value, current))

        if not changed:
            await self._commit()
            return

        revision = BusinessEntityRevision(
            business_entity_id=entity_id,
            reason=payload.reason,
            metadata_json=payload.revision_metadata,
        )
        self.session.add(revision)
        await self.session.flush()

        for field, value, current in changed:
            await self._replace_current_value(
                field=field,
                new_value=value,
                confirmed_by=payload.confirmed_by,
                revision_id=_persisted_id(
                    revision.id,
                    "Business entity revision",
                ),
                current=current,
            )

        await self._commit_conflict("The entity state was changed by another request.")

    async def create_relation(
            self,
            from_entity_id: int,
            payload: BusinessEntityRelationCreate,
    ) -> BusinessEntityRelation:
        await self.get_entity(from_entity_id)
        await self.get_entity(payload.to_entity_id)

        relation_key = _normalize_machine_key(payload.relation_key)
        existing = await self.session.execute(
            select(BusinessEntityRelation).where(
                col(BusinessEntityRelation.from_entity_id) == from_entity_id,
                col(BusinessEntityRelation.to_entity_id) == payload.to_entity_id,
                col(BusinessEntityRelation.relation_key) == relation_key,
                col(BusinessEntityRelation.valid_to).is_(None),
            )
        )
        current = existing.scalar_one_or_none()
        if current is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This active relation already exists.",
            )

        relation = BusinessEntityRelation(
            from_entity_id=from_entity_id,
            to_entity_id=payload.to_entity_id,
            relation_key=relation_key,
            metadata_json=payload.metadata_json,
        )
        self.session.add(relation)
        await self._commit_conflict("This active relation already exists.")
        await self.session.refresh(relation)
        return relation

    async def get_relation(
            self,
            relation_id: int,
            *,
            for_update: bool = False,
    ) -> BusinessEntityRelation:
        stmt = select(BusinessEntityRelation).where(
            col(BusinessEntityRelation.id) == relation_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        relation = result.scalar_one_or_none()
        if relation is None:
            raise _not_found("Business entity relation", relation_id)
        return relation

    async def list_relations(
            self,
            entity_id: int,
            *,
            direction: RelationDirection,
            relation_key: str | None,
            active_only: bool,
    ) -> list[BusinessEntityRelation]:
        await self.get_entity(entity_id)

        if direction == "incoming":
            predicate = col(BusinessEntityRelation.to_entity_id) == entity_id
        elif direction == "outgoing":
            predicate = col(BusinessEntityRelation.from_entity_id) == entity_id
        else:
            predicate = or_(
                col(BusinessEntityRelation.from_entity_id) == entity_id,
                col(BusinessEntityRelation.to_entity_id) == entity_id,
            )

        stmt = select(BusinessEntityRelation).where(predicate)
        if relation_key is not None:
            stmt = stmt.where(
                col(BusinessEntityRelation.relation_key)
                == _normalize_machine_key(relation_key)
            )
        if active_only:
            stmt = stmt.where(col(BusinessEntityRelation.valid_to).is_(None))

        result = await self.session.execute(
            stmt.order_by(col(BusinessEntityRelation.id))
        )
        return list(result.scalars().all())

    async def close_relation(self, relation_id: int) -> None:
        relation = await self.get_relation(relation_id, for_update=True)
        if relation.valid_to is None:
            relation.valid_to = _now()
            await self._commit()
        else:
            await self._commit()

    async def list_revisions(
            self,
            entity_id: int,
            *,
            offset: int,
            limit: int,
    ) -> list[BusinessEntityRevision]:
        await self.get_entity(entity_id)
        result = await self.session.execute(
            select(BusinessEntityRevision)
            .where(col(BusinessEntityRevision.business_entity_id) == entity_id)
            .order_by(col(BusinessEntityRevision.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_revision(self, revision_id: int) -> BusinessEntityRevision:
        result = await self.session.execute(
            select(BusinessEntityRevision).where(
                col(BusinessEntityRevision.id) == revision_id
            )
        )
        revision = result.scalar_one_or_none()
        if revision is None:
            raise _not_found("Business entity revision", revision_id)
        return revision

    async def _replace_current_value(
            self,
            *,
            field: BusinessEntityField,
            new_value: Any,
            confirmed_by: ConfirmedBy,
            revision_id: int | None,
            current: BusinessEntityFieldValue | None,
    ) -> BusinessEntityFieldValue:
        now = _now()
        if current is not None:
            current.valid_to = now
            # Make the old row non-current before inserting the replacement;
            # this is required by the partial unique index on current values.
            await self.session.flush()

        new_row = BusinessEntityFieldValue(
            business_entity_field_id=_persisted_id(
                field.id,
                "Business entity field",
            ),
            revision_id=revision_id,
            value_json=new_value,
            confirmed_by=confirmed_by,
            valid_from=now,
        )
        self.session.add(new_row)
        await self.session.flush()
        return new_row

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def _commit_conflict(self, detail: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
