# Sources service

Sources is a module in the existing FastAPI application and PostgreSQL database.
It owns source registration, identity, lifecycle state and state history. Its service
and repository do not import the business layer, task models, or Temporal.

`POST /sources` stores an `UNDISCOVERED` source and its initial history entry in one
transaction. It does not fetch the URL, discover content, start a workflow, or create
a task. A future orchestration module can call `SourcesService` from a Temporal
activity using its own session. HTTP status, hashes, snapshots, polling schedules and
extraction execution remain separate concerns.

## Run

Use Python 3.13 or 3.14, configure `.env` from `.env.example`, and start PostgreSQL.
`HOST_DATABASE_URL` is the async PostgreSQL URL used by Alembic;
`DCKR_DATABASE_URL` is the async PostgreSQL URL reachable from the application.
When running outside Docker, set `DCKR_DATABASE_URL` to the host connection URL.

```bash
python -m pip install -e '.[dev]'
python -m alembic upgrade head
python -m business_layer.main
```

The API runs on port 8000. Swagger UI is at `/docs`; the live schema is at `/openapi.json`.
The migration adds `stored_files`, `sources`, and `source_state_history` after the
existing business migration. It does not create legacy extraction/runtime tables.

## API

All paths below are relative to `/api/v1`. Collection URLs use no trailing slash;
FastAPI redirects trailing-slash requests to the canonical path.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/sources` | Register an HTML or PDF URL; return `201` and the source |
| GET | `/sources` | Filter by `state`, `source_type`, or exact normalized `url` |
| GET | `/sources/{id}` | Read a registered source |
| PATCH | `/sources/{id}` | Correct URL, type or file reference before the first lifecycle transition |
| PUT | `/sources/{id}/state` | Check the expected state and record a permitted transition |
| GET | `/sources/{id}/state-history` | Read history in chronological order |
| DELETE | `/sources/{id}` | Archive while retaining source identity and history; return `204` |

Lists return `items`, `total`, `offset`, and `limit`. The default limit and maximum
limit are both 100. Sources are ordered by ID. History is ordered by timestamp and
ID. Archived sources remain visible and reserve their URL; filter by state when needed.

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/funding","source_type":"HTML"}'

curl 'http://localhost:8000/api/v1/sources?state=UNDISCOVERED&limit=20'

curl -X PUT http://localhost:8000/api/v1/sources/1/state \
  -H 'Content-Type: application/json' \
  -d '{"expected_state":"UNDISCOVERED","state":"DISCOVERING","triggered_by":"SYSTEM"}'
```

`source_type` is required and supports `HTML` and `PDF`. URLs must use HTTP(S).
Normalization lowercases the host, removes default ports and fragments, and adds
the root path when absent. Path case, query parameters and non-root trailing slashes
are preserved. Credential-bearing URLs and URLs longer than 2048 UTF-8 bytes are
rejected. A duplicate canonical URL returns `409`, including concurrent registrations.

`file_id` optionally references an existing, unpurged `stored_files` row whose MIME
type matches the source type. This is a storage reference, not a file upload. Both
HTML and PDF registrations require a URL. `PATCH {"file_id": null}` clears the
reference; URL and source type cannot be null. After the first lifecycle transition, registration
details cannot be edited, even if recovery returns the source to `UNDISCOVERED`. A different source URL should normally get a new identity.

Unknown sources return `404`; invalid payloads and file references return `422`;
duplicate URLs, stale expected states, and invalid lifecycle operations return `409`.
Unexpected database errors propagate after rollback.

## Lifecycle

The normal path is `UNDISCOVERED → DISCOVERING → VALIDATING → ACTIVE`.
Transitions are defined in `sources/services/lifecycle.py`:

| Current state | Processing/recovery targets |
| --- | --- |
| ADDING | UNDISCOVERED, FAILED |
| UNDISCOVERED | DISCOVERING |
| DISCOVERING | VALIDATING, NEEDS_REVIEW, FAILED |
| VALIDATING | ACTIVE, NEEDS_REVIEW, FAILED |
| ACTIVE | DEGRADED, REDISCOVERING, NEEDS_REVIEW |
| DEGRADED | ACTIVE, REDISCOVERING, NEEDS_REVIEW, FAILED |
| REDISCOVERING | VALIDATING, NEEDS_REVIEW, FAILED |
| NEEDS_REVIEW | DISCOVERING, REDISCOVERING, VALIDATING, FAILED |
| FAILED | UNDISCOVERED, DISCOVERING |
| SUSPENDED, BLOCKED_BY_POLICY | UNDISCOVERED |
| ARCHIVED | No outgoing transitions |

Every non-archived state can also transition to `SUSPENDED`, `BLOCKED_BY_POLICY`,
or `ARCHIVED`. Resuming suspended or policy-blocked sources restarts at
`UNDISCOVERED`, allowing orchestration to recheck policy and discovery.

State changes lock the source row, compare `expected_state`, and commit the new
state, timestamps, and history together. A request for the current state is a no-op
when `expected_state` matches. A stale expected state always returns `409`; callers
should read the source again before deciding to retry. Repeated archive calls are
no-ops. History has no update/delete API.

`triggered_by` records the caller-supplied domain trigger. It is provenance metadata,
not an authenticated user identity or authorization check. The router uses the same
access model as the existing application.

## Module boundaries and compatibility

`shared.database` supplies the one engine/session factory. Existing business database
imports remain aliases to it. `sources.schemas` is the canonical home of the three
registry models and source enums; legacy `schemas.core.db` modules re-export the same
classes. The migration loader imports only the active business and Sources models.

Each `SourcesService` mutation owns and commits its transaction. Give it a session
scoped to one request or orchestration activity, without unrelated pending writes.
Repository methods flush but do not commit. A future worker can reuse this service
without making HTTP calls within the monolith.

## Verification

```bash
python -m pytest tests/test_sources.py -q
python -m alembic upgrade head --sql
```

The default tests use temporary SQLite databases for API and rollback behavior. To
also exercise PostgreSQL enums, foreign keys, duplicate registration races, and row
locks, point the suite at a dedicated PostgreSQL test database:

```bash
SOURCES_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/burbot_test \
  python -m pytest tests/test_sources.py -q
```

The PostgreSQL test fixture creates and drops a unique schema for each test. The
test database user must be able to create schemas. Apply Alembic migrations to an
empty test database separately to check the full business/Sources migration chain.
