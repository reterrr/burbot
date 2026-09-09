# Layer 2 — Sources / Acquisition

The `sources` module implements Layer 2 from the supplied generic Burbot DBML.
It runs inside the existing FastAPI application and shares its PostgreSQL database.
`SourcesService` executes SQLAlchemy queries directly through `AsyncSession`.

## Tables

| Model | Table | Purpose |
| --- | --- | --- |
| StoredFile | `stored_files` | Describe externally stored bytes |
| Source | `sources` | HTML/PDF acquisition identity with URL, file reference, or both |
| SourceMetadata | `source_metadata` | Latest content/structure hashes |
| SourceCheckSchedule | `source_check_schedules` | One configured fetch cadence per source |
| SourceStateHistory | `source_state_history` | Lifecycle history |
| SourceWarning | `source_warnings` | Source warnings and their resolution |
| SourceBusinessEntity | `source_business_entities` | Contextual association with an entity type |
| SourceBusinessObject | `source_business_objects` | Association with a known concrete object |
| SourceFieldTracking | `source_field_trackings` | Source + logical entity field |
| SourceObjectFieldTracking | `source_object_field_trackings` | Source + exact business object field |

Column names follow the DBML, including `sources.type` and nullable `sources.url`.
Identifiers and their references use PostgreSQL `bigint`. Runtime hashes are stored
in `source_metadata`; source registration does not contain fetch status or extraction
results. The active models are independent of the old `schemas.core.db` registry.

## Schema setup

No handwritten migration is included. The model loader imports the active business
and Sources models so Alembic can discover the changes. Use Python 3.13 or 3.14,
configure `.env` from `.env.example`, and connect to your development database:

```bash
python -m pip install -e '.[dev]'
mkdir -p migrations/versions
python -m alembic revision --autogenerate --version-path migrations/versions -m "sources layer"
```

After reviewing the generated revision, apply it and run the existing application:

```bash
python -m alembic upgrade head
python -m business_layer.main
```

`HOST_DATABASE_URL` is the async PostgreSQL URL Alembic uses. `DCKR_DATABASE_URL`
is the async PostgreSQL URL reachable from the application; set it to the host URL
when running the application outside Docker. Swagger UI is at `/docs`, with the live
schema at `/openapi.json`. No schema changes run automatically on application startup.

## API

All paths below are relative to `/api/v1/sources`. Lists return `items`, `total`,
`offset`, and `limit`; the default and maximum limit are 100. Source listing supports
`type`, `state`, and normalized `url` filters. Warning listing supports `status` and
`severity` filters.

| Methods | Path | Operation |
| --- | --- | --- |
| POST | `/stored-files` | Register a stored-file descriptor |
| GET | `/stored-files/{file_id}` | Read the descriptor |
| POST, GET | Collection root | Register/list sources |
| GET, PATCH, DELETE | `/{source_id}` | Read/correct/archive a source |
| PUT | `/{source_id}/state` | Compare expected state and transition |
| GET | `/{source_id}/state-history` | Read chronological history |
| GET, PUT | `/{source_id}/metadata` | Read/replace latest hash metadata |
| GET, PUT | `/{source_id}/check-schedule` | Read/replace source cadence |
| POST, GET | `/{source_id}/warnings` | Add/list warnings |
| PATCH | `/{source_id}/warnings/{warning_id}` | Resolve, ignore, or reopen a warning |
| GET | `/{source_id}/business-entities` | List contextual entity links |
| PUT, DELETE | `/{source_id}/business-entities/{entity_id}` | Link/unlink an entity type |
| GET | `/{source_id}/business-objects` | List concrete object links |
| PUT, DELETE | `/{source_id}/business-objects/{object_id}` | Link/unlink a known object |
| POST, GET | `/{source_id}/field-trackings` | Create/list field tracking contracts |
| GET, PATCH | `/{source_id}/field-trackings/{tracking_id}` | Read/configure a field tracking |
| POST, GET | `/{source_id}/field-trackings/{tracking_id}/object-field-trackings` | Bind/list concrete object fields |
| GET, PATCH | `/{source_id}/field-trackings/{tracking_id}/object-field-trackings/{object_tracking_id}` | Read/configure a concrete binding |

