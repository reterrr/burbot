# Canonical value validation versions

Every accepted `BusinessObjectFieldValue` has a required
`validated_against_field_version_id` referencing the exact
`BusinessEntityFieldVersion` used for validation. Services select the active
definition while holding the model lock, so schema publication cannot race with
value acceptance. Clients cannot supply this ID.

This applies to initial values, generated IDs, defaults, seeds, scalar/reference
assignments, explicit nulls, and collection pointers. Unset slots have no value
row and expose a null validation-version ID. Object reads and canonical value
history expose `validated_against_field_version_id`.

The ID records validation provenance, rather than a live link that changes on
every schema publication. Existing historical values keep their original ID.
Accepting the same value under a newer definition creates a new canonical
decision; accepting it again under the same definition remains a no-op. When a
backdated correction copies an earlier valid-time prefix, that prefix retains
the original ID. New decisions use the current active definition even when their
`effective_at` predates the latest schema revision, matching scalar validation.

Addressed collection edits normally create only item history. If the active
field definition has changed, a successful edit also records the new validation
version on the affected canonical pointer timeline. It preserves other pointer
segments, old transaction beliefs, and earlier validation versions. Historical
collection edits must satisfy both the applicable historical constraints and the
current definition recorded as their validation provenance. A failed validation
rolls back both item and pointer changes. After a schema change, reload the
object before a whole-field edit to obtain its latest `value_id` guard.

## Migration

Apply `python -m alembic upgrade head`. New migration
`b202_value_field_version` adds the column, backfills existing values, and then
enforces `NOT NULL` and an `ON DELETE RESTRICT` foreign key. Earlier migrations
are unchanged.

Backfill resolves the active definition at the original decision's recorded
time. Copied prefixes with the same slot, valid-time start, and payload inherit
the original decision's definition. It does not attach all old data to today's
schema. If legacy values lack a matching active definition, migration fails
atomically with a repair message; restore their definition history before
retrying. The migration does not revalidate or change stored JSON values.

Downgrading to `b201_collections` removes this validation metadata while
preserving canonical values and collection data. Re-upgrade uses the same legacy
backfill rules; dropping the column loses the distinction between explicit
revalidation and copied decisions with identical values and valid-time starts.

## Verification

Use a disposable PostgreSQL database:

```bash
COLLECTIONS_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/test_db \
  pytest -q tests/test_field_value_versions.py tests/test_collections_postgres.py \
  tests/test_collections_language.py
```

The focused tests cover initial/system/default/seed values, null and List
carriers, schema changes, repeated assignments, backdated corrections, addressed
collection edits, rollback on validation failure, required foreign keys, legacy
backfill, missing-definition refusal, and downgrade/re-upgrade.
