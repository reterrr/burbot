# Automatic Source Monitoring

Prefect 3 runs one scheduler every 60 seconds. It writes due checks to PostgreSQL
and dispatches processing for verified uploads. A running Firefox polls the queue,
opens an inactive container tab, runs the pinned SelectorTree definitions and
uploads a sanitized rendered DOM to MinIO. The Burbot API and Prefect worker
require no browser installation.

## Run the local stack

The Compose example uses PostgreSQL 18, the official Linux amd64 MinIO community
binary and a Prefect 3 Process work pool. The API, S3 endpoint and Prefect UI bind
to loopback. Database, bucket and Prefect state use named volumes.

```bash
cp .env.monitoring.example .env.monitoring
# Fill the database password, operator token and S3 credentials.
docker compose --env-file .env.monitoring -f compose.monitoring.yml up --build
```

Initialization applies `m100_source_monitoring` and creates the private bucket.
Worker startup registers `schedule-monitoring/monitoring-scheduler` with a
60-second interval and concurrency of one, and
`process-monitoring/monitoring-process` with concurrency of four.

For an existing deployment, install `burbot-orm[monitoring]`, migrate with
Alembic, and provision the private bucket. Run these commands with the repository
available to the Process worker.

```bash
export PREFECT_API_URL=https://prefect.example.org/api
prefect work-pool create --type process burbot-monitoring
python -m monitoring.deployments
prefect worker start --pool burbot-monitoring --limit 5
```

Set `DCKR_DATABASE_URL` on the API and worker and `HOST_DATABASE_URL` for
Alembic. Both application processes use `MONITORING_S3_INTERNAL_URL`,
`MONITORING_S3_PUBLIC_URL`, `MONITORING_S3_BUCKET`,
`MONITORING_S3_ACCESS_KEY` and `MONITORING_S3_SECRET_KEY`. The private S3
identity needs object read, write and deletion in the monitoring bucket. Use a
browser-reachable HTTPS public endpoint for remote installations. Serve the API
over HTTPS and restrict access to the existing Sources, Extraction and Tasks APIs
as part of the Burbot deployment.

## Approve a source and enroll Firefox

1. Register an active HTML Source, configure its `SourceCheckSchedule`, and
   approve the relevant SelectorTree version through Extraction.
2. Send `PUT /monitoring/sources/{sourceId}/approval` with the bearer token
   configured in `MONITORING_ADMIN_TOKEN`. Use `{}` for the Source's origin,
   or `{"additionalOrigins":["https://assets.example.org"]}` for approved
   redirect or dependency origins.
3. Send `POST /monitoring/agents/register` with the same operator credential and
   `{"name":"My Firefox","sourceIds":[15]}`. Save the returned `agentToken`
   when issued. Issue a separate token for each Firefox profile and grant the
   IDs it can read. The backend stores token digests.
4. In the Firefox extension's **Source monitoring** options, enter the API
   origin, public S3 origin, issued agent token and approved HTTPS origins.
   Enable monitoring and grant the Firefox permissions. Firefox must support
   contextual identities and the profile must have containers enabled.
5. Wait for the next schedule or send
   `POST /monitoring/sources/{sourceId}/jobs` as operator. Inspect the
   paginated `GET /monitoring/sources/{sourceId}/history` response and Prefect UI.

`GET /monitoring/agents/{agentId}` shows last-seen and connected status.
`DELETE /monitoring/agents/{agentId}` revokes the token and releases its leases
for retry. To pause automatic planning, disable the Source schedule. To
withdraw permission to acquire a Source, send `{"enabled":false}` to its approval
endpoint.

## Queue and upload protocol

| Agent request | Result |
| --- | --- |
| `POST /monitoring/agents/heartbeat` | Records the agent's presence |
| `POST /monitoring/jobs/claim` | One available scoped job with lease ID and immutable definitions, or HTTP 204 |
| `GET /monitoring/jobs/{jobId}` | State of a job assigned to the caller |
| `POST /monitoring/jobs/{jobId}/heartbeat` | Extends the matching lease |
| `POST /monitoring/jobs/{jobId}/uploads` | Grants a 60-second PUT for the declared length and `text/html` type |
| `POST /monitoring/jobs/{jobId}/complete` | Validates and seals the object and records the reported evaluations |
| `POST /monitoring/jobs/{jobId}/fail` | Records an acquisition failure and schedules a bounded retry |

