"""HTTP surface for provisioned Burbot workspaces."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from extension_sync.contracts import (
    Commit,
    ReportCapture,
    Resolve,
    SelectorPreview,
    SelectorSync,
    SourcePreview,
    SourceResolve,
)
from extension_sync.identity import authenticate
from extension_sync.operations import SyncOperations
from extraction.exceptions import ExtractionConflict, ExtractionNotFound, ExtractionValidationError
from shared.database import get_session


class BoundedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method == "POST":
                payload = bytearray()
                async for chunk in request.stream():
                    if len(payload) + len(chunk) > 8 * 1024 * 1024:
                        raise HTTPException(413, detail={"code": "SYNC_PAYLOAD_TOO_LARGE"})
                    payload.extend(chunk)

                async def receive():
                    return {"type": "http.request", "body": bytes(payload)}

                request = Request(request.scope, receive)
            try:
                return await handler(request)
            except RequestValidationError as error:
                # Validation locations are useful without echoing submitted literals or credentials.
                locations = [list(item["loc"]) for item in error.errors()[:12]]
                raise HTTPException(
                    422,
                    detail={
                        "code": "INVALID_SYNC_REQUEST",
                        "paths": locations,
                    },
                ) from error

        return bounded


router = APIRouter(
    prefix="/api/v1/extension-sync", tags=["extension sync"], route_class=BoundedRoute
)
Session = Annotated[AsyncSession, Depends(get_session)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))]


async def execute(session, credentials, operation, request=None, *, readonly=False):
    token = credentials.credentials if credentials else None
    try:
        async with session.begin():
            workspace = await authenticate(
                session, token, getattr(request, "workspace_uuid", None), lock=not readonly
            )
            service = SyncOperations(session, workspace)
            method = getattr(service, operation)
            return await (method(request) if request is not None else method())
    except (ExtractionConflict, ExtractionNotFound, ExtractionValidationError) as error:
        status = 409 if isinstance(error, ExtractionConflict) else 422
        raise HTTPException(
            status, detail={"code": "EXTRACTION_SYNC_CONFLICT", "message": str(error)}
        ) from error


@router.get("/schema")
async def schema(session: Session, credentials: Credentials, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await execute(session, credentials, "schema", readonly=True)


@router.post("/objects/resolve")
async def resolve(request: Resolve, session: Session, credentials: Credentials):
    return await execute(session, credentials, "resolve", request)


@router.post("/commits")
async def commit(request: Commit, session: Session, credentials: Credentials):
    return await execute(session, credentials, "commit", request)


@router.post("/sources/preview")
async def preview_sources(request: SourcePreview, session: Session, credentials: Credentials):
    return await execute(session, credentials, "preview_sources", request, readonly=True)


@router.post("/sources/resolve")
async def resolve_sources(request: SourceResolve, session: Session, credentials: Credentials):
    return await execute(session, credentials, "resolve_sources", request)


@router.post("/selectors/preview")
async def preview_selectors(request: SelectorPreview, session: Session, credentials: Credentials):
    return await execute(session, credentials, "preview_selectors", request, readonly=True)


@router.post("/selectors")
async def selector(request: SelectorSync, session: Session, credentials: Credentials):
    return await execute(session, credentials, "sync_selector", request)


@router.post("/captures")
async def capture(request: ReportCapture, session: Session, credentials: Credentials):
    return await execute(session, credentials, "capture", request)
