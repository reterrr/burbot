# Automatic Source Monitoring

The monitoring worker submits one Prefect scheduler flow per minute when the
previous one has finished. The flow writes due checks to PostgreSQL. The worker
independently looks for verified uploads and submits their processing flows.
A named onboarding policy lets the same scheduler discover new HTML Sources
and enroll those approved for monitoring.
A running Firefox polls the PostgreSQL queue through the API,
opens an inactive container tab, runs the pinned SelectorTree definitions and
uploads a sanitized rendered DOM to MinIO. The Burbot API and Prefect worker
require no browser installation.

## Trusted local mode

Use trusted mode on a controlled local Burbot installation with a dedicated
Firefox profile. The scheduler enrolls HTML Sources with public site URLs in
`UNDISCOVERED`, `FAILED`, `ACTIVE` or `DEGRADED` state. A disabled schedule
or explicit monitoring revocation prevents automatic checks. The scheduler
also finds Sources registered after startup. PDF and XLSX counts appear under
`unsupportedSourceTypes` in the monitoring overview.

Firefox validates the rendered page. For a previously undiscovered or failed
Source, Prefect records discovery, validation and activation in Source history
when it commits the first verified snapshot. A browser failure remains visible
in check history during lease retries. After three failed attempts, a newly
discovered Source moves to `FAILED` and stays eligible at its next scheduled
check. Existing schedules keep their settings. Newly created schedules use a
24-hour interval, with the same configurable spread for first checks.

Each job carries the exact entry origin of its Source URL. Firefox checks both
top-level redirects and page dependencies using public DNS, ordinary HTTP(S)
ports, and GET or HEAD. It bounds navigation to ten top-level requests and
rejects credentials, sensitive URL parameters, and local, private or internal
destinations. An HTTPS Source uses HTTPS for its entire check. Set
`"trustedAllowHttp":true` to admit public HTTP Sources and allow those jobs to
use HTTP and HTTPS. Firefox performs hostname checks at request time. Use
network-level egress controls for connection-level enforcement in the monitoring
profile.

### Deploy and register Firefox

Set this line in the backend's `.env`. The example makes new schedules
immediately due and limits the active queue to 25 jobs. A trusted agent can
hold one live capture lease at a time.

```dotenv
MONITORING_ONBOARDING_CONFIG='{"mode":"trusted","defaultSchedule":{"initialSpreadSeconds":0},"jobBatchSize":10,"maxActiveJobs":25}'
```

