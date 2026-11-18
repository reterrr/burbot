"""Bridge the previously unmigrated business refactor without deleting history.

Additive metadata survives downgrade. Rolling back native UUID relations or
archived objects requires an explicit migration rather than losing their meaning.
"""

from alembic import op

revision = "b200_business_baseline"
down_revision = "e102_extraction_recipes"
branch_labels = None
depends_on = None


def constraint(table, name, body):
    # Database-side guards work for online application and offline SQL export.
    op.execute(f"""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
            WHERE conrelid = '{table}'::regclass AND conname = '{name}') THEN
            ALTER TABLE {table} ADD CONSTRAINT {name} {body};
        END IF;
    END $$""")


def rename_revision_columns(old, new):
    for table in (
        "business_entity_versions",
        "business_entity_field_versions",
        "business_entity_relation_versions",
    ):
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema=current_schema() AND table_name='{table}'
                    AND column_name='{old}')
            AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema=current_schema() AND table_name='{table}'
                    AND column_name='{new}')
            THEN ALTER TABLE {table} RENAME COLUMN {old} TO {new}; END IF;
        END $$""")


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("ALTER TABLE business_objects ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ")
    op.execute("""ALTER TABLE business_entities
        ADD COLUMN IF NOT EXISTS effective_business_entity_version_id BIGINT""")
    op.execute(
        "ALTER TABLE business_object_fields ADD COLUMN IF NOT EXISTS effective_value_id BIGINT"
    )
    rename_revision_columns("revision_id", "business_model_revision_id")
    op.execute("ALTER TABLE business_model_revisions ALTER COLUMN business_model_id TYPE BIGINT")
    constraint(
        "business_model_revisions",
        "uq_business_model_revisions_model_id",
        "UNIQUE (business_model_id, id)",
    )
    constraint(
        "business_entities",
        "uq_business_entities_model_table_name",
        "UNIQUE (business_model_id, table_name)",
    )
    op.execute(
        "ALTER TABLE business_entity_fields ADD COLUMN IF NOT EXISTS persistent_key VARCHAR(150)"
    )
    op.execute("""UPDATE business_entity_fields f SET persistent_key = COALESCE(
        f.physical_name, (SELECT v.key FROM business_entity_field_versions v
        WHERE v.business_entity_field_id=f.id ORDER BY v.transaction_from, v.valid_from LIMIT 1),
        'field_' || f.id::text) WHERE persistent_key IS NULL""")
    op.execute("ALTER TABLE business_entity_fields ALTER COLUMN persistent_key SET NOT NULL")
    op.execute("""ALTER TABLE business_entity_fields
        DROP CONSTRAINT IF EXISTS uq_business_entity_fields_entity_physical_name""")
    constraint(
        "business_entity_fields",
        "uq_business_entity_fields_entity_persistent_key",
        "UNIQUE (business_entity_id, persistent_key)",
    )
    constraint(
        "business_entity_fields",
        "business_entity_fields_persistent_key_valid",
        "CHECK (persistent_key <> '' AND persistent_key = trim(persistent_key))",
    )
    constraint(
        "business_entity_fields",
        "uq_business_entity_fields_entity_id",
        "UNIQUE (business_entity_id, id)",
    )
    constraint(
        "business_entity_versions",
        "uq_business_entity_versions_entity_id",
        "UNIQUE (business_entity_id, id)",
    )
    constraint(
        "business_models",
        "fk_business_models_current_revision_own",
        """FOREIGN KEY
        (id, current_revision_id) REFERENCES business_model_revisions(business_model_id,id)
        ON DELETE RESTRICT""",
    )
    constraint(
        "business_entities",
        "fk_business_entities_effective_version_own",
        """FOREIGN KEY
        (id, effective_business_entity_version_id)
        REFERENCES business_entity_versions(business_entity_id,id) ON DELETE RESTRICT""",
    )
    constraint(
        "business_object_fields",
        "fk_business_object_fields_effective_value",
        """FOREIGN KEY
        (effective_value_id) REFERENCES business_object_field_values(id) ON DELETE RESTRICT""",
    )
    op.execute(
        "ALTER TABLE business_entity_relation_versions ADD COLUMN IF NOT EXISTS relation_id UUID"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema()
            AND table_name='business_entity_relation_versions'
            AND column_name='business_entity_relation_id') THEN
            UPDATE business_entity_relation_versions SET relation_id =
                md5('burbot-relation:' || business_entity_relation_id::text)::uuid
                WHERE relation_id IS NULL;
            ALTER TABLE business_entity_relation_versions
                ALTER COLUMN business_entity_relation_id DROP NOT NULL;
        END IF;
    END $$""")
    op.execute(
        "ALTER TABLE business_entity_relation_versions ALTER COLUMN relation_id SET NOT NULL"
    )
    op.execute("""ALTER TABLE business_entity_relation_versions
        DROP CONSTRAINT IF EXISTS ex_business_entity_relation_versions_bitemporal_overlap""")
    constraint(
        "business_entity_relation_versions",
        "ex_business_entity_relation_versions_bitemporal_overlap",
        """EXCLUDE USING gist
        (relation_id WITH =, tstzrange(valid_from,valid_to,'[)') WITH &&,
        tstzrange(transaction_from,transaction_to,'[)') WITH &&)""",
    )
    constraint(
        "business_entity_relation_versions",
        "fk_relation_versions_from_field_own",
        """FOREIGN KEY
        (from_entity_id,from_field_id) REFERENCES business_entity_fields(business_entity_id,id)
        ON DELETE RESTRICT""",
    )
    constraint(
        "business_entity_relation_versions",
        "fk_relation_versions_to_field_own",
        """FOREIGN KEY
        (to_entity_id,to_field_id) REFERENCES business_entity_fields(business_entity_id,id)
        ON DELETE RESTRICT""",
    )
    op.execute("""CREATE TABLE IF NOT EXISTS business_definition_code_versions (
        id BIGSERIAL PRIMARY KEY,
        business_model_id BIGINT NOT NULL REFERENCES business_models(id) ON
        DELETE RESTRICT,
        version INTEGER NOT NULL, code TEXT NOT NULL, sha256 VARCHAR(64) NOT
        NULL,
        schema_revision_id BIGINT, reason TEXT, created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),
        CONSTRAINT uq_business_definition_code_version UNIQUE(business_model_id,
        version),
        CONSTRAINT fk_business_definition_code_schema_own FOREIGN
        KEY(business_model_id,schema_revision_id)
        REFERENCES business_model_revisions(business_model_id,id) ON DELETE
        RESTRICT)""")


