# Extraction service

The backend has one write pipeline: `ExtractionService` → `CaptureService` →
`CaptureWriter`. SelectorTree is the reusable web definition. Manual capture
and snapshot execution both record evidence and source tracking through that
writer. Reconciliation owns the canonical business values.

## Frontend workflow

1. Resolve/create the Source and business object identities through their owning services.
2. Register immutable snapshot metadata with `POST /sources/{source_id}/snapshots`.
   For persisted bytes, register a StoredFile through the existing Sources API and
   include its `file_id`. Include the captured `page_url` (including its fragment);
   otherwise registration copies `Source.url` at that moment. Metadata-only snapshots
   support manual capture; HTML/PDF/XLSX readers need the actual saved bytes.
3. Register token definitions once with `POST /extraction/token-classes`.
4. Create a pending run with `POST /extraction/runs`.
5. Submit the complete local graph to `POST /extraction/runs/{run_id}/capture`.
6. Send `reconciliation_observations` to the reconciliation layer. Keep unresolved
   observations for object resolution. Neither list changes canonical business data.

The existing `main.api` mounts these paths directly. Add your deployment's API
prefix when using a reverse proxy or mounting the routers under a prefix.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/sources/{source_id}/snapshots` | Register immutable acquisition metadata |
| GET | `/sources/{source_id}/snapshots/{snapshot_id}` | Read one snapshot |
| POST | `/extraction/token-classes` | Idempotently register a named literal type |
| POST | `/extraction/runs` | Create a pending run for an existing snapshot |
| GET | `/extraction/runs/{run_id}` | Inspect lifecycle and failure details |
| POST | `/extraction/runs/{run_id}/capture` | Commit the complete extraction graph |
| GET | `/extraction/runs/{run_id}/capture` | Retrieve the original committed receipt |
| GET | `/extraction/observations/{observation_id}` | Read an interpretation and its literals |
| POST | `/extraction/observations/{observation_id}/resolve-object` | Attach an existing object |
| POST | `/extraction/runs/{run_id}/execute` | Execute through a configured snapshot adapter |

Historical `GET /extractions` and `GET /extractions/{id}` remain available,
including old `completed` runs and their ordered multiple literals.
`POST /extractions` is a deprecated alias of `POST /extraction/runs`: it accepts
`CreateRunRequest` and creates a pending run. Submit evidence through the capture
endpoint afterward. The old workflow/field_observations request shape returns 422;
there is no second evidence writer or fabricated recipe. New run statuses are `pending`, `running`, `succeeded`, `partial`, and `failed`, following the existing
lowercase API convention. A workflow is optional on the new create-run endpoint;
when supplied it must be active and reference exactly the run's source/snapshot.

Errors use 404 for missing resources, 422 for invalid graphs or business bindings,
409 for state/idempotency conflicts, and 501 when automatic execution has no adapter.

## Unified SelectorTree

The database stores a selector's stable UUID and its versions, independent
recipes, ordered parts, and alternative locators in normalized tables. Portable
responses use the extension's camelCase keys. Export orders versions by
`versionNo` and components by `order`. [Firefox extension contract](https://github.com/reterrr/extension/blob/7dec21ceec4f436a47d7ecbe024feedcc5aacbda/src/shared/types/selectors.ts)

| Method | Path under `/extraction/selectors` | Purpose |
| --- | --- | --- |
| POST | `/` | Create a selector with one draft |
| GET | `/` | Page selector definitions |
| GET | `/{uuid}`, `/{uuid}/export` | Read the portable tree and its ETag |
| POST | `/import` | Import a portable tree with its UUIDs and history |
| GET | `/{uuid}/versions`, `/{uuid}/versions/{version_uuid}` | Inspect version definitions |
| POST | `/{uuid}/drafts` | Clone the active or latest version with new component UUIDs |
| PUT | `/{uuid}/drafts/{version_uuid}` | Replace the draft using a portable version object |
| POST | `/{uuid}/drafts/{version_uuid}/approve`, `/{uuid}/drafts/{version_uuid}/reject` | Review a draft |
| POST | `/{uuid}/evaluate` | Execute the active version on a run's snapshot |
| POST | `/{uuid}/evaluations` | Record a client-reported evaluation |
| GET | `/{uuid}/evaluations` | Page stored evaluations |

Create and import take an object with `tree` and `binding`. The binding names
the existing backend `businessEntityFieldId`, optional `sourceId`, and optional
`businessObjectFieldId`. The slot must belong to the field. Portable
`target.objectId`, `target.field`, and `sourceUuid` are kept as external
identifiers. Use `snapshotBindings` to explicitly map a
`createdFromSnapshotUuid` to an existing integer snapshot ID for that source.
Unmapped snapshot UUIDs remain in the portable metadata. A new installation
supplies its own backend binding when importing the exported tree.

Send the quoted `ETag` from the response as `If-Match` on draft creation,
editing, review, and imports that change existing history. A stale token
returns 409. Importing the same tree and bindings is idempotent. Review seals the
definition and approval supersedes the previous active version in the same
transaction. A failed evaluation leaves all version statuses as they were.
Editing the recipe graph of a draft clears client diagnostics for its previous
graph.

### Execute a stored HTML snapshot

Register its SourceSnapshot, create an ExtractionRun, and register the token
class used for raw evidence. Call `POST /extraction/selectors/{uuid}/evaluate`
with `runId`, `captureKey`, optional `sourceSnapshotId`, and optional
`tokenClassId` (default `text`). The selector must bind to the same Source as
the run. There are two ways to provide the saved document.

- Set `api.state.selector_snapshot_reader` to an async function taking the
  snapshot and its registered StoredFile and returning the recorded bytes.
  The evaluator verifies recorded SHA-256 hashes when available.
- Provide UTF-8 `html` whose bytes match the SHA-256 recorded on the snapshot or
  its StoredFile. Unavailable bytes yield 501 and a digest mismatch yields 422.

The evaluator parses the recorded HTML locally with a 5 MiB limit. It resolves
CSS, XPath, element ID, and TextQuote over the stored markup. Live page state and
JavaScript rendering require a serialized rendered DOM snapshot. DOM paths,
ranges, positions, and text fragments keep their structured payloads and yield
`unsupported` diagnostics. Position definitions require representation,
version, units, and digest. Text uses the extension's whitespace rules,
attribute values retain their contents, and relative href/src resolve against the
snapshot URL and its base tag. Portable `name` addresses an HTML attribute.
Legacy `attribute` inputs retain the whitelist below.

Each part checks every locator. Successful locators must agree exactly, and
all parts must succeed for a recipe to complete. The resolver inserts each
subsequent part's `joinWith` before its value. Every independent recipe must
produce the same full string. The evaluation contains every nested diagnostic
and remains separate from the version.

A successful backend evaluation and its capture commit together. Observations
link the evaluation and exact version. The existing capture writer stores the
raw ConcreteValue, binding, and tracking references. Without an explicit object
slot, the observation remains unresolved. A failed result persists diagnostics
and a failed run without an observation. Replaying a run and capture key returns
that attempt's original evaluation and receipt, even after a new approval.

`POST /extraction/selectors/{uuid}/evaluations` accepts `pageUrl`, a
`SelectorEvaluationResult` in `result`, and an optional explicitly resolved
`sourceSnapshotId`. These results carry `client_reported` provenance.
The service validates every referenced recipe, part, and locator against the
version. Evidence is created by backend execution via `/evaluate`.

## Copyable requests

The IDs below are illustrative: entity `42` is Recruitment, field `101` belongs to
that entity, object `1001` is an already resolved recruitment, and snapshot `123`
belongs to the page or file being captured. Replace them with IDs from your model.

| Request file | Send to |
| --- | --- |
| [Create snapshot](examples/extraction/create-snapshot.json) | `POST /sources/{source_id}/snapshots` |
| [Register text token](examples/extraction/create-token-class.json) | `POST /extraction/token-classes` |
| [Create run](examples/extraction/create-run.json) | `POST /extraction/runs` |
| [Manual HTML, resolved Recruitment](examples/extraction/manual-html-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Unresolved Recruitment](examples/extraction/unresolved-object-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Harmonogram PDF](examples/extraction/harmonogram-pdf-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Harmonogram XLSX](examples/extraction/harmonogram-xlsx-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Resolve Recruitment](examples/extraction/resolve-recruitment.json) | `POST /extraction/observations/{id}/resolve-object` |
| [HTML harmonogram link (`attribute.href`)](examples/extraction/harmonogram-link-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Contextual text selection](examples/extraction/selection-quote-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Page URL, no DOM locator](examples/extraction/page-url-capture.json) | `POST /extraction/runs/{run_id}/capture` |
| [Execute later snapshot](examples/extraction/execute-later-snapshot.json) | `POST /extraction/runs/{new_run_id}/execute` |

For PDF/XLSX examples, create a Source of type `PDF`/`XLSX` and register that file's
snapshot first. Use `application/pdf` or
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` as its MIME type.
The downloadable harmonogram is its own Source, distinct from the HTML downloads
page. Discovering a newly published file and tracking the parent page's links remain
acquisition/discovery responsibilities. A parsed row can represent a planned
Recruitment without creating a separate Harmonogram business entity.

