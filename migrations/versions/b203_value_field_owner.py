"""Require a canonical value's validating version to belong to its slot's field."""

import sqlalchemy as sa
from alembic import op

revision = "b203_value_field_owner"
down_revision = "b202_value_field_version"
branch_labels = None
depends_on = None

VALUES = "business_object_field_values"
SLOTS = "business_object_fields"
VERSIONS = "business_entity_field_versions"
FIELD_ID = "business_entity_field_id"
VERSION_ID = "validated_against_field_version_id"
SLOT_ID = "business_object_field_id"
SLOT_FK = "business_object_field_values_business_object_field_id_fkey"
VALIDATION_FK = "fk_business_values_validated_field_version"
OWNER_FK = "fk_business_values_slot_field"
SLOT_OWNER = "uq_business_object_fields_field_owner"
VERSION_OWNER = "uq_business_field_versions_field_owner"
HISTORY_INDEX = "ix_business_values_entity_field_version"


def upgrade():
    op.add_column(VALUES, sa.Column(FIELD_ID, sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE business_object_field_values AS value
        SET business_entity_field_id = slot.business_entity_field_id
        FROM business_object_fields AS slot
        WHERE slot.id = value.business_object_field_id
    """)
    op.alter_column(VALUES, FIELD_ID, nullable=False)
    op.create_unique_constraint(SLOT_OWNER, SLOTS, ["id", FIELD_ID])
    op.create_unique_constraint(VERSION_OWNER, VERSIONS, ["id", FIELD_ID])
    op.drop_constraint(SLOT_FK, VALUES, type_="foreignkey")
    op.drop_constraint(VALIDATION_FK, VALUES, type_="foreignkey")
    op.create_foreign_key(OWNER_FK, VALUES, SLOTS, [SLOT_ID, FIELD_ID], ["id", FIELD_ID])
    op.create_foreign_key(
        VALIDATION_FK,
        VALUES,
        VERSIONS,
        [VERSION_ID, FIELD_ID],
        ["id", FIELD_ID],
        ondelete="RESTRICT",
    )
    op.create_index(HISTORY_INDEX, VALUES, [FIELD_ID, VERSION_ID])


def downgrade():
    op.drop_index(HISTORY_INDEX, table_name=VALUES)
    op.drop_constraint(OWNER_FK, VALUES, type_="foreignkey")
    op.drop_constraint(VALIDATION_FK, VALUES, type_="foreignkey")
    op.create_foreign_key(SLOT_FK, VALUES, SLOTS, [SLOT_ID], ["id"])
    op.create_foreign_key(
        VALIDATION_FK, VALUES, VERSIONS, [VERSION_ID], ["id"], ondelete="RESTRICT"
    )
    op.drop_constraint(SLOT_OWNER, SLOTS, type_="unique")
    op.drop_constraint(VERSION_OWNER, VERSIONS, type_="unique")
    op.drop_column(VALUES, FIELD_ID)