Use `tracking_enabled: false` to stop tracking while retaining its identity and
provenance. Disabling a field tracking makes its child bindings effectively inactive;
workers must check both the parent and child flags. Context links are independent
of tracking contracts. Linking an entity never implies that the source represents
one concrete object. Repeated PUT/DELETE link operations are idempotent.

Registration creates an `UNDISCOVERED` source, an empty metadata row, and its initial
history entry in one transaction. It does not fetch, discover, create a task, start
Temporal, or start polling. A schedule stores configuration only; a future scheduler
uses source cadence and field-level demand to decide what to execute.

### Register a URL

```json
{"type": "HTML", "url": "https://example.com/funding"}
```

URLs use HTTP(S); host casing, default ports and fragments are normalized. Query
parameters, path case, and non-root trailing slashes are preserved. Duplicate URLs
return `409`. Credential-bearing URLs and URLs exceeding 2048 UTF-8 bytes are rejected.

### Register a file-backed source

First register the descriptor after storing the bytes:

```json
{"storage_key": "documents/rules.pdf", "mime_type": "application/pdf", "size_bytes": 12345}
```

Then POST the source with the returned file ID:

```json
{"type": "PDF", "file_id": 1}
```

The source URL may be null. At least one of `url` or `file_id` must be present.
A supplied file reference must exist and its MIME type must match the source type.
The descriptor endpoint does not upload bytes. A source's initial locator/type can
be corrected before its first lifecycle transition; PATCH cannot remove both locators.

## Lifecycle and consistency

The normal lifecycle is `UNDISCOVERED → DISCOVERING → VALIDATING → ACTIVE`.
Additional allowed transitions are defined in `sources/services/lifecycle.py`.
State updates require `expected_state`; stale expectations and invalid transitions
return `409`. State, timestamps, and history commit together under a source row lock.
Repeated archive operations are harmless. Archival is terminal, retains all source
records, and disables its schedule and both levels of tracking. Existing warnings
can still be resolved after archival.

`triggered_by` records the supplied domain trigger and is not an authenticated user
identity. The router uses the same access model as the existing application.

All mutations have one service-owned transaction. Use a session scoped to one
request or orchestration activity, without unrelated pending writes. Cross-module
references are validated with direct queries against the existing business models.

## Tracking and the Layer 3 boundary

When creating a concrete binding, the service checks that the BusinessObjectField
uses the same BusinessEntityField as the parent SourceFieldTracking, and that its
object belongs to that field's entity. Nested endpoints also verify source and
tracking ownership.

`last_observation_id` and `baseline_observation_id` reference evidence from Layer 3.
Neither is a canonical BusinessObjectFieldValue. Updating `last_checked_at` does not
change `last_changed_at` or the baseline. The acquisition caller explicitly sets
`last_changed_at` after comparing the newly observed source value with its baseline.
This service never writes canonical business values or reconciles observations.

Layer 3's generic `FieldObservation` model is not implemented in this change.
Until that real model is registered, non-null observation pointer updates return
`409`; the nullable bigint columns remain available. Their two physical foreign-key
constraints are deliberately deferred rather than creating a placeholder evidence
table. All other Layer 2 foreign keys are declared normally.

When implementing Layer 3, import its models in `migrations/load_models.py` before
`register_evidence_references()`. That function attaches the two named foreign keys
to metadata, using `use_alter` for the Layer 2/3 cycle. The next Alembic autogeneration
will include them. The function only configures metadata; it executes no DDL.
Once Layer 3 is available, the service verifies that each observation belongs to
both the exact SourceObjectFieldTracking and its parent SourceFieldTracking.

## Verification

```bash
python -m pytest tests/test_sources.py -q
```

Tests cover API validation, file-backed registration, transactions, metadata,
scheduling configuration, warnings, context links, cross-source/object tracking
invariants, evidence ownership, and archival. SQLite runs use the real Layer 2
models plus the business identity tables, with PostgreSQL types compiled for SQLite.

For native PostgreSQL enum/locking behavior, use a dedicated test database:

```bash
SOURCES_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/burbot_test \
  python -m pytest tests/test_sources.py -q
```

The fixture creates and drops a unique schema per test. It uses model metadata,
not migration revisions. The PostgreSQL concurrency test is skipped without that URL.
