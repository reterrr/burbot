# Seed Burbot from Firefox SQLite

Run the seeder from the backend checkout with Python 3.13+ and the backend's
`DCKR_DATABASE_URL`. The command checks PostgreSQL's Alembic heads and the
registered `burbot` BusinessModel before importing. It reads the expected Alembic
heads from the checkout. Schema registration and Alembic upgrades are separate
administrative steps.

## Docker Compose

Take a consistent backup before mounting it. SQLite's backup command includes
committed WAL changes and produces a self-contained database. Use a private
directory for reports because they retain original values and pending evidence.

```bash
sqlite_file="${BURBOT_SQLITE_FILE:-$HOME/burbot-firefox/data/burbot.sqlite}"
seed_dir="$(mktemp -d)"
mkdir -m 700 "$seed_dir/reports"
sqlite3 -readonly "$sqlite_file" \
  ".backup '$seed_dir/burbot.sqlite'"

docker compose build bot
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$seed_dir/burbot.sqlite:/seed/burbot.sqlite:ro" \
  -v "$seed_dir/reports:/seed-reports" \
  bot python scripts/seed_burbot_sqlite.py \
  --sqlite-file /seed/burbot.sqlite --dry-run --report /seed-reports/dry-run.json

cat "$seed_dir/reports/dry-run.json"
```

The Compose commands use the existing database and, for stored file bytes, the
existing private object storage configured for `bot`. `--no-deps` bypasses the
Compose initializer and worker. Keep the same backup and workspace namespace
between preview and apply. After the dry-run report has been reviewed and the
import explicitly authorized, run:

```bash
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$seed_dir/burbot.sqlite:/seed/burbot.sqlite:ro" \
  -v "$seed_dir/reports:/seed-reports" \
  bot python scripts/seed_burbot_sqlite.py \
  --sqlite-file /seed/burbot.sqlite --apply --report /seed-reports/apply.json

docker compose run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$seed_dir/burbot.sqlite:/seed/burbot.sqlite:ro" \
  -v "$seed_dir/reports:/seed-reports" \
  bot python scripts/seed_burbot_sqlite.py \
  --sqlite-file /seed/burbot.sqlite --dry-run --report /seed-reports/verify.json
```

For a native backend environment:

```bash
python scripts/seed_burbot_sqlite.py --sqlite-file /seed/burbot.sqlite --report dry-run.json
```

Dry-run is the default. It uses a query-only SQLite connection and a PostgreSQL
read-only transaction, including during preview of new references. A planned
object has a null PostgreSQL ID in the report. It acquires its database-generated
ID only during apply.

The namespace uses `backend_workspace_identity.workspace_uuid` when present.
For an older SQLite database the command has one fixed legacy namespace. Use
`--workspace-uuid UUID` on both runs when importing a distinct legacy workspace.
The importer reuses existing scoped bindings. It creates a disabled identity
namespace when needed to store external keys and idempotent import receipts.
Pre-existing objects without an external binding are counted in the preview for
review. Adoption requires a verified external identity.

## Operator-owned files

The Burbot business schema supports an optional `DocumentFile.operator_owner`
reference. A dry run on a revision without that field marks those records
`OPERATOR_FILE_OWNER_FIELD_UNREGISTERED`, retains their local owner and provenance,
and still plans eligible file bytes. Preview the additive business schema change
with `python -m extension_sync bootstrap` in the backend environment. Register
that revision through the existing schema workflow after reviewing the preview.

## SQLite to PostgreSQL mapping

The extension writes overlapping projections in one SQLite transaction.
The seeder merges them by local object or child identity and counts the
duplicates in `mirrored`. The serialized data supplies complete values and
workspace-only properties. Typed SQLite columns fill gaps, including numeric
foreign keys, and existing normalized SelectorTrees supply the durable graph.