def downgrade():
    # Keep additive metadata, so later re-upgrade retains persistent identities
    # and code history. Legacy code can omit those now-nullable columns.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM business_objects WHERE archived_at IS NOT NULL)
        THEN
            RAISE EXCEPTION 'Cannot downgrade archived business objects
            without an explicit migration';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE
        table_schema=current_schema()
            AND table_name='business_entity_relation_versions'
            AND column_name='business_entity_relation_id') THEN
            RAISE EXCEPTION 'Cannot downgrade native UUID relations without
            an explicit migration';
        END IF;
        IF EXISTS (SELECT 1 FROM business_entity_relation_versions
                   WHERE business_entity_relation_id IS NULL) THEN
            RAISE EXCEPTION 'Cannot downgrade native UUID relations without
            an explicit migration';
        END IF;
    END $$""")
    rename_revision_columns("business_model_revision_id", "revision_id")
    op.execute("ALTER TABLE business_entity_fields ALTER COLUMN persistent_key DROP NOT NULL")
    constraint(
        "business_entity_fields",
        "uq_business_entity_fields_entity_physical_name",
        "UNIQUE (business_entity_id, physical_name)",
    )
    op.execute(
        "ALTER TABLE business_entity_relation_versions ALTER COLUMN relation_id DROP NOT NULL"
    )
    constraint(
        "business_entity_relation_versions",
        "ex_business_relation_legacy_overlap",
        """EXCLUDE
        USING gist (business_entity_relation_id WITH =, tstzrange(valid_from,valid_to,'[)') WITH &&,
        tstzrange(transaction_from,transaction_to,'[)') WITH &&)""",
    )
