"""Page object reviews and their source-scoped, recorded findings."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text

from business_layer.schemas.models import BusinessObjectField
from monitoring.attention import MONITORING_TASKS, OPEN_TASKS
from monitoring.models import MonitoringJob, SourceCheckRun
from monitoring.presentation import (
    display_text,
    field_definitions,
    object_presentations,
    recorded_id,
    source_query,
)
from monitoring.review import EVIDENCE_STATUS
from monitoring.security import MonitoringError
from monitoring.workspace import captured_results, task_summary
from sources.schemas.models import Source
from tasks.schemas.models import TaskStatus
from tasks.services.task import TASK_STATUS_TRANSITIONS

# Legacy field reviews can participate through the exact owner of their recorded slot.
OBJECT_TASKS = f"""
    SELECT t.*, target.object_id, target.legacy_slot_id
    FROM ({MONITORING_TASKS}) t
    JOIN LATERAL (
        SELECT min(candidate.object_id) AS object_id,
               CASE WHEN count(DISTINCT candidate.slot_id) = 1
                    THEN min(candidate.slot_id) END AS legacy_slot_id
        FROM (
            SELECT r.reference_id AS object_id, NULL::bigint AS slot_id FROM task_references r
            WHERE t.type = 'review_business_object' AND r.task_id = t.id
              AND r.role = 'target' AND r.reference_type = 'business_object'
            UNION ALL
            SELECT slot.business_object_id, slot.id FROM task_references r
            JOIN business_object_fields slot ON slot.id = r.reference_id
            WHERE t.type = 'review_source_change' AND r.task_id = t.id
              AND r.reference_type = 'business_object_field'
        ) candidate
        HAVING count(DISTINCT candidate.object_id) = 1
    ) target ON true
    JOIN business_objects obj ON obj.id = target.object_id
"""

LATEST_CHECK = """
    LEFT JOIN LATERAL (
        SELECT j.id, j.completed_at FROM monitoring_jobs j
        WHERE j.source_id = t.source_id AND j.status IN ({statuses})
        ORDER BY j.created_at DESC, j.id DESC LIMIT 1
    ) latest ON true
"""

OBJECT_INBOX = text(f"""
    WITH grouped AS (
        SELECT t.object_id, count(DISTINCT t.id) AS task_count,
               count(DISTINCT t.source_id) AS source_count,
               count(DISTINCT slot.id) AS field_count,
               max(coalesce(latest.completed_at, t.completed_at)) AS last_checked,
               bool_or(t.status = 'in_progress') AS started,
               max(CASE WHEN t.evidence_status IN (
                   'EXTRACTION_FAILED', 'MISSING', 'AMBIGUOUS', 'CONFLICT'
               ) THEN 2 WHEN t.evidence_status = 'CHANGED' THEN 1 ELSE 0 END) AS priority
        FROM ({OBJECT_TASKS}) t
        LEFT JOIN task_references refs
            ON refs.task_id = t.id AND refs.reference_type = 'business_object_field'
        LEFT JOIN business_object_fields slot
            ON slot.id = refs.reference_id AND slot.business_object_id = t.object_id
        {LATEST_CHECK.format(statuses="'completed', 'failed'")}
        WHERE {OPEN_TASKS}
        GROUP BY t.object_id
    )
    SELECT page.*, counter.total
    FROM (SELECT count(*) AS total FROM grouped) counter
    LEFT JOIN (
        SELECT * FROM grouped ORDER BY priority DESC, last_checked DESC NULLS LAST, object_id
        OFFSET :offset LIMIT :limit
    ) page ON true
    ORDER BY priority DESC, last_checked DESC NULLS LAST, object_id
