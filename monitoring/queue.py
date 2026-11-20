"""Source scheduling, scoped agents, leases, and verified completion."""

import json
import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select

from extraction.schemas.common import utc_now
from extraction.schemas.selector import Selector, SelectorVersion
from extraction.schemas.selector_tree import validate_selector_evaluation
from extraction.services.selectors import SelectorService
from monitoring.contracts import (
    MAX_SELECTORS,
    REPRESENTATION,
    ClaimedJob,
    JobStatus,
    PinnedSelector,
    UploadURL,
)
from monitoring.models import (
    ACTIVE,
    LEASED,
    PROCESSABLE,
    READY,
    TERMINAL,
    MonitoringAgent,
    MonitoringAgentSource,
    MonitoringJob,
    MonitoringJobSelector,
    MonitoringSource,
    MonitoringUpload,
    SourceCheckRun,
)
from monitoring.report import validate_consensus
from monitoring.security import (
    MonitoringError,
    approve_origins,
    check_origin,
    fingerprint,
    new_token,
    token_digest,
)
from monitoring.storage import storage_from_env
from sources.schemas.models import Source, SourceCheckSchedule, StoredFile

LEASE_SECONDS = 180
UPLOAD_SECONDS = 60
ATTEMPT_LIMIT = 3
PROCESSING_LIMIT = 5


def retry_delay(attempt):
    return timedelta(seconds=min(900, 30 * 2 ** max(0, min(attempt, 6) - 1)))


def status(job):
    return JobStatus(
        job_id=job.id,
        source_id=job.source_id,
        status=job.status,
        attempt_count=job.attempt_count,
        source_snapshot_id=job.source_snapshot_id,
        extraction_run_id=job.extraction_run_id,
        error_code=job.error_code,
    )


def sanitize_diagnostics(node):
    if "diagnostic" in node:
        node["diagnostic"] = node["status"]
    if node["status"] != "success":
        node.pop("rawValue", None)
    for key in ("recipeResults", "partResults", "locatorResults"):
        for child in node.get(key, []):
            sanitize_diagnostics(child)


