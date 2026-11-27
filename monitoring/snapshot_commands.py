"""One expiring operator command delivers one archived capture to one Firefox agent."""

import re
from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from extraction.schemas.common import utc_now
from monitoring.archives import blob_key, manifest_key
from monitoring.contracts import (
    MAX_BYTES,
    MAX_VISUAL_ARCHIVE_BYTES,
    MIME_TYPE,
    ClaimedSnapshotCommand,
    SnapshotAgentChoice,
    SnapshotCommandResponse,
    SnapshotSelectorContext,
)
from monitoring.enrollment import approval_matches, trusted_enrollment_matches
from monitoring.models import (
    MonitoringAgent,
    MonitoringAgentSource,
    MonitoringArchiveUpload,
    MonitoringJob,
    MonitoringSource,
    MonitoringVisualArchive,
    SnapshotOpenCommand,
)
from monitoring.onboarding_config import onboarding_config
from monitoring.security import MonitoringError
from monitoring.snapshot_config import FULL_ARCHIVE_VERSION
from monitoring.snapshots import snapshot_record
from monitoring.workspace import field_review
from sources.schemas.models import Source, SourceSnapshot, StoredFile

COMMAND_TTL = timedelta(seconds=90)
FULL_COMMAND_TTL = timedelta(minutes=5)
PRESENCE_TTL = timedelta(seconds=45)
PRESENCE_UPDATE = timedelta(seconds=10)
ACTIVE_COMMANDS = ("pending", "claimed")


def source_scope(agent_id, trusted):
    grant = (
        select(MonitoringAgentSource.source_id)
        .where(
            MonitoringAgentSource.agent_id == agent_id,
            MonitoringAgentSource.source_id == Source.id,
            MonitoringAgentSource.enabled.is_(True),
        )
        .correlate(Source, MonitoringAgent)
        .exists()
    )
    strict = and_(grant, *approval_matches())
    config = onboarding_config()
    if config.mode == "trusted":
        return or_(strict, and_(trusted, *trusted_enrollment_matches(config.trusted_allow_http)))
    return strict


async def assert_source_scope(session, agent, source_id):
    if not await session.scalar(
        select(Source.id)
        .join(MonitoringSource, MonitoringSource.source_id == Source.id)
        .where(Source.id == source_id, source_scope(agent.id, agent.trusted))
    ):
        raise MonitoringError(403, "SNAPSHOT_SOURCE_FORBIDDEN")


async def available_agents(session, source_id):
    return (
        await session.scalars(
            select(MonitoringAgent)
            .join(Source, Source.id == source_id)
            .join(MonitoringSource, MonitoringSource.source_id == Source.id)
            .where(
                MonitoringAgent.enabled.is_(True),
                MonitoringAgent.snapshot_seen_at >= utc_now() - PRESENCE_TTL,
                source_scope(MonitoringAgent.id, MonitoringAgent.trusted.is_(True)),
            )
            .order_by(MonitoringAgent.name, MonitoringAgent.id)
        )
    ).all()


async def agent_choices(session, source_id):
    return [
        SnapshotAgentChoice(agent_id=agent.id, name=agent.name)
        for agent in await available_agents(session, source_id)
    ]


def response(command):
    return SnapshotCommandResponse(
        command_id=command.id,
        source_id=command.source_id,
        snapshot_id=command.snapshot_id,
        target_agent_id=command.target_agent_id,
        created_at=command.created_at,
        expires_at=command.expires_at,
        state=command.state,
        error_code=command.error_code,
    )


def expire(command):
    if command.state in ACTIVE_COMMANDS and command.expires_at <= utc_now():
        command.state = "expired"


async def command_row(session, command_id, *, agent_id=None, lock=True):
    query = select(SnapshotOpenCommand).where(SnapshotOpenCommand.id == command_id)
    if agent_id is not None:
        query = query.where(SnapshotOpenCommand.target_agent_id == agent_id)
    if lock:
        query = query.with_for_update()
    command = await session.scalar(query)
    if command is None:
        raise MonitoringError(404, "SNAPSHOT_COMMAND_NOT_FOUND")
    if lock:
        expire(command)
    return command


def repeat(command, request, context):
    if (
        command.source_id != request.source_id
        or command.snapshot_id != request.snapshot_id
        or command.selector_context != context
        or command.check_id != request.check_id
        or request.target_agent_id not in (None, command.target_agent_id)
    ):
        raise MonitoringError(409, "SNAPSHOT_COMMAND_CONFLICT")
    expire(command)
    return response(command)