PostgreSQL row locks and a partial unique index permit one active job per Source.
The first claim pins approved version UUIDs, version numbers and SHA-256 definition
fingerprints. Retries use those pins. A lease lasts three minutes, renewed every
20 seconds during acquisition. Three acquisition attempts use exponential
backoff. Inactive Firefox profiles leave jobs pending and preserve the last
successful check time.

The agent uploads at most 5 MiB. It sends a per-attempt completion key and the
same JSON payload on replay. The backend verifies the actual length, media type
and SHA-256, then seals the verified bytes under a backend-owned key. Temporary
objects and sealed objects without a registered StoredFile are collected after
the last grant expires and the attempt loses ownership or finishes. The browser
keeps the pending completion payload in local storage until delivery and clears
it when monitoring is disabled. HTML stays out of the outbox.

## Snapshot and extraction semantics

- `rendered_dom/firefox-dom-1` serializes a detached copy of the settled HTML
  document as `<!doctype html>`, a newline, and the root's HTML, encoded in
  UTF-8. It strips extension overlays, executable script and embedded documents,
  form values, comments, and common credential-bearing attributes and URLs.
  SHA-256 covers the exact uploaded bytes.
- `dom-shape-1` hashes a UTF-8 JSON array in element traversal order. Each row
  includes parent index, namespace URI, local name and sorted attribute names.
  Text and attribute values are excluded from the shape hash.
- The latest SourceSnapshot is comparable when it has stored bytes and the same
  representation and hash versions. Incompatible snapshots start a new
  `INITIAL_FETCH` comparison. Identical hashes reuse the prior snapshot while
  registering fresh selector evaluations and updating the check schedule.
- Backend validation checks the complete diagnostics tree and recomputes the
  reported consensus from its outcomes. Evaluations carry
  `browser_agent_reported` provenance. CaptureWriter saves successful raw
  literals as `DETECTED` observations. Failed selectors retain their evaluation
  and an extraction issue.
- Field comparison uses the current accepted source baseline and compares token
  class, semantic-null flag and normalized-or-raw value. The agent supplies raw
  text. Canonical values, baseline pointers and BusinessObjects stay under the
  existing human review workflow.
- Review tasks use the existing workflow generation and reference the Source,
  Snapshot, run, observation and field as available. Pending and in-progress
  monitoring reviews move to the active workflow on supersession. The same
  pending outcome for a target and baseline/value pair reuses its task.
- Acquisition commits before evidence processing. A technical processing
  failure retries against the same snapshot and extraction run, with up to five
  attempts. A check's history shows acquisition and processing times, Prefect
  run IDs, change classification, selector versions, task IDs and safe error
  codes.

## Source access

Approve only public content whose rendered HTML may be stored. The agent uses a
temporary Firefox container and checks requested origins against both backend and
local approvals. It allows HTTPS hostnames whose Firefox DNS answers are public,
validates redirects and disallows authenticated or local sources. Point the agent
only at trusted backend and S3 endpoints. Isolate the monitoring Firefox
profile's outbound traffic where an enforced network boundary is required.
Firefox hostname checks run at the request layer and depend on Firefox's DNS and
network configuration.

## Verification

Use separate disposable PostgreSQL and MinIO services. The integration tests
create and drop an isolated schema and bucket per test.

```bash
python -m pip install -e '.[dev,monitoring]'
export COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://burbot:local@127.0.0.1:55432/burbot_test
export MONITORING_TEST_S3_URL=http://127.0.0.1:19000
export MONITORING_TEST_S3_ACCESS_KEY=local
export MONITORING_TEST_S3_SECRET_KEY=local-test-only
pytest -q tests/test_monitoring_postgres.py
```
