# Automatic Source Monitoring

The monitoring worker submits one Prefect scheduler flow per minute when the
previous one has finished. The flow writes due checks to PostgreSQL. The worker
independently looks for verified uploads and submits their processing flows.
A running Firefox polls the PostgreSQL queue through the API,
opens an inactive container tab, runs the pinned SelectorTree definitions and
uploads a sanitized rendered DOM to MinIO. The Burbot API and Prefect worker
require no browser installation.

## Run the local stack

Compose uses PostgreSQL 18, MinIO and a Prefect 3.9.4 Process work pool. The
API, S3 endpoint and Prefect UI bind to loopback. PostgreSQL and Prefect use
named volumes. MinIO uses the existing `~/minio/data` directory.

```bash
docker network inspect burbot >/dev/null 2>&1 || docker network create burbot
docker compose up -d --build
```

Compose reads `.env`. Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`DCKR_DATABASE_URL` (using `db:5432`), `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD` and `MONITORING_ADMIN_TOKEN`. Initialization applies
Alembic migrations and creates the private bucket. Use the recovery and upgrade
procedure below if the Prefect deployments already use the old interval.

For a deployment outside Compose, install `burbot-orm[monitoring]`, migrate
with Alembic and provision the private bucket. Run the module from a Linux
container that owns the lifetime of its local flow processes.

```bash
export PREFECT_API_URL=https://prefect.example.org/api
python -m monitoring.worker
```

Set `DCKR_DATABASE_URL` on the API and worker and `HOST_DATABASE_URL` for
Alembic. Both application processes use `MONITORING_S3_INTERNAL_URL`,
`MONITORING_S3_PUBLIC_URL`, `MONITORING_S3_BUCKET`,
`MONITORING_S3_ACCESS_KEY` and `MONITORING_S3_SECRET_KEY`. The private S3
identity needs object read, write and deletion in the monitoring bucket. Use a
browser-reachable HTTPS public endpoint for remote installations. Serve the API
over HTTPS and restrict access to the existing Sources, Extraction and Tasks APIs
as part of the Burbot deployment.

## Prefect scheduling and recovery

The `burbot-monitoring` pool has two dedicated queues. The Process worker
polls exactly these queues and runs at most five subprocesses in total.

| Queue | Priority | Concurrent runs | Deployment |
| --- | --- | --- | --- |
| `monitoring-processing` | 1 | 4 | `process-monitoring/monitoring-process` |
| `monitoring-scheduling` | 2 | 1 | `schedule-monitoring/monitoring-scheduler` |

Run a single worker container for these queues. Clear any externally imposed
pool capacity restriction below five if you want all five queue slots to be
available. The worker creates missing Prefect resources and reads existing
settings at startup. Deployment and queue pauses are respected when submitting
new runs. Use a queue pause to also stop workers picking up its already
scheduled runs.

With the old configuration, Prefect counted only future scheduled runs when
deciding whether to generate another interval tick. Overdue runs could
accumulate even without a worker. The default deployment collision strategy
(`ENQUEUE`) rescheduled rejected `Pending` proposals as
`AwaitingConcurrencySlot`. That state explains the worker's non-pending
`SCHEDULED` log when the slot was full. Both deployments shared the default
queue, which exposed processing runs to the same polling order and local
capacity as the backlog. Reapplying deployments at worker startup could also
replace their schedules and future auto-scheduled runs. The reported
`Submitting` run and occupied slot are consistent with interrupted submission.
The original process and lease owner require inspection on the affected host.

Prefect 3.9.4 stores deployment lease records in memory by default and slot
counters in the server database. A server restart can lose the lease record
while retaining the counter. The `CANCEL_NEW` strategy needs a full deployment
limit to cancel a tick, so an offline worker with zero occupied slots would
still leave interval runs queued.

The worker now coalesces missed ticks and creates at most one outstanding
automatic scheduler run in its queue. PostgreSQL locks and the unique
active-job constraint protect source scheduling. Prefect queue limits govern
admission from `Pending` and `Running` states. The monitoring deployments
use those queue limits in place of deployment concurrency leases.

