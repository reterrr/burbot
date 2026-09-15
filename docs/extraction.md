# Extraction service

The active backend now supports snapshot-based capture in addition to the existing
`POST /extractions` workflow submission. It records evidence and source-specific
tracking state. It never creates BusinessObjects, chooses source trust policy, or
reads/writes canonical `BusinessObjectFieldValue` rows.

## Frontend workflow

1. Resolve/create the Source and business object identities through their owning services.
2. Register immutable snapshot metadata with `POST /sources/{source_id}/snapshots`.
   For persisted bytes, register a StoredFile through the existing Sources API and
   include its `file_id`. Metadata-only snapshots support manual capture; automatic
   adapters need the actual saved snapshot bytes.
3. Register token definitions once with `POST /extraction/token-classes`.
4. Create a pending run with `POST /extraction/runs`.
5. Submit the complete local graph to `POST /extraction/runs/{run_id}/capture`.
6. Send `reconciliation_observations` to the reconciliation layer. Keep unresolved
   observations for object resolution. Neither list changes canonical business data.

The existing `main.api` mounts these paths directly. Add your deployment's API
prefix when using a reverse proxy or mounting the routers under a prefix.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/sources/{source_id}/snapshots` | Register immutable acquisition metadata |
| GET | `/sources/{source_id}/snapshots/{snapshot_id}` | Read one snapshot |
| POST | `/extraction/token-classes` | Idempotently register a named literal type |
| POST | `/extraction/runs` | Create a pending run for an existing snapshot |
| GET | `/extraction/runs/{run_id}` | Inspect lifecycle and failure details |
| POST | `/extraction/runs/{run_id}/capture` | Commit the complete extraction graph |
| GET | `/extraction/runs/{run_id}/capture` | Retrieve the original committed receipt |
| GET | `/extraction/observations/{observation_id}` | Read an interpretation and its literals |
| POST | `/extraction/observations/{observation_id}/resolve-object` | Attach an existing object |
| POST | `/extraction/runs/{run_id}/execute` | Execute through a configured snapshot adapter |

The legacy `/extractions`, `/extractions/{id}` endpoints remain available. They
retain the existing `completed` status and workflow request shape. New run statuses
are `pending`, `running`, `succeeded`, `partial`, and `failed`, following the existing
lowercase API convention. A workflow is optional on the new create-run endpoint;
when supplied it must be active and reference exactly the run's source/snapshot.

Errors use 404 for missing resources, 422 for invalid graphs or business bindings,
409 for state/idempotency conflicts, and 501 when automatic execution has no adapter.

## Copyable requests

The IDs below are illustrative: entity `42` is Recruitment, field `101` belongs to
that entity, object `1001` is an already resolved recruitment, and snapshot `123`
belongs to the page or file being captured. Replace them with IDs from your model.

| Request file | Send to |
| --- | --- |
| [Create snapshot](examples/extraction/create-snapshot.json) | `POST /sources/{source_id}/snapshots` |
| [Register text token](examples/extraction/create-token-class.json) | `POST /extraction/token-classes` |
| [Create run](examples/extraction/create-run.json) | `POST /extraction/runs` |
| [Manual HTML, resolved Recruitment](examples/extraction/manual-html-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Unresolved Recruitment](examples/extraction/unresolved-object-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Harmonogram PDF](examples/extraction/harmonogram-pdf-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Harmonogram XLSX](examples/extraction/harmonogram-xlsx-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Resolve Recruitment](examples/extraction/resolve-recruitment.json) | `POST /extraction/observations/{id}/resolve-object` |
| [Execute later snapshot](examples/extraction/execute-later-snapshot.json) | `POST /extraction/runs/{new_run_id}/execute` |

For PDF/XLSX examples, create a Source of type `PDF`/`XLSX` and register that file's
snapshot first. Use `application/pdf` or
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` as its MIME type.
The downloadable harmonogram is its own Source, distinct from the HTML downloads
page. Discovering a newly published file and tracking the parent page's links remain
acquisition/discovery responsibilities. A parsed row can represent a planned
Recruitment without creating a separate Harmonogram business entity.

Create a new run for each later snapshot. Reuse the source's definitions; do not
reuse a successful run with new content. `/execute` returns 501 until the application
configures its execution adapter (see below).

## Batch graph and identity

- `scopes` declares reusable, source-specific definitions. Exactly one parentless
  scope is named `ROOT`; it may have no business entity. Scope names are unique per
  source. Business meaning uses existing `BusinessEntityField` IDs instead of a
  parallel hardcoded `target_fields` registry.
- `scope_instances` declares concrete occurrences. Ten rows share one scope
  definition and have ten instances. `occurrence_index` is zero-based within the
  parent occurrence. Position and hashes never decide business-object identity.
- `elements` declares document nodes. HTML, PDF, and XLSX each require exactly their
  corresponding subtype metadata. All nodes are inside the root document element.
- `values` associates a literal with one field in one occurrence. One field
  interpretation is allowed per occurrence in a batch. Different occurrences may
  have different values for the same field. Selectors within a shared scope must be
  reusable and agree across repeated rows.
- Local `client_key` references can appear in any order. Duplicate/missing keys,
  cyclic parents, wrong entity/object bindings, and out-of-scope elements are rejected.
- HTML character offsets are Python/Unicode code-point offsets into `text_content`,
  using `[char_start, char_end)`. Convert Firefox's JavaScript UTF-16 offsets before
  sending, or omit both offsets. Provided offsets must select exactly `raw_value`.
