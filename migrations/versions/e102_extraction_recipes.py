"""Persist complete extraction recipes and immutable snapshot page URLs.

Revision ID: e102_extraction_recipes
Revises: e101_extraction_capture

Existing selectors stay NULL/unknown: offsets and literal token classes do not
prove which extraction operation was intended. Execution refuses these active
definitions until manual rediscovery appends a typed recipe version. Old snapshot
URLs are also unknown; never backfill them from a potentially changed Source.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e102_extraction_recipes"
down_revision = "e101_extraction_capture"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "field_selectors", sa.Column("extraction_json", postgresql.JSONB(), nullable=True)
    )
    op.alter_column("field_selectors", "selector_type", nullable=True)
    op.alter_column("field_selectors", "selector_string", nullable=True)
    op.create_check_constraint(
        "selector_complete_locator",
        "field_selectors",
        "(selector_type IS NULL) = (selector_string IS NULL)",
    )
    op.add_column("source_snapshots", sa.Column("page_url", sa.Text(), nullable=True))


def downgrade():
    # Dropping HOW would quietly turn attribute/selection recipes back into
    # ambiguous locators. Refuse data loss, including closed historical versions.
    op.execute("""
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM field_selectors WHERE extraction_json IS NOT NULL)
       OR EXISTS (SELECT 1 FROM source_snapshots WHERE page_url IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot downgrade: extraction recipes or snapshot URLs would be lost';
    END IF;
END $$;
    """)
    op.drop_column("source_snapshots", "page_url")
    op.drop_constraint("selector_complete_locator", "field_selectors", type_="check")
    op.alter_column("field_selectors", "selector_string", nullable=False)
    op.alter_column("field_selectors", "selector_type", nullable=False)
    op.drop_column("field_selectors", "extraction_json")