""")


async def object_inbox(session, offset, limit):
    rows = (
        (await session.execute(OBJECT_INBOX, {"offset": offset, "limit": limit})).mappings().all()
    )
    identities = {row["object_id"] for row in rows if row["object_id"] is not None}
    objects = await object_presentations(session, identities)
    return {
        "total": rows[0]["total"],
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "object": objects[row["object_id"]],
                "taskCount": row["task_count"],
                "sourceCount": row["source_count"],
                "fieldCount": row["field_count"],
                "lastCheckedAt": row["last_checked"],
                "status": "in_progress" if row["started"] else "pending",
                "severity": ("informational", "normal", "high")[row["priority"]],
            }
            for row in rows
            if row["object_id"] in objects
        ],
    }


def recorded_uuid(value):
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def recorded_checks(session, check_ids):
    if not check_ids:
        return {}
    checks = {}
    for job, check in await session.execute(
        select(MonitoringJob, SourceCheckRun)
        .join(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
        .where(MonitoringJob.id.in_(check_ids), MonitoringJob.status == "completed")
    ):
        rows = check.field_results or []
        if any(not field.get("selectorUuid") for field in rows):
            rows = list((await captured_results(session, job, check)).values())
        checks[job.id] = (job, rows)
    return checks


def finding_pointers(task):
    index = (task["metadata_json"] or {}).get("monitoringFindings", {})
    if not isinstance(index, dict):
        return
    for selector, data in index.items():
        if isinstance(data, dict) and (job_id := recorded_uuid(data.get("checkId"))):
            yield selector, job_id


def task_capture_fields(task, check, selectors=()):
    job, rows = check
    return [
        (
            job,
            {"businessObjectFieldId": task["legacy_slot_id"], **row},
        )
        for row in rows
        if job.source_id == task["source_id"]
        and row.get("taskId") == task["id"]
        and (not selectors or row.get("selectorUuid") in selectors)
    ]


def task_fields(task, checks):
    by_check = defaultdict(set)
    for selector, job_id in finding_pointers(task):
        by_check[job_id].add(selector)
    if not by_check:
        by_check[task["job_id"]] = set()

    captures = []
    for job_id, selectors in by_check.items():
        if job_id in checks:
            captures.extend(task_capture_fields(task, checks[job_id], selectors))
    if task["latest_check_id"] in checks:
        job, fields = checks[task["latest_check_id"]]
        affected = {field.get("businessObjectFieldId") for _, field in captures}
        captures.extend(
            (job, field)
            for field in fields
            if field.get("status") == "FIELD_UNCHANGED"
            and field.get("businessObjectFieldId") not in affected
        )
    return captures


async def present_fields(session, object_id, captures):
    slots = {
        field.get("businessObjectFieldId")
        for _, field in captures
        if recorded_id(field.get("businessObjectFieldId"))
    }
    by_slot = {}
    if slots:
        by_slot = dict(
            (
                await session.execute(
                    select(
                        BusinessObjectField.id, BusinessObjectField.business_entity_field_id
                    ).where(
                        BusinessObjectField.id.in_(slots),
                        BusinessObjectField.business_object_id == object_id,
                    )
                )
            ).all()
        )
    definitions, _ = await field_definitions(
        session, set(by_slot.values()), set(), datetime.now(UTC)
    )
    output = {}
    for job, field in captures:
        slot = field.get("businessObjectFieldId")
        status, selector = field.get("status"), recorded_uuid(field.get("selectorUuid"))
        if (
            not recorded_id(slot)
            or slot not in by_slot
            or status not in EVIDENCE_STATUS
            or not selector
        ):
            continue
        field_id = by_slot[slot]
        key, version = definitions.get(field_id, (None, None))
        output[job.id, selector] = {
            "businessField": {
                "id": field_id,
                "persistentKey": key,
                "name": version.label if version else key,
            },
            "businessObjectFieldId": slot,
            "selectorUuid": selector,
            "status": status,
            "checkId": job.id,
            "checkedAt": job.completed_at,
            "snapshotId": job.source_snapshot_id,
            "selectorVersionUuid": recorded_uuid(field.get("selectorVersionUuid")),
            "observationId": field.get("observationId"),
            "evaluationId": field.get("evaluationId"),
        }
    return output


def presented_fields(presentations, captures):
    fields = [
        item
        for job, field in captures
        if (item := presentations.get((job.id, recorded_uuid(field.get("selectorUuid")))))
        is not None
    ]
    return sorted(
        fields,
        key=lambda field: (field["status"] == "FIELD_UNCHANGED", field["businessField"]["id"]),
    )


async def object_review(session, object_id, offset, limit, *, task_id=None):
    obj = (await object_presentations(session, [object_id])).get(object_id)
    if obj is None:
        raise MonitoringError(404, "BUSINESS_OBJECT_NOT_FOUND")
    params = {"object": object_id, "offset": offset, "limit": limit}
    source = f"FROM ({OBJECT_TASKS}) t WHERE t.object_id = :object"
    if task_id is not None:
        source += " AND t.id = :task"
        params["task"] = task_id
    total = await session.scalar(text(f"SELECT count(*) {source}"), params)
    tasks = (
        (
            await session.execute(
                text(f"""
        SELECT t.*, latest.id AS latest_check_id,
               CASE WHEN t.type = 'review_business_object' AND t.status = 'failed' THEN EXISTS (
                   SELECT 1 FROM tasks active
                   WHERE active.workflow_id = t.workflow_id AND active.id <> t.id
                     AND active.type = 'review_business_object'
                     AND active.status IN ('pending', 'in_progress')
                     AND active.metadata_json ->> 'monitoringKey'
                         = t.metadata_json ->> 'monitoringKey'
               ) ELSE false END AS replaced
        FROM (SELECT * {source} ORDER BY ({OPEN_TASKS}) DESC, t.created_at DESC, t.id DESC
              OFFSET :offset LIMIT :limit) t
        {LATEST_CHECK.format(statuses="'completed'")}
        ORDER BY ({OPEN_TASKS}) DESC, t.created_at DESC, t.id DESC
    """),
                params,
            )
        )
        .mappings()
        .all()
    )

    sources = {}
    if tasks:
        sources = {
            row.id: {"id": row.id, "url": row.url, "name": display_text(name), "state": row.state}
            for row, name in await session.execute(
                source_query().where(Source.id.in_({task["source_id"] for task in tasks}))
            )
        }
    check_ids = {task[key] for task in tasks for key in ("job_id", "latest_check_id") if task[key]}
    check_ids.update(job for task in tasks for _, job in finding_pointers(task))
    checks = await recorded_checks(session, check_ids)
    captures = {task["id"]: task_fields(task, checks) for task in tasks}
    fields = await present_fields(
        session, object_id, [entry for rows in captures.values() for entry in rows]
    )
    return {
        "object": obj,
        "tasks": {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [
                {
                    **task_summary(task),
                    "type": task["type"],
                    "source": sources[task["source_id"]],
                    "allowedStatuses": allowed_statuses(task),
                    "fields": presented_fields(fields, captures[task["id"]]),
                }
                for task in tasks
            ],
        },
    }


def allowed_statuses(task):
    if task["workflow_status"] != "active":
        return []
    if task["replaced"]:
        return [TaskStatus.CANCELLED]
    return sorted(TASK_STATUS_TRANSITIONS[TaskStatus(task["status"])])


async def finding_history(session, task_id, offset, limit):
    task = (
        (
            await session.execute(
                text(f"SELECT * FROM ({OBJECT_TASKS}) t WHERE t.id = :id"), {"id": task_id}
            )
        )
        .mappings()
        .one_or_none()
    )
    if task is None:
        raise MonitoringError(404, "OBJECT_REVIEW_NOT_FOUND")
    params = {
        "task": task_id,
        "source": task["source_id"],
        "origin": task["job_id"],
        "offset": offset,
        "limit": limit,
    }
    scope = """
        FROM monitoring_jobs j JOIN source_check_runs c ON c.job_id = j.id
        WHERE j.source_id = :source AND j.status = 'completed'
          AND (j.id = :origin OR EXISTS (
              SELECT 1 FROM task_references r WHERE r.task_id = :task AND r.role = 'context'
                AND r.reference_type = 'extraction_run' AND r.reference_id = j.extraction_run_id
          ))
    """
    total = await session.scalar(text(f"SELECT count(*) {scope}"), params)
    ids = (
        await session.scalars(
            text(f"""
        SELECT j.id {scope} ORDER BY c.processed_at DESC NULLS LAST, j.id DESC
        OFFSET :offset LIMIT :limit
    """),
            params,
        )
    ).all()
    checks = await recorded_checks(session, ids)
    captures = {identity: task_capture_fields(task, check) for identity, check in checks.items()}
    fields = await present_fields(
        session, task["object_id"], [entry for rows in captures.values() for entry in rows]
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "checkId": identity,
                "checkedAt": checks[identity][0].completed_at,
                "snapshotId": checks[identity][0].source_snapshot_id,
                "fields": presented_fields(fields, captures[identity]),
            }
            for identity in ids
            if identity in checks
        ],
    }
