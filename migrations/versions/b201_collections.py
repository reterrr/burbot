"""Universal collection containers and independently versioned ordered items."""

import sqlalchemy as sa
from alembic import op

revision = "b201_collections"
down_revision = "b200_business_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE business_collections (
        id BIGSERIAL PRIMARY KEY, root_field_id BIGINT REFERENCES
        business_object_fields(id) ON DELETE RESTRICT,
        parent_item_id BIGINT, revision BIGINT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT business_collections_one_owner
        CHECK(num_nonnulls(root_field_id,parent_item_id)=1),
        CONSTRAINT business_collections_revision CHECK(revision>=0),
        CONSTRAINT uq_business_collections_parent_item UNIQUE(parent_item_id),
        CONSTRAINT uq_business_collections_root_identity
        UNIQUE(root_field_id,id))""")
    op.execute(
        "CREATE INDEX ix_business_collections_root_field ON business_collections(root_field_id)"
    )
    op.execute("""CREATE TABLE business_collection_items (
        id BIGSERIAL PRIMARY KEY, collection_id BIGINT NOT NULL REFERENCES
        business_collections(id) ON DELETE RESTRICT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_business_collection_items_owner UNIQUE(id,collection_id))""")
    op.execute(
        "CREATE INDEX ix_business_collection_items_collection ON "
        "business_collection_items(collection_id)"
    )
    op.execute(
        "ALTER TABLE business_collections ADD CONSTRAINT "
        "fk_business_collections_parent_item FOREIGN KEY(parent_item_id) REFERENCES "
        "business_collection_items(id) ON DELETE RESTRICT"
    )
    op.execute("""CREATE TABLE business_collection_item_versions (
        id BIGSERIAL PRIMARY KEY, item_id BIGINT NOT NULL, collection_id BIGINT
        NOT NULL,
        position INTEGER, value_json JSONB,
        reference_object_id BIGINT REFERENCES business_objects(id) ON DELETE
        RESTRICT,
        source_id BIGINT REFERENCES sources(id) ON DELETE RESTRICT,
        present BOOLEAN NOT NULL, valid_from TIMESTAMPTZ NOT NULL, valid_to
        TIMESTAMPTZ,
        transaction_from TIMESTAMPTZ NOT NULL, transaction_to TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT fk_business_collection_versions_item_owner FOREIGN
        KEY(item_id,collection_id)
            REFERENCES business_collection_items(id,collection_id) ON DELETE
            RESTRICT,
        CONSTRAINT business_collection_versions_valid_range CHECK(valid_to IS
        NULL OR valid_to>valid_from),
        CONSTRAINT business_collection_versions_transaction_range
        CHECK(transaction_to IS NULL OR transaction_to>transaction_from),
        CONSTRAINT business_collection_versions_value_channel CHECK(
            (present AND position>=0 AND position IS NOT NULL AND
            num_nonnulls(value_json,reference_object_id,source_id)=1
            AND (value_json IS NULL OR value_json<>'null'::jsonb)) OR
            (NOT present AND position IS NULL AND
            num_nonnulls(value_json,reference_object_id,source_id)=0)),
        CONSTRAINT ex_business_collection_versions_item_overlap EXCLUDE USING
        gist (
            item_id WITH =, tstzrange(valid_from,valid_to,'[)') WITH &&,
            tstzrange(transaction_from,transaction_to,'[)') WITH &&),
        CONSTRAINT ex_business_collection_versions_position_overlap EXCLUDE
        USING gist (
            collection_id WITH =, position WITH =,
            tstzrange(valid_from,valid_to,'[)') WITH &&,
            tstzrange(transaction_from,transaction_to,'[)') WITH &&)
            WHERE(present)
            DEFERRABLE INITIALLY DEFERRED)""")
    for suffix, column in (
        ("item", "item_id"),
        ("collection", "collection_id"),
        ("reference", "reference_object_id"),
        ("source", "source_id"),
    ):
        op.execute(
            f"CREATE INDEX ix_business_collection_versions_{suffix} "
            f"ON business_collection_item_versions({column})"
        )
    op.execute("ALTER TABLE business_object_field_values ALTER COLUMN value_json DROP NOT NULL")
    op.execute("""CREATE INDEX ix_business_collection_versions_recorded
        ON business_collection_item_versions(collection_id, transaction_from)""")
    op.execute(
        "ALTER TABLE business_object_field_values ADD COLUMN collection_id BIGINT "
        "REFERENCES business_collections(id) ON DELETE RESTRICT"
    )
    op.execute(
        "CREATE INDEX ix_business_object_field_values_collection_id ON "
        "business_object_field_values(collection_id)"
    )
    op.execute("""ALTER TABLE business_object_field_values ADD CONSTRAINT
business_object_field_values_value_channel CHECK(
        (collection_id IS NULL AND value_json IS NOT NULL) OR (collection_id IS
        NOT NULL AND value_json IS NULL))""")
    op.execute("""ALTER TABLE business_object_field_values ADD CONSTRAINT
fk_business_values_collection_owner
        FOREIGN KEY(business_object_field_id,collection_id) REFERENCES
        business_collections(root_field_id,id) ON DELETE RESTRICT""")


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM business_collections) OR EXISTS(SELECT 1 FROM "
            "business_entity_field_versions WHERE definition_json->>'type'='list')"
        )
    ):
        raise RuntimeError(
            "Cannot downgrade Collections without losing collection data or definitions"
        )
    op.execute(
        "ALTER TABLE business_object_field_values DROP CONSTRAINT "
        "fk_business_values_collection_owner"
    )
    op.execute(
        "ALTER TABLE business_object_field_values DROP CONSTRAINT "
        "business_object_field_values_value_channel"
    )
    op.execute("ALTER TABLE business_object_field_values DROP COLUMN collection_id")
    op.execute("ALTER TABLE business_object_field_values ALTER COLUMN value_json SET NOT NULL")
    op.execute(
        "ALTER TABLE business_collections DROP CONSTRAINT fk_business_collections_parent_item"
    )
    op.drop_table("business_collection_item_versions")
    op.drop_table("business_collection_items")
    op.drop_table("business_collections")