def verified_digest(file, *, max_bytes=MAX_BYTES):
    if file is None:
        raise MonitoringError(404, "SNAPSHOT_ARTIFACT_NOT_FOUND")
    if file.mime_type.partition(";")[0].strip().lower() != MIME_TYPE:
        raise MonitoringError(415, "SNAPSHOT_NOT_HTML")
    if file.size_bytes is not None and file.size_bytes > max_bytes:
        raise MonitoringError(413, "SNAPSHOT_TOO_LARGE")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", file.sha256 or ""):
        raise MonitoringError(422, "SNAPSHOT_DIGEST_UNAVAILABLE")
    return file.sha256.lower()


async def selector_details(session, source_id, snapshot_id, context):
    if context is None:
        return None, None
    check_id = await session.scalar(
        select(MonitoringJob.id).where(
            MonitoringJob.source_id == source_id,
            MonitoringJob.source_snapshot_id == snapshot_id,
            MonitoringJob.extraction_run_id == context.extraction_run_id,
            MonitoringJob.status == "completed",
        )
    )
    if check_id is None:
        raise MonitoringError(422, "SNAPSHOT_SELECTOR_CONTEXT_INVALID")
    result = await field_review(session, source_id, check_id, context.selector_uuid)
    selector = result["selector"]
    if selector is None or str(selector["version"]["uuid"]) != str(context.selector_version_uuid):
        raise MonitoringError(422, "SNAPSHOT_SELECTOR_CONTEXT_INVALID")
    return selector, result["evaluation"]


async def create_command(session, request):
    context = request.selector_context.portable() if request.selector_context else None
    existing = await session.get(SnapshotOpenCommand, request.request_id, with_for_update=True)
    if existing is not None:
        return repeat(existing, request, context)

    _, file = await snapshot_record(session, request.source_id, request.snapshot_id)
    verified_digest(file)
    agents = await available_agents(session, request.source_id)
    if request.target_agent_id is None and len(agents) > 1:
        raise MonitoringError(409, "SNAPSHOT_AGENT_REQUIRED")
    agent = next((row for row in agents if request.target_agent_id in (None, row.id)), None)
    if agent is None:
        raise MonitoringError(409, "SNAPSHOT_AGENT_OFFLINE")
    await selector_details(
        session, request.source_id, request.snapshot_id, request.selector_context
    )
    check = await archive_check(
        session, request.source_id, request.snapshot_id, request.check_id, context
    )
    if request.check_id is not None and check is None:
        raise MonitoringError(422, "SNAPSHOT_CHECK_MISMATCH")

    now = utc_now()
    command = await session.scalar(
        insert(SnapshotOpenCommand)
        .values(
            id=request.request_id,
            source_id=request.source_id,
            snapshot_id=request.snapshot_id,
            target_agent_id=agent.id,
            created_at=now,
            expires_at=now + (FULL_COMMAND_TTL if full_manifest(check) else COMMAND_TTL),
            state="pending",
            selector_context=context,
            check_id=request.check_id,
        )
        .on_conflict_do_nothing(index_elements=[SnapshotOpenCommand.id])
        .returning(SnapshotOpenCommand)
    )
    if command is None:
        return repeat(await command_row(session, request.request_id), request, context)
    return response(command)


async def archive_check(
    session, source_id, snapshot_id, check_id=None, selector_context=None, *, before=None
):
    query = select(MonitoringJob).where(
        MonitoringJob.source_id == source_id,
        MonitoringJob.source_snapshot_id == snapshot_id,
        MonitoringJob.status.in_(("completed", "failed"))
        if check_id is not None
        else MonitoringJob.status == "completed",
    )
    if check_id is not None:
        query = query.where(MonitoringJob.id == check_id)
    if selector_context is not None:
        query = query.where(MonitoringJob.extraction_run_id == selector_context["extractionRunId"])
    if check_id is None and selector_context is None:
        query = query.where(
            MonitoringJob.archive_result["status"].as_string().in_(("stored", "partial"))
        )
    if before is not None:
        query = query.where(MonitoringJob.completed_at <= before)
    return await session.scalar(
        query.order_by(MonitoringJob.completed_at.desc(), MonitoringJob.id.desc()).limit(1)
    )


def full_manifest(job):
    return job and job.archive_result and job.archive_result.get("status") in {"stored", "partial"}


