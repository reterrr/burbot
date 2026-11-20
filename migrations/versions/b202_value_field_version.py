"""Record the field definition used to validate each canonical value."""

import sqlalchemy as sa
from alembic import op

revision = "b202_value_field_version"
down_revision = "b201_collections"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "business_object_field_values",
        sa.Column("validated_against_field_version_id", sa.BigInteger(), nullable=True),
    )
    # A copied valid-time prefix was not revalidated when it was copied. Find
    # its original decision (same slot, start and payload) before resolving the
    # definition active at that decision's recorded time. Do not use today's
    # definition, or the backdated value's valid_from, to infer validation.
    op.execute("""
        WITH decisions AS (
            SELECT value.id, slot.business_entity_field_id,
                (SELECT min(original.transaction_from)
                 FROM business_object_field_values AS original
                 WHERE original.business_object_field_id = value.business_object_field_id
                   AND original.valid_from = value.valid_from
                   AND original.transaction_from <= value.transaction_from
                   AND original.value_json IS NOT DISTINCT FROM value.value_json
                   AND original.collection_id IS NOT DISTINCT FROM value.collection_id
                   AND (original.valid_to IS NULL OR original.valid_to >= value.valid_to)
                ) AS recorded_at
            FROM business_object_field_values AS value
            JOIN business_object_fields AS slot ON slot.id = value.business_object_field_id
        )
        UPDATE business_object_field_values AS value
        SET validated_against_field_version_id = (
            SELECT definition.id
            FROM business_entity_field_versions AS definition
            JOIN decisions ON decisions.id = value.id
            WHERE definition.business_entity_field_id = decisions.business_entity_field_id
              AND definition.status = 'ACTIVE'
              AND tstzrange(definition.valid_from, definition.valid_to, '[)')
                  @> decisions.recorded_at
              AND tstzrange(definition.transaction_from, definition.transaction_to, '[)')
                  @> decisions.recorded_at
        )
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM business_object_field_values
                WHERE validated_against_field_version_id IS NULL
            ) THEN
                RAISE EXCEPTION 'Cannot backfill validated_against_field_version_id: '
                    'no active field definition at the original decision time; '
                    'repair legacy definition history before retrying';
            END IF;
        END $$
    """)
    op.alter_column(
        "business_object_field_values", "validated_against_field_version_id", nullable=False
    )
    op.create_foreign_key(
        "fk_business_values_validated_field_version",
        "business_object_field_values",
        "business_entity_field_versions",
        ["validated_against_field_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "fk_business_values_validated_field_version",
        "business_object_field_values",
        type_="foreignkey",
    )
    op.drop_column("business_object_field_values", "validated_against_field_version_id")
