# Sources / Acquisition — Layer 2

`SourcesService` executes SQLAlchemy queries directly through its `AsyncSession`.
The main user-facing tracking resource is a **source + concrete business object
field**. Clients supply `source_id` and `business_object_field_id`; the service
resolves the entity field and creates supporting records in the same transaction.

## Public API

Paths below are relative to `/sources`. The root `main.api` mounts this router
there; `business_layer.main.app` mounts it under `/api/v1/sources`.
Lists return `items`, `total`, `offset`, and `limit` (default/maximum 100).

| Methods | Path | Operation |
| --- | --- | --- |
| POST, GET | Collection root | Register/list sources |
| GET, PATCH, DELETE | `/{source_id}` | Read/correct/archive a source |
| POST | `/stored-files` | Register an externally stored file descriptor |
| GET | `/stored-files/{file_id}` | Read the descriptor |
| PUT | `/{source_id}/state` | Transition using `expected_state` |
| GET | `/{source_id}/state-history` | Read lifecycle history |
| GET, PUT | `/{source_id}/metadata` | Read/replace source hashes |
| GET, PUT | `/{source_id}/check-schedule` | Read/replace source cadence |
| POST, GET | `/{source_id}/warnings` | Add/list warnings |
| PATCH | `/{source_id}/warnings/{warning_id}` | Resolve, ignore, or reopen a warning |
| POST, GET | `/{source_id}/object-field-trackings` | Create a binding / list current versions |
| GET, PATCH, DELETE | `/{source_id}/object-field-trackings/{tracking_id}` | Read, append a changed version, or disable |
| GET | `/{source_id}/object-field-trackings/{tracking_id}/versions` | List all versions, oldest first |
| GET | `/{source_id}/object-field-trackings/{tracking_id}/versions/{version}` | Read one historical version |

`SourceFieldTracking` and `SourceBusinessObject` are internal records. Their former
CRUD endpoints and DTOs are removed from the public API and OpenAPI, including
nested routes requiring a source field tracking ID. Obsolete entity-link routes
are removed as well. Object field responses never expose `source_field_tracking_id`.

### Create and manage a binding

POST `/sources/7/object-field-trackings`:

```json
{
  "business_object_field_id": 50,
  "desired_refresh_seconds": 300
}
```

The response includes a stable UUID `id`, a numeric `version_id`, `version: 1`,
`source_id`, `business_object_field_id`, configuration, observation pointers,
timestamps, `valid_from`, `valid_to`, and `is_current`. `tracking_enabled` defaults
to true. A second POST for the same source/object field returns `409`, including
when the existing binding is disabled; use its UUID to re-enable it.

PATCH `/sources/7/object-field-trackings/<id>`:

```json
{
  "expected_version": 1,
  "tracking_enabled": false,
  "change_reason": "Paused by the operator"
}
```

The response retains `id`, gets a new `version_id`, and reports `version: 2`.
`expected_version` is required. A stale value returns `409`, including for otherwise
identical updates. An unchanged configuration with a matching version returns the
existing snapshot. Reasons alone do not create a new version.

`DELETE .../<id>?expected_version=2` is a soft disable and returns the resulting
snapshot (`200`). Repeating it with the current version is a no-op. Re-enable using
PATCH with `tracking_enabled: true`. No public operation deletes tracking history.
The source and business object field of a binding cannot be reassigned through PATCH.

Current listing supports `business_object_id`, `business_object_field_id`, and
`tracking_enabled` filters. Disabled bindings are included unless filtered out.
History has separate pagination, so an older version never inflates current counts.

GET `.../<id>?at=2026-09-11T12:00:00Z` reads the version effective at that instant.
Times must include an offset. The intervals are `[valid_from, valid_to)`; at a
transition boundary the successor is returned. A time before the first known
version returns `404`. `is_current` indicates whether that stored version is the
current head now, even when queried through the historical endpoint.

## Version storage and consistency

`source_object_field_trackings` uses SCD Type 2 in the existing table:

| Column | Meaning |
| --- | --- |
| `id` | Bigint primary key of one snapshot; exposed as `version_id` |
| `tracking_id` | UUID shared by all snapshots of a binding; exposed as `id` |
| `version` | Increasing integer starting at 1 |
| `valid_from`, `valid_to` | Snapshot lifetime; null `valid_to` marks the current version |
| `change_reason` | Optional explanation for this version |
| `tracking_enabled`, `desired_refresh_seconds` | Configuration of this snapshot |
| Observation references and check/change times | Acquisition state captured by this snapshot |

Each actual configuration or internal observation update inserts a complete new
snapshot. Only `valid_to` changes on the previous row; its payload, original bigint
ID, `created_at`, and `updated_at` remain unchanged. Closing and inserting commit
atomically. A failure rolls the closure back too. This is single-axis temporal
versioning, not a separate event log or bitemporal model.

All binding mutations lock the source row first. Concurrent changes using the same
`expected_version` produce one winner and a `409` for the stale writer. Partial
unique indexes allow one current row per binding UUID and one per source field /
business object field pair, including disabled rows. Another unique constraint
protects `(tracking_id, version)`. The service creates contiguous positive periods;
DB checks also reject nonpositive versions and invalid period lengths. Writes
through this service preserve snapshots; direct SQL writers must obey the same
contract (no immutability trigger is installed).

