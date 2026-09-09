from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_layer.api.database import get_session
from business_layer.services.business import BusinessService
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


SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_business_service(
        session: SessionDep,
) -> BusinessService:
    return BusinessService(
        session=session,

        model_repository=BusinessModelRepository(
            session
        ),
        model_revision_repository=BusinessModelRevisionsRepository(
            session
        ),

        entity_repository=BusinessEntityRepository(
            session
        ),
        entity_version_repository=BusinessEntityVersionsRepository(
            session
        ),

        field_repository=BusinessEntityFieldsRepository(
            session
        ),
        field_version_repository=BusinessEntityFieldVersionsRepository(
            session
        ),

        relation_repository=BusinessEntityRelationsRepository(
            session
        ),
        relation_version_repository=BusinessEntityRelationVersionsRepository(
            session
        ),
    )


BusinessServiceDep = Annotated[
    BusinessService,
    Depends(get_business_service),
]