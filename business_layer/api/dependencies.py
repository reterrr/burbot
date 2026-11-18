from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_layer.api.database import get_session
from business_layer.services import (
    BusinessService,
    CollectionsService,
    DataService,
    EntitiesService,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_business_service(session: SessionDep) -> BusinessService:
    return BusinessService(session)


BusinessServiceDep = Annotated[BusinessService, Depends(get_business_service)]


def get_entities_service(business: BusinessServiceDep) -> EntitiesService:
    return business.entities


def get_data_service(business: BusinessServiceDep) -> DataService:
    return business.data


EntitiesServiceDep = Annotated[EntitiesService, Depends(get_entities_service)]
DataServiceDep = Annotated[DataService, Depends(get_data_service)]


def get_collections_service(data: DataServiceDep):
    return data.collections


CollectionsServiceDep = Annotated[CollectionsService, Depends(get_collections_service)]
