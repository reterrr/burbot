"""Apply explicit monitoring approvals and create missing Source schedules."""

from datetime import timedelta
from hashlib import sha256

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from extraction.schemas.common import utc_now
from monitoring.models import MonitoringAgent, MonitoringAgentSource, MonitoringSource
from monitoring.security import MonitoringError, check_origin, origin, trusted_origin
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import Source, SourceCheckSchedule

INITIAL_CAPTURE_STATES = (SourceState.UNDISCOVERED, SourceState.FAILED)
TRUSTED_SOURCE_STATES = (*INITIAL_CAPTURE_STATES, SourceState.ACTIVE, SourceState.DEGRADED)


def trusted_origin_matches(allow_http):
    if allow_http:
        return MonitoringSource.trusted_origin.is_not(None)
    return MonitoringSource.trusted_origin.startswith("https://")


def trusted_enrollment_matches(allow_http):
    return (
        Source.type == SourceType.HTML,
        Source.state.in_(TRUSTED_SOURCE_STATES),
        MonitoringSource.enabled.is_(True),
        MonitoringSource.trusted_url == Source.url,
        trusted_origin_matches(allow_http),
    )


def origin_key(url):
    # This SQL expression narrows candidates. The Python origin check is still
    # required before a network request or a new approval.
    return func.regexp_replace(func.lower(func.substring(url, r"^[^:/]+://[^/?#]+")), r":443$", "")


def approval_matches():
    return (
        MonitoringSource.enabled.is_(True),
        MonitoringSource.url == Source.url,
        MonitoringSource.origins.bool_op("?")(origin_key(Source.url)),
        Source.type == SourceType.HTML,
    )


def authorized_agent(*, since=None, mode="strict"):
    query = select(MonitoringAgent.id).where(MonitoringAgent.enabled.is_(True))
    if mode == "trusted":
        query = query.where(MonitoringAgent.trusted.is_(True))
    else:
        query = (
            query.join(MonitoringAgentSource, MonitoringAgent.id == MonitoringAgentSource.agent_id)
            .where(
                MonitoringAgentSource.source_id == Source.id,
                MonitoringAgentSource.enabled.is_(True),
            )
            .correlate(Source)
        )
    if since is not None:
        query = query.where(MonitoringAgent.last_seen_at >= since)
    return query.exists()


def assigned_source(agent_id):
    return (
        select(MonitoringAgentSource.source_id)
        .where(
            MonitoringAgentSource.source_id == Source.id,
            MonitoringAgentSource.agent_id == agent_id,
            MonitoringAgentSource.enabled.is_(True),
        )
        .correlate(Source)
        .exists()
    )


def missing_policy_agent(agent_ids):
    return (
        select(MonitoringAgent.id)
        .where(
            MonitoringAgent.enabled.is_(True),
            MonitoringAgent.id.in_(agent_ids),
            ~select(MonitoringAgentSource.agent_id)
            .where(
                MonitoringAgentSource.agent_id == MonitoringAgent.id,
                MonitoringAgentSource.source_id == Source.id,
            )
            .correlate(MonitoringAgent, Source)
            .exists(),
        )
        .correlate(Source)
        .exists()
    )


async def grant_agent_sources(session, grants, *, explicit=False):
    if not grants:
        return
    statement = insert(MonitoringAgentSource).values(
        [{"agent_id": agent, "source_id": source, "enabled": True} for agent, source in grants]
    )
    if explicit:
        statement = statement.on_conflict_do_update(
            index_elements=["agent_id", "source_id"], set_={"enabled": True}
        )
    else:
        statement = statement.on_conflict_do_nothing()
    await session.execute(statement)