Create a new run for each later snapshot. Reuse the source's definitions; do not
reuse a successful run with new content. `/execute` returns 501 until the application
configures its execution adapter (see below).

## WHERE, HOW, literal, meaning

| Concept | Question | Persisted owner |
| --- | --- | --- |
| SourceScope | WHERE is a reusable region/record? | `source_scopes`, e.g. `table tbody tr` |
| Field locator | WHERE is the field? | SelectorTree locator, or a legacy scope rule |
| ExtractionSpec | HOW should the literal be read? | SelectorTree part, or `FieldSelector.extraction_json` for legacy rules |
| ConcreteValue | WHAT was read on this snapshot? | Literal, token class, element, optional runtime offsets |
| FieldObservation | WHAT DOES IT MEAN? | Entity field, occurrence, optional resolved business object |

`FieldSelector` remains the compatibility record for the existing scoped capture
request and file-oriented recipes. It is owned by Extraction;
Sources owns Source, SourceSnapshot and the two tracking models. A future
Investigation orchestrator resolves local identifiers, registers snapshot metadata,
and passes typed rules to Extraction; it does not write extraction tables itself.

The legacy capture value can still teach one optional **`rule`**:

```json
{
  "selector": {"type": "CSS", "value": "a.schedule"},
  "extraction": {"type": "attribute", "attribute": "href"},
  "confidence": 1.0,
  "discovered_by": "MANUAL"
}
```

