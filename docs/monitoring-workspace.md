# Monitoring Review Workspace

The workspace reads monitoring checks, their captured field outcomes, current
Business Layer values, and Task state. Apply Alembic revision
`m103_monitoring_source_history` before running the backend. It adds an index on
the source and creation order of jobs.

## Operator API

Each route uses the existing Monitoring operator Bearer credential and returns
`Cache-Control: no-store`. All routes in this table use GET.

| Path | Query parameters | Response |
| --- | --- | --- |
| `/monitoring/objects` | `offset`, `limit` | Open reviews grouped by BusinessObject ID, with the name, stored code, entity, distinct affected slots and Sources, task count, severity, status, and last check time. |
| `/monitoring/objects/{object_id}/review` | `offset`, `limit`, optional `taskId` | Object display data and a page of Source-scoped tasks. Open tasks appear first. Each task includes recorded findings, unchanged fields from the latest completed check when available, and allowed status transitions. |
| `/monitoring/object-reviews/{task_id}/history` | `offset`, `limit` | Captures associated with the task, newest first, with the field, selector version, evaluation, observation, and snapshot IDs. |
| `/monitoring/attention/sources` | `offset`, `limit`, `search`, `issue`, `sort`, `includeAll` | `{items, total, offset, limit}`. Each source includes `id`, `name`, `url`, `state`, `lastCheck`, `counts`, `openTaskCount`, `severity` and `reason`. |
| `/monitoring/sources/{source_id}/review` | Optional `checkId`, `tasksOffset`, `tasksLimit` | Source metadata, `latestCheck`, `latestCompletedCheck`, `selectedCheck`, its `snapshot`, `fields`, and the `earlierTasks` page. |
| `/monitoring/reviews/{task_id}` | None | Evidence and canonical value for the task's originating check, captured diagnostics, and readable task references. |
| `/monitoring/sources/{source_id}/review/{check_id}/{selector_uuid}` | None | `{selector, evaluation, extractionRunId}` for the recorded field result. |
| `/monitoring/sources/{source_id}/history?summary=true` | `offset`, `limit` | Paginated check summaries with check status, time, change status, error code, run ID, and snapshot ID. The existing history response is still available with the default query. |
| `/monitoring/sources/{source_id}/snapshots/{snapshot_id}/preview` | None | Passive `text/html` with a restrictive CSP. Use an iframe with an empty `sandbox` attribute. |
| `/monitoring/sources/{source_id}/snapshots/{snapshot_id}/content` | Optional `metadataOnly=true` | JSON with `source`, `snapshot`, `artifact` and the UTF-8 HTML in `html`. Metadata-only reads return `html: null` and read the database record. |
| `/monitoring/sources/{source_id}/snapshots/{snapshot_id}/download` | None | Exact stored bytes as an `application/octet-stream` attachment named `snapshot-{snapshot_id}.html`. |

Most recent means the latest completed or failed job by creation order. An
in-flight or cancelled job does not replace a settled result. A failed job
without evaluations leaves configured fields unchecked. Use `checkId` to
inspect a historical job and the snapshot from that particular acquisition.
The history view includes checks which reused an earlier snapshot.

## Object reviews

Monitoring creates one open `REVIEW_BUSINESS_OBJECT` task per affected object
and Source. The object's slot owner is the `business_object` target. The task
remains in the Source workflow and carries forward with its original ID when a
snapshot advances the workflow. Different Sources keep independent task statuses
and share one Inbox row for the object. A slot contributes once to the Inbox
field count even when several selectors or Sources monitor it.

Each check stores its slot, selector version, evaluation, observation and
outcome in `SourceCheckRun.field_results`. Multiple field results can reference
the same task. The task retains the originating check, an index of the latest
distinct findings per selector, and context references to the relevant
captures, slots, and observations. The recorded check retains the evidence and
the executed SelectorTree version. Identical findings reuse the existing task,
and a materially different finding can start a new review after completion.
A failed review can be retried while its object and Source have no replacement
open review.

Legacy `REVIEW_SOURCE_CHANGE` tasks remain available through the original review
endpoint and appear under their object when the recorded slot identifies a
single owner. Unbound observations still use `RESOLVE_OBSERVATION` and the
explicit `POST /extraction/observations/{observation_id}/resolve-object`
operation. HTTP failures and page timeouts
belong to the Source and appear in Attention. The Inbox ranks missing,
ambiguous, conflicting and failed extraction findings above changed evidence,
followed by initial evidence.