A typed business value goes through `DataService` into its registered
`BusinessObjectField` and `BusinessObjectFieldValue`. Field definitions are looked
up by persistent key at the active schema revision. `List(Reference(...))` uses
the Business Layer's ordered collection storage. Each nested object has an
explicit owner reference.

| SQLite input | PostgreSQL mapping |
| --- | --- |
| `workspace_objects.object_id`, `object_type` and `values_json`; `workspace_state.objects` | `Operator`, `Project` and `Recruitment` BusinessObjects. Legacy `nabor` uses the manifest's Recruitment aliases such as `title` → `external_number` and `amount` → `legacy_amount`. `ExternalObjectBinding` stores the scoped identity. |
| `workspace_objects.created_at`, `updated_at`, `import_key`, `label`, `creation_note`, `source_url`, manual fields | Original creation time populates newly created `BusinessObject.created_at`. The original timestamp strings, import key, label, note, URL and metadata are retained in the object provenance receipt. `last_checked_at` is a typed business field. |
| `operators`, `projects`, `recruitments` | Matching registered fields. Semicolon-separated Operator websites are retained in provenance. The `website` field is set only when the list resolves to one valid distinct URL. Numeric `recruitments.project_id` and `operator_id` first resolve to SQLite object IDs and then to BusinessObjects. `start_low_date`, `start_ceil_date`, `end_low_date`, `end_ceil_date`, `start_time`, `end_time` map to the corresponding `dataRozpoczecia*`, `dataZakonczenia*` and `godzina*` fields. `closed_status`, `status_reason`, `announcement_url` project to `statusZakonczenia`, `powodStatusu`, `urlOgloszenia`. Legacy planned calendar columns map to `planowanyStart*` and `planowanyKoniec*`. |
| `projects_operators`, `recruitment_operators`, `workspace_state.operatorAssignments` | `OperatorAssignment.operatorId`, `operatorType` and `project_owner` or `recruitment_owner`. Serialized assignment IDs take precedence. The owner/operator pair is the stable key for join-only legacy rows. |
| `operator_contacts` and `workspace_state.operatorContacts` | `OperatorContact` with `operator_owner`, `kind`, `variant_no` and `value`. |
| `geographies`, `geography_groups`, geography dictionaries and `workspace_state.geographies` | `Geography.type`, `role`, `value`, owner reference and `operatorId`. The owner groups the rows. The legacy group ID and original `copiedFromProjectId`, `copiedFromGeographyId` and `copiedAt` remain in provenance. Inherited recruitment geographies are stored as independent copies. |
| `workspace_state.serviceCategories`, `financing_rules.payload_json`, `workspace_state.financingRules` | `ServiceCategory` and every `FundingVariant`, with owner and `service_category_id` references. A recruitment variant can reuse a category owned by its verified parent project. The registered variants, percentages, amounts, company sizes and contribution forms are preserved. |
| `file_sources` and `workspace_state.fileSources` | `DocumentFile` with original URL, name, file type, Project, Recruitment or Operator owner, and workflow metadata. The `source` slot references the canonical Source when supported. A file receipt records the stored bytes even for formats without a Source. Discovery page, import keys and copy metadata are preserved in provenance. |
| `document_requirements.payload_json` and `workspace_state.documentRequirements` | `DocumentRequirement` fields and owning Project or Recruitment. `source_file_source_ids` stays in source order. An additional `original_file_source_id` is included in the collection if absent and retained as the original-file marker in provenance. |
| `import_sources`, object Source URLs, file URLs and discovery pages, and selector and evidence URLs | Layer 2 `Source` and `SourceBusinessObject` provenance links. The Sources layer canonicalizes URLs and strips fragments while preserving query parameters. Original URLs remain in their business fields, selectors, receipts or pending report entries. HTML, PDF and XLSX can register as Sources. DOC, DOCX, ZIP and other formats keep their file business records when present. For an unsupported remote file with no bytes in SQLite, the report records the location and the file preservation status. |
| `local_file_blobs` | `StoredFile` with SHA-256, size, name, media type and upload timestamp, using a stable object-storage key. An extractable blob can also get a file-only `Source`. The original Firefox loopback URL remains on the file record. The `stored_files` report category tracks byte preservation independently of extraction capability. |
| `selectors`, `selector_versions`, `selector_recipes`, `selector_parts`, `selector_locators` | Existing `SelectorService.import_tree` and normalized extraction models. The portable selectors retain UUIDs, version numbers and statuses, active references, extraction payloads, recipes, parts and locators. A selector binds through its registered persistent field key and local Source provenance. A legacy document type key binds only when exactly one document under the same owner matches. Unresolved or ambiguous targets stay pending with their full SelectorTree. |
| `selector_evaluations` and serialized evaluations | Validated `SelectorEvaluation` with original UUID, timestamp, page URL and result, using `client_reported` provenance. |
| `field_evidence`, `workspace_objects.evidence_json`, `workspace_state.importTargetEvidence`, `import_sources.snapshot_json`, legacy rules without a portable tree | Full pending payloads and any resolvable source associations in the JSON report. These historical captures lack the acquisition context needed to create a canonical snapshot or observation. A selector's portable snapshot UUID is retained and bound only when an existing mapping identifies a matching backend snapshot. |
| SQLite `backend_*` tables | The workspace UUID selects the scope. Cached server IDs, previous operation queues and sync jobs are report-only bookkeeping. |

