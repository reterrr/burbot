# Firefox business schema and identity synchronization

The Burbot model uses one Business Layer schema for Project, Recruitment and
Operator. Firefox keeps its existing local IDs, workspace, drafts and
SelectorTree history in SQLite. Server identity and acceptance of values are
distinct operations.

## Register the schema

Apply the Alembic migrations through `x101_bulk_source_sync`, then run the
bootstrap command with the backend database configured.

```bash
alembic upgrade head
python -m extension_sync bootstrap
python -m extension_sync bootstrap --apply
```

The first command with no flags previews the diff. Bootstrap uses the stable
model key `burbot` and its normal EntitiesService schema registration. A matching
schema is idempotent. Apply a reviewed diff to an existing revision with
`python -m extension_sync bootstrap --apply --expected-revision REVISION_ID`.
The bootstrap keeps server-only definitions and matches managed fields by their
persistent keys.

The manifest in `extension_sync/manifest.json` comes from the extension's
`npm run --silent export:schema` output and includes non-enumerable legacy
fields. Regenerate the manifest from the same extension revision when changing
its domain schema. The backend validates the generated types and enum members
before registration.

String and multiline fields map to String and Text. Numbers, percentages and
money map to Decimal. Percentages keep their bounds and monetary fields use
two decimal places. Time, URL and NIP use constrained strings. Dates,
timestamps, booleans, references, enums and ordered collections use the
corresponding Business Layer types. Polish enum values are stored as declared.
The registry supplies explicit legacy aliases and the current stable and
version IDs. `nabor` maps to Recruitment, with a legacy key map including
`title` to `external_number`.

## Provision the workspace

1. Start the Firefox extension's SQLite service and open **Backend
   synchronization** in Options. Copy the workspace UUID.
2. Provision that UUID from an administrative backend shell. Flags grant
   capability to create identities, bind existing objects within this model,
   accept reviewed values, and use specific Sources for selectors and captures.
3. Enter the backend origin and the issued workspace token in Firefox. Refresh
   the schema. Remote connections use HTTPS. The example supports loopback HTTP
   for development.

```bash
python -m extension_sync provision WORKSPACE_UUID --create --bind-existing --commit --source 15
```

Keep the token in the Firefox profile. The backend stores its digest. An
administrator can rotate it with `provision WORKSPACE_UUID --rotate` and the
desired grants, or revoke it with `revoke WORKSPACE_UUID`. The local workspace
adopts the namespace from the token at its first connection. Restore the
original SQLite file or reconnect an unlinked workspace using the same token
and local IDs to recover server mappings.

Use the provisioned API through the network boundary for the Burbot deployment.
Give workspace users access to `/api/v1/extension-sync` and reserve the existing
general business administration API for authorized callers.

## Resolve and review

**Preview bindings** checks selected records without creating objects or slots.
An existing server object can be bound by confirming its ID. The server enforces
the model, entity type and one-to-one binding within the workspace. Review legacy
Nabór records with no binding and confirm the intended existing Recruitment or
explicitly create a new identity. Names and import keys remain local hints.

**Create selected identities** uses DataService to create objects and slots.
Identity-only creation leaves business defaults for the explicit value-review
workflow. Existing required fields can require an administrator to create the
object with validated initial data before binding it.

**Compare selected values** refreshes the server heads and displays the proposed
differences. Confirm to queue those changes. The optional setting for future
approved commits queues the changes in the same SQLite transaction as the
local Commit. The server checks the schema revision, field version, slot and
expected value IDs or collection revisions. It stores a receipt under the
operation UUID in the same transaction as the canonical write. Retry uses the
same payload. Conflicts show the server head and require a new comparison and
confirmation. Firefox can keep editing and committing locally while the backend
is unavailable.

**Selector and capture synchronization** resolves portable targets through their
bindings. Select an allowed Source and explicitly synchronize the local
SelectorTree, including any already reviewed versions. For a successful local
evaluation, provide the ID of its registered SourceSnapshot to send evidence.
The server checks the snapshot, source, slot, version and diagnostic consensus.
CaptureService stores the literal as a `DETECTED` observation. Approved bound
selectors are available to the existing monitoring worker.

## Synchronize Sources and SelectorTrees in bulk

The backend migration adds a Source policy to each existing workspace. The
policy starts empty, and separately granted Sources remain available. Business
identity creation permission applies only to business objects.