## Source and field review

Attention counts come from the latest settled check, with one outcome per
selector-backed field binding. Open tasks are counted independently from live
task state on active workflows. The task's originating job identifies its
capture even when a later check reuses the same task ID. The source review
includes currently configured fields when viewing the latest check and
capture-bound fields when viewing an earlier check.

Attention ranks failed jobs, extraction problems, and open high-priority field
reviews first. Other open reviews and website changes with incomplete coverage
are normal priority. Website changes with complete field coverage can be
informational. Healthy monitored sources are available with `includeAll=true`.
Sort by `priority` or `last_checked`. Issue values are `changed`, `missing`,
`extraction_failed`, `initial`, `ambiguous`, `conflict`, `source_changed`,
`job_failed`, and `open_tasks`. Search accepts a source ID or a case-insensitive
URL substring. A Source's `name` is its original file name when available. The
Studio can use the hostname for a Source with a URL.

Field rows contain the business field and optional named business object, live
canonical value and value ID, previous/current evidence, captured selector and
evaluation identifiers, and any linked task. Missing evidence and unchecked
fields have distinct statuses. Definitions and diagnostics are read only when
the inspector opens and use the job's pinned version. Legacy results may have
unavailable evidence or diagnostics. Snapshot viewing uses authorized metadata.

Task and source review expose optional `canonicalDisplay` alongside
`canonicalValue` and `canonicalValueId`. It contains the field `kind` from the
definition that validated the value and its unchanged `rawValue`. Lists include
`itemKind` and typed `items`. `reference` targets use BusinessObject and the
declared reference entity, while `source` targets use Source. A linked target has
an optional `target` descriptor and `resolved` status. Missing or incompatible
targets display their ID when available. Unknown types use their raw JSON.

Object names use the current textual field identified by the entity version's
`definition_json.display_field` persistent key when it has a value. For the
Firefox model, `BusinessModel.metadata_json.extensionEntities` maps an exact
entity table to the corresponding type in the extension sync manifest. Its
`primaryLabelField` identifies the synced canonical value, such as Project
`name` or Recruitment `external_number`. Extension records bind to a stable
BusinessObject ID through their workspace and external ID. The browser-local
`object.label` has no sync field. The fallback order is `name`, `title`, then
`BusinessObject #<id>` in Studio. A stored `code_field`, Project `number`, or
`code` can appear alongside the name.

Source values use the URL or original file name. A resolved label has
`labelBasis: "current"`, including when the evidence comes from an earlier
capture. The task and source review read the effective canonical value at
request time. Reference resolution describes the stored target. Extracted
evidence retains its recorded text and validation state.

The shared `businessField` presentation includes `persistentKey`, the field
`kind`, and `referenceEntity` where applicable. Task reviews also expose the
slot owner as `businessObject` and `referenceDisplays` keyed by TaskReference ID.
Reference displays use the source label, snapshot capture time, extraction run
status, or recorded observation/field text where available.

## HTML Snapshot Viewer

Open **View snapshot** in Source Review, Monitoring History, Task Details,
Evidence Review, Object Review history, or the Field Inspector. The Studio opens
`#/monitoring/sources/:sourceId/snapshots/:snapshotId` with the snapshot ID from
that check or task. A check that reused a snapshot opens the same viewer URL.

The backend validates ownership, reads through the private SnapshotStorage S3
client, enforces the 5 MiB capture limit, and verifies recorded size and artifact
SHA-256. The artifact digest comes from StoredFile. Snapshot content and
structure hashes describe comparisons. `artifact` is `null` when the file
record is missing. Preview, source, and download return errors for missing,
corrupt, oversized, or unsupported artifacts. The Details tab still shows the
recorded capture metadata.

Preview rebuilds HTML from passive tags and attributes with script execution,
forms, navigation, and resource loading disabled. HTML Source displays the
stored text in the read-only Monaco editor. The original download uses the
stored bytes. The local Vite proxy forwards the three explicit GET routes with
its server-side operator credential. Production Studio keeps operator snapshot
access disabled.

Completing a review uses the existing Task status operation. Field statuses
describe extraction outcomes from their recorded checks. Baseline acceptance
and canonical value changes use separate operations.
