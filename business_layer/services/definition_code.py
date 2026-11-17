"""Version definition source without replacing semantic definition history."""
from difflib import unified_diff
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from business_layer.schemas.models import BusinessDefinitionCodeVersion, BusinessModel
from business_layer.services.entities import EntitiesService
from business_layer.services.transactions import transaction


class DefinitionCodeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_versions(self, model_id: int, *, limit: int = 100, offset: int = 0):
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("Invalid history pagination")
        return list((await self.session.scalars(select(BusinessDefinitionCodeVersion).where(
            BusinessDefinitionCodeVersion.business_model_id == model_id
        ).order_by(BusinessDefinitionCodeVersion.version.desc()).limit(limit).offset(offset))).all())

    async def get_version(self, model_id: int, version: int | None = None):
        query = select(BusinessDefinitionCodeVersion).where(
            BusinessDefinitionCodeVersion.business_model_id == model_id)
        if version is not None:
            query = query.where(BusinessDefinitionCodeVersion.version == version)
        row = await self.session.scalar(query.order_by(BusinessDefinitionCodeVersion.version.desc()).limit(1))
        if row is None and version is not None:
            raise LookupError("Definition code version not found")
        return row

    async def save(self, model_id: int, code: str, *, reason: str | None = None,
                   expected_version: int | None = None, schema_revision_id: int | None = None):
        """Save validated source. expected_version=0 requires an empty history.

        Saving does not execute constructors or apply definitions. A successful
        BusinessService.execute records the corresponding semantic revision too.
        """
        async with transaction(self.session):
            model = await self.session.scalar(select(BusinessModel).where(
                BusinessModel.id == model_id).with_for_update())
            if model is None:
                raise LookupError("Business model not found")
            current = await self.get_version(model_id)
            number = current.version if current else 0
            if expected_version is not None and expected_version != number:
                raise HTTPException(409, "Definition code changed; reload its latest version")
            await EntitiesService(self.session).compile(model_id, code)
            digest = sha256(code.encode()).hexdigest()
            if current and current.code == code and (
                schema_revision_id is None or current.schema_revision_id == schema_revision_id
            ):
                return current
            row = BusinessDefinitionCodeVersion(
                business_model_id=model_id, version=number + 1, code=code,
                sha256=digest, schema_revision_id=schema_revision_id, reason=reason)
            self.session.add(row)
            await self.session.flush()
            return row

    async def diff(self, model_id: int, before: int, after: int) -> str:
        first = await self.get_version(model_id, before)
        second = await self.get_version(model_id, after)
        return ''.join(unified_diff(first.code.splitlines(keepends=True),
                                    second.code.splitlines(keepends=True),
                                    fromfile=f'version-{before}', tofile=f'version-{after}'))

    async def restore(self, model_id: int, version: int, *, expected_version: int | None = None):
        """Copy old source to a new head; applying it is a separate execute call."""
        source = await self.get_version(model_id, version)
        return await self.save(model_id, source.code, reason=f"Restore version {version}",
                               expected_version=expected_version)
