from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session
from sources.exceptions import (
    SourceConflict,
    SourceError,
    SourceNotFound,
    SourceResourceNotFound,
    SourceValidationError,
)
from sources.services.sources import SourcesService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_sources_service(session: SessionDep) -> AsyncIterator[SourcesService]:
    try:
        yield SourcesService(session)
    except SourceError as error:
        status_code = 500
        if isinstance(error, (SourceNotFound, SourceResourceNotFound)):
            status_code = 404
        elif isinstance(error, SourceConflict):
            status_code = 409
        elif isinstance(error, SourceValidationError):
            status_code = 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error


SourcesServiceDep = Annotated[SourcesService, Depends(get_sources_service)]
