"""Source scheduling, scoped agents, leases, and verified completion."""

import json
import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select, tuple_, update

from extraction.schemas.common import utc_now
from extraction.schemas.selector import Selector, SelectorVersion
from extraction.schemas.selector_tree import validate_selector_evaluation
from extraction.services.selectors import SelectorService
from monitoring.contracts import (
    MAX_SELECTORS,
    MAX_VISUAL_ARCHIVE_BYTES,
    REPRESENTATION,
    VISUAL_ARCHIVE_VERSION,
    ClaimedJob,
    JobStatus,
    PinnedSelector,
    TrustedNavigation,
    UploadURL,
)
from monitoring.enrollment import (
    TRUSTED_SOURCE_STATES,
    MonitoringEnrollmentService,
    approval_matches,
    assigned_source,
    authorized_agent,
    grant_agent_sources,
    origin_key,
    trusted_enrollment_matches,
)
from monitoring.models import (
    ACTIVE,
    LEASED,
    PROCESSABLE,
    READY,
    STRICT_NAVIGATION,
    TERMINAL,
    TRUSTED_HTTP,
    TRUSTED_HTTPS,
    MonitoringAgent,
    MonitoringAgentSource,
    MonitoringJob,
    MonitoringJobSelector,
    MonitoringSource,
    MonitoringUpload,
    SourceCheckRun,
)
from monitoring.onboarding_config import onboarding_config
from monitoring.report import validate_consensus
from monitoring.security import (
    MonitoringError,
    approve_origins,
    check_origin,
    fingerprint,
    new_token,
    token_digest,
    trusted_origin,
)
from monitoring.storage import storage_from_env
from sources.schemas.enums import SourceState as State
from sources.schemas.enums import SourceStateTrigger as Trigger
from sources.schemas.enums import SourceType
from sources.schemas.models import Source, SourceCheckSchedule, StoredFile
from sources.services.sources import SourcesService

