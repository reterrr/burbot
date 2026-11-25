"""Page monitored sources using their latest settled check and live task states."""

from typing import Literal

from sqlalchemy import text

from monitoring.presentation import display_text

AttentionIssue = Literal[
    "changed",
    "missing",
    "extraction_failed",
    "initial",
    "ambiguous",
    "conflict",
    "source_changed",
    "job_failed",
    "open_tasks",
]
AttentionSort = Literal["priority", "last_checked"]

# A carried task belongs to the job that created it, even when a later check reuses its ID.
MONITORING_TASKS = """
    SELECT t.id, t.title, t.type, t.status, t.created_at, t.metadata_json, t.workflow_id,
           w.status AS workflow_status,
           j.id AS job_id, j.source_id, j.source_snapshot_id, j.completed_at,
           t.metadata_json ->> 'evidenceStatus' AS evidence_status
    FROM tasks t
    JOIN workflows w ON w.id = t.workflow_id
    JOIN monitoring_jobs j ON j.source_id = w.source_id AND j.id = CASE
        WHEN t.metadata_json ->> 'monitoringJobId' ~*
             '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        THEN CAST(t.metadata_json ->> 'monitoringJobId' AS uuid)
    END
"""
OPEN_TASKS = "status IN ('pending', 'in_progress') AND workflow_status = 'active'"

ATTENTION = text(f"""
    WITH candidates AS (
        SELECT s.id, s.url, s.state, f.original_name AS name
        FROM monitoring_sources ms JOIN sources s ON s.id = ms.source_id
        LEFT JOIN stored_files f ON f.id = s.file_id
        WHERE CASE WHEN CAST(:source_id AS bigint) IS NOT NULL THEN s.id = :source_id
                   ELSE :search = '' OR strpos(lower(s.url), lower(:search)) > 0 END
    ),
    task_totals AS (
        SELECT source_id, count(*) AS open_tasks,
               bool_or(evidence_status IN (
                   'CHANGED', 'MISSING', 'AMBIGUOUS', 'CONFLICT', 'EXTRACTION_FAILED'
               )) AS urgent_task
        FROM ({MONITORING_TASKS}) t
        WHERE {OPEN_TASKS} AND source_id IN (SELECT id FROM candidates)
        GROUP BY source_id
    ),
    outcomes AS (
        SELECT s.*, j.id AS job_id, j.status AS job_status, j.source_snapshot_id,
               j.error_code, coalesce(j.completed_at, c.processed_at, j.created_at) AS checked_at,
               c.change_status,
               c.change_status IN ('CONTENT_CHANGED', 'STRUCTURE_CHANGED',
                                    'CONTENT_AND_STRUCTURE_CHANGED') AS source_changed,
               coalesce(t.open_tasks, 0) AS open_tasks,
               coalesce(t.urgent_task, false) AS urgent_task,
               counts.*
        FROM candidates s
        LEFT JOIN LATERAL (
            SELECT j.id, j.status, j.source_snapshot_id, j.error_code,
                   j.completed_at, j.created_at
            FROM monitoring_jobs j
            WHERE j.source_id = s.id AND j.status IN ('completed', 'failed')
            ORDER BY j.created_at DESC, j.id DESC
            LIMIT 1
        ) j ON true
        LEFT JOIN source_check_runs c ON c.job_id = j.id
        LEFT JOIN task_totals t ON t.source_id = s.id
        CROSS JOIN LATERAL (
            SELECT count(*) FILTER (WHERE field->>'status' = 'FIELD_CHANGED') AS changed,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_MISSING') AS missing,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_EXTRACTION_FAILED') AS failed,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_NEW') AS initial,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_UNCHANGED') AS unchanged,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_AMBIGUOUS') AS ambiguous,
                   count(*) FILTER (WHERE field->>'status' = 'FIELD_CONFLICT') AS conflict,
                   count(*) AS checked_fields,
                   coalesce(array_agg(field->>'selectorUuid'), ARRAY[]::text[]) AS checked_selectors
            FROM jsonb_array_elements(CASE
                WHEN jsonb_typeof(c.field_results) = 'array' THEN c.field_results
                ELSE '[]'::jsonb
            END) AS fields(field)
            WHERE field->>'selectorUuid' IS NOT NULL OR field->>'evaluationId' IS NOT NULL
        ) counts
    ),
    ranked AS (
        SELECT o.*, changed + missing + failed + ambiguous + conflict AS problems,
               CASE
                   WHEN job_status = 'failed' THEN 'job_failed'
                   WHEN missing + failed + ambiguous + conflict > 0 THEN 'field_problems'
                   WHEN open_tasks > 0 THEN 'open_tasks'
                   WHEN source_changed AND (
                       checked_fields = 0 OR EXISTS (
                           SELECT 1 FROM selectors sel
                           WHERE sel.source_id = o.id AND sel.active_version_id IS NOT NULL
                             AND NOT coalesce(
                                 CAST(sel.uuid AS text) = ANY(checked_selectors), false
                             )
                       )
                   ) THEN 'source_changed_incomplete_coverage'
                   WHEN source_changed AND unchanged = checked_fields
                       THEN 'source_changed_fields_unchanged'
                   WHEN source_changed THEN 'source_changed'
               END AS reason
        FROM outcomes o
    ),
    filtered AS (
        SELECT r.*,
               CASE WHEN reason IN ('job_failed', 'field_problems') OR urgent_task THEN 0
                    WHEN reason IN ('open_tasks', 'source_changed_incomplete_coverage') THEN 1
                    ELSE 2 END AS priority
        FROM ranked r
        WHERE (:include_all OR reason IS NOT NULL) AND CASE :issue
            WHEN 'changed' THEN changed > 0
            WHEN 'missing' THEN missing > 0
            WHEN 'extraction_failed' THEN failed > 0
            WHEN 'initial' THEN initial > 0
            WHEN 'ambiguous' THEN ambiguous > 0
            WHEN 'conflict' THEN conflict > 0
            WHEN 'source_changed' THEN source_changed
            WHEN 'job_failed' THEN job_status = 'failed'
            WHEN 'open_tasks' THEN open_tasks > 0
            ELSE true END
    )
    SELECT page.*, totals.total
    FROM (SELECT count(*) AS total FROM filtered) totals
    LEFT JOIN (
        SELECT * FROM filtered
        ORDER BY CASE WHEN :sort = 'priority' THEN priority END, checked_at DESC NULLS LAST, id
        OFFSET :offset LIMIT :limit
    ) page ON true
    ORDER BY CASE WHEN :sort = 'priority' THEN priority END, checked_at DESC NULLS LAST, id
""")