The locator contains only `type` and `value`; recipe confidence/discovery are on the
rule. SourceScope's separate `selector` retains its scope discovery annotations.
Omit the rule when supplying runtime evidence using a previously taught recipe.
A capture without a new rule does not invent a reusable definition.

| Extraction JSON | Meaning | Field locator |
| --- | --- | --- |
| `{"type":"text"}` | Read the node's text | Required |
| `{"type":"attribute","attribute":"href"}` | Read the raw named attribute | Required, HTML only |
| `{"type":"selection","quote":{"exact":"GK","prefix":"Program: ","suffix":"."}}` | Read a uniquely anchored quote | Required |
| `{"type":"pageUrl"}` | Read the URL recorded on this snapshot | Must be null/absent |

Supported attributes are exactly `href`, `src`, `datetime`, `title`, `alt`, and
`content`. The API uses an OpenAPI `oneOf` union discriminated by `type`, with strict
extra-field rejection. Attribute names, quote structure, and locator/operation
compatibility are also validated when loading persisted JSON. No arbitrary JSON
is passed to the adapter as an extraction spec.

Selection preserves `exact`, `prefix`, and `suffix` exactly, including whitespace.
It never becomes an offset-only definition. Empty
prefix/suffix means no restriction on that side. `ConcreteValue.char_start/char_end`
are optional evidence positions for this snapshot, not reusable selection anchors.
Attribute and pageUrl evidence cannot have offsets into element text. Page URL
values use the document ROOT element as provenance, without a fake CSS selector.

`CaptureWriter.register_selector` compares locator, complete extraction JSON,
confidence, and discovery method. Equal recipes reuse the current row. A changed
operation, attribute, quote context, locator, or annotation closes that row and
appends `version + 1`. Scope rollover carries valid recipes into the new scope;
explicitly re-taught rules replace the old ones there. Repeated occurrences must
agree on the whole rule, not merely the same CSS path.

**Compatibility:** `ValueRequest.selector` has been removed. Selector-only captures
return 422 rather than guessing their extraction operation. Update clients to
send `rule.selector` plus `rule.extraction`. Original capture receipts and evidence
remain readable. A rewritten old payload is not an idempotent retry of the old
receipt: retrieve it with GET, or teach the full recipe in a new run.

## Complete example: teach a harmonogram link, execute it later

The plugin selects this initial HTML:

```html
<a class="schedule" href="/files/harmonogram-2026.xlsx">Pobierz harmonogram</a>
```

