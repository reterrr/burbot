"""Durable bulk onboarding work advanced by the existing monitoring scheduler."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from extraction.schemas.api import Identifier
from extraction.schemas.common import utc_now
from extraction.schemas.selector_tree import PortableModel
from monitoring.enrollment import (
    MonitoringEnrollmentService,
    approval_matches,
    missing_policy_agent,
    origin_key,
)
from monitoring.models import DiscoveryOrigin, MonitoringSource, OnboardingItem, OnboardingRun
from monitoring.onboarding_config import PolicyName
from monitoring.security import MonitoringError
from sources.schemas.api import SourceStateChangeRequest
from sources.schemas.enums import SourceState as State
from sources.schemas.enums import SourceStateTrigger as Trigger
from sources.schemas.enums import SourceType
from sources.schemas.models import Source, SourceCheckSchedule
from sources.services.sources import SourcesService

ONBOARDING_TICK_SECONDS = 40


class OnboardingRequest(PortableModel):
    policy: PolicyName
    source_type: SourceType = SourceType.HTML
    source_state: State | None = None
    source_ids: list[Identifier] = Field(default_factory=list, max_length=1000)
    approve_selected: bool = False
    batch_size: int | None = Field(default=None, ge=1, le=100)
    request_id: UUID | None = None

    @model_validator(mode="after")
    def validate_selection(self):
        if self.approve_selected and not self.source_ids:
            raise ValueError("Explicit approval requires selected source IDs")
        return self

    def criteria(self):
        values = self.model_dump(mode="json", exclude={"policy", "request_id"})
        values["source_ids"] = sorted(set(self.source_ids))
        return values


def source_filters(request):
    yield Source.type == request.source_type
    if request.source_state is not None:
        yield Source.state == request.source_state
    elif not request.source_ids:
        yield Source.state.in_([State.UNDISCOVERED, State.ACTIVE])
    if request.source_ids:
        yield Source.id.in_(request.source_ids)


def eligible_approval(policy, approve_selected):
    approved = and_(*approval_matches())
    if policy.auto_enroll or approve_selected:
        return or_(MonitoringSource.source_id.is_(None), approved)
    return approved


class OnboardingService:
    def __init__(self, session, config):
        self.session = session
        self.config = config

    async def preview(self, request):
        policy = self.config.policy(request.policy)
        in_scope = (Source.type == SourceType.HTML) & origin_key(Source.url).in_(policy.origins)
        approved = eligible_approval(policy, request.approve_selected)
        totals = (
            (
                await self.session.execute(
                    select(
                        func.count().label("selected"),
                        func.count().filter(Source.type != SourceType.HTML).label("unsupported"),
                        func.count()
                        .filter(in_scope, Source.state == State.UNDISCOVERED)
                        .label("discoverable"),
                        func.count()
                        .filter(
                            in_scope, Source.state.in_([State.UNDISCOVERED, State.ACTIVE]), approved
                        )
                        .label("approvedIfActive"),
                        func.count()
                        .filter(
                            in_scope,
                            Source.state.in_([State.UNDISCOVERED, State.ACTIVE]),
                            ~approved,
                        )
                        .label("needsApproval"),
                        func.count()
                        .filter(Source.type == SourceType.HTML, ~func.coalesce(in_scope, False))
                        .label("outsidePolicy"),
                    )
                    .select_from(Source)
                    .outerjoin(MonitoringSource, MonitoringSource.source_id == Source.id)
                    .where(*source_filters(request))
                )
            )
            .mappings()
            .one()
        )
        return {"policy": request.policy, "counts": dict(totals)}

    async def create_run(self, request):
        self.config.policy(request.policy)
        run_id = request.request_id or uuid4()
        ceiling = await self.session.scalar(select(func.max(Source.id))) or 0
        proposed = OnboardingRun(
            id=run_id,
            policy_name=request.policy,
            criteria=request.criteria(),
            through_source_id=ceiling,
        )
        await self.session.execute(
            insert(OnboardingRun).values(proposed.model_dump()).on_conflict_do_nothing()
        )
        run = await self.session.get(OnboardingRun, run_id)
        if (
            run.continuous
            or run.policy_name != request.policy
            or run.criteria != request.criteria()
        ):
            raise MonitoringError(409, "ONBOARDING_REQUEST_CONFLICT")
        return run

    async def run(self, run_id, *, lock=False):
        run = await self.session.get(OnboardingRun, run_id, with_for_update=lock)
        if run is None:
            raise MonitoringError(404, "ONBOARDING_RUN_NOT_FOUND")
        return run

    async def list_runs(self, after, limit):
        statement = select(OnboardingRun).order_by(OnboardingRun.id).limit(limit + 1)
        if after is not None:
            statement = statement.where(OnboardingRun.id > after)
        rows = list(await self.session.scalars(statement))
        return {
            "runs": [
                {
                    "runId": run.id,
                    "policy": run.policy_name,
                    "continuous": run.continuous,
                    "createdAt": run.created_at,
                }
                for run in rows[:limit]
            ],
            "nextAfterRunId": rows[limit - 1].id if len(rows) > limit else None,
        }

    async def progress(self, run_id, after, limit):
        run = await self.run(run_id)
        counts = dict(
            (
                await self.session.execute(
                    select(OnboardingItem.status, func.count())
                    .where(OnboardingItem.run_id == run_id)
                    .group_by(OnboardingItem.status)
                )
            ).all()
        )
        rows = (
            await self.session.execute(
                select(OnboardingItem, Source.state)
                .join(Source, Source.id == OnboardingItem.source_id)
                .where(OnboardingItem.run_id == run_id, OnboardingItem.source_id > after)
                .order_by(OnboardingItem.source_id)
                .limit(limit + 1)
            )
        ).all()
        policy = self.config.policies.get(run.policy_name)
        if run.scan_complete and not counts.get("pending"):
            state = "completed"
        elif policy is None or (run.continuous and not policy.continuous):
            state = "paused"
        else:
            state = "running" if run.last_serviced_at else "pending"
        return {
            "runId": run.id,
            "policy": run.policy_name,
            "continuous": run.continuous,
            "status": state,
            "createdAt": run.created_at,
            "lastServicedAt": run.last_serviced_at,
            "scanComplete": run.scan_complete,
            "scannedThroughSourceId": run.after_source_id,
            "counts": counts,
            "items": [
                {
                    "sourceId": item.source_id,
                    "sourceState": source_state,
                    "status": item.status,
                    "attempts": item.attempts,
                    "retryAt": item.available_at if item.status == "pending" else None,
                    "diagnostics": item.diagnostics,
                }
                for item, source_state in rows[:limit]
            ],
            "nextAfterSourceId": rows[limit - 1][0].source_id if len(rows) > limit else None,
        }

    async def retry(self, run_id, limit):
        run = await self.run(run_id, lock=True)
        self.config.policy(run.policy_name)
        selected = (
            select(OnboardingItem.source_id)
            .join(Source, Source.id == OnboardingItem.source_id)
            .where(
                OnboardingItem.run_id == run_id,
                OnboardingItem.status == "failed",
                OnboardingItem.diagnostics["retryable"].as_boolean().is_(True),
                Source.state == State.FAILED,
                Source.last_state_change_at == OnboardingItem.source_state_at,
            )
            .order_by(OnboardingItem.source_id)
            .limit(limit)
            .with_for_update(of=OnboardingItem, skip_locked=True)
        )
        rows = await self.session.execute(
            update(OnboardingItem)
            .where(OnboardingItem.run_id == run_id, OnboardingItem.source_id.in_(selected))
            .values(status="pending", attempts=0, available_at=utc_now())
            .returning(OnboardingItem.source_id)
        )
        return {"runId": run_id, "requeued": len(rows.all())}

    async def continuous_runs(self):
        rows = [
            OnboardingRun(policy_name=name, continuous=True).model_dump()
            for name, policy in self.config.policies.items()
            if policy.continuous
        ]
        if rows:
            await self.session.execute(insert(OnboardingRun).values(rows).on_conflict_do_nothing())

    async def scan(self, run, request, policy, limit):
        statement = select(Source.id).where(
            Source.id > run.after_source_id, *source_filters(request)
        )
        if run.continuous:
            statement = (
                statement.outerjoin(MonitoringSource, MonitoringSource.source_id == Source.id)
                .outerjoin(SourceCheckSchedule, SourceCheckSchedule.source_id == Source.id)
                .where(
                    origin_key(Source.url).in_(policy.origins),
                    or_(
                        Source.state == State.UNDISCOVERED,
                        eligible_approval(policy, False)
                        & or_(
                            MonitoringSource.source_id.is_(None),
                            SourceCheckSchedule.source_id.is_(None),
                            missing_policy_agent(policy.agent_ids),
                        ),
                    ),
                )
            )
        else:
            statement = statement.where(Source.id <= run.through_source_id)
        ids = list(await self.session.scalars(statement.order_by(Source.id).limit(limit)))
        if ids:
            statement = insert(OnboardingItem).values(
                [
                    OnboardingItem(run_id=run.id, source_id=source_id).model_dump()
                    for source_id in ids
                ]
            )
            if run.continuous:
                statement = statement.on_conflict_do_update(
                    index_elements=["run_id", "source_id"],
                    set_={
                        "status": "pending",
                        "attempts": 0,
                        "available_at": utc_now(),
                        "source_state_at": None,
                        "diagnostics": {},
                    },
                    where=OnboardingItem.status != "pending",
                )
            else:
                statement = statement.on_conflict_do_nothing()
            await self.session.execute(statement)
            run.after_source_id = ids[-1]
        if len(ids) < limit:
            if run.continuous:
                run.after_source_id = 0
            else:
                run.scan_complete = True

    async def next_batch(self):
        if not self.config.policies:
            return None, []
        await self.continuous_runs()
        now = utc_now()
        ready = (
            select(OnboardingItem.source_id)
            .where(
                OnboardingItem.run_id == OnboardingRun.id,
                OnboardingItem.status == "pending",
                OnboardingItem.available_at <= now,
            )
            .exists()
        )
        run = await self.session.scalar(
            select(OnboardingRun)
            .where(
                OnboardingRun.policy_name.in_(self.config.policies),
                or_(
                    OnboardingRun.continuous.is_(False),
                    OnboardingRun.policy_name.in_(
                        [name for name, policy in self.config.policies.items() if policy.continuous]
                    ),
                ),
                or_(OnboardingRun.scan_complete.is_(False), ready),
            )
            .order_by(
                func.coalesce(OnboardingRun.last_serviced_at, OnboardingRun.created_at),
                OnboardingRun.created_at,
                OnboardingRun.id,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run is None:
            return None, []
        run.last_serviced_at = now
        request = OnboardingRequest(policy=run.policy_name, **run.criteria)
        limit = min(self.config.batch_size, request.batch_size or self.config.batch_size)
        pending = (
            select(OnboardingItem.source_id)
            .where(
                OnboardingItem.run_id == run.id,
                OnboardingItem.status == "pending",
            )
            .order_by(OnboardingItem.available_at, OnboardingItem.source_id)
            .limit(limit)
        )
        ids = list(
            await self.session.scalars(pending.where(OnboardingItem.available_at <= utc_now()))
        )
        if not run.scan_complete and len(ids) < limit:
            await self.scan(run, request, self.config.policy(run.policy_name), limit - len(ids))
            ids = list(
                await self.session.scalars(pending.where(OnboardingItem.available_at <= utc_now()))
            )
        return run.id, ids


async def reserve_origin(factory, site, interval, timeout):
    if not interval:
        return None
    delay = timedelta(seconds=interval)
    now = utc_now()
    wait_limit = timedelta(seconds=min(3, timeout / 2))
    async with factory.begin() as session:
        slot = await session.scalar(
            insert(DiscoveryOrigin)
            .values(origin=site, next_request_at=now + delay)
            .on_conflict_do_update(
                index_elements=["origin"],
                set_={
                    "next_request_at": func.greatest(DiscoveryOrigin.next_request_at, now) + delay
                },
                where=DiscoveryOrigin.next_request_at <= now + wait_limit,
            )
            .returning(DiscoveryOrigin.next_request_at)
        )
        if slot is None:
            return await session.scalar(
                select(DiscoveryOrigin.next_request_at).where(DiscoveryOrigin.origin == site)
            )
    wait = (slot - delay - utc_now()).total_seconds()
    if wait > 0:
        await asyncio.sleep(wait)
    return None


async def change_state(service, source, state, reason, trigger):
    result = await service.change_state(
        source.id,
        SourceStateChangeRequest(
            state=state,
            expected_state=source.state,
            reason=reason,
            triggered_by=trigger,
        ),
    )
    return result.last_state_change_at


def finish_item(item, status, code):
    item.status = status
    item.diagnostics = {**item.diagnostics, "code": code}


async def process_item(factory, config, run_id, source_id, probe):
    from monitoring.discovery import discoverable_origin

    # Source and item are locked only for this bounded probe. A worker crash
    # rolls back both, so the next tick can pick up the same item.
    async with factory.begin() as session:
        item = await session.get(
            OnboardingItem, (run_id, source_id), with_for_update={"skip_locked": True}
        )
        if item is None or item.status != "pending" or item.available_at > utc_now():
            return False
        run = await session.get(OnboardingRun, run_id)
        policy = config.policy(run.policy_name)
        source = await session.get(Source, source_id, with_for_update={"skip_locked": True})
        if source is None:
            return False
        requested_type = run.criteria.get("source_type", SourceType.HTML)
        if requested_type != SourceType.HTML or source.type != SourceType.HTML:
            finish_item(item, "skipped", "UNSUPPORTED_SOURCE_TYPE")
            return True
        owned = item.source_state_at == source.last_state_change_at
        requested_state = run.criteria.get("source_state")
        if (
            requested_state is not None
            and requested_state != source.state
            and not (owned and source.state in {State.DISCOVERING, State.FAILED})
        ):
            finish_item(item, "skipped", "SOURCE_STATE_CHANGED")
            return True
        sources = SourcesService(session, commit=False)
        try:
            site = discoverable_origin(source.url)
        except MonitoringError:
            if source.state == State.UNDISCOVERED or (owned and source.state == State.DISCOVERING):
                if source.state == State.UNDISCOVERED:
                    await change_state(
                        sources,
                        source,
                        State.DISCOVERING,
                        "DISCOVERY_STARTED",
                        Trigger.DISCOVERY_ENGINE,
                    )
                item.source_state_at = await change_state(
                    sources, source, State.NEEDS_REVIEW, "URL_NOT_ALLOWED", Trigger.POLICY_CHECK
                )
                finish_item(item, "needs_review", "URL_NOT_ALLOWED")
            else:
                finish_item(item, "skipped", "URL_NOT_ALLOWED")
            return True
        if site not in policy.origins:
            if owned and source.state == State.DISCOVERING:
                item.source_state_at = await change_state(
                    sources, source, State.NEEDS_REVIEW, "ORIGIN_NOT_APPROVED", Trigger.POLICY_CHECK
                )
            finish_item(item, "needs_approval", "ORIGIN_NOT_APPROVED")
            return True

        visited_origins = ()
        if source.state != State.ACTIVE:
            if source.state == State.UNDISCOVERED or (
                source.state == State.FAILED and owned and item.diagnostics.get("retryable")
            ):
                item.source_state_at = await change_state(
                    sources,
                    source,
                    State.DISCOVERING,
                    "DISCOVERY_STARTED",
                    Trigger.DISCOVERY_ENGINE,
                )
            elif source.state != State.DISCOVERING or not owned:
                finish_item(item, "skipped", "SOURCE_STATE_CHANGED")
                return True

            async def reserve(site):
                return await reserve_origin(
                    factory, site, config.per_origin_interval_seconds, config.probe_timeout_seconds
                )

            result = await probe(source.url, policy, reserve, config.probe_timeout_seconds)
            item.diagnostics = result.diagnostics()
            if result.state == State.DISCOVERING:
                item.available_at = result.retry_at
                return True
            item.attempts += 1
            if result.retryable and item.attempts < config.discovery_attempts:
                delay = min(3600, config.retry_base_seconds * 2 ** (item.attempts - 1))
                earliest = utc_now() + timedelta(seconds=delay)
                item.available_at = max(earliest, result.retry_at or earliest)
                return True
            if result.state == State.ACTIVE or result.http_status == 200:
                await change_state(
                    sources,
                    source,
                    State.VALIDATING,
                    "HTTP_RESOURCE_RECEIVED",
                    Trigger.DISCOVERY_ENGINE,
                )
            item.source_state_at = await change_state(
                sources,
                source,
                result.state,
                result.code,
                Trigger.VALIDATOR if source.state == State.VALIDATING else Trigger.DISCOVERY_ENGINE,
            )
            if result.state != State.ACTIVE:
                item.status = "failed" if result.state == State.FAILED else "needs_review"
                return True
            visited_origins = result.visited_origins

        code = await MonitoringEnrollmentService(session, config.default_schedule).enroll(
            source,
            policy,
            approve_selected=run.criteria.get("approve_selected", False),
            visited_origins=visited_origins,
        )
        finish_item(item, "enrolled" if code == "ENROLLED" else "needs_approval", code)
        return True


async def run_onboarding_batch(factory, config, logger, *, probe=None):
    if probe is None:
        from monitoring.discovery import probe_html

        probe = probe_html
    async with factory.begin() as session:
        run_id, items = await OnboardingService(session, config).next_batch()
    if not items:
        return 0

    capacity = asyncio.Semaphore(config.probe_concurrency)

    async def work(source_id):
        async with capacity:
            try:
                return await process_item(factory, config, run_id, source_id, probe)
            except Exception as error:
                logger.warning(
                    "onboarding_run_id=%s source_id=%s onboarding_status=retry error_category=%s",
                    run_id,
                    source_id,
                    type(error).__name__,
                )
                return False

    results = await asyncio.gather(*(work(source_id) for source_id in items))
    return sum(results)
