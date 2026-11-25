# Open a historical snapshot in Firefox

Burbot Studio sends an operator request for an existing capture. The backend queues
one command for one eligible Firefox agent. Firefox fetches the archived bytes
through the backend, verifies them, and creates an extension-owned viewer tab.
Studio displays the agent's acknowledgement. The capture remains in the private
MinIO bucket throughout the workflow.

## Run locally

1. Use the backend, Studio and Firefox extension versions with the snapshot bridge.
   Configure PostgreSQL, MinIO and the operator token as in [Monitoring setup](monitoring.md).
2. Apply Alembic head so the backend includes `m104_snapshot_open_commands`.
   For the Docker stack, run `docker compose run --rm --no-deps initialize alembic upgrade head`.
3. Run Studio on loopback with `BURBOT_API_TARGET` set to the backend origin and
   the backend's `MONITORING_ADMIN_TOKEN` set in the Vite server environment.
4. Build the Firefox extension with `npm install` and `npm run build`. Load
   `dist/manifest.json` as a temporary add-on at `about:debugging#/runtime/this-firefox`
   or install the updated signed extension. Configure its **Monitoring** settings
   with the backend origin, MinIO upload origin and an issued agent token. Enable
   the agent and keep Firefox running.
5. In Studio, open `http://127.0.0.1:5173/#/monitoring/sources/57/snapshots/386`
   when that capture exists. Choose **Open in Firefox**, select the agent if Studio
   lists more than one, and wait for **Opened in Firefox**. The tab shows Source
   #57 and Snapshot #386. The Studio address uses the actual port from `npm run dev`.

**Open in Firefox** is also available beside the snapshot link in Source Review,
Monitoring History, Evidence Review and Field Inspector. Opening from a field
carries the recorded selector UUID, version UUID and extraction run ID when available.
Preview, HTML Source, Details and Download original HTML remain available in Studio.

## API contracts and credentials

| Method and path | Credential | Purpose |
| --- | --- | --- |
| `GET /monitoring/sources/{source_id}/snapshot-agents` | Operator | List eligible Firefox agents seen by the snapshot receiver in the last 45 seconds. Returns `{agentId, name}` records. |
| `POST /monitoring/snapshots/open-commands` | Operator | Queue one command. Accepts `requestId` (UUID), `sourceId`, `snapshotId`, optional `targetAgentId` (UUID), `action: "open_snapshot"`, and optional `selectorContext: {extractionRunId, selectorUuid, selectorVersionUuid}`. |
| `GET /monitoring/snapshots/open-commands/{command_id}` | Operator | Read `commandId`, action, Source, snapshot, target agent, creation and expiration timestamps, and `state` with optional `errorCode`. |
| `POST /monitoring/agents/snapshot-commands/claim` | Agent | Record receiver presence. Return `204` while the agent has no work. A command includes `sourceUrl`, `capturedAt`, optional selector context, the pinned SelectorTree and recorded diagnostics when available. |
| `GET /monitoring/agents/snapshot-commands/{command_id}/artifact` | Assigned agent | Return the verified original bytes for a live claimed command as `application/octet-stream`, with `X-Burbot-Snapshot-Mime`, `X-Burbot-Snapshot-Size` and `X-Burbot-Snapshot-SHA256`. |
| `POST /monitoring/agents/snapshot-commands/{command_id}/ack` | Assigned agent | Record `{"state":"opened"}` or `{"state":"failed","errorCode":"…"}`. Repeating the same result is idempotent. |

Use the same `requestId` when retrying an uncertain create response. A new
command begins as `pending` and expires after 90 seconds. A claim sets `claimed`
and may redeliver the same UUID until acknowledgement. Firefox records opening
locally before creating a tab and reuses the result when a claim or acknowledgement
repeats. Terminal states are `opened`, `failed` and `expired`. When a background
stops during tab creation and Firefox cannot confirm the tab, the agent reports
`VIEWER_INTERRUPTED`. An operator can then issue a fresh command.

Studio calls three allowlisted routes through the existing same-origin loopback
Vite proxy. The proxy adds the server-side operator Bearer token. Agent routes
use the registered agent's Bearer token directly. Delivery uses the existing
approved Source grants in strict mode, or the designated trusted agent and
eligible enrolled Sources when trusted monitoring is enabled. The artifact read
checks Source access again, verifies the capture's Source and StoredFile, and
reads the file by stored MinIO key. The maximum size is 5 MiB. The bridge requires
a stored SHA-256 digest, verifies it before transfer, and Firefox verifies the
received bytes again. Responses use `Cache-Control: no-store`.

## Local inspection and monitoring tabs

Firefox's viewer uses a sandboxed frame with a restrictive content policy and
renders the archived page structure after stripping active elements and resource
and navigation attributes. The exact UTF-8 source is available in the viewer.
CSS, XPath and element ID tests use a separate offline DOM reconstructed from the
capture. Recorded execution diagnostics appear separately from new local match
counts. Remote images, styles and original site scripts are blocked. Viewer
operations read the capture and record delivery status.

Monitoring uses an extension-marked temporary tab in a uniquely named container.
It attempts tab removal and then container removal even when capture fails. On
startup it checks its persisted ownership record and Firefox's per-tab marker.
A container holding an unrelated tab is retained until cleanup can proceed
safely. Old records with ambiguous ownership are retained for the same reason.
Logs use job, tab and context IDs and cleanup reason codes. User-opened snapshot
tabs are closed through normal Firefox controls.

## Verification

Run `pytest tests/test_snapshot_open_commands.py tests/test_monitoring_snapshots.py`
using the disposable PostgreSQL and MinIO fixture variables from the monitoring
test setup. Run `npm run test:snapshot-bridge` in the extension after installing
its Playwright Firefox build. Studio's `npm run test:ui` covers command delivery,
agent choice, connection errors and the existing Preview and HTML Source.