SQLite `0` and `1` are converted to booleans for boolean fields. Numeric enums
use the registered numeric members. The manifest defines enum aliases such as
project `ACTIVE` → `AKTYWNY` and recruitment `ANNOUNCED` → `OGLOSZONY`. Decimal
values use strings for canonical validation. An empty typed control represents
null. Missing values remain unset, and values without a typed slot remain in
provenance. References resolve by identity and owner before a field can be written.

## Reports, retries and verification

The JSON report records SQLite columns, foreign keys and counts, target Alembic
and business schema revisions, imported or reused PostgreSQL IDs, and per-input
outcomes. `would_import`, `imported` and `reused` identify the import path.
`pending`, `unsupported`, `preserved`, and `skipped` identify provenance and
capability limits. `conflict` and `failed` give the reason and relevant input
and set exit status 1. Keep the original SQLite backup for pending evidence and
unsupported file bytes.

The apply uses batches of up to 50 records and a savepoint per record. Stable
external bindings, Source identity, file keys and selector UUIDs make retries
reusable. Existing canonical field values and SelectorTrees are compared before
write. A difference is reported as a conflict. Unset fields can be filled on
retry. Conditional object-storage writes also make file upload retryable when a
SQL savepoint rolls back after upload.

Compare `apply.json` and `verify.json` after a successful apply. Expected
successes transition to `reused`, PostgreSQL IDs match, and remaining conflicts
and pending evidence remain visible. The import writes business values, Source
registrations and provenance, selector definitions and client-reported
evaluations. A registered Source starts in the Sources service's normal
undiscovered state.

To compare a revised dry run, keep the original `dry-run.json` and use
`--report /seed-reports/dry-run-after.json` with the same backup and PostgreSQL
target. The following query groups both reports by status, input category and reason.

```bash
jq -s '
  def counts:
    .records
    | group_by(.status, (.inputCategory // .input), .reason)
    | map({
        status: .[0].status,
        category: (.[0].inputCategory // .[0].input),
        reason: .[0].reason,
        count: length
      });
  {before: (.[0] | counts), after: (.[1] | counts)}
' "$seed_dir/reports/dry-run.json" "$seed_dir/reports/dry-run-after.json"
```

## Automated verification

Set `COLLECTIONS_TEST_DATABASE_URL` to a disposable PostgreSQL database for the
repository's integration fixture. It applies the real migrations in a fresh
schema per test.

```bash
COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://tester:password@127.0.0.1:5432/burbot_test \
  python -m pytest -q tests/test_seed_burbot_sqlite.py
```