The worker preserves scheduled processing runs while capacity is busy.
For `Pending` (including `Submitting`), `Running` and `Cancelling`, it
checks its in-flight submissions and the local process identity. Only an
orphan in an owned queue is reconciled automatically. A lost submission or
execution becomes `Crashed`. An orphan already in `Cancelling` becomes
`Cancelled`. Paused runs require the operator's decision. PostgreSQL records
the assigned processing run, retry eligibility and evidence checkpoints. On a
terminal or missing Prefect run, dispatch can assign a new run to the same job.
The new run reuses committed acquisition data and resumes the evidence
transaction. Job and evidence writes are fenced by the assigned run ID.

### One-time upgrade and recovery

Use this procedure from the repository root with the existing Compose project.
Set `monitoring_job` to the UUID of the uploaded job you want to verify.

1. Build the image and inspect the two deployments, including the job's
   current processing flow ID. The report shows legacy deployment slots,
   counts and oldest waiting runs, PostgreSQL job counts and optional run IDs.

   ```bash
   docker compose build worker
   docker compose run --rm -T --no-deps worker python -m monitoring.recovery \
     status --runs --job-id "$monitoring_job" > monitoring-recovery.json
   ```

2. Let active processing finish. Stop the legacy monitoring worker and confirm
   that all Process workers serving the old queue and their flow subprocesses
   have exited. Firefox can continue uploading to the API during the worker
   pause. PostgreSQL holds those jobs for dispatch when the worker returns.

   ```bash
   docker compose stop -t 180 worker
   docker compose ps -a worker
   ```

3. Keep the scheduler deployment paused if it was already paused. If it is
   active, temporarily turn off Prefect's interval Scheduler by recreating
   only the Prefect service with the override below. This briefly interrupts
   the Prefect API and pauses new interval scheduling across that server.
   The existing `prefect-data` volume carries the history across the restart.

   ```bash
   docker compose -f docker-compose.yml -f - up -d --no-deps --wait \
     --force-recreate prefect <<'YAML'
   services:
     prefect:
       environment:
         PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED: "false"
   YAML
   ```

4. Refresh the report with `status --runs` and review the scheduler
   candidates. Select only obsolete automatic interval runs in the legacy
   queue with a scheduled state, zero starts and no infrastructure PID.
   Put the approved UUIDs in `reviewed-scheduler-runs.txt`, one per line.
   The command validates the manifest against the current states and cancels
   those runs through Prefect, retaining their history. If you turned off the
   server Scheduler, review any future automatic ticks too, then pause the
   deployment with the command below. It requires zero remaining future
   automatic scheduled runs before changing the deployment.

   ```bash
   docker compose run --rm -T --no-deps worker python -m monitoring.recovery \
     cancel-scheduler < reviewed-scheduler-runs.txt
   docker compose run --rm -T --no-deps worker python -m monitoring.recovery pause-scheduler
   ```

5. For each old `Submitting`, `Pending`, `Running` or `Cancelling` run,
   use the worker attribution, infrastructure PID, container state and logs
   to confirm whether an execution still exists. Reconcile only runs whose
   execution has stopped. Repeat the following for each confirmed orphan in
   either monitoring deployment. The terminal transition releases the run's
   deployment slot through Prefect. Record any remaining leaked slot counts
   from `status` before moving the drained deployments in step 7.

   ```bash
   docker compose run --rm -T --no-deps worker python -m monitoring.recovery \
     reconcile-orphan --confirm-stopped "$orphan_flow_run"
   ```

6. If the uploaded job is still linked to an unstarted `Scheduled` processing
   run in the legacy queue, confirm the processing deployment, queue, and
   run ID against `status --runs --job-id "$monitoring_job"`. Cancel that
   specific flow. Apply the same check to other stranded processing jobs if
   needed. Dispatch will read the terminal run and reuse the uploaded job.

   ```bash
   docker compose run --rm -T --no-deps worker prefect flow-run cancel "$legacy_processing_run"
   ```