class MonitoringEnrollmentService:
    def __init__(self, session, defaults):
        self.session = session
        self.defaults = defaults

    async def _ensure_schedule(self, source_id):
        if await self.session.get(SourceCheckSchedule, source_id) is not None:
            return False
        spread = self.defaults.initial_spread_seconds
        position = int.from_bytes(sha256(str(source_id).encode()).digest()[:8], "big")
        delay = position % spread if spread else 0
        self.session.add(
            SourceCheckSchedule(
                source_id=source_id,
                interval_seconds=self.defaults.interval_seconds,
                enabled=self.defaults.enabled,
                next_check_at=utc_now() + timedelta(seconds=delay),
            )
        )
        return True

    async def enroll(self, source, policy=None, *, approve_selected=False, visited_origins=()):
        """The caller holds the Source row lock during enrollment."""
        if source.type != SourceType.HTML or source.state != SourceState.ACTIVE:
            return "SOURCE_NOT_ELIGIBLE"
        approval = await self.session.get(MonitoringSource, source.id)
        try:
            site = origin(source.url or "")
        except MonitoringError:
            return "URL_NOT_ALLOWED"
        if approval is None or (approval.enabled and not approval.origins):
            if policy is None or not (policy.auto_enroll or approve_selected):
                return "APPROVAL_REQUIRED"
            if site not in policy.origins:
                return "ORIGIN_NOT_APPROVED"
            allowed = set(policy.origins) | set(policy.additional_origins)
            origins = sorted({site, *policy.additional_origins, *(set(visited_origins) & allowed)})
            if approval is None:
                approval = MonitoringSource(source_id=source.id, url=source.url, origins=origins)
                self.session.add(approval)
            else:
                approval.url = source.url
                approval.origins = origins
                approval.approved_at = utc_now()
            await self.session.flush()
        elif not approval.enabled or approval.url != source.url:
            return "APPROVAL_DISABLED_OR_STALE"
        else:
            try:
                check_origin(source.url, approval.origins)
            except MonitoringError:
                return "APPROVAL_DISABLED_OR_STALE"

        await self._ensure_schedule(source.id)
        if policy is not None and site in policy.origins and policy.agent_ids:
            agent_ids = list(
                await self.session.scalars(
                    select(MonitoringAgent.id).where(
                        MonitoringAgent.id.in_(policy.agent_ids), MonitoringAgent.enabled.is_(True)
                    )
                )
            )
            await grant_agent_sources(
                self.session, [(agent_id, source.id) for agent_id in agent_ids]
            )
        return "ENROLLED"

    async def enroll_trusted(self, source, *, allow_http):
        """Classify the URL without probing the page. The caller locks the Source."""
        if (
            source.type != SourceType.HTML
            or source.state not in TRUSTED_SOURCE_STATES
            or source.url is None
        ):
            return None, False
        enrollment = await self.session.get(MonitoringSource, source.id)
        if enrollment is None:
            enrollment = MonitoringSource(source_id=source.id, url=source.url, origins=[])
            self.session.add(enrollment)
        elif not enrollment.enabled:
            return None, False
        if enrollment.trusted_url != source.url:
            try:
                enrollment.trusted_origin = trusted_origin(source.url, allow_http=True)
            except MonitoringError:
                enrollment.trusted_origin = None
            # Remember exclusions so invalid lower IDs cannot starve later batches.
            enrollment.trusted_url = source.url
        site = enrollment.trusted_origin
        if site is None or (not allow_http and site.startswith("http://")):
            return None, False
        return site, await self._ensure_schedule(source.id)

    async def reconcile_trusted(self, limit, *, allow_http):
        sources = await self.session.scalars(
            select(Source)
            .outerjoin(MonitoringSource, MonitoringSource.source_id == Source.id)
            .outerjoin(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
            .where(
                Source.type == SourceType.HTML,
                Source.state.in_(TRUSTED_SOURCE_STATES),
                Source.url.is_not(None),
                or_(MonitoringSource.source_id.is_(None), MonitoringSource.enabled.is_(True)),
                or_(
                    MonitoringSource.trusted_url.is_distinct_from(Source.url),
                    and_(
                        SourceCheckSchedule.source_id.is_(None),
                        trusted_origin_matches(allow_http),
                    ),
                ),
            )
            .order_by(Source.id)
            .limit(limit)
            .with_for_update(of=Source, skip_locked=True)
        )
        created = 0
        for source in sources:
            _, scheduled = await self.enroll_trusted(source, allow_http=allow_http)
            created += scheduled
        return created

    async def reconcile_approvals(self, limit):
        sources = list(
            await self.session.scalars(
                select(Source)
                .join(MonitoringSource, MonitoringSource.source_id == Source.id)
                .outerjoin(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
                .where(
                    *approval_matches(),
                    Source.state == SourceState.ACTIVE,
                    SourceCheckSchedule.source_id.is_(None),
                )
                .order_by(Source.id)
                .limit(limit)
                .with_for_update(of=Source, skip_locked=True)
            )
        )
        created = 0
        for source in sources:
            created += await self.enroll(source) == "ENROLLED"
        return created