Its local rule is:

```json
{
  "pageUrl": "https://example.org/downloads",
  "selector": "a.schedule",
  "extraction": {"type": "attribute", "attribute": "href"}
}
```

The orchestrator records `pageUrl` as snapshot metadata and maps the CSS string to
`rule.selector = {"type":"CSS","value":"a.schedule"}`. It passes `extraction`
unchanged, together with the business field ID, token class and sampled raw href.
Use the complete [capture request](examples/extraction/harmonogram-link-capture.json)
after creating the run for that snapshot. The durable definition becomes:

```text
FieldSelector
  scope_id: <ROOT scope ID>
  source_field_tracking_id: <source + business entity field ID>
  selector_type: CSS
  selector_string: a.schedule
  extraction_json: {"type":"attribute","attribute":"href"}
  confidence_score: 1.0
  discovered_by: MANUAL
  version: 1
  valid_to: NULL
```

The initial literal is `/files/harmonogram-2026.xlsx`. The observation assigns its
business field/occurrence; the recipe is on neither of those evidence rows.

Later acquisition stores a new snapshot:

```html
<a class="schedule" href="/files/harmonogram-2027.xlsx">Pobierz harmonogram</a>
```

Create a new run and call `/extraction/runs/{id}/execute`. The adapter loads the
saved snapshot bytes, locates `a.schedule`, and applies the database rule:

```python
from extraction.services.recipes import read_html_literal

literal = read_html_literal(
    definition.rule.extraction,
    text_content="Pobierz harmonogram",
    attributes={"href": "/files/harmonogram-2027.xlsx"},
    page_url=snapshot.page_url,
)
assert literal.raw_value == "/files/harmonogram-2027.xlsx"
```

The adapter returns the new element, scope occurrence and literal in CaptureRequest,
with `discovered_by="AUTOMATIC"`, `confirmed_by_human=false`, and no `rule` update.
The same capture writer records that evidence. The recipe remains version 1; the
link text is not the extracted value. Relative hrefs stay relative; normalization
or URL resolution is a separate decision and does not alter the saved operation.

`read_html_literal` is a reusable operation helper for already located nodes. It
reads full text, raw attributes, contextual selections, or snapshot URLs. It reports
missing/ambiguous selections through `RecipeReadError`, which the adapter maps to
an IssueRequest; it never falls back to full paragraph text. Parsing and locator
execution remain in the configured SnapshotExtractor; no browser infrastructure
or default full HTML/PDF/XLSX adapter is added by this refactor.

The [selection example](examples/extraction/selection-quote-capture.json) teaches
`p.description` plus the exact quote `Generator Kompetencji 3.0`, prefix `Program: `,
and suffix ` oraz informacje dodatkowe.`. Later execution finds that anchored quote
within the new paragraph and returns just the quote, with new runtime offsets when
known. Missing or ambiguous anchors create issues instead of invented literals.

## Batch graph and identity

- `scopes` declares reusable, source-specific definitions. Exactly one parentless
  scope is named `ROOT`; it may have no business entity. Scope names are unique per
  source. Business meaning uses existing `BusinessEntityField` IDs instead of a
  parallel hardcoded `target_fields` registry.
- `scope_instances` declares concrete occurrences. Ten rows share one scope
  definition and have ten instances. `occurrence_index` is zero-based within the
  parent occurrence. Position and hashes never decide business-object identity.
- `elements` declares document nodes. HTML, PDF, and XLSX each require exactly their
  corresponding subtype metadata. All nodes are inside the root document element.
- `values` associates a literal with one field in one occurrence. One field
  interpretation is allowed per occurrence in a batch. Different occurrences may
  have different values for the same field. Selectors within a shared scope must be
  reusable and agree across repeated rows.
- Local `client_key` references can appear in any order. Duplicate/missing keys,
  cyclic parents, wrong entity/object bindings, and out-of-scope elements are rejected.
- HTML character offsets are Python/Unicode code-point offsets into `text_content`,
  using `[char_start, char_end)`. Convert Firefox's JavaScript UTF-16 offsets before
  sending, or omit both offsets. Provided offsets must select exactly `raw_value`.
- Raw literals are required. `normalized_value=null` means normalization was not
  provided and comparisons fall back to raw text. Only `is_semantic_null=true`, with
  explicit source text such as `brak`, represents semantic null.
