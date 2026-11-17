# Persistent service walkthrough

These scripts call BusinessService, EntitiesService, and DataService directly.
They connect to your Docker PostgreSQL using `HOST_DATABASE_URL` in the project's
`.env`. No API, pytest, mock database, automatic cleanup, or test rollback is used.
Successful writes **commit and remain visible in your database**.

Run from the project root. List the commands:

```bash
.venv/bin/python -m business_layer.scripts
# The old entry point also lists them:
.venv/bin/python -m business_layer.test
```

Run each numbered module individually, inspect the database, then run the next:

```bash
.venv/bin/python -m business_layer.scripts.step_01_create_model
.venv/bin/python -m business_layer.scripts.step_02_compile_and_preview
.venv/bin/python -m business_layer.scripts.step_03_register_schema
.venv/bin/python -m business_layer.scripts.step_04_seed_objects
.venv/bin/python -m business_layer.scripts.step_05_read_objects
```

Continue with the following modules in order:

| Step/module | What you can inspect afterward |
| --- | --- |
| `step_01_create_model` | Model namespace, key, name, metadata |
| `step_02_compile_and_preview` | Read-only schema/enum resolution and proposed changes |
| `step_03_register_schema` | Schema revision, entities, fields, relation definitions |
| `step_04_seed_objects` | Objects, field slots, default values, references |
| `step_05_read_objects` | Read-only current schema, resolved names, objects and relations |
| `step_06_create_object` | Additional Recruitment created directly through DataService |
| `step_07_update_values` | Changed budget, enum, float, bigint and JSON values; new history rows |
| `step_08_read_value_history` | Read-only old/current beliefs for the same business time |
| `step_09_validation_rejections` | Expected failures for types, nulls, enum, uniqueness, references and stale writes |
| `step_10_evolve_schema` | New schema revision adding Project.score; objects not synchronized yet |
| `step_11_sync_fields` | New empty score slot; existing slots retain their IDs |
| `step_12_set_new_field` | Score value and its first value version |
| `step_13_read_definition_history` | Read-only schema revisions and entity/field/relation histories |
| `step_14_archive_object` | Project archived, history retained, default listing excludes it |
| `step_15_restore_object` | Project restored with the same identity and history |
| `step_16_update_model_metadata` | Model name/description/metadata changed without a schema revision |
| `step_17_deletion_protection` | Expected rejection of hard deletion for records with history |
| `step_18_create_empty_model` | Separate empty model to inspect before deletion |
| `step_19_delete_empty_model` | Only that empty model removed; main walkthrough model retained |
| `step_20_execute_program` | Combined schema + seed execution in a separate model |
| `step_21_repeat_execution` | Definitions reapplied without constructors or an extra schema revision |
| `step_22_rename_fields_with_persistent_keys` | Rename budget/operator fields with fixed keys; preserve slot/value IDs and relation UUID |

| `step_23_definition_code_history` | Source saves, diff, restore, conflict rejection and execution links; fresh constructor objects |

For example:

```bash
.venv/bin/python -m business_layer.scripts.step_07_update_values
# Inspect the database here.
.venv/bin/python -m business_layer.scripts.step_08_read_value_history
```

## Finding the records

The default main model key is **`business_service_demo`**. Scripts print the model,
entity, object, field-slot and value IDs they affect. The model's `metadata_json`
also stores the seed IDs and timestamps needed by later steps; there is no local
state file. Look at:

- `business_models`, `business_model_revisions`
- `business_entities`, `business_entity_versions`
- `business_entity_fields`, `business_entity_field_versions`
- `business_entity_relation_versions`
- `business_objects`, `business_object_fields`, `business_object_field_values`
- `business_definition_code_versions`

Step 22 shows client-controlled field identity. It renames `budget` to
`funding_budget` using `persistent_key="budget"`, and `operator` to `provider`
using `persistent_key="operator"`. Those existing keys were backfilled from the
original field names. Compare the before/after IDs printed by the script.

The combined-execution example uses `business_service_demo_execute`, so it
does not reset the main model's edited values or schema. The deletion example uses
`business_service_demo_empty` and deletes only that explicitly created empty model.

Use a different key for a separate walkthrough; pass the **same key to every step**:

```bash
.venv/bin/python -m business_layer.scripts.step_01_create_model --model-key my_walkthrough
.venv/bin/python -m business_layer.scripts.step_03_register_schema --model-key my_walkthrough
```

## Behavior

- `_programs.py` contains the editable language schema and sample seed values.
- Successful write steps commit before printing `COMMITTED`.
- Read-only steps print `READ ONLY`; naturally they add no rows.
- Invalid writes are rejected by the services and their failed operations are
  unwound normally. There is no outer cleanup transaction removing valid demo data.
- Step 04 reuses named seeds, but reapplies their supplied/defaulted values. Run it
  again only when you want to reset those seed values.
- Re-running schema registration steps reapplies that step's schema. Use a fresh
  `--model-key` when you want to restart the walkthrough independently.
- Step 06 creates another manual object each time. Step 07 increases the budget
  each time so every run demonstrates a real value-version change.
- Synchronization adds slots but does not backfill defaults; steps 11 and 12 let
  you inspect those two operations separately.
- Normal objects already have generated ID history. Hard deletion is therefore
  rejected; archive/restore is the supported lifecycle shown here.
- The nullable Source field is left empty. Populating it requires an existing
  source managed by the Sources layer.
- Scripts do not automatically start Docker, migrate the database, run later steps,
  or delete the walkthrough data. Prepare the database first if necessary:

```bash
docker compose up -d db
.venv/bin/python -m alembic -x scope=business upgrade head
```

Constructor names are local to an execution. Repeating step 04 or 20 can fail unique constraints; use a new walkthrough key for a fresh run. Step 23 is independent and uses a separate `<model-key>_code_history` namespace.
