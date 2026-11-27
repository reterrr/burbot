"""The operator enrolls agents. Source-scoped agents poll and report under a lease."""

import asyncio
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from extraction.schemas.common import utc_now
from monitoring.attention import AttentionIssue, AttentionSort, attention_sources
from monitoring.contracts import (
    MAX_BYTES,
    MAX_VISUAL_ARCHIVE_BYTES,
    MIME_TYPE,
    VISUAL_ARCHIVE_VERSION,
    AgentSourcesUpdate,
    Approval,
    ArchiveObjectGrant,
    ArchiveObjectTarget,
    ArchiveReport,
    ArchiveSummary,
    ClaimedJob,
    ClaimedSnapshotCommand,
    Completion,
    Digest,
    EvidenceReviewResponse,
    Failure,
    FindingCapture,
    Heartbeat,
    JobStatus,
    MonitoringPage,
    ObjectInboxItem,
    ObjectReviewResponse,
    OpenSnapshotRequest,
    RegisterAgent,
    SnapshotAgentChoice,
    SnapshotCommandAck,
    SnapshotCommandResponse,
    SnapshotContent,
    SourceReviewResponse,
    UploadRequest,
    UploadURL,
    VisualArchiveUpload,
)
from monitoring.diagnostics import coverage, overview
from monitoring.object_reviews import finding_history, object_inbox, object_review
from monitoring.onboarding import OnboardingRequest, OnboardingService
from monitoring.onboarding_config import MonitoringMode, onboarding_config
from monitoring.queue import MonitoringQueue, status
from monitoring.review import review_detail
from monitoring.security import MonitoringError, authenticate_agent, authorize_admin
from monitoring.snapshot_commands import (
    acknowledge_command,
    agent_choices,
    claim_command,
    command_archive_object,
    command_artifact,
    command_row,
    create_command,
)
from monitoring.snapshot_commands import (
    response as snapshot_command_response,
)
from monitoring.snapshot_config import MAX_MANIFEST_BYTES
from monitoring.snapshots import (
    SNAPSHOT_HEADERS,
    artifact_bytes,
    sanitized_preview,
    snapshot_content,
    snapshot_record,
)
from monitoring.storage import ARCHIVE_CHUNK_BYTES, ARCHIVE_MEDIA_TYPE, storage_from_env
from monitoring.workspace import check_history, field_review, source_review
from shared.database import get_session


class MonitoringRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method in {"POST", "PUT"}:
                body = bytearray()
                if request.url.path.endswith("/complete"):
                    limit = 8 * 1024 * 1024
                elif request.url.path.endswith("/full-archive"):
                    limit = MAX_MANIFEST_BYTES
                else:
                    limit = 32 * 1024
                async for chunk in request.stream():
                    if len(body) + len(chunk) > limit:
                        raise HTTPException(413, detail={"code": "REQUEST_TOO_LARGE"})
                    body.extend(chunk)

                async def receive():
                    return {"type": "http.request", "body": bytes(body)}

                request = Request(request.scope, receive)
            try:
                return await handler(request)
            except RequestValidationError as error:
                # Requests can contain captured text. Keep it out of error responses.
                raise HTTPException(422, detail={"code": "INVALID_REQUEST"}) from error
            except MonitoringError as error:
                raise as_http(error) from error

        return bounded


