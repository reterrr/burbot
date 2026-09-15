from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.exceptions import (
    ExtractionConflict,
    ExtractionError,
    ExtractionNotFound,
    ExtractionValidationError,
)
from extraction.services.extraction import ExtractionService
from shared.database import get_session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_extraction_service(
    session: SessionDep,
) -> AsyncIterator[ExtractionService]:
    try:
        yield ExtractionService(session)
    except ExtractionError as error:
        status_code = 500
        if isinstance(error, ExtractionNotFound):
            status_code = 404
        elif isinstance(error, ExtractionConflict):
            status_code = 409
        elif isinstance(error, ExtractionValidationError):
            status_code = 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error


ExtractionServiceDep = Annotated[ExtractionService, Depends(get_extraction_service)]