7. Move the deployments to their dedicated queues and retire the legacy
   interval. The command preserves deployment and schedule IDs, sets the old
   scheduler schedules inactive and removes their drained deployment
   concurrency limits. It refuses to move a deployment with in-flight runs or
   future automatic runs. Bring Prefect up with the regular Compose settings
   if you disabled its server Scheduler or if the running server uses a
   different Prefect version. Recreating Prefect briefly interrupts its API.

   ```bash
   docker compose run --rm -T --no-deps worker python -m monitoring.deployments --migrate
   docker compose up -d --no-deps --wait --force-recreate prefect  # when needed
   docker compose up -d --no-deps worker
   ```

8. Resume the scheduler if you are ready for source planning. Leave it paused
   if the original pause was an administrative decision. Processing uploaded
   jobs continues independently. Check the job's status until it reaches
   `completed` with the original job ID and a snapshot reference. An upload
   with selector evaluations should also have an extraction run reference.

   ```bash
   docker compose run --rm -T --no-deps worker python -m monitoring.recovery resume-scheduler
   docker compose exec worker python -m monitoring.recovery status --job-id "$monitoring_job"
   docker compose logs --since 10m worker
   ```

After migration, `docker compose restart worker` restarts polling and
reconciliation. Use `docker compose up -d --build worker` for worker code
updates. `docker compose restart prefect` uses the persisted Prefect SQLite
database and the worker resumes polling when the API returns. The upgrade uses
the existing PostgreSQL monitoring tables and requires no schema migration.

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
- Monitoring compares the raw literal against a comparable accepted observation
  for the tracked Source and object field. When that baseline is missing, it uses
  the previous observation of the same SelectorTree, Source and concrete field.
  A changed selector version can continue the history of the same tree.
- Selector sync registers the tree and its field binding. Firefox's workspace
  keeps `rawValue` and `valueAtCapture` separate. A capture reported for an existing
  backend snapshot supplies an observed literal. A human-confirmed capture uses
  the existing validation and evidence baseline rules.
- The history retains `FIELD_NEW`, `FIELD_UNCHANGED`, `FIELD_CHANGED`, and
  `FIELD_MISSING` for existing consumers. `evidenceStatus` makes their meaning
  explicit as `INITIAL_EVIDENCE`, `UNCHANGED`, `CHANGED`, and `MISSING`. Ambiguous,
  conflicting, and failed evaluations also have evidence statuses. The legacy
  `value_changed` task reason refers to a change in the source literal.
  `evidenceChanged` is true or false for a comparison between two literals and
  null when that comparison was unavailable. `comparison` identifies
  `accepted_baseline` or `previous_observation` when available.
- The first bound observation without prior comparable evidence can create an
  initial evidence review. A repeat of the same literal updates the evidence
  history and check time. The existing acceptance workflow controls the baseline.
  An extraction issue and missing evidence review carry the evaluation for a
  `not_found` result.
- Monitoring reviews retain the Source, snapshot, run, field, and available
  previous and current evidence references. Pending and in-progress reviews move
  to the active workflow on supersession. Repeated comparisons with the same
  outcome for a target and evidence pair reuse the open task. A consecutive
  identical result can also reference its completed or cancelled review.
- Operators can request `GET /monitoring/reviews/{task_id}` for the original review
  context. It shows raw previous and current evidence when available, their
  observation IDs, the evaluation and baseline IDs, and the current canonical
  field value and its value ID. The canonical value is read through the Business
  Layer at request time. The review task uses the existing workflow lifecycle.
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

Use separate disposable PostgreSQL and MinIO services. The orchestration tests
start a temporary Prefect server and real Process worker. The PostgreSQL test
role needs `CREATEDB` for the worker tests' isolated databases. Tests drive
the Firefox protocol through the API and upload to MinIO.

```bash
python -m pip install -e '.[dev,monitoring]'
export COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://burbot:local@127.0.0.1:55432/burbot_test
export MONITORING_TEST_S3_URL=http://127.0.0.1:19000
export MONITORING_TEST_S3_ACCESS_KEY=local
export MONITORING_TEST_S3_SECRET_KEY=local-test-only
pytest -q tests/test_monitoring_postgres.py tests/test_monitoring_orchestration.py
```
