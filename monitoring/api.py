"""The operator enrolls agents. Source-scoped agents poll and report under a lease."""

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring.contracts import (
    AgentSourcesUpdate,
    Approval,
    ClaimedJob,
    Completion,
    Failure,
    Heartbeat,
    JobStatus,
    RegisterAgent,
    UploadRequest,
    UploadURL,
)
from monitoring.diagnostics import coverage, overview
from monitoring.onboarding import OnboardingRequest, OnboardingService
from monitoring.onboarding_config import onboarding_config
from monitoring.queue import MonitoringQueue, status
from monitoring.review import review_detail
from monitoring.security import MonitoringError, authenticate_agent, authorize_admin
from shared.database import get_session


class MonitoringRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method in {"POST", "PUT"}:
                body = bytearray()
                limit = 8 * 1024 * 1024 if request.url.path.endswith("/complete") else 32 * 1024
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


router = APIRouter(prefix="/monitoring", tags=["monitoring"], route_class=MonitoringRoute)
bearer = HTTPBearer(auto_error=False)
Session = Annotated[AsyncSession, Depends(get_session)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
SourceCursor = Annotated[int, Query(alias="afterSourceId", ge=0, le=9223372036854775807)]
PageLimit = Annotated[int, Query(ge=1, le=100)]


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
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await MonitoringQueue(session).history(source_id, offset, limit)


@router.get("/reviews/{task_id}", dependencies=[Depends(operator)])
async def get_review(task_id: int, session: Session):
    try:
        return await review_detail(session, task_id)
    except MonitoringError as error:
        raise as_http(error) from error


async def agent_operation(session, credentials, action, *, job_id=None, payload=None):
    # Authentication, ownership, lease validation and mutation share one transaction.
    try:
        async with session.begin():
            agent = await authenticate_agent(session, token(credentials))
            queue = MonitoringQueue(session)
            seen = queue.seen(agent)
            if action == "seen":
                return seen
            if action == "claim":
                return await queue.claim(agent)
            job = await queue.owned(job_id, agent, lock=action != "status")
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
async def claim(session: Session, credentials: Credentials):
    claimed = await agent_operation(session, credentials, "claim")
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