async def claim_command(session, agent):
    now = utc_now()
    if not agent.snapshot_seen_at or agent.snapshot_seen_at < now - PRESENCE_UPDATE:
        agent.snapshot_seen_at = now
    row = (
        await session.execute(
            select(SnapshotOpenCommand, SourceSnapshot, Source.url)
            .join(Source, Source.id == SnapshotOpenCommand.source_id)
            .join(MonitoringSource, MonitoringSource.source_id == Source.id)
            .join(SourceSnapshot, SourceSnapshot.id == SnapshotOpenCommand.snapshot_id)
            .where(
                SnapshotOpenCommand.target_agent_id == agent.id,
                SnapshotOpenCommand.state.in_(ACTIVE_COMMANDS),
                SnapshotOpenCommand.expires_at > now,
                SourceSnapshot.source_id == Source.id,
                source_scope(agent.id, agent.trusted),
            )
            .order_by(
                (SnapshotOpenCommand.state == "claimed").desc(),
                SnapshotOpenCommand.created_at,
                SnapshotOpenCommand.id,
            )
            .limit(1)
            .with_for_update(of=SnapshotOpenCommand)
        )
    ).one_or_none()
    if row is None:
        return None
    command, snapshot, source_url = row
    command.state = "claimed"
    context = (
        SnapshotSelectorContext.model_validate(command.selector_context)
        if command.selector_context is not None
        else None
    )
    try:
        selector, evaluation = await selector_details(
            session, command.source_id, command.snapshot_id, context
        )
    except MonitoringError:
        selector, evaluation = None, None  # The snapshot remains available if a pin was removed.
    check = await archive_check(
        session,
        command.source_id,
        command.snapshot_id,
        command.check_id,
        command.selector_context,
        before=command.created_at,
    )
    return ClaimedSnapshotCommand(
        **response(command).model_dump(),
        source_url=snapshot.page_url or source_url,
        captured_at=snapshot.fetched_at,
        selector_context=context,
        selector=selector,
        evaluation=evaluation,
        archive_version=FULL_ARCHIVE_VERSION if full_manifest(check) else None,
    )


async def authorized_command(session, agent, command_id):
    command = await command_row(session, command_id, agent_id=agent.id, lock=False)
    if command.expires_at <= utc_now():
        raise MonitoringError(410, "SNAPSHOT_COMMAND_EXPIRED")
    if command.state != "claimed":
        raise MonitoringError(409, "SNAPSHOT_COMMAND_NOT_CLAIMED")
    await assert_source_scope(session, agent, command.source_id)
    return command


async def command_archive_object(session, agent, command_id, digest=None):
    command = await authorized_command(session, agent, command_id)
    job = await archive_check(
        session,
        command.source_id,
        command.snapshot_id,
        command.check_id,
        command.selector_context,
        before=command.created_at,
    )
    if not full_manifest(job):
        raise MonitoringError(404, "SNAPSHOT_ARCHIVE_UNAVAILABLE")
    if digest is None:
        archive = job.archive_result
        return (
            manifest_key(job),
            archive["manifestSizeBytes"],
            archive["manifestSha256"],
            command.expires_at,
        )
    upload = await session.get(MonitoringArchiveUpload, (job.id, job.lease_id, digest))
    if upload is None or not upload.included or not upload.sealed:
        raise MonitoringError(404, "SNAPSHOT_ARCHIVE_UNAVAILABLE")
    return blob_key(digest), upload.size_bytes, digest, command.expires_at


async def command_artifact(session, agent, command_id, *, prefer_visual=False):
    command = await authorized_command(session, agent, command_id)
    _, file = await snapshot_record(session, command.source_id, command.snapshot_id)
    if prefer_visual and (command.check_id or command.selector_context):
        check = await archive_check(
            session,
            command.source_id,
            command.snapshot_id,
            command.check_id,
            command.selector_context,
        )
        prefer_visual = check is None or check.snapshot_policy is None
    if prefer_visual:
        archive = await session.scalar(
            select(StoredFile)
            .join(MonitoringVisualArchive, MonitoringVisualArchive.file_id == StoredFile.id)
            .where(MonitoringVisualArchive.snapshot_id == command.snapshot_id)
        )
        if archive is not None:
            digest = verified_digest(archive, max_bytes=MAX_VISUAL_ARCHIVE_BYTES)
            return archive, digest, command.expires_at, True
    return file, verified_digest(file), command.expires_at, False


async def acknowledge_command(session, agent, command_id, ack):
    command = await command_row(session, command_id, agent_id=agent.id)
    if command.state == ack.state and command.error_code == ack.error_code:
        return response(command)
    if command.state == "expired":
        raise MonitoringError(410, "SNAPSHOT_COMMAND_EXPIRED")
    if command.state != "claimed":
        raise MonitoringError(409, "SNAPSHOT_COMMAND_NOT_CLAIMED")
    if ack.state == "opened":
        await assert_source_scope(session, agent, command.source_id)
    command.state = ack.state
    command.error_code = ack.error_code
    return response(command)