An administrator can authorize URL-based registration and grants on exact
origins. An origin includes the scheme and hostname, such as
`https://example.org`. Use another `--origin` flag for each additional site.
The two flags below authorize registration of missing Sources and granting
access to existing Sources respectively. Choose the flags independently.

```bash
python -m extension_sync source-policy WORKSPACE_UUID \
  --origin https://example.org --allow-create --allow-grant-existing
python -m extension_sync source-grant WORKSPACE_UUID 15
python -m extension_sync source-grant WORKSPACE_UUID 15 --revoke
```

`source-policy` replaces the workspace's origin list and capabilities. Run it
with the workspace UUID alone to clear automatic registration and grant
capabilities. Use `source-grant` to administer specific existing grants. Both
commands preserve the workspace bearer token.

In Firefox Options, open **Bulk Source & Selector Synchronization**.

1. **Scan local sources** reads the committed SQLite revision. Discovery uses
   imported Sources, SelectorTree and evaluation URLs, and local provenance.
   A file's URL identifies the file. Its source-page URL identifies an
   independent HTML candidate. URL identity drops fragments and preserves
   queries. Both clients apply the public-host URL policy without fetching
   any page or resolving DNS during planning.
2. **Preview synchronization** checks candidates and targets against the
   current server registry. The preview reports registrations, required
   grants, missing business bindings and conflicts. Choose a discovered Source
   or enter a corrected URL for an ambiguous selector and preview again.
   Bind missing parent and nested business objects through **Preview bindings**
   before preparing their selectors. Resolve conflicting Source types or
   selector ownership before attempting a new preview.
3. Select the Sources and selectors to synchronize. Approve publication of
   locally reviewed selector versions if any selected item requires it, then
   confirm **Synchronize selected**. Execution saves the approval in SQLite
   first. It checks grants and Source identity, then pins the business field,
   schema and selector revisions when uploading the existing SelectorTree.
4. **Retry failed** follows the saved operation after a connection drop or
   restart. It uses the original approvals and rechecks the server for an
   accepted selector before resending. A changed selector, schema or ownership
   needs a fresh preview. **Export report** downloads the per-item results and
   pending-evidence count as JSON.

SQLite schema version 16 adds Source bindings and per-item progress through
the normal service startup. Backend IDs are decimal strings throughout.
Source registration creates an `UNDISCOVERED` identity. Monitoring approval,
scheduling and agent assignment still use the monitoring workflow. Historic
captures stay pending until a genuine matching server snapshot is registered.
The bulk workflow leaves local evidence, portable selector history and canonical
business values intact. The setting for sending future approved commits controls
canonical values independently.

## Nested records and provenance

| Local structure | Backend representation |
| --- | --- |
| Operator assignments | OperatorAssignment with owner and Operator references and a role |
| Operator contacts | OperatorContact with owner, kind, value and variant number |
| Geographies | Geography with owner, area type, role, value and Operator scope |
| Financing rules | FundingVariant per local row with amounts, percentage bounds, size, variant and service category reference |
| Service categories | ServiceCategory with project or recruitment owner |
| File sources | DocumentFile with owner, URL, metadata and a registered Source reference |
| Document requirements | DocumentRequirement with typed fields and an ordered collection of File references |
| Field evidence | Existing Selector evaluations and Extraction observations |
| Import sources | Existing Sources and SourceSnapshots |

Nested bindings use the parent local ID, target kind and target row ID. Reconcile
the parent before its nested records and reconcile referenced records before
sending their values. The initial sync transports these typed values and
references. Local file bytes, import provenance and legacy document selectors
whose target cannot be matched to a row remain available in SQLite and portable
exports. Bulk synchronization can register eligible remote Source identities.
Snapshot registration remains a separate operator action.

## API and verification

The workspace bearer token scopes every response. The new JSON contract uses
decimal strings for database identifiers and revision identities.

| Method | Path under `/api/v1/extension-sync` |
| --- | --- |
| GET | `/schema` |
| POST | `/objects/resolve` |
| POST | `/commits` |
| POST | `/sources/preview` |
| POST | `/sources/resolve` |
| POST | `/selectors/preview` |
| POST | `/selectors` |
| POST | `/captures` |

Run `pytest -q tests/test_extension_sync_postgres.py` with
`COLLECTIONS_TEST_DATABASE_URL` set to a disposable PostgreSQL database. The
extension tests exercise discovery, read-only preview, SQLite migration,
BIGINT transport and durable retries with
`node --test tests/backend-sync-contracts.test.mjs`.
