"""Operator views for onboarding, enrollment, coverage and the monitoring queue."""

from datetime import timedelta

from sqlalchemy import distinct, func, or_, select

from extraction.schemas.common import utc_now
from monitoring.enrollment import approval_matches, authorized_agent
from monitoring.models import MonitoringJob, MonitoringSource
from monitoring.queue import LEASE_SECONDS
from sources.schemas.enums import SourceState as State
from sources.schemas.enums import SourceType
from sources.schemas.models import Source, SourceCheckSchedule, SourceStateHistory


def approved_html():
    return (
        select(Source.id)
        .join(MonitoringSource, MonitoringSource.source_id == Source.id)
        .where(*approval_matches())
    )


async def coverage(session, after, limit, only_uncovered):
    authorized = authorized_agent()
    online = authorized_agent(since=utc_now() - timedelta(seconds=LEASE_SECONDS))
    if only_uncovered:
        conditions = (~authorized,)
    else:
        conditions = ()
    rows = (
        await session.execute(
            approved_html()
            .add_columns(authorized, online)
            .where(Source.state == State.ACTIVE, Source.id > after, *conditions)
            .order_by(Source.id)
            .limit(limit + 1)
        )
    ).all()
    return {
        "sources": [
            {"sourceId": identity, "hasAuthorizedAgent": assigned, "hasOnlineAgent": connected}
            for identity, assigned, connected in rows[:limit]
        ],
        "nextAfterSourceId": rows[limit - 1][0] if len(rows) > limit else None,
    }


async def overview(session):
    source_counts = (
        await session.execute(
            select(Source.type, Source.state, func.count()).group_by(Source.type, Source.state)
        )
    ).all()
    by_type, by_state = {}, {}
    for source_type, state, total in source_counts:
        by_type[source_type] = by_type.get(source_type, 0) + total
        by_state[state] = by_state.get(state, 0) + total

    history_counts = (
        await session.execute(
            select(
                func.count(distinct(SourceStateHistory.source_id)).filter(
                    SourceStateHistory.to_state.in_([State.VALIDATING, State.ACTIVE])
                ),
                func.count(distinct(SourceStateHistory.source_id)).filter(
                    SourceStateHistory.to_state == State.ACTIVE
                ),
            )
            .join(Source, Source.id == SourceStateHistory.source_id)
            .where(Source.type == SourceType.HTML)
        )
    ).one()
    eligible_html = await session.scalar(
        select(func.count())
        .select_from(Source)
        .where(
            Source.type == SourceType.HTML, Source.state == State.ACTIVE, Source.url.is_not(None)
        )
    )
    schedule_enabled = SourceCheckSchedule.enabled.is_(True)
    scheduled = SourceCheckSchedule.next_check_at
    now = utc_now()
    due = or_(scheduled.is_(None), scheduled <= now)
    active = Source.state == State.ACTIVE
    assigned = authorized_agent()
    online = authorized_agent(since=utc_now() - timedelta(seconds=LEASE_SECONDS))
    approved = (
        approved_html()
        .outerjoin(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
        .with_only_columns(
            func.count().label("approvedSources"),
            func.count().filter(active).label("approvedActiveSources"),
            func.count().filter(active, schedule_enabled).label("scheduledSources"),
            func.count().filter(active, ~assigned).label("sourcesWithoutAuthorizedAgent"),
            func.count().filter(active, ~online).label("sourcesWithoutOnlineAgent"),
            func.count().filter(active, schedule_enabled, due).label("overdueSources"),
            func.min(func.coalesce(scheduled, now))
            .filter(active, schedule_enabled)
            .label("nextScheduledCheck"),
        )
    )
    schedule_counts = (await session.execute(approved)).mappings().one()
    jobs = dict(
        (
            await session.execute(
                select(MonitoringJob.status, func.count()).group_by(MonitoringJob.status)
            )
        ).all()
    )
    last_check = await session.scalar(
        select(func.max(MonitoringJob.completed_at)).where(MonitoringJob.status == "completed")
    )
    return {
        "totalSources": sum(by_type.values()),
        "sourcesByType": by_type,
        "sourcesByState": by_state,
        "eligibleHtmlSources": eligible_html,
        "discoveredSources": history_counts[0],
        "validatedSources": history_counts[1],
        "sourcesAwaitingReview": by_state.get(State.NEEDS_REVIEW, 0),
        **schedule_counts,
        "jobsByStatus": jobs,
        "pendingJobs": jobs.get("pending", 0) + jobs.get("retry_pending", 0),
        "processingJobs": jobs.get("uploaded", 0) + jobs.get("processing", 0),
        "failedJobs": jobs.get("failed", 0),
        "lastSuccessfulCheck": last_check,
    }