- Raw literals are required. `normalized_value=null` means normalization was not
  provided and comparisons fall back to raw text. Only `is_semantic_null=true`, with
  explicit source text such as `brak`, represents semantic null.
- `issues` records `VALUE_NOT_FOUND`, `SELECTOR_BROKEN`, or `AMBIGUOUS_MATCH`. An
  issue-only capture finishes as `partial`; missing values create no null literals
  and never clear canonical data.

Token IDs remain strings such as `text` and `date`, preserving existing extension
payloads. New capture validates their existence. The legacy endpoint registers its
previously free-form token IDs on first use. Token regex/parser names are metadata;
actual parsing/normalization belongs to the execution adapter, and business-value
validation belongs to reconciliation.

## Transactions, history and baselines

Capture holds the source row lock shared with SourcesService, then the run lock;
workflow-backed requests acquire the workflow lock first. Database unique indexes
and `ON CONFLICT DO NOTHING` protect reusable identities, including object-field
slots that may be discovered concurrently from different sources.

A successful run has one persisted capture receipt. The globally unique
`capture_key` plus a canonical JSON payload hash makes identical retries return
exactly that receipt, including its original ID maps. Reusing a key for a different
run or changing a successful payload returns 409. Retry clients must preserve list
order, keys, and payload. Creating a run is a separate operation: save its returned ID.

Capture uses one savepoint inside the request transaction. Failure rolls back its
elements, definitions, bindings, observations and ground truth, then persists the
run as `failed`. Fix the payload and retry that run, or create another run. Request
shape errors and preflight conflicts do not start a run. A process crash before
commit leaves the prior durable state; no intermediate `running` state is committed.

Definitions use append-only versions: only `valid_to` closes an old version. A
changed parent scope reparents successor child definitions and carries their
selectors; a changed entity does not inherit the old entity's field selectors.
Evidence retains the exact versions used when it was captured.

Object-field tracking remains SCD2. An observation references the binding version
current when it was captured; updating observation pointers creates a successor
tracking version. The stable `tracking_id` ties these versions together. Shared
version-writing code lives in `sources/services/tracking.py`.

Baseline policy lives in `extraction/services/tracking.py`:

- Human-confirmed observations are `VALIDATED` and receive one GroundTruth row.
  Other observations are `DETECTED`.
- Detected observations update the last/check pointers without accepting a baseline.
  Validated observations initialize or advance the source baseline.
- Comparison uses `(token_class_id, is_semantic_null, normalized-or-raw value)`.
  Canonical BusinessObjectFieldValue is never part of this comparison.
- The first accepted baseline has no change timestamp. A different later accepted
  value advances the baseline and `last_changed_at`; an equal value preserves them.
- Evidence from older snapshots is stored without rewinding tracking pointers.
- `changed_source_object_fields` contains IDs of the new SourceObjectFieldTracking
  versions whose source baseline changed. `reconciliation_observations` contains
  only resolved, validated observations. `resolved_observations` also includes
  detected evidence, so do not treat that list as an automatic acceptance decision.

Object resolution preserves the observation ID and its review status. It checks
other resolved fields in the same occurrence for incompatible object identity.
The capture receipt is an immutable original result; read the observation endpoint
for its current resolution. Merely observing a newer snapshot does not supersede
older evidence. Explicit `supersedes_observation_id` is supported for a validated
replacement with consistent source/object/field identity.

## Service structure and adapter boundary

`ExtractionService` exposes `create_run`, `register_capture`,
`resolve_observation_object`, and `execute` alongside the legacy methods.
`CaptureService` coordinates lifecycle/transactions; `CaptureWriter` handles scopes,
elements, occurrences, selectors, bindings, literals and observations;
`ExtractionRepository` owns the shared queries and conflict-safe inserts.

Implement `SnapshotExtractor` from `extraction/services/adapters.py` and assign it to
`api.state.snapshot_extractor`, or inject it into `ExtractionService(session, adapter)`.
Its `extract(snapshot, definitions, capture_key=...)` method receives saved snapshot
metadata and the active definitions, and returns the same `CaptureRequest` graph.

Adapters must use existing definitions, omit field-selector updates, avoid
human-confirmation claims, use `AUTOMATIC` discovery, and report missing/ambiguous
values as issues. Definitions are checked again under the source lock before
commit. An adapter error marks the run failed. The service does not download URLs,
open Playwright, perform OCR, execute arbitrary parser names, or invent objects.
Browser/PDF/XLSX readers, object deduplication, scheduling, and reconciliation remain
separate responsibilities.

## Database setup and validation

Run `alembic upgrade head` with `HOST_DATABASE_URL` configured. Two migrations follow
`c67ac5d0c446`:

1. `e100_extraction_legacy` registers the three previously unmigrated workflow
   extraction tables. It preserves existing tables created with the old models.
2. `e101_extraction_capture` adds snapshots, definitions, element subtypes, ground
   truth, capture receipts, issues, nullable unresolved bindings, status fields,
   normalized literals, token references and the source/evidence pointer FKs.

Legacy evidence is retained. No fabricated snapshots or normalized baselines are
backfilled. Downgrading refuses when captures or workflow-free runs would be lost;
PostgreSQL enum labels added to existing enum types remain on a downgrade.

Run `pytest -q` for local SQLite integration checks and PostgreSQL DDL compilation.
Set `EXTRACTION_TEST_DATABASE_URL=postgresql+asyncpg://...` to also test source locks,
concurrent captures and the complete migration chain in isolated PostgreSQL schemas.
The extraction GitHub Actions workflow provisions PostgreSQL 18 and checks upgrade,
legacy preservation, capture behavior, downgrade/re-upgrade and linting.
