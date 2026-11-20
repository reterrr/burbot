"""Coordinate schema-language programs through the business definition/data owners."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_layer.schemas.execution import ExecutionResult
from business_layer.schemas.models import BusinessModel
from business_layer.services.data import DataService
from business_layer.services.definition_code import DefinitionCodeService
from business_layer.services.entities import EntitiesService, RegisterResult, SchemaChange
from business_layer.services.schema_parser import Program, analyze_program
from business_layer.services.transactions import transaction


class BusinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.entities = EntitiesService(session)
        self.data = DataService(session)
        self.definition_code = DefinitionCodeService(session)

    async def compile(self, model_id: int, code: str) -> Program:
        """Validate and preview source against a model without writing anything."""
        return await self.entities.compile(model_id, code)

    async def execute(
        self,
        model_id: int,
        *,
        code: str | None = None,
        program: Program | None = None,
        reason: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Register definitions and apply named objects in one atomic operation."""
        if (code is None) == (program is None):
            raise HTTPException(422, "Provide exactly one of code or program")
        async with transaction(self.session):
            model = await self.session.scalar(
                select(BusinessModel)
                .where(
                    BusinessModel.id == model_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if model is None:
                raise LookupError("Business model not found")
            plan = (
                await self.compile(model_id, code)
                if code is not None
                else analyze_program(program.model_copy(deep=True))
            )
            revision = await self.entities.register_program(
                model_id,
                plan,
                reason=reason,
                metadata_json=metadata_json,
            )
            seeds = await self.data.seed_objects(model_id, plan)
            source = (await self.definition_code.save(
                model_id, code, reason=reason, schema_revision_id=revision.revision_id
            )) if code is not None else None
            return ExecutionResult(
                code_version=source.version if source else None,
                revision_id=revision.revision_id,
                schema_changed=revision.changed,
                **seeds.model_dump(),
            )

    def __getattr__(self, name):
        # Preserve public methods used before definition/data ownership was split.
        if name.startswith("_"):
            raise AttributeError(name)
        if hasattr(self.entities, name):
            return getattr(self.entities, name)
        return getattr(self.data, name)


__all__ = ["BusinessService", "RegisterResult", "SchemaChange"]
