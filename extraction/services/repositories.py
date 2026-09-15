"""Queries and conflict-safe inserts used by extraction; never commits a transaction."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from business_layer.schemas.models import (
    BusinessEntity,
    BusinessEntityField,
    BusinessObject,
    BusinessObjectField,
)
from extraction.exceptions import ExtractionNotFound, ExtractionValidationError
from extraction.schemas.evidence import ExtractionCapture, FieldSelector, SourceScope
from extraction.schemas.models import ConcreteValue, ExtractionRun, FieldObservation
from extraction.services.recipes import stored_rule
from sources.schemas.models import (
    Source,
    SourceFieldTracking,
    SourceObjectFieldTracking,
    SourceSnapshot,
)


class ExtractionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get[Model: SQLModel](
        self,
        model: type[Model],
        identifier: int | str,
        *,
        lock: bool = False,
        validation: bool = False,
    ) -> Model:
        statement = select(model).where(model.id == identifier)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            error = ExtractionValidationError if validation else ExtractionNotFound
            raise error(f"{model.__name__} {identifier} does not exist")
        return row

    async def get_run(self, run_id: int, *, lock=False) -> ExtractionRun:
        return await self.get(ExtractionRun, run_id, lock=lock)

    async def get_snapshot(self, snapshot_id: int) -> SourceSnapshot:
        return await self.get(SourceSnapshot, snapshot_id)

    async def lock_source(self, source_id: int) -> Source:
        return await self.get(Source, source_id, lock=True)

    async def entity(self, entity_id: int) -> BusinessEntity:
        return await self.get(BusinessEntity, entity_id, validation=True)

    async def field(self, field_id: int) -> BusinessEntityField:
        return await self.get(BusinessEntityField, field_id, validation=True)

    async def object(self, object_id: int) -> BusinessObject:
        return await self.get(BusinessObject, object_id, validation=True)

    async def add[Model: SQLModel](self, row: Model) -> Model:
        if isinstance(row, FieldSelector):
            # Includes recipe copies on scope rollover. No new unchecked/legacy JSON.
            row.extraction_json = stored_rule(row).extraction.model_dump(mode="json")
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_or_create[Model: SQLModel](
        self,
        model: type[Model],
        identity: dict[str, Any],
        defaults: dict[str, Any] | None = None,
    ) -> Model:
        """Use the database unique identity even when different sources race."""
        insert = pg_insert if self.session.bind.dialect.name == "postgresql" else sqlite_insert
        statement = insert(model).values(**(defaults or {}), **identity).on_conflict_do_nothing()
        await self.session.execute(statement)
        query = select(model).filter_by(**identity).execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        if row is None:
            raise ExtractionValidationError(f"{model.__name__} conflicts with another identity")
        return row

    async def source_field(self, source_id: int, field_id: int) -> SourceFieldTracking:
        return await self.get_or_create(
            SourceFieldTracking,
            {
                "source_id": source_id,
                "business_entity_field_id": field_id,
            },
        )

    async def object_field(self, object_id: int, field_id: int) -> BusinessObjectField:
        return await self.get_or_create(
            BusinessObjectField,
            {
                "business_object_id": object_id,
                "business_entity_field_id": field_id,
            },
        )

    async def current_tracking(
        self, source_field_id: int, object_field_id: int
    ) -> SourceObjectFieldTracking | None:
        return await self.session.scalar(
            select(SourceObjectFieldTracking)
            .where(
                SourceObjectFieldTracking.source_field_tracking_id == source_field_id,
                SourceObjectFieldTracking.business_object_field_id == object_field_id,
                SourceObjectFieldTracking.valid_to.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def current_scope(self, source_id: int, name: str) -> SourceScope | None:
        return await self.session.scalar(
            select(SourceScope).where(
                SourceScope.source_id == source_id,
                SourceScope.name == name,
                SourceScope.valid_to.is_(None),
            )
        )

    async def current_selector(self, scope_id: int, source_field_id: int) -> FieldSelector | None:
        return await self.session.scalar(
            select(FieldSelector).where(
                FieldSelector.scope_id == scope_id,
                FieldSelector.source_field_tracking_id == source_field_id,
                FieldSelector.valid_to.is_(None),
            )
        )

    async def definitions(
        self, source_id: int
    ) -> tuple[list[SourceScope], list[FieldSelector], list[SourceFieldTracking]]:
        scopes = list(
            await self.session.scalars(
                select(SourceScope)
                .where(
                    SourceScope.source_id == source_id,
                    SourceScope.valid_to.is_(None),
                )
                .order_by(SourceScope.id)
                .execution_options(populate_existing=True)
            )
        )
        selectors = list(
            await self.session.scalars(
                select(FieldSelector)
                .join(
                    SourceScope,
                    SourceScope.id == FieldSelector.scope_id,
                )
                .where(
                    SourceScope.source_id == source_id,
                    SourceScope.valid_to.is_(None),
                    FieldSelector.valid_to.is_(None),
                )
                .order_by(FieldSelector.id)
                .execution_options(populate_existing=True)
            )
        )
        fields = list(
            await self.session.scalars(
                select(SourceFieldTracking)
                .where(
                    SourceFieldTracking.source_id == source_id,
                )
                .order_by(SourceFieldTracking.id)
                .execution_options(populate_existing=True)
            )
        )
        return scopes, selectors, fields

    async def get_capture(self, run_id: int) -> ExtractionCapture | None:
        return await self.session.get(ExtractionCapture, run_id)

    async def capture_for_key(self, key: str) -> ExtractionCapture | None:
        return await self.session.scalar(
            select(ExtractionCapture).where(ExtractionCapture.capture_key == key)
        )

    async def observation_values(self, observation: FieldObservation) -> list[ConcreteValue]:
        if observation.concrete_value_id is not None:
            return [await self.get(ConcreteValue, observation.concrete_value_id, validation=True)]
        return list(
            await self.session.scalars(
                select(ConcreteValue)
                .where(
                    ConcreteValue.field_observation_id == observation.id,
                )
                .order_by(ConcreteValue.value_index)
            )
        )

    async def bound_siblings(self, scope_instance_id: int) -> list[FieldObservation]:
        return list(
            await self.session.scalars(
                select(FieldObservation).where(
                    FieldObservation.scope_instance_id == scope_instance_id,
                    FieldObservation.business_object_id.is_not(None),
                )
            )
        )

    async def observation_value(self, observation: FieldObservation) -> ConcreteValue | None:
        if observation.concrete_value_id is None:
            return None  # Legacy multi-literal evidence has no single normalized baseline.
        return await self.get(ConcreteValue, observation.concrete_value_id, validation=True)
