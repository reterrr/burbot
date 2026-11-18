# Collections and `List(T)`

Collections are universal containers used by the business DSL's `List` type.
They use the existing EAV field slots, canonical value history, transactions,
and model/object write locks. They do not introduce per-entity or per-type SQL
storage, inverse relationships, cascades, or association records.

## Declarations

```python
class ProjectStatus(Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class Operator(Entity):
    name: String(nullable=False)

class Project(Entity):
    name: String(nullable=False)
    operators: List(
        Reference("Operator"),
        persistent_key="operators",
        nullable=False,
        min_items=0,
        max_items=100,
        unique_items=True,
    )
    tags: List(String(max_length=100))
    scores: List(Integer(ge=0, le=100))
    statuses: List(ProjectStatus())
    sources: List(Source())
```

Supported item types: `String`, `Text`, `Integer`, `BigInteger`, `Float`,
`Decimal`, `Boolean`, `Date`, `DateTime`, `UUID`, `JSON`, declared enums,
`Reference`, and `Source`. Item constructors contain their value constraints;
`nullable`, `min_items`, `max_items`, and `unique_items` on `List(...)` describe
the container. Field options such as `persistent_key`, `default`, and `index`
also belong to the outer declaration. Whole-field `unique` and `primary_key`
are rejected for Lists; use `unique_items` for membership uniqueness.

Lists are nullable by default. Bounds default to no bound, and duplicate items
are allowed by default. `max_items=0` permits only an empty list. Null **items**
are unsupported, including for `JSON()`; nulls inside a non-null JSON object or
array remain ordinary JSON data. Item-level defaults, indexes, uniqueness, and
primary keys are rejected. Explicit `nullable=True` on an item is also rejected.
`List(List(T))` is rejected with `UNSUPPORTED_NESTED_COLLECTION` in both DSL and
JSON schemas. Source is parsed with AST; no user Python is evaluated or executed.

Minimal semantic JSON can describe the same rule:

```json
{
  "name": "operators",
  "persistent_key": "operators",
  "type": "list",
  "location": {"line": 1, "column": 1, "end_line": 1, "end_column": 2},
  "nullable": false,
  "min_items": 0,
  "max_items": 100,
  "unique_items": true,
  "item": {"type": "reference", "reference": "Operator"}
}
```

The schema must also declare `Operator`. Sema resolves enum members and validates
inner/outer constraints for source and JSON alike. Enum values supplied by a
client are not trusted. Reference targets are resolved to the target entity's
stable identity when field definitions are persisted. Renaming the target class
while preserving its table identity therefore retains existing reference values.

Named construction supports reference lists, including forward dependencies:

```python
project = Project(name="Example", operators=[operator], tags=["A", "B"])
operator = Operator(name="Example operator")
```

The compiler derives a dependency-safe execution order and checks duplicates
before any writes. Values written through DataService are ordinary JSON lists;
Reference/Source entries are positive integer object/source IDs, not field-slot
IDs. Decimal entries may be exact strings. Membership uniqueness uses logical
numeric/UUID/datetime equality and JSON structural equality, keeping booleans
separate from numbers.

## Canonical values and identities

| Field state | Applicable `BusinessObjectFieldValue` | Storage |
| --- | --- | --- |
| Unset | No version | No canonical value |
| Explicit null | Version exists | `collection_id` absent; `value_json` is JSON null |
| Empty List | Version exists | Collection FK; no present items |
| Nonempty List | Version exists | Collection FK; independently versioned items |
| Scalar/JSON field | Version exists | Existing JSONB carrier, including JSON arrays |

The collection and item tables are:

- `business_collections`: stable owner identity, exactly one of `root_field_id`
  (a BusinessObjectField) or `parent_item_id`, and a monotonic revision token.
- `business_collection_items`: stable item ID and collection ownership.
- `business_collection_item_versions`: position, presence, one value channel,
  and valid/transaction intervals. Scalars/enums use JSONB, references use
  `reference_object_id`, and Sources use `source_id` with actual foreign keys.