class SnapshotRoute(MonitoringRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def protect(request):
            try:
                response = await handler(request)
            except HTTPException as error:
                error.headers = {**(error.headers or {}), **SNAPSHOT_HEADERS}
                raise
            response.headers.update(SNAPSHOT_HEADERS)
            return response

        return protect


router = APIRouter(prefix="/monitoring", tags=["monitoring"], route_class=MonitoringRoute)
bearer = HTTPBearer(auto_error=False)
Session = Annotated[AsyncSession, Depends(get_session)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
SourceCursor = Annotated[int, Query(alias="afterSourceId", ge=0, le=9223372036854775807)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0, le=2147483647)]
SourceId = Annotated[int, Path(ge=1, le=9223372036854775807)]


def token(credentials):
    if credentials is None or not 0 < len(credentials.credentials) <= 256:
        raise MonitoringError(401, "BEARER_TOKEN_REQUIRED")
    return credentials.credentials


def as_http(error):
    return HTTPException(
        status_code=error.status,
        detail={"code": error.code},
        headers={"WWW-Authenticate": "Bearer"} if error.status == 401 else None,
    )


async def operator(credentials: Credentials):
    try:
        authorize_admin(token(credentials), os.getenv("MONITORING_ADMIN_TOKEN"))
    except MonitoringError as error:
        raise as_http(error) from error


snapshot_routes = APIRouter(
    prefix="/sources/{source_id}/snapshots/{snapshot_id}",
    route_class=SnapshotRoute,
    dependencies=[Depends(operator)],
)


@snapshot_routes.get("/preview", response_class=HTMLResponse)
async def get_snapshot_preview(source_id: SourceId, snapshot_id: SourceId, session: Session):
    _, file = await snapshot_record(session, source_id, snapshot_id)
    body = await artifact_bytes(file)
    return HTMLResponse(await asyncio.to_thread(sanitized_preview, body))


@snapshot_routes.get("/content", response_model=SnapshotContent)
async def get_snapshot_content(
    source_id: SourceId,
    snapshot_id: SourceId,
    session: Session,
    metadata_only: Annotated[bool, Query(alias="metadataOnly")] = False,
):
    return await snapshot_content(session, source_id, snapshot_id, metadata_only=metadata_only)


@snapshot_routes.get(
    "/download",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def get_snapshot_download(source_id: SourceId, snapshot_id: SourceId, session: Session):
    _, file = await snapshot_record(session, source_id, snapshot_id)
    return Response(
        await artifact_bytes(file),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="snapshot-{snapshot_id}.html"'},
    )


router.include_router(snapshot_routes)


bridge_routes = APIRouter(route_class=SnapshotRoute)
OPEN_COMMANDS = "/snapshots/open-commands"
AGENT_COMMANDS = "/agents/snapshot-commands"


@bridge_routes.get(
    "/sources/{source_id}/snapshot-agents",
    dependencies=[Depends(operator)],
    response_model=list[SnapshotAgentChoice],
)
async def snapshot_agents(source_id: SourceId, session: Session):
    return await agent_choices(session, source_id)


@bridge_routes.post(
    OPEN_COMMANDS, dependencies=[Depends(operator)], response_model=SnapshotCommandResponse
)
async def open_snapshot(request: OpenSnapshotRequest, session: Session):
    async with session.begin():
        return await create_command(session, request)


@bridge_routes.get(
    OPEN_COMMANDS + "/{command_id}",
    dependencies=[Depends(operator)],
    response_model=SnapshotCommandResponse,
)
async def snapshot_command(command_id: UUID, session: Session):
    async with session.begin():
        return snapshot_command_response(await command_row(session, command_id))


@bridge_routes.post(AGENT_COMMANDS + "/claim", response_model=ClaimedSnapshotCommand)
async def claim_snapshot_command(session: Session, credentials: Credentials):
    async with session.begin():
        agent = await authenticate_agent(session, token(credentials))
        command = await claim_command(session, agent)
    return command if command is not None else Response(status_code=204)


@bridge_routes.get(AGENT_COMMANDS + "/{command_id}/artifact", response_class=Response)
async def snapshot_command_artifact(
    command_id: UUID,
    session: Session,
    credentials: Credentials,
    archive_format: Annotated[str | None, Header(alias="X-Burbot-Snapshot-Accept")] = None,
):
    async with session.begin():
        agent = await authenticate_agent(session, token(credentials), lock=False)
        file, digest, expires_at, visual = await command_artifact(
            session, agent, command_id, prefer_visual=archive_format == VISUAL_ARCHIVE_VERSION
        )
        # End the DB transaction before waiting for storage. Carry only the verified file record.
        session.expunge(file)
    content = await artifact_bytes(
        file, max_bytes=MAX_VISUAL_ARCHIVE_BYTES if visual else MAX_BYTES
    )
    if expires_at <= utc_now():
        raise MonitoringError(410, "SNAPSHOT_COMMAND_EXPIRED")
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="snapshot.html"',
            "X-Burbot-Snapshot-Mime": MIME_TYPE,
            "X-Burbot-Snapshot-SHA256": digest,
            "X-Burbot-Snapshot-Size": str(len(content)),
            **({"X-Burbot-Snapshot-Format": VISUAL_ARCHIVE_VERSION} if visual else {}),
        },
    )


