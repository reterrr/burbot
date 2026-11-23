# Tasks and review API

Monitoring records review work in Tasks and Workflows. Each task links to the
Source and snapshot behind its evidence. Field reviews also link to the field and
any available extraction run and observations. A source-only review links to the
snapshots being compared. See [automatic review tasks](monitoring.md#automatic-review-tasks).

## Inbox and history

Use the bearer token configured in `MONITORING_ADMIN_TOKEN` for `/tasks` and
`/monitoring/reviews`. This is the same operator credential used to approve Sources.

| Request | Result |
| --- | --- |
| `GET /tasks/inbox` | Pending and in-progress tasks in active workflows, newest first |
| `GET /tasks/inbox/count` | Total number of actionable tasks matching the filters, as a JSON integer |
| `GET /tasks/{task_id}` | Task record and references |
| `GET /tasks/sources/{source_id}/workflows` | Paginated workflow history, including superseded workflows |
| `GET /tasks/workflows/{workflow_id}/tasks` | Paginated task history for a workflow, including completed and cancelled tasks |
| `GET /monitoring/reviews/{task_id}` | Original review context and the current task status |
| `PATCH /tasks/{task_id}/status` | Updated task record and references |

Inbox and count accept `source_id`, `type`, and `reason`. The filters are combined
with AND. Inbox returns `items`, `total`, `offset`, and `limit` and accepts an
`offset` of 0 or more and a `limit` of 1 to 100. The default page size is 20.
Count and `total` describe all matching tasks before pagination. The Inbox item
identifies the current workflow snapshot. Use the task's references or review
details for the original snapshot after a task has moved to a newer workflow.

```bash
BURBOT_API_URL=http://127.0.0.1:8000
auth_header="Authorization: Bearer $MONITORING_ADMIN_TOKEN"

curl -fsS -H "$auth_header" \
  "$BURBOT_API_URL/tasks/inbox?source_id=123&type=review_source_change&reason=value_changed&limit=20&offset=0"
curl -fsS -H "$auth_header" \
  "$BURBOT_API_URL/tasks/inbox/count?source_id=123&type=review_source_change&reason=value_changed"
curl -fsS -H "$auth_header" "$BURBOT_API_URL/tasks/42"
curl -fsS -H "$auth_header" "$BURBOT_API_URL/monitoring/reviews/42"
curl -fsS -H "$auth_header" "$BURBOT_API_URL/tasks/sources/123/workflows"
curl -fsS -H "$auth_header" "$BURBOT_API_URL/tasks/workflows/7/tasks"
```

## Task status

In an active workflow, a `pending` task can enter `in_progress`, `completed`,
`failed`, or `cancelled`. An `in_progress` task can enter `completed`, `failed`,
or `cancelled`. A `failed` task can be retried by moving to `pending` or
`in_progress`, or can be cancelled. `completed` and `cancelled` are terminal.
Status changes in a superseded workflow return `409`. Invalid transitions
within an active workflow return `422`.

```bash
curl -fsS -X PATCH -H "$auth_header" -H 'Content-Type: application/json' \
  -d '{"status":"completed"}' "$BURBOT_API_URL/tasks/42/status"
```

Completion closes the review. Accepting an observation or editing a canonical
value still takes an explicit operation through Extraction or the Business Layer.

## Review details

`reviewType` identifies the review response. `changeTimestamp` records when
monitoring acquired the evidence. `requiresReview` reflects a pending or
in-progress task in an active workflow.

A changed field has its original evidence and observation IDs alongside the
canonical value read from the Business Layer at request time.

```json
{
  "taskId": 42,
  "taskStatus": "pending",
  "sourceId": 123,
  "monitoringJobId": "924efc38-ad09-4611-8a96-15b8f006aee3",
  "changeTimestamp": "2026-11-23T10:00:00Z",
  "requiresReview": true,
  "reviewType": "field",
  "sourceSnapshotId": 21,
  "businessObjectFieldId": 314,
  "selectorVersionId": 8,
  "selectorVersionUuid": "bc4e738b-3156-4b9f-8b71-90d8a26eeb93",
  "canonicalValueId": 501,
  "canonicalValue": "Open to small businesses",
  "previousObservationId": 37,
  "observationId": 41,
  "previousEvidence": "Open to small businesses",
  "currentEvidence": "Open to small and medium-sized businesses",
  "evaluationId": 86,
  "baselineObservationId": 37,
  "comparison": "accepted_baseline",
  "evidenceStatus": "CHANGED",
  "evidenceChanged": true
}
```

A source-only review supplies the change classification, snapshots, and hashes.

```json
{
  "taskId": 43,
  "taskStatus": "in_progress",
  "sourceId": 123,
  "monitoringJobId": "3f3f0d4e-79b9-4b28-9a3a-9781f8f26e5d",
  "changeTimestamp": "2026-11-23T11:00:00Z",
  "requiresReview": true,
  "reviewType": "source",
  "changeStatus": "CONTENT_CHANGED",
  "previousSnapshotId": 21,
  "currentSnapshotId": 22,
  "previousContentHash": "1111111111111111111111111111111111111111111111111111111111111111",
  "currentContentHash": "2222222222222222222222222222222222222222222222222222222222222222",
  "previousStructureHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "currentStructureHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```