- `issues` records `VALUE_NOT_FOUND`, `SELECTOR_BROKEN`, or `AMBIGUOUS_MATCH`. An
  issue-only capture finishes as `partial`; missing values create no null literals
  and never clear canonical data.

Token IDs remain strings such as `text`, `date`, and `url`. Register them explicitly
before capture; new capture validates their existence. Token class describes the
literal type, independently of HOW it was read (for example `attribute.href` with
token class `url`, or `text` with token class `date`). Token regex/parser names are metadata;
actual parsing/normalization belongs to the execution adapter, and business-value
validation belongs to reconciliation.

## Transactions, history and baselines

Capture holds the source row lock shared with SourcesService, then the run lock;
workflow-backed requests acquire the workflow lock first. Database unique indexes
and `ON CONFLICT DO NOTHING` protect reusable identities, including object-field
slots that may be discovered concurrently from different sources.

A successful run has one persisted capture receipt. The globally unique
`capture_key` plus a canonical JSON payload hash makes identical retries return
exactly that receipt, including its original ID maps. Reusing a key for a different
run or changing a successful payload returns 409. Retry clients must preserve list
order, keys, and payload. Creating a run is a separate operation: save its returned ID.

Capture uses one savepoint inside the request transaction. Failure rolls back its
elements, definitions, bindings, observations and ground truth, then persists the
run as `failed`. Fix the payload and retry that run, or create another run. Request
shape errors and preflight conflicts do not start a run. A process crash before
commit leaves the prior durable state; no intermediate `running` state is committed.

Definitions use append-only versions: only `valid_to` closes an old version. A
changed parent scope reparents successor child definitions and carries their
selectors; a changed entity does not inherit the old entity's field selectors.
Evidence retains the exact versions used when it was captured.

Object-field tracking remains SCD2. An observation references the binding version
current when it was captured; updating observation pointers creates a successor
tracking version. The stable `tracking_id` ties these versions together. Shared
version-writing code lives in `sources/services/tracking.py`.

Baseline policy lives in `extraction/services/tracking.py`:

- Human-confirmed observations are `VALIDATED` and receive one GroundTruth row.
  Other observations are `DETECTED`.
- Detected observations update the last/check pointers without accepting a baseline.
  Validated observations initialize or advance the source baseline.
- Comparison uses `(token_class_id, is_semantic_null, normalized-or-raw value)`.
  Canonical BusinessObjectFieldValue is never part of this comparison.
- The first accepted baseline has no change timestamp. A different later accepted
  value advances the baseline and `last_changed_at`; an equal value preserves them.
- Evidence from older snapshots is stored without rewinding tracking pointers.
- `changed_source_object_fields` contains IDs of the new SourceObjectFieldTracking
  versions whose source baseline changed. `reconciliation_observations` contains
  only resolved, validated observations. `resolved_observations` also includes
  detected evidence, so do not treat that list as an automatic acceptance decision.

Object resolution preserves the observation ID and its review status. It checks
other resolved fields in the same occurrence for incompatible object identity.
The capture receipt is an immutable original result; read the observation endpoint
for its current resolution. Merely observing a newer snapshot does not supersede
older evidence. Explicit `supersedes_observation_id` is supported for a validated
replacement with consistent source/object/field identity.

## Service structure and adapter boundary

`ExtractionService` exposes `create_run`, `register_capture`,
`resolve_observation_object`, `execute`, `get_run`, `get_capture`, and
`get_observation`. Historical list/read methods remain for existing evidence.
`create_extraction_run`, `_EvidenceValue`, `_EvidenceGroup`, `_PreparedObservation`,
and the old write DTOs have been removed.
`CaptureService` coordinates lifecycle/transactions; `CaptureWriter` handles scopes,
elements, occurrences, selectors, bindings, literals and observations;
`ExtractionRepository` owns the shared queries and conflict-safe inserts.

Implement `SnapshotExtractor` from `extraction/services/adapters.py` and assign it to
`api.state.snapshot_extractor`, or inject it into `ExtractionService(session, adapter)`.
This adapter handles existing scoped, page URL, PDF and XLSX rules. After
approval of a migrated web selector, its legacy rule is omitted from new
adapter definitions and the SelectorTree is executed through `/evaluate`.
Its `extract(snapshot, definitions, capture_key=...)` method receives saved snapshot
metadata and the active definitions, and returns the same `CaptureRequest` graph.
`definitions.selectors` retains its collection name, but each item is a
`FieldRecipeDefinition` containing `id`, `scope_id`, `source_field_tracking_id`,
`business_entity_field_id`, `version`, and a validated `rule`. Thus the adapter reads
`definition.rule.selector` and `definition.rule.extraction` directly. Scopes still
locate repeated regions separately from each field rule.