async def attention_sources(session, *, search, issue, sort, include_all, offset, limit):
    search = search.strip()
    digits = search.removeprefix("#")
    source_id = None
    if digits.isascii() and digits.isdecimal():
        digits = digits.lstrip("0")
        source_id = int(digits or "0") if len(digits) <= 19 else 0
        if source_id >= 2**63:
            source_id = 0
    rows = (
        (
            await session.execute(
                ATTENTION,
                {
                    "search": search,
                    "source_id": source_id,
                    "issue": issue or "",
                    "sort": sort,
                    "include_all": include_all,
                    "offset": offset,
                    "limit": limit,
                },
            )
        )
        .mappings()
        .all()
    )
    return {
        "total": rows[0]["total"],
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": row["id"],
                "url": row["url"],
                "name": display_text(row["name"]),
                "state": row["state"],
                "lastCheck": {
                    "id": row["job_id"],
                    "status": row["job_status"],
                    "checkedAt": row["checked_at"],
                    "changeStatus": row["change_status"],
                    "errorCode": row["error_code"],
                    "snapshotId": row["source_snapshot_id"],
                }
                if row["job_id"]
                else None,
                "counts": {
                    "changed": row["changed"],
                    "missing": row["missing"],
                    "extractionFailed": row["failed"],
                    "initial": row["initial"],
                    "unchanged": row["unchanged"],
                    "ambiguous": row["ambiguous"],
                    "conflict": row["conflict"],
                    "problems": row["problems"],
                },
                "openTaskCount": row["open_tasks"],
                "severity": ("high", "normal", "informational")[row["priority"]],
                "reason": row["reason"],
            }
            for row in rows
            if row["id"] is not None
        ],
    }
