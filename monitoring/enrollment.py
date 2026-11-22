"""Apply explicit monitoring approvals and create missing Source schedules."""

from datetime import timedelta
from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from extraction.schemas.common import utc_now
from monitoring.models import MonitoringAgent, MonitoringAgentSource, MonitoringSource
from monitoring.security import MonitoringError, check_origin, origin
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import Source, SourceCheckSchedule


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


def authorized_agent(*, since=None):
    query = (
        select(MonitoringAgentSource.source_id)
        .join(MonitoringAgent, MonitoringAgent.id == MonitoringAgentSource.agent_id)
        .where(
            MonitoringAgentSource.source_id == Source.id,
            MonitoringAgentSource.enabled.is_(True),
            MonitoringAgent.enabled.is_(True),
        )
    )
    if since is not None:
        query = query.where(MonitoringAgent.last_seen_at >= since)
    return query.correlate(Source).exists()


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

    async def enroll(self, source, policy=None, *, approve_selected=False, visited_origins=()):
        """The caller holds the Source row lock during enrollment."""
        if source.type != SourceType.HTML or source.state != SourceState.ACTIVE:
            return "SOURCE_NOT_ELIGIBLE"
        approval = await self.session.get(MonitoringSource, source.id)
        try:
            site = origin(source.url or "")
        except MonitoringError:
            return "URL_NOT_ALLOWED"
        if approval is None:
            if policy is None or not (policy.auto_enroll or approve_selected):
                return "APPROVAL_REQUIRED"
            if site not in policy.origins:
                return "ORIGIN_NOT_APPROVED"
            allowed = set(policy.origins) | set(policy.additional_origins)
            approval = MonitoringSource(
                source_id=source.id,
                url=source.url,
                origins=sorted(
                    {site, *policy.additional_origins, *(set(visited_origins) & allowed)}
                ),
            )
            self.session.add(approval)
            await self.session.flush()
        elif not approval.enabled or approval.url != source.url:
            return "APPROVAL_DISABLED_OR_STALE"
        else:
            try:
                check_origin(source.url, approval.origins)
            except MonitoringError:
                return "APPROVAL_DISABLED_OR_STALE"

        schedule = await self.session.get(SourceCheckSchedule, source.id)
        if schedule is None:
            spread = self.defaults.initial_spread_seconds
            position = int.from_bytes(sha256(str(source.id).encode()).digest()[:8], "big")
            delay = position % spread if spread else 0
            self.session.add(
                SourceCheckSchedule(
                    source_id=source.id,
                    interval_seconds=self.defaults.interval_seconds,
                    enabled=self.defaults.enabled,
                    next_check_at=utc_now() + timedelta(seconds=delay),
                )
            )
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