Use the [local stack setup](#run-the-local-stack) for the other settings. On a
fresh installation, start the stack from the backend checkout.

```bash
mkdir -p "$HOME/minio/data"
docker network inspect burbot >/dev/null 2>&1 || docker network create burbot
docker compose up -d --build
```

On an existing installation, apply the migration before restarting the API and
worker. The initialization image is shared with the API and worker.

```bash
docker compose stop worker
docker compose build bot
docker compose run --rm --no-deps initialize alembic upgrade head
docker compose up -d --no-deps --force-recreate bot worker
```

Register a trusted Firefox Agent once per profile. These commands use `jq`.
Keep the returned token private.

```bash
monitoring_api=http://127.0.0.1:8000
read -rsp 'Monitoring admin token ' monitoring_token
printf '\n'
curl -fsS "$monitoring_api/monitoring/agents/register" \
  -H "Authorization: Bearer $monitoring_token" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Local Firefox","trusted":true}' | jq
```

From the Firefox extension checkout, start a local build in Firefox 140 or later.

```bash
npm install --no-package-lock
npm start
```

In the extension options, choose **Source monitoring → Trusted local**, enter
`http://127.0.0.1:8000` as the backend origin, `http://127.0.0.1:9000` as
the MinIO origin, and the returned `agentToken`. Enable monitoring and grant
Firefox's requested permissions. Use your configured origins if the ports
differ. Keep that Firefox instance running for the one-minute polls.

Strict is the default mode. To return to it, set `"mode":"strict"` in
`MONITORING_ONBOARDING_CONFIG`, recreate the API and worker, and choose
**Strict** in Firefox. Strict enrollment and agent scopes use the existing
approval workflow. Verified trusted uploads continue through processing.

### Verify a trusted installation

With Firefox polling, use an existing HTML Source ID or register another
public HTML Source to verify continuous enrollment.

```bash
read -rp 'Public HTML Source URL ' monitoring_source_url
source_id=$(curl -fsS "$monitoring_api/api/v1/sources" \
  -H 'Content-Type: application/json' \
  --data "$(jq -nc --arg url "$monitoring_source_url" '{type:"HTML",url:$url}')" | jq -er .id)

curl -fsS "$monitoring_api/monitoring/overview" \
  -H "Authorization: Bearer $monitoring_token" | jq
curl -fsS "$monitoring_api/monitoring/sources/$source_id/history" \
  -H "Authorization: Bearer $monitoring_token" | jq
docker compose logs --tail=100 worker
```

After the scheduler and Firefox poll, check for `reason: scheduled` and a
`schedulingFlowRunId`. A completed capture also has a `processingFlowRunId`
and a `sourceSnapshotId`. Check a Source with an active SelectorTree to see
its field evaluations and observation IDs. The database query shows the
stored hashes and should return zero rows for duplicate active jobs.

```bash
docker compose exec -T db sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT s.id, s.state, sc.interval_seconds, sc.next_check_at,
       ss.page_url, ss.content_hash, ss.structure_hash, cr.field_results
FROM monitoring_jobs AS j
JOIN source_check_runs AS cr ON cr.job_id = j.id
JOIN sources AS s ON s.id = j.source_id
JOIN source_check_schedules AS sc ON sc.source_id = s.id
JOIN source_snapshots AS ss ON ss.id = j.source_snapshot_id
WHERE j.status = 'completed'
ORDER BY j.completed_at DESC LIMIT 10;

SELECT source_id, count(*)
FROM monitoring_jobs
WHERE status NOT IN ('completed', 'failed', 'cancelled')
GROUP BY source_id HAVING count(*) > 1;
SQL
```

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

## Strict mode bulk onboarding and continuous enrollment

Set `MONITORING_ONBOARDING_CONFIG` on both the API and monitoring worker.
Compose passes it through from `.env`. With no named policies, the scheduler
still creates missing schedules for previously approved, active HTML Sources.
Discovery runs only for origins named in a configured policy.

```dotenv
MONITORING_ONBOARDING_CONFIG='{"policies":{"official":{"origins":["https://example.org"],"continuous":false,"autoEnroll":true,"agentIds":[]}},"defaultSchedule":{"enabled":true,"intervalSeconds":86400,"initialSpreadSeconds":86400},"jobBatchSize":50,"maxActiveJobs":200,"batchSize":20}'
```

Replace the example origin with the exact public HTTPS origins an administrator
has approved for discovery. An origin is a scheme and hostname on port 443.
`additionalOrigins` explicitly permits redirect or dependency origins for the
policy. Discovery checks each redirect against that policy, rejects any DNS
answer containing a non-public address, and connects to a validated address with
HTTPS verification for the original hostname. Probes ignore proxy settings and
sample at most 256 KiB of HTML. An authenticated page, unreadable content, or a
JavaScript shell that requires rendering goes to `NEEDS_REVIEW`. Transient DNS,
network, timeout, and HTTP failures use the persisted retry schedule. Burbot
records the probe's code, HTTP status, redirect count, and retryability.

`autoEnroll: true` also grants monitoring approval for the policy's entry
origins. Use `autoEnroll: false` for discovery with a separate approval step.
An operator can approve selected Source IDs in a run with
`"approveSelected": true`. Those URLs must still match the selected policy.
`agentIds` grants scopes to the specific enabled agents named in the policy when
a Source enrolls. Start an agent with an empty `sourceIds` list when there are no
approved Sources yet. Firefox still needs its own trusted backend, S3, and
navigation origins configured. Existing approvals and grants are durable.
To withdraw them, use the Source approval and agent scope endpoints. Policy
edits govern future discoveries and grants.

The default schedule creates one check per day and distributes initial due times
using a stable offset derived from each Source ID. The saved dates, intervals,
and enabled flags persist across restarts. A schedule update that sends only an
interval preserves existing timestamps and the enabled flag. Acquisition
advances the execution timestamps using the current interval.

| Configuration | Default | Effect |
| --- | --- | --- |
| `mode` | `"strict"` | Use `"trusted"` to enroll public HTML Sources for a trusted Firefox Agent. |
| `trustedAllowHttp` | `false` | Include public HTTP Sources in trusted mode. |
| `monitoringEnabled` | `true` | Enables automatic admission of due jobs. Manual requests remain available. |
| `defaultSchedule.enabled` | `true` | Enables newly created schedules. |
| `defaultSchedule.intervalSeconds` | `86400` | Cadence for newly created schedules. |
| `defaultSchedule.initialSpreadSeconds` | `86400` | Window for the first check. Use zero for an immediate due check. |
| `jobBatchSize` | `50` | Maximum automatic jobs admitted per tick. |
| `maxActiveJobs` | `200` | Automatic admission considers all active jobs, including manual jobs. |
| `maxActiveJobsPerOrigin` | Unset | Optional automatic admission cap per HTTPS origin. |
| `agentUnavailableGraceSeconds` | `600` | Grace period for waiting automatic jobs with no recent scoped agent heartbeat or claim. |
| `batchSize` | `20` | Maximum onboarding items considered per tick. |
| `probeConcurrency` | `4` | Parallel onboarding items. |
| `probeTimeoutSeconds` | `8` | End-to-end discovery deadline for an item. |
| `perOriginIntervalSeconds` | `1` | Minimum interval between validation attempts per origin. Same-origin redirect hops share a reservation. Use zero to disable the rate limit. |
| `discoveryAttempts` | `3` | Maximum attempts before a retryable failure reaches `FAILED`. |
| `retryBaseSeconds` | `30` | Initial exponential backoff. A supported `Retry-After` can extend it up to one hour. |

Due schedules advance oldest first. Automatic jobs require a recent heartbeat
or claim from an enabled agent scoped to the Source. After the offline grace
period the scheduler cancels waiting automatic jobs and leaves their Sources
due, freeing capacity for other agents. Jobs with leases, verified uploads and
manual requests follow their usual lifecycles. PostgreSQL retains the
one-active-job constraint while admission respects the configured caps.

Set `continuous: true` to keep enrolling newly registered Sources. The scheduler
saves its scan cursor and per-Source progress in PostgreSQL. Each tick services
one run in rotation, with a bounded discovery budget. Interrupted transactions
roll back their work and the next tick can pick up the same item. Uploaded
monitoring jobs keep their separate Prefect processing queue.

### Deploy on an existing Compose stack

Set the same policy for the API and worker in `.env` before recreating them.
For an initial dry run, keep `continuous: false` until the preview and bulk
results have been reviewed. Apply the PostgreSQL migration before starting
the new worker.

```bash
docker compose build worker
docker compose stop worker
docker compose run --rm --no-deps initialize alembic upgrade head
docker compose up -d --no-deps --force-recreate bot worker
```

This pauses monitoring briefly while PostgreSQL holds the jobs and Prefect
retains its volume. The legacy Prefect upgrade further below applies to stacks
whose deployments still use the original interval and shared queue.

### Run the first bulk onboarding

1. Review the HTTPS hosts in PostgreSQL. This query shows candidates for
   administrator review.

   ```bash
   docker compose exec -T db sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
   SELECT substring(lower(url) FROM '^https://([a-z0-9.-]+)(?::443)?(?:[/?#]|$)') AS host,
          count(*) AS sources
   FROM sources
   WHERE type = 'HTML' AND state = 'UNDISCOVERED'
   GROUP BY 1 ORDER BY 2 DESC, 1;
   SQL
   ```

2. Populate `origins` and the authorized `agentIds` for the named policy.
   Use an existing agent or register one via `POST /monitoring/agents/register`
   with `{"name":"monitoring-firefox","sourceIds":[]}`. Save the issued token
   privately and configure Firefox. After editing `.env`, apply the policy with
   `docker compose up -d --no-deps --force-recreate bot worker`.

3. Preview, start a bounded run, and inspect progress. Set the API URL for
   your stack and supply the operator token. These commands use `jq`.

   ```bash
   monitoring_api=http://127.0.0.1:8000
   read -rsp 'Monitoring admin token ' monitoring_token
   printf '\n'
   onboarding_request=$(python3 -c 'from uuid import uuid4; print(uuid4())')
   onboarding_payload=$(jq -nc --arg id "$onboarding_request" \
     '{policy:"official", sourceType:"HTML", sourceState:"UNDISCOVERED", requestId:$id}')

   curl -fsS "$monitoring_api/monitoring/onboarding/preview" \
     -H "Authorization: Bearer $monitoring_token" -H 'Content-Type: application/json' \
     --data "$onboarding_payload" | jq
   onboarding_run=$(curl -fsS "$monitoring_api/monitoring/onboarding/runs" \
     -H "Authorization: Bearer $monitoring_token" -H 'Content-Type: application/json' \
     --data "$onboarding_payload" | jq -er .runId)
   curl -fsS "$monitoring_api/monitoring/onboarding/runs/$onboarding_run" \
     -H "Authorization: Bearer $monitoring_token" | jq
   ```

   Reuse the same `requestId` and payload after an uncertain response. To
   limit a run to specific records, include `sourceIds`. Type and state
   filters are evaluated as the run scans records, up to the largest Source
   ID visible when the run began.

4. Inspect coverage and successful checks. Use the reported
   `nextAfterSourceId` for the next page.

   ```bash
   curl -fsS "$monitoring_api/monitoring/coverage" \
     -H "Authorization: Bearer $monitoring_token" | jq
   curl -fsS "$monitoring_api/monitoring/overview" \
     -H "Authorization: Bearer $monitoring_token" | jq
   ```

   ```bash
   docker compose exec -T db sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
   SELECT s.state, count(*) AS html_sources,
          count(*) FILTER (WHERE m.enabled AND m.url = s.url) AS approved,
          count(*) FILTER (WHERE m.enabled AND m.url = s.url AND sc.enabled) AS scheduled
   FROM sources AS s
   LEFT JOIN monitoring_sources AS m ON m.source_id = s.id
   LEFT JOIN source_check_schedules AS sc ON sc.source_id = s.id
   WHERE s.type = 'HTML'
   GROUP BY s.state ORDER BY s.state;

   SELECT j.status, count(*) AS scheduled_jobs, max(j.completed_at) AS last_finished
   FROM monitoring_jobs AS j
   JOIN source_check_runs AS cr ON cr.job_id = j.id
   WHERE j.reason = 'scheduled' AND cr.scheduling_flow_run_id IS NOT NULL
   GROUP BY j.status ORDER BY j.status;

   SELECT j.source_id, j.id, j.source_snapshot_id, j.extraction_run_id, j.completed_at
   FROM monitoring_jobs AS j
   WHERE j.reason = 'scheduled' AND j.status = 'completed'
   ORDER BY j.completed_at DESC LIMIT 10;
   SQL
   ```

5. Enable `continuous: true` when ready for automatic discovery and reconciliation
   of future Sources. Apply the setting with
   `docker compose up -d --no-deps --force-recreate bot worker`.

### Operator API

Use the existing monitoring operator bearer token.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/monitoring/onboarding/policies` | Named discovery policies and their configured agent scope |
| POST | `/monitoring/onboarding/preview` | Read-only counts for the requested policy and filters |
| POST | `/monitoring/onboarding/runs` | Accepted run ID for a durable bulk operation |
| GET | `/monitoring/onboarding/runs` | Paginated finite and continuous runs |
| GET | `/monitoring/onboarding/runs/{runId}` | State, outcome counts, and paginated per-Source diagnostics |
| POST | `/monitoring/onboarding/runs/{runId}/retry` | Requeue a bounded page of exhausted, retryable items |
| GET, PUT | `/monitoring/agents/{agentId}/sources` | List and update an agent's scope |
| GET | `/monitoring/coverage` | Uncovered approved active Sources. Use `onlyUncovered=false` to include covered Sources and online status. |
| GET | `/monitoring/overview` | Source counts, lifecycle history counts, scheduling and agent coverage, queue counts, and check times |

Bulk scope changes use `addSourceIds` and `removeSourceIds`. A named `policy`
adds an approved page by origin, which can be continued with
`afterSourceId`. Explicit removal releases any capture lease and prevents
future policy enrollment from restoring that assignment. Explicitly adding its
Source ID restores the scope.

PDF and XLSX Sources appear in type and state counts. Their monitoring requires
document acquisition, content hashes, versioned snapshots, and document-specific
extraction, which are outside this HTML pipeline.

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
It limits the number of outstanding processing runs in Prefect to 50.
Further verified uploads wait in PostgreSQL for dispatch capacity.
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
the existing PostgreSQL monitoring tables. Apply the onboarding migration
separately before using the bulk onboarding API.

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
| `POST /monitoring/jobs/claim` | One available scoped job with lease ID, immutable definitions and `comparisonVersion`, or HTTP 204 |
| `GET /monitoring/jobs/{jobId}` | State of a job assigned to the caller |
| `POST /monitoring/jobs/{jobId}/heartbeat` | Extends the matching lease |
| `POST /monitoring/jobs/{jobId}/uploads` | Grants a 60-second PUT for the declared length and `text/html` type |
| `POST /monitoring/jobs/{jobId}/complete` | Validates and seals the object and records the evaluations and optional `comparison` |
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

- Firefox settles the DOM after navigation commits and the document is ready.
  The settle window uses 600 ms of DOM quiet and a 4-second cap. Image loads
  can continue during capture.
- `rendered_dom/firefox-dom-1` serializes a detached copy of the settled HTML
  document as `<!doctype html>`, a newline, and the root's HTML, encoded in
  UTF-8. It strips known Burbot overlays and `div#automa-palette`, executable
  script and embedded documents, form values, comments, and common
  credential-bearing attributes and URLs. `contentHash` is the SHA-256 of these
  exact uploaded bytes. SelectorTrees evaluate the sanitized DOM and preserve
  the existing CSS, XPath, text and attribute extraction behavior.
- `structureHash` uses `dom-shape-1` on the sanitized DOM. It hashes a UTF-8
  JSON array in element traversal order. Each row
  includes parent index, namespace URI, local name and sorted attribute names.
  Text and attribute values are excluded from the shape hash.
- The claim response advertises `comparisonVersion: "dom-comparison-1"`.
  Agents that support it may include `comparison` with `version`, `contentHash`
  and `structureHash` in the completion. These are SHA-256 fingerprints of
  UTF-8 JSON. The content fingerprint covers normalized element structure,
  attributes and literal text in DOM order. The structure fingerprint covers
  hierarchy and normalized attribute names. Comparison resolves supported URL
  attributes against the sanitized base, orders attributes deterministically,
  and recognizes `lazy-hidden` and `lazy-loaded` on HTML images. For a
  `lazy-hidden` image, it can resolve a missing source or `lazy_placeholder.gif`
  to a safe deferred resource. It coalesces redundant `data-src` and `data-srcset`
  values. A real `src` takes precedence over a differing deferred URL. Safe
  native image `srcset` candidates participate in the fingerprints. HTML
  sanitization redacts the raw `srcset` attribute. Other lazy-loading conventions
  can still produce changes.
- The backend retains the reported comparison in the existing job completion
  record. It compares the latest stored snapshot using the most recent
  acquisition linked to it. Matching artifact versions and matching comparison
  versions permit fingerprint comparison. Two acquisitions without `comparison`
  use the legacy hashes. A missing baseline or incompatible versions yield
  `INITIAL_FETCH`. Old agents can omit `comparison`, and new agents send it
  only after a compatible claim. Historical snapshots retain their stored bytes
  and hashes.
- A comparison can return `UNCHANGED` when the exact HTML bytes differ. Each
  distinct artifact gets a SourceSnapshot so fresh selector evaluations refer
  to the evidence used during capture. A matching artifact and page URL reuse
  the prior snapshot. The backend verifies uploaded bytes independently of the
  agent-reported fingerprints.
- The saved HTML is a capture artifact. Opening it through `file://` may render
  differently from the live page because styling, scripts and dependent
  resources can be absent or unavailable.
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

Monitor public content whose rendered HTML may be stored. The agent uses a
temporary Firefox container and validates navigation and requests. Strict
mode checks origins against the backend and Firefox approvals. Trusted mode
uses the job's entry origin and public navigation policy. Point the agent at
trusted backend and S3 endpoints. Firefox hostname checks depend on Firefox's
DNS and network configuration.

## Verification

Use separate disposable PostgreSQL and MinIO services. The orchestration tests
start a temporary Prefect server and real Process worker. The PostgreSQL test
role needs `CREATEDB` for the worker tests' isolated databases. Tests drive
the Firefox protocol through the API and upload to MinIO.

```bash
docker run --rm -d --name burbot-monitoring-test-pg \
  -p 127.0.0.1:55432:5432 -e POSTGRES_USER=burbot -e POSTGRES_PASSWORD=local \
  -e POSTGRES_DB=burbot_test postgres:18.0
docker run --rm -d --name burbot-monitoring-test-minio \
  -p 127.0.0.1:19000:9000 -e MINIO_ROOT_USER=local \
  -e MINIO_ROOT_PASSWORD=local-test-only cgr.dev/chainguard/minio:latest server /data
until docker exec burbot-monitoring-test-pg pg_isready -U burbot -d burbot_test; do sleep 1; done
until curl -fsS http://127.0.0.1:19000/minio/health/live; do sleep 1; done

python -m pip install -e '.[dev,monitoring]'
export COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://burbot:local@127.0.0.1:55432/burbot_test
export MONITORING_TEST_S3_URL=http://127.0.0.1:19000
export MONITORING_TEST_S3_ACCESS_KEY=local
export MONITORING_TEST_S3_SECRET_KEY=local-test-only
pytest -q tests/test_monitoring_discovery.py tests/test_monitoring_onboarding.py \
  tests/test_monitoring_postgres.py tests/test_monitoring_orchestration.py \
  tests/test_monitoring_trusted.py

docker stop burbot-monitoring-test-pg burbot-monitoring-test-minio
```