class MonitoringQueue:
    """All mutations run in the caller's PostgreSQL transaction."""

    def __init__(self, session, storage=None):
        self.session = session
        self.storage = storage
        self.selectors = SelectorService(session)

    @property
    def store(self):
        return self.storage if self.storage is not None else storage_from_env()

    async def _source(self, source_id):
        row = await self.session.get(
            Source, source_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            raise MonitoringError(404, "SOURCE_NOT_FOUND")
        return row

    async def approve(self, source_id, request):
        source = await self._source(source_id)
        policy = await self.session.get(MonitoringSource, source_id)
        if not request.enabled and policy is None:
            return {"sourceId": source_id, "enabled": False, "allowedOrigins": []}
        if request.enabled and (source.type != "HTML" or not source.url):
            raise MonitoringError(422, "HTML_SOURCE_REQUIRED")
        origins = (
            approve_origins(source.url, request.additional_origins)
            if request.enabled
            else policy.origins
        )
        if policy is None:
            policy = MonitoringSource(source_id=source_id, url=source.url, origins=origins)
            self.session.add(policy)
        elif not request.enabled or policy.url != source.url or policy.origins != origins:
            jobs = await self.session.scalars(
                select(MonitoringJob)
                .where(MonitoringJob.source_id == source_id, MonitoringJob.status.in_(ACTIVE))
                .with_for_update()
            )
            for job in jobs:
                self._finish(job, "cancelled", "APPROVAL_CHANGED")
        policy.enabled = request.enabled
        policy.origins = origins
        if request.enabled:
            policy.url = source.url
        policy.approved_at = utc_now()
        await self.session.flush()
        return {"sourceId": source_id, "enabled": policy.enabled, "allowedOrigins": policy.origins}

    async def register(self, request):
        ids = set(request.source_ids)
        permitted = set(
            await self.session.scalars(
                select(MonitoringSource.source_id).where(
                    MonitoringSource.source_id.in_(ids), MonitoringSource.enabled.is_(True)
                )
            )
        )
        if permitted != ids:
            raise MonitoringError(422, "SOURCE_APPROVAL_REQUIRED")
        token = new_token()
        agent = MonitoringAgent(name=request.name, token_digest=token_digest(token))
        self.session.add(agent)
        await self.session.flush()
        self.session.add_all(
            [
                MonitoringAgentSource(agent_id=agent.id, source_id=source_id)
                for source_id in sorted(ids)
            ]
        )
        return {"agentId": agent.id, "agentToken": token, "sourceIds": sorted(ids)}

    async def revoke(self, agent_id):
        agent = await self.session.get(MonitoringAgent, agent_id, with_for_update=True)
        if agent is None:
            raise MonitoringError(404, "AGENT_NOT_FOUND")
        agent.enabled = False
        rows = await self.session.scalars(
            select(MonitoringJob)
            .where(MonitoringJob.agent_id == agent_id, MonitoringJob.status.in_(LEASED))
            .with_for_update()
        )
        for job in rows:
            await self._retry(job, "AGENT_REVOKED")
        return {"agentId": agent.id, "enabled": False}

    @staticmethod
    def seen(agent):
        agent.last_seen_at = utc_now()
        return {"agentId": agent.id, "lastSeenAt": agent.last_seen_at}

    async def agent_state(self, agent_id):
        agent = await self.session.get(MonitoringAgent, agent_id)
        if agent is None:
            raise MonitoringError(404, "AGENT_NOT_FOUND")
        return {
            "agentId": agent.id,
            "name": agent.name,
            "enabled": agent.enabled,
            "lastSeenAt": agent.last_seen_at,
            "connected": bool(
                agent.enabled
                and agent.last_seen_at
                and (utc_now() - agent.last_seen_at < timedelta(seconds=LEASE_SECONDS))
            ),
        }

    async def create_job(self, source_id, reason="scheduled", flow_run_id=None):
        source = await self._source(source_id)
        policy = await self.session.get(MonitoringSource, source_id)
        self._check_policy(source, policy)
        existing = await self.session.scalar(
            select(MonitoringJob).where(
                MonitoringJob.source_id == source_id, MonitoringJob.status.in_(ACTIVE)
            )
        )
        if existing is not None:
            return existing
        job = MonitoringJob(
            source_id=source_id, url=source.url, origins=policy.origins, reason=reason
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(SourceCheckRun(job_id=job.id, scheduling_flow_run_id=flow_run_id))
        return job

    @staticmethod
    def _check_policy(source, policy, job=None):
        if (
            source is None
            or policy is None
            or not policy.enabled
            or source.state != "ACTIVE"
            or source.type != "HTML"
            or source.url != policy.url
            or (job is not None and (job.url != policy.url or job.origins != policy.origins))
        ):
            raise MonitoringError(409, "SOURCE_NOT_APPROVED_OR_ACTIVE")
        check_origin(policy.url, policy.origins)

    async def schedule_due(self, flow_run_id=None, limit=100):
        now = utc_now()
        active = (
            select(MonitoringJob.id)
            .where(MonitoringJob.source_id == Source.id, MonitoringJob.status.in_(ACTIVE))
            .exists()
        )
        source_ids = list(
            await self.session.scalars(
                select(Source.id)
                .join(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
                .join(MonitoringSource, MonitoringSource.source_id == Source.id)
                .where(
                    Source.state == "ACTIVE",
                    Source.type == "HTML",
                    MonitoringSource.enabled.is_(True),
                    MonitoringSource.url == Source.url,
                    SourceCheckSchedule.enabled.is_(True),
                    or_(
                        SourceCheckSchedule.next_check_at.is_(None),
                        SourceCheckSchedule.next_check_at <= now,
                    ),
                    ~active,
                )
                .order_by(SourceCheckSchedule.next_check_at.nulls_first(), Source.id)
                .limit(limit)
                .with_for_update(of=Source, skip_locked=True)
            )
        )
        return [
            await self.create_job(source_id, flow_run_id=flow_run_id) for source_id in source_ids
        ]

    @staticmethod
    def _finish(job, state, error_code=None):
        job.status = state
        job.error_code = error_code
        job.completed_at = utc_now()

    async def _retry(self, job, code):
        job.error_code = code
        job.lease_expires_at = None
        if job.attempt_count < ATTEMPT_LIMIT:
            job.status = "retry_pending"
            job.available_at = utc_now() + retry_delay(job.attempt_count)
        else:
            self._finish(job, "failed", code)
            schedule = await self.session.get(SourceCheckSchedule, job.source_id)
            if schedule is not None:
                schedule.next_check_at = utc_now() + timedelta(seconds=schedule.interval_seconds)

    async def expire_leases(self, limit=100):
        rows = list(
            await self.session.scalars(
                select(MonitoringJob)
                .where(
                    MonitoringJob.status.in_(LEASED), MonitoringJob.lease_expires_at <= utc_now()
                )
                .order_by(MonitoringJob.lease_expires_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for job in rows:
            await self._retry(job, "LEASE_EXPIRED")
        return len(rows)

    async def cancel_stale(self, limit=100):
        rows = list(
            await self.session.scalars(
                select(MonitoringJob)
                .join(MonitoringSource, MonitoringSource.source_id == MonitoringJob.source_id)
                .join(Source, Source.id == MonitoringJob.source_id)
                .where(
                    MonitoringJob.status.in_(ACTIVE),
                    or_(
                        Source.state != "ACTIVE",
                        Source.type != "HTML",
                        Source.url.is_distinct_from(MonitoringJob.url),
                        MonitoringSource.enabled.is_(False),
                        MonitoringSource.url != MonitoringJob.url,
                        MonitoringSource.origins != MonitoringJob.origins,
                    ),
                )
                .order_by(MonitoringJob.created_at)
                .limit(limit)
                .with_for_update(of=MonitoringJob, skip_locked=True)
            )
        )
        for job in rows:
            self._finish(job, "cancelled", "SOURCE_NOT_APPROVED_OR_ACTIVE")
        return len(rows)

    async def _pins(self, job):
        return list(
            (
                await self.session.execute(
                    select(MonitoringJobSelector, SelectorVersion, Selector)
                    .join(SelectorVersion, SelectorVersion.id == MonitoringJobSelector.version_id)
                    .join(Selector, Selector.id == MonitoringJobSelector.selector_id)
                    .where(MonitoringJobSelector.job_id == job.id)
                    .order_by(Selector.id)
                )
            ).all()
        )

    async def definition(self, version, selector):
        return (await self.selectors.definition(version, selector.uuid)).model_copy(
            update={"status": "active"}
        )

    async def claim(self, agent):
        now = utc_now()
        job = await self.session.scalar(
            select(MonitoringJob)
            .join(MonitoringAgentSource, MonitoringAgentSource.source_id == MonitoringJob.source_id)
            .join(MonitoringSource, MonitoringSource.source_id == MonitoringJob.source_id)
            .join(Source, Source.id == MonitoringJob.source_id)
            .where(
                MonitoringAgentSource.agent_id == agent.id,
                MonitoringJob.status.in_(READY),
                MonitoringJob.available_at <= now,
                MonitoringSource.enabled.is_(True),
                Source.state == "ACTIVE",
                Source.url == MonitoringJob.url,
                MonitoringSource.url == MonitoringJob.url,
                MonitoringSource.origins == MonitoringJob.origins,
            )
            .order_by(MonitoringJob.available_at, MonitoringJob.created_at)
            .limit(1)
            .with_for_update(of=MonitoringJob, skip_locked=True)
        )
        if job is None:
            return None

        pinned = await self._pins(job)
        definitions = []
        if job.attempt_count == 0:
            rows = list(
                (
                    await self.session.execute(
                        select(Selector, SelectorVersion)
                        .join(SelectorVersion, SelectorVersion.id == Selector.active_version_id)
                        .where(
                            Selector.source_id == job.source_id, SelectorVersion.status == "active"
                        )
                        .order_by(Selector.id)
                        .limit(MAX_SELECTORS + 1)
                        .with_for_update(of=Selector, read=True)
                    )
                ).all()
            )
            if len(rows) > MAX_SELECTORS:
                self._finish(job, "failed", "TOO_MANY_SELECTORS")
                schedule = await self.session.get(SourceCheckSchedule, job.source_id)
                if schedule is not None:
                    schedule.next_check_at = now + timedelta(seconds=schedule.interval_seconds)
                return None
            for selector, version in rows:
                definition = await self.definition(version, selector)
                pin = MonitoringJobSelector(
                    job_id=job.id,
                    selector_id=selector.id,
                    version_id=version.id,
                    fingerprint=fingerprint(definition.portable()),
                )
                self.session.add(pin)
                pinned.append((pin, version, selector))

        for pin, version, selector in pinned:
            definition = await self.definition(version, selector)
            definitions.append(
                PinnedSelector(
                    selector_uuid=selector.uuid,
                    version_uuid=version.uuid,
                    version_no=version.version_no,
                    definition_fingerprint=pin.fingerprint,
                    definition=definition,
                )
            )
        job.status = "claimed"
        job.claimed_at = now
        job.attempt_count += 1
        job.agent_id = agent.id
        job.lease_id = uuid4()
        job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        job.error_code = None
        return ClaimedJob(
            job_id=job.id,
            source_id=job.source_id,
            url=job.url,
            reason=job.reason,
            allowed_origins=job.origins,
            lease_id=job.lease_id,
            lease_expires_at=job.lease_expires_at,
            representation=REPRESENTATION,
            selectors=definitions,
        )

    async def owned(self, job_id, agent, *, lock=True):
        query = (
            select(MonitoringJob)
            .join(MonitoringAgentSource, MonitoringAgentSource.source_id == MonitoringJob.source_id)
            .where(
                MonitoringJob.id == job_id,
                MonitoringJob.agent_id == agent.id,
                MonitoringAgentSource.agent_id == agent.id,
            )
        )
        if lock:
            query = query.with_for_update(of=MonitoringJob)
        job = await self.session.scalar(query)
        if job is None:
            raise MonitoringError(404, "JOB_NOT_FOUND")
        return job

    async def _lease(self, job, lease_id):
        if (
            job.status not in LEASED
            or job.lease_id != lease_id
            or job.lease_expires_at is None
            or job.lease_expires_at <= utc_now()
        ):
            raise MonitoringError(409, "LEASE_LOST")
        source = await self.session.get(Source, job.source_id)
        policy = await self.session.get(MonitoringSource, job.source_id)
        self._check_policy(source, policy, job)

    async def heartbeat(self, job, request):
        await self._lease(job, request.lease_id)
        if request.phase == "capturing" and job.status == "claimed":
            job.status = "capturing"
        job.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
        return {"leaseExpiresAt": job.lease_expires_at, "status": job.status}

    async def grant_upload(self, job, request):
        await self._lease(job, request.lease_id)
        now = utc_now()
        ttl = min(UPLOAD_SECONDS, math.floor((job.lease_expires_at - now).total_seconds()))
        if ttl <= 0:
            raise MonitoringError(409, "LEASE_LOST")
        intent = await self.session.scalar(
            select(MonitoringUpload)
            .where(MonitoringUpload.job_id == job.id, MonitoringUpload.lease_id == job.lease_id)
            .with_for_update()
        )
        if intent is None:
            intent = MonitoringUpload(
                job_id=job.id,
                lease_id=job.lease_id,
                storage_key=f"monitoring/pending/{uuid4()}",
                content_hash=request.content_hash,
                content_size=request.content_size,
                expires_at=now + timedelta(seconds=ttl),
            )
            self.session.add(intent)
            await self.session.flush()
        if (intent.content_size, intent.content_hash) != (
            request.content_size,
            request.content_hash,
        ):
            raise MonitoringError(409, "UPLOAD_INTENT_CONFLICT")
        intent.expires_at = max(intent.expires_at, now + timedelta(seconds=ttl + 1))
        job.status = "uploading"
        url = self.store.presign(intent.storage_key, ttl, intent.content_size)
        return UploadURL(
            upload_intent_id=intent.id, url=url, expires_at=now + timedelta(seconds=ttl)
        )

    async def complete(self, job, request):
        supplied = request.portable()
        digest = fingerprint(supplied)
        if job.completion_key is not None:
            if job.completion_key != request.completion_key or job.completion_digest != digest:
                raise MonitoringError(409, "COMPLETION_CONFLICT")
            return status(job)
        await self._lease(job, request.lease_id)
        intent = await self.session.get(
            MonitoringUpload, request.upload_intent_id, with_for_update=True
        )
        if (
            intent is None
            or intent.job_id != job.id
            or intent.lease_id != job.lease_id
            or intent.cleaned_at is not None
        ):
            raise MonitoringError(404, "UPLOAD_INTENT_NOT_FOUND")
        if (intent.content_hash, intent.content_size) != (
            request.content_hash,
            request.content_size,
        ):
            raise MonitoringError(422, "UPLOAD_METADATA_MISMATCH")
        check_origin(request.page_url, job.origins)
        now = utc_now()
        if request.captured_at > now + timedelta(minutes=5) or (
            request.captured_at < job.claimed_at - timedelta(minutes=5)
        ):
            raise MonitoringError(422, "CAPTURE_TIME_OUTSIDE_ATTEMPT")

        reports = {item.result.selector_version_uuid: item for item in request.evaluations}
        pins = await self._pins(job)
        if len(reports) != len(request.evaluations) or reports.keys() != {
            version.uuid for _, version, _ in pins
        }:
            raise MonitoringError(422, "EVALUATION_SET_MISMATCH")
        for pin, version, selector in pins:
            report = reports[version.uuid]
            definition = await self.definition(version, selector)
            if (
                report.definition_fingerprint != pin.fingerprint
                or fingerprint(definition.portable()) != pin.fingerprint
            ):
                raise MonitoringError(422, "EVALUATION_FINGERPRINT_MISMATCH")
            try:
                validate_selector_evaluation(report.result, definition)
                validate_consensus(report.result, definition)
            except ValueError as error:
                raise MonitoringError(422, "INVALID_EVALUATION") from error
        for item in supplied["evaluations"]:
            sanitize_diagnostics(item["result"])
        if len(json.dumps(supplied).encode()) > 8 * 1024 * 1024:
            raise MonitoringError(422, "EVALUATIONS_TOO_LARGE")

        sealed_key = f"monitoring/snapshots/{intent.id}/{intent.content_hash}.html"
        await self.store.seal(
            intent.storage_key, sealed_key, intent.content_size, intent.content_hash
        )
        intent.sealed_key = sealed_key
        job.completion_key = request.completion_key
        job.completion_digest = digest
        job.completion_json = supplied
        job.status = "uploaded"
        job.available_at = utc_now()
        return status(job)

    async def fail(self, job, request):
        await self._lease(job, request.lease_id)
        await self._retry(job, request.code)
        return status(job)

    async def processable(self, limit=50):
        return (
            await self.session.execute(
                select(MonitoringJob.id, SourceCheckRun.processing_flow_run_id)
                .join(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
                .where(
                    MonitoringJob.status.in_(PROCESSABLE), MonitoringJob.available_at <= utc_now()
                )
                .order_by(MonitoringJob.available_at)
                .limit(limit)
            )
        ).all()

    async def cleanup_uploads(self, limit=50):
        rows = list(
            (
                await self.session.execute(
                    select(MonitoringUpload, MonitoringJob)
                    .join(MonitoringJob, MonitoringJob.id == MonitoringUpload.job_id)
                    .where(
                        MonitoringUpload.cleaned_at.is_(None),
                        MonitoringUpload.expires_at < utc_now(),
                        or_(
                            MonitoringJob.status.in_(TERMINAL),
                            MonitoringJob.lease_id != MonitoringUpload.lease_id,
                            MonitoringJob.status.in_(READY),
                        ),
                    )
                    .order_by(MonitoringUpload.expires_at)
                    .limit(limit)
                    .with_for_update(of=MonitoringUpload, skip_locked=True)
                )
            ).all()
        )
        for intent, _ in rows:
            await self.store.delete(intent.storage_key)
            # The deterministic seal key also covers a crash between S3 and DB commit.
            key = (
                intent.sealed_key or f"monitoring/snapshots/{intent.id}/{intent.content_hash}.html"
            )
            registered = await self.session.scalar(
                select(StoredFile.id).where(StoredFile.storage_key == key)
            )
            if registered is None:
                await self.store.delete(key)
            intent.cleaned_at = utc_now()
        return len(rows)

    async def history(self, source_id, offset, limit):
        return [
            {
                **status(job).portable(),
                "reason": job.reason,
                "createdAt": job.created_at,
                "agentId": job.agent_id,
                "claimedAt": job.claimed_at,
                "completedAt": job.completed_at,
                "acquiredAt": check.acquired_at,
                "processedAt": check.processed_at,
                "changeStatus": check.change_status,
                "capturedAt": (job.completion_json or {}).get("capturedAt"),
                "schedulingFlowRunId": check.scheduling_flow_run_id,
                "processingFlowRunId": check.processing_flow_run_id,
                "fields": check.field_results or [],
            }
            for job, check in (
                await self.session.execute(
                    select(MonitoringJob, SourceCheckRun)
                    .join(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
                    .where(MonitoringJob.source_id == source_id)
                    .order_by(MonitoringJob.created_at.desc(), MonitoringJob.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        ]