async def archive_response(session, credentials, command_id, digest=None):
    async with session.begin():
        agent = await authenticate_agent(session, token(credentials), lock=False)
        key, size, checksum, expires = await command_archive_object(
            session, agent, command_id, digest
        )
    handle = await storage_from_env().read_archive_file(key, size, checksum)
    if expires <= utc_now():
        handle.close()
        raise MonitoringError(410, "SNAPSHOT_COMMAND_EXPIRED")
    return StreamingResponse(
        iter(lambda: handle.read(ARCHIVE_CHUNK_BYTES), b""),
        media_type=ARCHIVE_MEDIA_TYPE,
        headers={
            "Content-Length": str(size),
            "Content-Disposition": "attachment",
            "X-Burbot-Snapshot-Size": str(size),
            "X-Burbot-Snapshot-SHA256": checksum,
        },
        background=BackgroundTask(handle.close),
    )


@bridge_routes.get(AGENT_COMMANDS + "/{command_id}/archive-manifest")
async def snapshot_command_manifest(command_id: UUID, session: Session, credentials: Credentials):
    return await archive_response(session, credentials, command_id)


@bridge_routes.get(AGENT_COMMANDS + "/{command_id}/archive-objects/{digest}")
async def snapshot_command_object(
    command_id: UUID, digest: Digest, session: Session, credentials: Credentials
):
    return await archive_response(session, credentials, command_id, digest)


@bridge_routes.post(AGENT_COMMANDS + "/{command_id}/ack", response_model=SnapshotCommandResponse)
async def ack_snapshot_command(
    command_id: UUID, request: SnapshotCommandAck, session: Session, credentials: Credentials
):
    async with session.begin():
        agent = await authenticate_agent(session, token(credentials))
        return await acknowledge_command(session, agent, command_id, request)


router.include_router(bridge_routes)


@router.put("/sources/{source_id}/approval", dependencies=[Depends(operator)])
async def approve(source_id: int, request: Approval, session: Session):
    try:
        async with session.begin():
            return await MonitoringQueue(session).approve(source_id, request)
    except MonitoringError as error:
        raise as_http(error) from error