Archiving a source appends disabled versions for all its enabled current bindings
and disables the source schedule and internal field demand in the same transaction.
Already disabled bindings do not acquire a redundant version. Repeated archival is
harmless. Current and historical reads remain available after archival.

## Internal associations and acquisition

`SourceFieldTracking` is automatically reused for the source + entity field.
`SourceBusinessObject` is automatically reused for the source + object. Creating a
binding validates that the object belongs to the entity defining its field. Failed
creation rolls back newly created supporting links as well. Links remain available
as provenance when a binding is disabled or its source is archived.

The internal field tracking aggregates enabled **current** object field versions:
`tracking_enabled` is true when any is enabled, and `desired_refresh_seconds` is the
minimum explicit demand among those enabled versions. Null demand means no explicit
request. The fetch cadence remains in `SourceCheckSchedule`; configuration changes
do not start polling, fetching, Temporal, or tasks, or change canonical business data.

Worker code uses `SourcesService.record_tracking_observation(...)` with
`TrackingObservationUpdate` from `sources.schemas.internal`. It requires
`expected_version` and appends a snapshot just like configuration updates. It has no
HTTP route. Public PATCH rejects observation IDs, worker timestamps, temporal fields,
and internal association IDs.

`last_observation_id` and `baseline_observation_id` refer to Layer 3 evidence.
Updating only `last_checked_at` does not advance a baseline or `last_changed_at`.
The worker explicitly supplies `last_changed_at` after comparing observed values.
Disabled bindings and archived sources reject new worker updates.

Layer 3 observations retain their bigint `source_object_field_tracking_id`, which
identifies the exact snapshot used during acquisition. Do not replace it with the
public UUID. An observation from an earlier snapshot can be carried forward only
within the same binding UUID, source field, and business object field. Versioning
never reassigns existing observations to a different row. A worker/task can retain
`version_id` for provenance and use the stable UUID plus `expected_version` for writes.

Until the real Layer 3 `field_observations` model is registered, setting a non-null
observation pointer raises `409`. No placeholder evidence tables are registered.
Import Layer 3 models and call `register_evidence_references()` after all model imports
when integrating that layer. It attaches the two physical observation foreign keys
to metadata without executing DDL. Other Sources foreign keys are declared normally.

## Source registration and lifecycle

Register a URL with `{"type": "HTML", "url": "https://example.com/funding"}`.
HTTP(S) host casing, default ports, and fragments are normalized. Queries, path
case, and non-root trailing slashes are retained. Duplicate URLs return `409`.
Credential-bearing URLs and URLs over 2048 UTF-8 bytes are rejected.

For file-backed sources, register the descriptor after storing the bytes, then
POST `{"type": "PDF", "file_id": 1}`. At least one of URL/file is required; the
file must exist and have a matching MIME type. The descriptor API does not upload
bytes. Registration creates an `UNDISCOVERED` source, metadata, and initial state
history together. The locator/type can change only before the first state transition.

The normal lifecycle is `UNDISCOVERED → DISCOVERING → VALIDATING → ACTIVE`.
Additional transitions are in `sources/services/lifecycle.py`. `expected_state`
protects state changes. Archival is terminal; warnings can still be resolved.
`triggered_by` is domain metadata, not an authenticated user identity. The router
keeps the application's existing access model.

## Schema setup and existing data

No Alembic revision is written or changed by this implementation. Use the existing
model loader and generate the revision against your development PostgreSQL database:

```bash
python -m alembic revision --autogenerate -m "version source object field tracking"
# Review the generated revision before applying it.
python -m alembic upgrade head
```

The existing table, all its columns, bigint IDs, payloads, and foreign-key targets
are retained. The added non-null columns have database defaults: a fresh UUID per
existing row, `version = 1`, and `valid_from = now()`. Existing rows therefore become
initial snapshots when the generated schema change is applied; no historical state
before that conversion is reconstructed. Their original timestamps are preserved.
The old unconditional source-field/object-field uniqueness constraint must be
replaced by the current-row partial index in the generated revision.

The new per-object refresh demand initially defaults to null; existing source
schedules are unchanged. Legacy field-level demand remains in the internal table
until recalculated from current object field settings on their next configuration
change. Set desired demand on concrete bindings through the new API.

For PostgreSQL's Alembic autogeneration, review check constraints as well: Alembic's
autogenerate support for their changes is limited. The required definitions are on
`SourceObjectFieldTracking.__table_args__`. No schema changes run at application
startup. `HOST_DATABASE_URL` is used by Alembic, and `DCKR_DATABASE_URL` by the API.
Use Python 3.13 or 3.14 as declared by the project. The checked-in `openapi.json`
comes from the root `main.api`; the live schema is always available at `/openapi.json`.

## Verification

```bash
python -m pytest tests/test_sources.py -q
```

Tests cover public contracts, automatic association reuse, object/source ownership,
historical payload preservation, temporal boundaries, stale writes, no-ops, soft
disable/re-enable, transaction rollback, archive behavior, and historical evidence
ownership, along with source registration, metadata, schedules, and warnings.

For PostgreSQL locking and concurrency checks, use a dedicated test database:

```bash
SOURCES_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/burbot_test \
  python -m pytest tests/test_sources.py -q
```

Tests create/drop an isolated schema per case. Without that URL, the two PostgreSQL
concurrency tests are skipped and the other tests use SQLite with the real models.