LEASE_SECONDS = 180
UPLOAD_SECONDS = 60
ATTEMPT_LIMIT = 3
PROCESSING_LIMIT = 5
SCHEDULING_LOCK = 0x42555242  # Burbot's PostgreSQL advisory lock namespace.


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
    # Free-form messages can contain page material. Structured locator errors
    # and bounded candidates have already been validated against the job pin.
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
            if source.type == "HTML" and source.url:
                self.session.add(
                    MonitoringSource(
                        source_id=source_id,
                        url=source.url,
                        origins=[],
                        enabled=False,
                    )
                )
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
                if not request.enabled or job.navigation_policy == STRICT_NAVIGATION:
                    self._finish(job, "cancelled", "APPROVAL_CHANGED")
        policy.enabled = request.enabled
        policy.origins = origins
        if request.enabled:
            policy.url = source.url
        policy.approved_at = utc_now()
        await self.session.flush()
        return {"sourceId": source_id, "enabled": policy.enabled, "allowedOrigins": policy.origins}

    async def register(self, request):
        if request.trusted and onboarding_config().mode != "trusted":
            raise MonitoringError(409, "TRUSTED_MODE_DISABLED")
        ids = set(request.source_ids)
        permitted = set(
            await self.session.scalars(
                select(MonitoringSource.source_id).where(
                    MonitoringSource.source_id.in_(ids),
                    MonitoringSource.enabled.is_(True),
                    MonitoringSource.origins != [],
                )
            )
        )
        if permitted != ids:
            raise MonitoringError(422, "SOURCE_APPROVAL_REQUIRED")
        token = new_token()
        agent = MonitoringAgent(
            name=request.name, token_digest=token_digest(token), trusted=request.trusted
        )
        self.session.add(agent)
        await self.session.flush()
        self.session.add_all(
            [
                MonitoringAgentSource(agent_id=agent.id, source_id=source_id)
                for source_id in sorted(ids)
            ]
        )
        return {
            "agentId": agent.id,
            "agentToken": token,
            "sourceIds": sorted(ids),
            **({"trusted": True} if agent.trusted else {}),
        }

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

    async def agent_sources(self, agent_id, after, limit):
        if await self.session.get(MonitoringAgent, agent_id) is None:
            raise MonitoringError(404, "AGENT_NOT_FOUND")
        rows = list(
            await self.session.scalars(
                select(MonitoringAgentSource)
                .where(
                    MonitoringAgentSource.agent_id == agent_id,
                    MonitoringAgentSource.source_id > after,
                )
                .order_by(MonitoringAgentSource.source_id)
                .limit(limit + 1)
            )
        )
        return {
            "agentId": agent_id,
            "sources": [
                {"sourceId": row.source_id, "enabled": row.enabled} for row in rows[:limit]
            ],
            "nextAfterSourceId": rows[limit - 1].source_id if len(rows) > limit else None,
        }

    async def update_agent_sources(self, agent_id, request):
        agent = await self.session.get(MonitoringAgent, agent_id, with_for_update=True)
        if agent is None:
            raise MonitoringError(404, "AGENT_NOT_FOUND")
        approved = (
            select(Source.id)
            .join(MonitoringSource, MonitoringSource.source_id == Source.id)
            .where(*approval_matches())
        )
        added = sorted(set(request.add_source_ids))
        if added and set(await self.session.scalars(approved.where(Source.id.in_(added)))) != set(
            added
        ):
            raise MonitoringError(422, "SOURCE_APPROVAL_REQUIRED")
        if (added or request.policy) and not agent.enabled:
            raise MonitoringError(409, "AGENT_DISABLED")
        await grant_agent_sources(
            self.session, [(agent_id, source_id) for source_id in added], explicit=True
        )

        removed = sorted(set(request.remove_source_ids))
        if removed:
            await self.session.execute(
                update(MonitoringAgentSource)
                .where(
                    MonitoringAgentSource.agent_id == agent_id,
                    MonitoringAgentSource.source_id.in_(removed),
                )
                .values(enabled=False)
            )
            leased = await self.session.scalars(
                select(MonitoringJob)
                .where(
                    MonitoringJob.agent_id == agent_id,
                    MonitoringJob.source_id.in_(removed),
                    MonitoringJob.navigation_policy == STRICT_NAVIGATION,
                    MonitoringJob.status.in_(LEASED),
                )
                .with_for_update()
            )
            for job in leased:
                await self._retry(job, "AGENT_SCOPE_REVOKED")
        next_id = None
        if request.policy:
            policy = onboarding_config().policy(request.policy)
            rows = list(
                await self.session.scalars(
                    approved.where(
                        Source.id > request.after_source_id,
                        origin_key(Source.url).in_(policy.origins),
                    )
                    .order_by(Source.id)
                    .limit(request.limit + 1)
                )
            )
            await grant_agent_sources(
                self.session, [(agent_id, source_id) for source_id in rows[: request.limit]]
            )
            if len(rows) > request.limit:
                next_id = rows[request.limit - 1]
        return {"agentId": agent_id, "nextAfterSourceId": next_id}

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
            "trusted": agent.trusted,
            "lastSeenAt": agent.last_seen_at,
            "connected": bool(
                agent.enabled
                and agent.last_seen_at
                and (utc_now() - agent.last_seen_at < timedelta(seconds=LEASE_SECONDS))
            ),
        }

    async def create_job(self, source_id, reason="scheduled", flow_run_id=None, *, config=None):
        config = config if config is not None else onboarding_config()
        source = await self._source(source_id)
        navigation = STRICT_NAVIGATION
        if config.mode == "trusted":
            if source.type != SourceType.HTML:
                raise MonitoringError(422, "UNSUPPORTED_SOURCE_TYPE")
            site, _ = await MonitoringEnrollmentService(
                self.session, config.default_schedule
            ).enroll_trusted(source, allow_http=config.trusted_allow_http)
            if site is None:
                raise MonitoringError(409, "SOURCE_NOT_ELIGIBLE")
            # A manual check can be requested before the next enrollment tick.
            await self.session.flush()
            origins = [site]
            navigation = TRUSTED_HTTP if site.startswith("http://") else TRUSTED_HTTPS
        else:
            policy = await self.session.get(MonitoringSource, source_id)
            self._check_policy(source, policy)
            origins = policy.origins
        existing = await self.session.scalar(
            select(MonitoringJob).where(
                MonitoringJob.source_id == source_id, MonitoringJob.status.in_(ACTIVE)
            )
        )
        if existing is not None:
            return existing
        job = MonitoringJob(
            source_id=source_id,
            url=source.url,
            origins=origins,
            navigation_policy=navigation,
            reason=reason,
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(SourceCheckRun(job_id=job.id, scheduling_flow_run_id=flow_run_id))
        return job

    @staticmethod
    def _check_policy(source, policy, job=None):
        if job is not None and job.navigation_policy != STRICT_NAVIGATION:
            if (
                source is None
                or policy is None
                or not policy.enabled
                or source.type != SourceType.HTML
                or source.state not in TRUSTED_SOURCE_STATES
                or source.url != job.url
                or policy.trusted_url != job.url
                or job.origins != [policy.trusted_origin]
                or trusted_origin(job.url, allow_http=job.navigation_policy == TRUSTED_HTTP)
                != policy.trusted_origin
            ):
                raise MonitoringError(409, "SOURCE_NOT_ELIGIBLE")
            return
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

    @staticmethod
    def _job_policy_matches():
        return and_(
            Source.type == SourceType.HTML,
            Source.url.is_not_distinct_from(MonitoringJob.url),
            MonitoringSource.enabled.is_(True),
            or_(
                and_(
                    MonitoringJob.navigation_policy == STRICT_NAVIGATION,
                    Source.state == State.ACTIVE,
                    MonitoringSource.url == MonitoringJob.url,
                    MonitoringSource.origins == MonitoringJob.origins,
                ),
                and_(
                    MonitoringJob.navigation_policy != STRICT_NAVIGATION,
                    Source.state.in_(TRUSTED_SOURCE_STATES),
                    MonitoringSource.trusted_url.is_not_distinct_from(MonitoringJob.url),
                    MonitoringSource.trusted_origin.is_not(None),
                    MonitoringJob.origins
                    == func.jsonb_build_array(MonitoringSource.trusted_origin),
                ),
            ),
        )

    async def schedule_due(self, flow_run_id=None, limit=None, *, config=None):
        config = config if config is not None else onboarding_config()
        if not config.monitoring_enabled:
            return []
        # One automatic admission transaction accounts for shared capacity. The
        # Source lock and partial unique index also cover manual job requests.
        if not await self.session.scalar(
            select(func.pg_try_advisory_xact_lock(SCHEDULING_LOCK, 1))
        ):
            return []
        now = utc_now()
        active_count = await self.session.scalar(
            select(func.count()).select_from(MonitoringJob).where(MonitoringJob.status.in_(ACTIVE))
        )
        requested = config.job_batch_size if limit is None else limit
        batch = min(requested, config.job_batch_size, config.max_active_jobs - active_count)
        if batch <= 0:
            return []
        active = (
            select(MonitoringJob.id)
            .where(MonitoringJob.source_id == Source.id, MonitoringJob.status.in_(ACTIVE))
            .exists()
        )
        due_at = func.coalesce(SourceCheckSchedule.next_check_at, SourceCheckSchedule.created_at)
        trusted = config.mode == "trusted"
        eligible = (
            trusted_enrollment_matches(config.trusted_allow_http)
            if trusted
            else (Source.state == State.ACTIVE, *approval_matches())
        )
        candidates = (
            select(Source.id.label("source_id"))
            .join(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
            .join(MonitoringSource, MonitoringSource.source_id == Source.id)
            .where(
                *eligible,
                SourceCheckSchedule.enabled.is_(True),
                or_(
                    SourceCheckSchedule.next_check_at.is_(None),
                    SourceCheckSchedule.next_check_at <= now,
                ),
                authorized_agent(since=now - timedelta(seconds=LEASE_SECONDS), mode=config.mode),
                ~active,
            )
        )
        if config.max_active_jobs_per_origin is not None:
            job_origin = case(
                (
                    MonitoringJob.navigation_policy == STRICT_NAVIGATION,
                    origin_key(MonitoringJob.url),
                ),
                else_=MonitoringJob.origins[0].astext,
            )
            occupancy = (
                select(job_origin.label("origin"), func.count().label("active"))
                .where(MonitoringJob.status.in_(ACTIVE))
                .group_by(job_origin)
                .subquery()
            )
            site = MonitoringSource.trusted_origin if trusted else origin_key(Source.url)
            ranked = (
                candidates.outerjoin(occupancy, occupancy.c.origin == site)
                .add_columns(
                    due_at.label("due_at"),
                    func.row_number()
                    .over(partition_by=site, order_by=(due_at, Source.id))
                    .label("position"),
                    func.coalesce(occupancy.c.active, 0).label("active"),
                )
                .subquery()
            )
            candidates = (
                select(Source.id)
                .join(ranked, ranked.c.source_id == Source.id)
                .where(ranked.c.position + ranked.c.active <= config.max_active_jobs_per_origin)
                .order_by(ranked.c.due_at, Source.id)
            )
        else:
            candidates = candidates.order_by(due_at, Source.id)
        source_ids = list(
            await self.session.scalars(
                candidates.limit(batch).with_for_update(of=Source, skip_locked=True)
            )
        )
        return [
            await self.create_job(source_id, flow_run_id=flow_run_id, config=config)
            for source_id in source_ids
        ]

    @staticmethod
    def _finish(job, state, error_code=None):
        job.status = state
        job.error_code = error_code
        job.completed_at = utc_now()

    async def _advance_failed_schedule(self, job):
        schedule = await self.session.get(SourceCheckSchedule, job.source_id)
        if schedule is not None:
            schedule.next_check_at = utc_now() + timedelta(seconds=schedule.interval_seconds)

    async def record_initial_failure(self, job, code):
        """Record terminal discovery failure while the caller holds the Source lock."""
        if job.navigation_policy == STRICT_NAVIGATION:
            return
        source = await self.session.get(Source, job.source_id)
        if source is None or source.state != State.UNDISCOVERED:
            return
        try:
            self._check_policy(source, await self.session.get(MonitoringSource, source.id), job)
        except MonitoringError:
            return
        sources = SourcesService(self.session, commit=False)
        await sources._change_state(source, State.DISCOVERING, "BROWSER_DISCOVERY", Trigger.CRAWLER)
        await sources._change_state(source, State.FAILED, code, Trigger.CRAWLER)

    async def _retry(self, job, code, *, record_failure=False):
        job.error_code = code
        job.lease_expires_at = None
        if job.attempt_count < ATTEMPT_LIMIT:
            job.status = "retry_pending"
            job.available_at = utc_now() + retry_delay(job.attempt_count)
        else:
            self._finish(job, "failed", code)
            await self._advance_failed_schedule(job)
            if record_failure:
                await self.record_initial_failure(job, code)

    async def expire_leases(self, limit=100):
        rows = list(
            await self.session.scalars(
                select(MonitoringJob)
                .join(Source, Source.id == MonitoringJob.source_id)
                .where(
                    MonitoringJob.status.in_(LEASED), MonitoringJob.lease_expires_at <= utc_now()
                )
                .order_by(MonitoringJob.lease_expires_at)
                .limit(limit)
                .with_for_update(of=(Source, MonitoringJob), skip_locked=True)
            )
        )
        for job in rows:
            await self._retry(job, "LEASE_EXPIRED", record_failure=True)
        return len(rows)

    async def expire_offline_jobs(self, grace_seconds, limit=100):
        cutoff = utc_now() - timedelta(seconds=grace_seconds)
        rows = list(
            await self.session.scalars(
                select(MonitoringJob)
                .join(Source, Source.id == MonitoringJob.source_id)
                .where(
                    MonitoringJob.reason == "scheduled",
                    MonitoringJob.status.in_(READY),
                    MonitoringJob.available_at <= cutoff,
                    or_(
                        and_(
                            MonitoringJob.navigation_policy == STRICT_NAVIGATION,
                            ~authorized_agent(since=cutoff),
                        ),
                        and_(
                            MonitoringJob.navigation_policy != STRICT_NAVIGATION,
                            ~authorized_agent(since=cutoff, mode="trusted"),
                        ),
                    ),
                )
                .order_by(MonitoringJob.available_at, MonitoringJob.id)
                .limit(limit)
                .with_for_update(of=MonitoringJob, skip_locked=True)
            )
        )
        for job in rows:
            self._finish(job, "cancelled", "AGENT_UNAVAILABLE")
        return len(rows)

    async def cancel_stale(self, limit=100, *, config=None):
        config = config if config is not None else onboarding_config()
        disabled_navigation = (
            MonitoringJob.navigation_policy != STRICT_NAVIGATION
            if config.mode != "trusted"
            else and_(
                not config.trusted_allow_http, MonitoringJob.navigation_policy == TRUSTED_HTTP
            )
        )
        rows = list(
            await self.session.scalars(
                select(MonitoringJob)
                .join(MonitoringSource, MonitoringSource.source_id == MonitoringJob.source_id)
                .join(Source, Source.id == MonitoringJob.source_id)
                .where(
                    MonitoringJob.status.in_(ACTIVE),
                    or_(
                        ~self._job_policy_matches(),
                        and_(MonitoringJob.status.not_in(PROCESSABLE), disabled_navigation),
                    ),
                )
                .order_by(MonitoringJob.created_at)
                .limit(limit)
                .with_for_update(of=MonitoringJob, skip_locked=True)
            )
        )
        for job in rows:
            code = (
                "SOURCE_NOT_APPROVED_OR_ACTIVE"
                if job.navigation_policy == STRICT_NAVIGATION
                else "SOURCE_NOT_ELIGIBLE"
            )
            self._finish(job, "cancelled", code)
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

    async def claim(self, agent, mode="strict"):
        now = utc_now()
        trusted = mode == "trusted"
        if trusted:
            config = onboarding_config()
            if config.mode != "trusted":
                raise MonitoringError(409, "TRUSTED_MODE_DISABLED")
            if not agent.trusted:
                raise MonitoringError(403, "TRUSTED_AGENT_REQUIRED")
        if agent.trusted:
            # Authentication locks this agent row. With the same token, two
            # concurrent polls can never acquire two live browser leases.
            has_lease = await self.session.scalar(
                select(
                    select(MonitoringJob.id)
                    .where(
                        MonitoringJob.agent_id == agent.id,
                        MonitoringJob.status.in_(LEASED),
                        MonitoringJob.lease_expires_at > now,
                    )
                    .exists()
                )
            )
            if has_lease:
                return None
        if trusted:
            navigation = (
                (TRUSTED_HTTPS, TRUSTED_HTTP) if config.trusted_allow_http else (TRUSTED_HTTPS,)
            )
            scope = MonitoringJob.navigation_policy.in_(navigation)
        else:
            scope = and_(
                MonitoringJob.navigation_policy == STRICT_NAVIGATION, assigned_source(agent.id)
            )
        job = await self.session.scalar(
            select(MonitoringJob)
            .join(MonitoringSource, MonitoringSource.source_id == MonitoringJob.source_id)
            .join(Source, Source.id == MonitoringJob.source_id)
            .where(
                scope,
                MonitoringJob.status.in_(READY),
                MonitoringJob.available_at <= now,
                self._job_policy_matches(),
            )
            .order_by(MonitoringJob.available_at, MonitoringJob.created_at)
            .limit(1)
            .with_for_update(
                of=(Source, MonitoringJob) if trusted else MonitoringJob, skip_locked=True
            )
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
                await self._advance_failed_schedule(job)
                await self.record_initial_failure(job, "TOO_MANY_SELECTORS")
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
            visual_archive_version=VISUAL_ARCHIVE_VERSION,
            selectors=definitions,
            **(
                {
                    "navigation": TrustedNavigation(
                        mode="trusted", allow_http=job.navigation_policy == TRUSTED_HTTP
                    )
                }
                if trusted
                else {}
            ),
        )

    async def owned(self, job_id, agent, *, lock=True, lock_source=False):
        scoped = and_(
            MonitoringJob.navigation_policy == STRICT_NAVIGATION, assigned_source(agent.id)
        )
        scope = (
            or_(scoped, MonitoringJob.navigation_policy != STRICT_NAVIGATION)
            if agent.trusted
            else scoped
        )
        query = (
            select(MonitoringJob)
            .join(Source, Source.id == MonitoringJob.source_id)
            .where(MonitoringJob.id == job_id, MonitoringJob.agent_id == agent.id, scope)
        )
        if lock_source and agent.trusted:
            source_id = await self.session.scalar(
                query.with_only_columns(MonitoringJob.source_id).where(
                    MonitoringJob.navigation_policy != STRICT_NAVIGATION
                )
            )
            if source_id is not None:
                # State changes take the Source lock before locking the job.
                await self._source(source_id)
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
        if job.navigation_policy != STRICT_NAVIGATION:
            config = onboarding_config()
            if config.mode != "trusted":
                raise MonitoringError(409, "TRUSTED_MODE_DISABLED")
            if job.navigation_policy == TRUSTED_HTTP and not config.trusted_allow_http:
                raise MonitoringError(409, "TRUSTED_HTTP_DISABLED")

    async def heartbeat(self, job, request):
        await self._lease(job, request.lease_id)
        if request.phase == "capturing" and job.status == "claimed":
            job.status = "capturing"
        job.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
        return {"leaseExpiresAt": job.lease_expires_at, "status": job.status}

    async def grant_visual_upload(self, job, request):
        return await self.grant_upload(job, request, kind="visual")

    async def grant_upload(self, job, request, *, kind="evidence"):
        await self._lease(job, request.lease_id)
        now = utc_now()
        ttl = min(UPLOAD_SECONDS, math.floor((job.lease_expires_at - now).total_seconds()))
        if ttl <= 0:
            raise MonitoringError(409, "LEASE_LOST")
        intent = await self.session.scalar(
            select(MonitoringUpload)
            .where(
                MonitoringUpload.job_id == job.id,
                MonitoringUpload.lease_id == job.lease_id,
                MonitoringUpload.kind == kind,
            )
            .with_for_update()
        )
        if intent is None:
            intent = MonitoringUpload(
                job_id=job.id,
                lease_id=job.lease_id,
                kind=kind,
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
        if request.visual_archive_upload_id is None:
            # Completions queued by older agents retain the same replay digest.
            supplied.pop("visualArchiveUploadId", None)
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
            or intent.kind != "evidence"
            or intent.cleaned_at is not None
        ):
            raise MonitoringError(404, "UPLOAD_INTENT_NOT_FOUND")
        if (intent.content_hash, intent.content_size) != (
            request.content_hash,
            request.content_size,
        ):
            raise MonitoringError(422, "UPLOAD_METADATA_MISMATCH")
        if job.navigation_policy == STRICT_NAVIGATION:
            check_origin(request.page_url, job.origins)
        else:
            trusted_origin(request.page_url, allow_http=job.navigation_policy == TRUSTED_HTTP)
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
        if request.visual_archive_upload_id is not None:
            await self._seal_visual_upload(job, request.visual_archive_upload_id)
        job.completion_key = request.completion_key
        job.completion_digest = digest
        job.completion_json = supplied
        job.status = "uploaded"
        job.available_at = utc_now()
        return status(job)

    async def _seal_visual_upload(self, job, upload_id):
        intent = await self.session.scalar(
            select(MonitoringUpload)
            .where(
                MonitoringUpload.id == upload_id,
                MonitoringUpload.job_id == job.id,
                MonitoringUpload.lease_id == job.lease_id,
                MonitoringUpload.kind == "visual",
                MonitoringUpload.cleaned_at.is_(None),
            )
            .with_for_update()
        )
        if intent is None:
            return
        key = f"monitoring/snapshots/{intent.id}/{intent.content_hash}.html"
        try:
            await self.store.seal(
                intent.storage_key,
                key,
                intent.content_size,
                intent.content_hash,
                max_bytes=MAX_VISUAL_ARCHIVE_BYTES,
            )
        except MonitoringError:
            # Visual delivery is optional. The sealed evidence remains usable.
            return
        intent.sealed_key = key

    async def fail(self, job, request):
        await self._lease(job, request.lease_id)
        await self._retry(job, request.code, record_failure=request.code != "CANCELLED")
        return status(job)

    async def processable(self, limit=50, *, after=None):
        position = tuple_(MonitoringJob.available_at, MonitoringJob.id)
        query = (
            select(MonitoringJob.available_at, MonitoringJob.id)
            .where(MonitoringJob.status.in_(PROCESSABLE), MonitoringJob.available_at <= utc_now())
            .order_by(MonitoringJob.available_at, MonitoringJob.id)
            .limit(limit)
        )
        if after is not None:
            query = query.where(position > tuple_(*after))
        return (await self.session.execute(query)).all()

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