`collection_id` is also included on item versions, protected by a composite FK
to the item's identity. This enables a deferred PostgreSQL exclusion constraint
that prevents two present items occupying the same position at the same valid
and transaction times. Each item's own overlap exclusion is immediate. Value
channel and temporal-range checks are enforced in PostgreSQL as well.

There is **no** unique constraint on `root_field_id` alone: a field can have
several historical containers. The canonical field-value pointer determines the
applicable container. A composite FK prevents a field value from selecting a
collection owned by a different slot. Parent-item ownership is unique and leaves
room for future nested collections; public nested operations are not implemented.

Changing an item creates item history, not a new canonical field-value version.
Unchanged item decisions are reused. Removing an item writes a tombstone;
restoring it explicitly can reuse the same item ID. Clearing a collection means
`[]`, not null. A null-to-List transition creates a new container and retains the
old container and its history. Whole-list replacement reuses the initial items
by position, adds identities for additional positions, and tombstones removed
identities. Use addressed item operations when identity matters independently of
position.

## Temporal writes and concurrency

`at` selects valid time; `known_at` selects transaction time. Ranges are half-open
`[start, end)`. Reads default both times to now. Mutation `effective_at` defaults
to now, must include a timezone offset, and cannot be in the future, matching the
existing scalar-value acceptance policy.

A historical item operation transforms each known valid-time slice from
`effective_at` onward. Unrelated later additions/removals and their identities
are retained, rather than resetting the entire collection to the earlier slice.
Set/move changes apply where that item remains present; they do not revive a
later tombstone. Structural changes recompute contiguous positions atomically.
Insert/move positions are checked at `effective_at` and clamped to later shorter
slices. Reorder permutes the specified present items in later slices and retains
later additions after them. Every affected slice is validated, so a historical
write that violates an earlier `min_items` is rejected even if today's count
would be valid. Edits stop affecting a container at slices where the field no
longer selects it or its definition is inactive.

The shared temporal acceptance engine preserves earlier transaction beliefs and
splits prefixes without rewriting old valid intervals. Scalar fields, collection
pointers, and item decisions all use this engine.

All writes reuse the model/entity/object lock order, then lock the container.
Every addressed API mutation requires the latest `expected_revision`; stale
writers receive 409. The token changes only when item decisions change; repeated
no-op reorder, identical update, or removal of an already absent item do not
manufacture new history. Direct service callers may omit the revision for a
serialized intentional write; HTTP callers cannot. Contents and revision guards
are selected in one SQL snapshot. Explicit `known_at` reads return the guard at
that knowledge time; fetch the current guard before applying a historical
correction. An `at`-only read uses current knowledge and its current guard.

Canonical whole-field updates through the existing `/objects/{id}/values`
endpoint retain the existing scalar conventions. Replacing or nullifying an
existing List additionally requires **both** preconditions, keyed by slot ID:

```json
{
  "field_values": {"9001": ["A", "B"]},
  "expected_value_ids": {"9001": 1234},
  "expected_collection_revisions": {"9001": 7}
}
```

The field-version guard prevents an old client from overwriting a different
container after a null/new-container cycle. The collection revision catches item
changes that intentionally leave the field-version ID unchanged. Object reads
now include `collection_id` and `collection_revision` alongside `value_id` and
the materialized JSON list. Scalar updates require no new preconditions.

## API

The existing business router mounts these routes at `/api/v1/business` in the
business application. Existing application mount points remain in control.
Runtime OpenAPI includes the recursive item definition and collection DTOs.

| Method | Relative route | Operation |
| --- | --- | --- |
| POST | `/object-fields/{field_id}/collection` | Create a root container for an unset/null List field |
| GET | `/collections/{id}` | Container and ordered present items |
| GET | `/collections/{id}/items` | Paginated present items |
| GET | `/collections/{id}/items/{item_id}/history` | Item audit history |
| POST | `/collections/{id}/items` | Append, or insert with `position` |
| PATCH | `/collections/{id}/items/{item_id}` | Set `value` or move with `position` |
| DELETE | `/collections/{id}/items/{item_id}` | Remove/tombstone |
| POST | `/collections/{id}/items/{item_id}/restore` | Restore the same identity with a value |
| POST | `/collections/{id}/reorder` | Atomic exact permutation using `item_ids` |
| PUT | `/collections/{id}/items` | Whole-list replacement using `values` |
| DELETE | `/collections/{id}/items` | Clear to an empty list |