@router.post("/agents/register", status_code=201, dependencies=[Depends(operator)])
async def register_agent(request: RegisterAgent, session: Session, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        async with session.begin():
            return await MonitoringQueue(session).register(request)
    except MonitoringError as error:
        raise as_http(error) from error


@router.get("/agents/{agent_id}", dependencies=[Depends(operator)])
async def agent_status(agent_id: UUID, session: Session):
    try:
        return await MonitoringQueue(session).agent_state(agent_id)
    except MonitoringError as error:
        raise as_http(error) from error


@router.delete("/agents/{agent_id}", dependencies=[Depends(operator)])
async def revoke(agent_id: UUID, session: Session):
    try:
        async with session.begin():
            return await MonitoringQueue(session).revoke(agent_id)
    except MonitoringError as error:
        raise as_http(error) from error


@router.get("/agents/{agent_id}/sources", dependencies=[Depends(operator)])
async def agent_sources(
    agent_id: UUID, session: Session, after: SourceCursor = 0, limit: PageLimit = 50
):
    return await MonitoringQueue(session).agent_sources(agent_id, after, limit)


@router.put("/agents/{agent_id}/sources", dependencies=[Depends(operator)])
async def update_agent_sources(agent_id: UUID, request: AgentSourcesUpdate, session: Session):
    async with session.begin():
        return await MonitoringQueue(session).update_agent_sources(agent_id, request)


@router.get("/coverage", dependencies=[Depends(operator)])
async def source_coverage(
    session: Session,
    after: SourceCursor = 0,
    limit: PageLimit = 50,
    only_uncovered: Annotated[bool, Query(alias="onlyUncovered")] = True,
):
    return await coverage(session, after, limit, only_uncovered)


@router.get("/overview", dependencies=[Depends(operator)])
async def monitoring_overview(session: Session):
    return await overview(session)


@router.get("/onboarding/policies", dependencies=[Depends(operator)])
async def onboarding_policies():
    return {
        name: policy.model_dump(mode="json", by_alias=True)
        for name, policy in onboarding_config().policies.items()
    }


@router.post("/onboarding/preview", dependencies=[Depends(operator)])
async def preview_onboarding(request: OnboardingRequest, session: Session):
    return await OnboardingService(session, onboarding_config()).preview(request)


@router.post("/onboarding/runs", status_code=202, dependencies=[Depends(operator)])
async def create_onboarding_run(request: OnboardingRequest, session: Session):
    async with session.begin():
        run = await OnboardingService(session, onboarding_config()).create_run(request)
        return {"runId": run.id, "policy": run.policy_name}


@router.get("/onboarding/runs", dependencies=[Depends(operator)])
async def list_onboarding_runs(
    session: Session,
    limit: PageLimit = 50,
    after: Annotated[UUID | None, Query(alias="afterRunId")] = None,
):
    return await OnboardingService(session, onboarding_config()).list_runs(after, limit)


@router.get("/onboarding/runs/{run_id}", dependencies=[Depends(operator)])
async def onboarding_progress(
    run_id: UUID, session: Session, after: SourceCursor = 0, limit: PageLimit = 50
):
    return await OnboardingService(session, onboarding_config()).progress(run_id, after, limit)


@router.post("/onboarding/runs/{run_id}/retry", status_code=202, dependencies=[Depends(operator)])
async def retry_onboarding(run_id: UUID, session: Session, limit: PageLimit = 50):
    async with session.begin():
        return await OnboardingService(session, onboarding_config()).retry(run_id, limit)


@router.post(
    "/sources/{source_id}/jobs", dependencies=[Depends(operator)], response_model=JobStatus
)
async def request_check(source_id: int, session: Session):
    try:
        async with session.begin():
            return status(await MonitoringQueue(session).create_job(source_id, reason="manual"))
    except MonitoringError as error:
        raise as_http(error) from error


@router.get("/sources/{source_id}/history", dependencies=[Depends(operator)])
async def history(
    source_id: int,
    session: Session,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    summary: bool = False,
):
    response.headers["Cache-Control"] = "no-store"
    if summary:
        return await check_history(session, source_id, offset, limit)
    return await MonitoringQueue(session).history(source_id, offset, limit)


@router.get(
    "/objects", dependencies=[Depends(operator)], response_model=MonitoringPage[ObjectInboxItem]
)
async def get_object_inbox(
    session: Session, response: Response, offset: PageOffset = 0, limit: PageLimit = 20
):
    response.headers["Cache-Control"] = "no-store"
    return await object_inbox(session, offset, limit)


@router.get(
    "/objects/{object_id}/review",
    dependencies=[Depends(operator)],
    response_model=ObjectReviewResponse,
)
async def get_object_review(
    object_id: SourceId,
    session: Session,
    response: Response,
    offset: PageOffset = 0,
    limit: PageLimit = 20,
    task_id: Annotated[int | None, Query(alias="taskId", ge=1, le=9223372036854775807)] = None,
):
    response.headers["Cache-Control"] = "no-store"
    return await object_review(session, object_id, offset, limit, task_id=task_id)


@router.get(
    "/object-reviews/{task_id}/history",
    dependencies=[Depends(operator)],
    response_model=MonitoringPage[FindingCapture],
)
async def get_finding_history(
    task_id: SourceId,
    session: Session,
    response: Response,
    offset: PageOffset = 0,
    limit: PageLimit = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return await finding_history(session, task_id, offset, limit)


@router.get("/attention/sources", dependencies=[Depends(operator)])
async def get_attention_sources(
    session: Session,
    response: Response,
    search: Annotated[str, Query(max_length=2048)] = "",
    issue: AttentionIssue | None = None,
    sort: AttentionSort = "priority",
    include_all: Annotated[bool, Query(alias="includeAll")] = False,
    offset: PageOffset = 0,
    limit: PageLimit = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return await attention_sources(
        session,
        search=search,
        issue=issue,
        sort=sort,
        include_all=include_all,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/sources/{source_id}/review",
    dependencies=[Depends(operator)],
    response_model=SourceReviewResponse,
    response_model_exclude_unset=True,
)
async def get_source_review(
    source_id: SourceId,
    session: Session,
    response: Response,
    check_id: Annotated[UUID | None, Query(alias="checkId")] = None,
    tasks_offset: Annotated[int, Query(alias="tasksOffset", ge=0, le=2147483647)] = 0,
    tasks_limit: Annotated[int, Query(alias="tasksLimit", ge=1, le=100)] = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return await source_review(
        session,
        source_id,
        check_id=check_id,
        tasks_offset=tasks_offset,
        tasks_limit=tasks_limit,
    )


@router.get(
    "/sources/{source_id}/review/{check_id}/{selector_uuid}", dependencies=[Depends(operator)]
)
async def get_field_review(
    source_id: SourceId, check_id: UUID, selector_uuid: UUID, session: Session, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    return await field_review(session, source_id, check_id, selector_uuid)


@router.get(
    "/reviews/{task_id}",
    dependencies=[Depends(operator)],
    response_model=EvidenceReviewResponse,
    response_model_exclude_unset=True,
)
async def get_review(task_id: int, session: Session, response: Response):
    try:
        detail = await review_detail(session, task_id)
    except MonitoringError as error:
        raise as_http(error) from error
    response.headers["Cache-Control"] = "no-store"
    return detail


async def agent_operation(
    session, credentials, action, *, job_id=None, payload=None, mode="strict"
):
    # Authentication, ownership, lease validation and mutation share one transaction.
    try:
        async with session.begin():
            agent = await authenticate_agent(session, token(credentials))
            queue = MonitoringQueue(session)
            seen = queue.seen(agent)
            if action == "seen":
                return seen
            if action == "claim":
                return await queue.claim(agent, mode)
            job = await queue.owned(
                job_id, agent, lock=action != "status", lock_source=action == MonitoringQueue.fail
            )
            if action == "status":
                return status(job)
            return await action(queue, job, payload)
    except MonitoringError as error:
        raise as_http(error) from error


@router.post("/agents/heartbeat")
async def agent_heartbeat(session: Session, credentials: Credentials):
    return await agent_operation(session, credentials, "seen")


@router.post(
    "/jobs/claim",
    response_model=ClaimedJob,
    response_model_exclude_unset=True,
    responses={204: {"description": "No job"}},
)
async def claim(session: Session, credentials: Credentials, mode: MonitoringMode = "strict"):
    claimed = await agent_operation(session, credentials, "claim", mode=mode)
    return claimed if claimed is not None else Response(status_code=204)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: UUID, session: Session, credentials: Credentials):
    return await agent_operation(session, credentials, "status", job_id=job_id)


@router.post("/jobs/{job_id}/heartbeat")
async def job_heartbeat(
    job_id: UUID, request: Heartbeat, session: Session, credentials: Credentials
):
    return await agent_operation(
        session,
        credentials,
        MonitoringQueue.heartbeat,
        job_id=job_id,
        payload=request,
    )


@router.post("/jobs/{job_id}/uploads", response_model=UploadURL)
async def upload(job_id: UUID, request: UploadRequest, session: Session, credentials: Credentials):
    return await agent_operation(
        session,
        credentials,
        MonitoringQueue.grant_upload,
        job_id=job_id,
        payload=request,
    )


@router.post("/jobs/{job_id}/archive-uploads", response_model=UploadURL)
async def upload_visual_archive(
    job_id: UUID, request: VisualArchiveUpload, session: Session, credentials: Credentials
):
    return await agent_operation(
        session,
        credentials,
        MonitoringQueue.grant_visual_upload,
        job_id=job_id,
        payload=request,
    )


@router.post("/jobs/{job_id}/full-archive/uploads", response_model=ArchiveObjectTarget)
async def upload_archive_object(
    job_id: UUID, request: ArchiveObjectGrant, session: Session, credentials: Credentials
):
    return await agent_operation(
        session, credentials, MonitoringQueue.grant_archive_object, job_id=job_id, payload=request
    )


@router.post("/jobs/{job_id}/full-archive/seal", response_model=ArchiveObjectTarget)
async def seal_archive_object(
    job_id: UUID, request: ArchiveObjectGrant, session: Session, credentials: Credentials
):
    return await agent_operation(
        session, credentials, MonitoringQueue.seal_archive_object, job_id=job_id, payload=request
    )


@router.post("/jobs/{job_id}/full-archive", response_model=ArchiveSummary)
async def report_full_archive(
    job_id: UUID, request: ArchiveReport, session: Session, credentials: Credentials
):
    return await agent_operation(
        session, credentials, MonitoringQueue.report_archive, job_id=job_id, payload=request
    )


@router.post("/jobs/{job_id}/complete", response_model=JobStatus)
async def complete(job_id: UUID, request: Completion, session: Session, credentials: Credentials):
    return await agent_operation(
        session,
        credentials,
        MonitoringQueue.complete,
        job_id=job_id,
        payload=request,
    )


@router.post("/jobs/{job_id}/fail", response_model=JobStatus)
async def fail(job_id: UUID, request: Failure, session: Session, credentials: Credentials):
    return await agent_operation(
        session,
        credentials,
        MonitoringQueue.fail,
        job_id=job_id,
        payload=request,
    )
