# Open a historical snapshot in Firefox

Burbot Studio sends an operator request for an existing capture. The backend queues
one command for one eligible Firefox agent. Firefox fetches the archived bytes
through the backend, verifies them, and opens a top-level HTML document in Firefox.
Studio displays the agent's acknowledgement. The capture remains in the private
MinIO bucket throughout the workflow.

## Run locally

1. Use the backend, Studio and Firefox extension versions with the snapshot bridge.
   Configure PostgreSQL, MinIO and the operator token as in [Monitoring setup](monitoring.md).
2. Apply Alembic head so the backend includes `m105_monitoring_visual_archives`.
   For the Docker stack, run `docker compose run --rm --no-deps initialize alembic upgrade head`.
3. Run Studio on loopback with `BURBOT_API_TARGET` set to the backend origin and
   the backend's `MONITORING_ADMIN_TOKEN` set in the Vite server environment.
4. Build the Firefox extension with `npm install` and `npm run build`. Load
   `dist/manifest.json` as a temporary add-on at `about:debugging#/runtime/this-firefox`
   or install the updated signed extension. Configure its **Monitoring** settings
   with the backend origin, MinIO upload origin and an issued agent token. Enable
   the agent and keep Firefox running.
5. In Studio, open Source Review and select the check that recorded the capture.
   Choose **Open snapshot**, select the agent if Studio lists more than one, and
   wait for **Opened in Firefox**.

**Open snapshot** is also available in Monitoring History, Evidence Review,
Field Inspector, Task Details and Object Review. Opening from a field carries
the recorded selector UUID, version UUID and extraction run ID when available.

## API contracts and credentials

| Method and path | Credential | Purpose |
| --- | --- | --- |
| `GET /monitoring/sources/{source_id}/snapshot-agents` | Operator | List eligible Firefox agents seen by the snapshot receiver in the last 45 seconds. Returns `{agentId, name}` records. |
| `POST /monitoring/snapshots/open-commands` | Operator | Queue one command. Accepts `requestId` (UUID), `sourceId`, `snapshotId`, optional `targetAgentId` (UUID), `action: "open_snapshot"`, and optional `selectorContext: {extractionRunId, selectorUuid, selectorVersionUuid}`. |
| `GET /monitoring/snapshots/open-commands/{command_id}` | Operator | Read `commandId`, action, Source, snapshot, target agent, creation and expiration timestamps, and `state` with optional `errorCode`. |
| `POST /monitoring/agents/snapshot-commands/claim` | Agent | Record receiver presence. Return `204` while the agent has no work. A command includes `sourceUrl`, `capturedAt`, optional selector context, the pinned SelectorTree and recorded diagnostics when available. |
| `GET /monitoring/agents/snapshot-commands/{command_id}/artifact` | Assigned agent | Return verified bytes for a live claim with `X-Burbot-Snapshot-Mime`, `X-Burbot-Snapshot-Size` and `X-Burbot-Snapshot-SHA256`. With `X-Burbot-Snapshot-Accept: visual-html-1`, return the visual archive when present and identify it with `X-Burbot-Snapshot-Format: visual-html-1`. Otherwise return the evidence. |
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
reads the file by stored MinIO key. The maximum size is 5 MiB for the evidence
and 16 MiB for the visual archive. The backend verifies each stored SHA-256
digest before transfer. Firefox checks the metadata and verifies the bytes
again. Responses use `Cache-Control: no-store`.

## Visual archives

When a claimed job includes `visualArchiveVersion: visual-html-1`, Firefox can
request a separate upload at `POST /monitoring/jobs/{job_id}/archive-uploads`.
The request includes `leaseId`, `contentHash`, `contentSize` and `mimeType`.
The completion includes the optional `visualArchiveUploadId`. The backend
verifies and seals that upload and associates it with a newly created snapshot.
Unavailable visual uploads leave the original evidence usable. Checks reusing
an existing snapshot keep its original files and hashes.

The optional Firefox response-filter permission records CSS, raster images and
fonts already loaded in the approved monitoring tab. The agent never fetches
missing resources to build the archive. It captures at most 4 MiB per resource
and 8 MiB of response bodies per check. It embeds allowed bytes in the saved HTML.
Inline styles and supported embedded images can be saved without this permission.
Old captures contain only their original evidence. Dynamic site code, canvas,
shadow DOM, video and missing resources can affect visual fidelity.

## Native Firefox tabs

The extension prepares passive HTML and uses a temporary sandboxed publisher
to hand Firefox an opaque `blob:null` URL. Firefox replaces the launch document
with the archived page as a top-level document. The resulting document has a
null origin and a policy blocking scripts, form submission and network loads.
No OAuth or agent credentials are included in the page. Firefox DevTools can
inspect its DOM and styles. Studio continues to show the pinned SelectorTree
and recorded diagnostics, and the extension retains the selector IDs in the
archive tab's session metadata.

The loaded page works offline. Opening again from Studio produces a new URL
when the original blob URL is no longer usable, including after a browser restart.

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
agent choice, connection errors and redirects for old snapshot links.