GETs accept `at` and `known_at`. Item history without either selector is the full
audit; other reads return the chosen snapshot. Paginated reads accept `offset`
and `limit` (1–500). A container GET can inspect a historical detached container;
`active` indicates whether the requested slice selects it. Item histories expose
tombstones and both intervals. Canonical field-value history exposes pointer
history; item edits are audited at the item-history endpoint.

Mutation bodies contain `expected_revision` and optional `effective_at`, plus:

- Append/insert: `value`, optionally `position`.
- Patch: exactly one of `value` or `position`.
- Reorder: `item_ids` listing every present item exactly once.
- Replace: `values`.
- Restore: `value`, optionally `position`.

Creation uses `values` and `expected_value_id` (null for an unset slot, the current
value ID for an explicit null). It rejects an existing collection rather than
replacing it. Wrong-collection item IDs return 404; stale guards/inactive owners
return 409; invalid types, counts, null items, or positions return 422. All
failures roll back item allocation and history changes. Archived owner objects
cannot be modified. Reference/Source validation reuses DataService's link policy:
objects must exist, match the stable target entity, and be unarchived; Sources
must exist. Ordered references are not automatic ManyToMany relationships.

## Schema revisions and migrations

List options and inner definitions participate in semantic hashes, diffs, and
field definition history; source locations do not. Keep `persistent_key` when
renaming a field and preserve `tablename` when renaming an entity. Carrier/target
type changes on a field with value history are rejected with 409 and require an
explicit data migration. Existing current contents must satisfy tightened item,
length, nullability, enum, and uniqueness constraints. Older historical snapshots
remain readable through their original definitions.

Apply migrations normally:

```bash
python -m alembic upgrade head
```

`b200_business_baseline` bridges the pre-existing gap between the last shipped
migration and the current business driver (persistent keys, renamed revision
columns, archived objects, source code history, and stable UUID relations). It
backfills existing records and retains legacy relation identity data. Downgrade
retains additive identity/code metadata and permits legacy-compatible databases
to be re-upgraded. Archived objects or native UUID relations that the legacy
columns cannot represent require an explicit migration before rollback.
`b201_collections` adds the universal tables and canonical collection channel.
It leaves old scalar JSONB values intact. Collections downgrade is supported
when there are no collections or List definition histories; otherwise it refuses
rather than silently deleting data. Old migration files are unchanged.

Applying explicit Alembic migrations no longer imports optional application
models. Autogeneration still imports the full model graph. At the base revision,
the repository has removed `extraction.schemas.evidence` and source/extraction
services while legacy modules/tests still import them. Those unrelated imports
continue to block the complete legacy suite and full application startup; the
business-router tests do not substitute fake persistence.

## Verification and walkthrough

Use Python 3.13+ and PostgreSQL with `btree_gist`. Tests create and drop unique
schemas inside a **disposable** PostgreSQL database; no application tables are
modified. The test role needs schema/extension privileges.

```bash
python -m pip install -e '.[dev]'
pytest -q tests/test_collections_language.py
COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/test_db \
  pytest -q tests/test_collections_language.py tests/test_collections_postgres.py
```

The integration tests apply the real Alembic chain and exercise migrations,
scalar compatibility, DB constraints/FKs, temporal corrections, independent
objects, reference/source lists, concurrency, revision guards, renames, schema
evolution, seed execution, and HTTP behavior against actual SQL rows.

A persistent service-only walkthrough uses the same helper conventions as the
existing scripts:

```bash
python -m business_layer.scripts.step_24_collections --model-key my_walkthrough
```

It creates/uses a separate `<model-key>_collections` demo namespace, creates three
operators and a project, reorders/removes/appends references, reads the earlier
snapshot, and renames the list with an unchanged persistent key. Successful
writes commit and remain in the configured database. Each run creates new demo
objects; it does not clean up or modify other walkthrough namespaces.