The inputs are detached copies; the service keeps separate authoritative copies.
Changing input definitions or returning a field rule (even an identical one) is
rejected. Fingerprints include locator, extraction JSON, scope/field identities,
versions and discovery metadata. After parsing, the service reloads the definitions
under the source lock and rejects a stale result with 409. Malformed DB JSON is
rejected with 422 before adapter I/O; legacy unknown recipes return 409 requiring
rediscovery. These preflight failures leave the run unstarted.

Adapters must use existing definitions, omit `ValueRequest.rule`, avoid
human-confirmation claims, use `AUTOMATIC` discovery, and report missing/ambiguous
values as issues. Definitions are checked again under the source lock before
commit. An adapter error marks the run failed. The service does not download URLs,
open Playwright, perform OCR, execute arbitrary parser names, or invent objects.
Browser/PDF/XLSX readers, object deduplication, scheduling, and reconciliation remain
separate responsibilities.

## Database setup and validation

Run `alembic upgrade head` with `HOST_DATABASE_URL` configured. The extraction
migrations preserve existing data through these changes.

1. `e100_extraction_legacy` registers the three previously unmigrated workflow
   extraction tables. It preserves existing tables created with the old models.
2. `e101_extraction_capture` adds snapshots, definitions, element subtypes, ground
   truth, capture receipts, issues, nullable unresolved bindings, status fields,
   normalized literals, token references and the source/evidence pointer FKs.
3. `e102_extraction_recipes` adds nullable `field_selectors.extraction_json` JSONB,
   permits a null locator pair for `pageUrl`, and records `source_snapshots.page_url`.
   Existing field rows retain NULL extraction behavior. No text default is inferred.
   Newly written recipes are validated before insertion, including scope rollover
   copies. Active unknown definitions block automatic execution until rediscovery
   supplies a full rule. An unchanged scope keeps the recipe version sequence; a new
   scope version receives its own recipes. If a scope changes, include complete
   rules for all of its legacy unknown fields in that capture.
   Old snapshot URLs stay NULL; pageUrl execution requires a newly registered
   snapshot with a recorded URL. Downgrade refuses if any recipe or snapshot URL
   would be discarded, including historical recipe versions.
4. `e103_selector_tree` creates the normalized tables and backfills the Sources
   tracking columns already used by capture. It keeps existing observation
   pointers and IDs. It groups complete HTML CSS/XPath rules by source, scope
   name, and business field. Each legacy rule ID maps to a version with
   deterministic UUIDs for its definition and children. Current rules become
   drafts with unverified provenance and no assumed snapshot. Closed rules
   remain available as superseded versions. The same mapping runs when new
   legacy captures teach a rule. Existing page URL, file, or unknown rules
   retain their original compatibility records. Downgrade requires the absence
   of selector history and source tracking changes that the older schema
   cannot represent.

The earlier per-locator ORM prototype in `extraction/schemas/selector.py` had
no shipped migration or callers. It is replaced by the normalized models.
`schemas/core/db/extraction/scopes.py` belongs to the retired fixed-entity
schema and is outside the application model registry. Historical workflow runs
and capture receipts continue to read the active evidence tables.

Legacy evidence is retained. No fabricated snapshots or normalized baselines are
backfilled. Downgrading refuses when captures or workflow-free runs would be lost;
PostgreSQL enum labels added to existing enum types remain on a downgrade.

Run `pytest -q` for local SQLite integration checks and PostgreSQL DDL compilation.
Set `EXTRACTION_TEST_DATABASE_URL=postgresql+asyncpg://...` to also test source locks,
concurrent captures and the complete migration chain in isolated PostgreSQL schemas.
Set `COLLECTIONS_TEST_DATABASE_URL` to the disposable PostgreSQL database for the
SelectorTree API and evidence integration tests. Set `SOURCES_TEST_DATABASE_URL`
to run the Sources suite against the same migration chain.
The extraction GitHub Actions workflow provisions PostgreSQL 18 and checks upgrade,
legacy preservation, capture behavior, downgrade/re-upgrade and linting.
