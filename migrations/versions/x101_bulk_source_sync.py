"""Authorize Source registration separately from workspace object creation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "x101_bulk_source_sync"
down_revision = "x100_extension_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "extension_sync_workspaces",
        sa.Column("source_policy", JSONB, nullable=False, server_default="{}"),
    )


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM extension_sync_workspaces WHERE source_policy <> '{}'::jsonb
            ) THEN
                RAISE EXCEPTION 'Clear workspace Source policies before downgrading';
            END IF;
        END $$;
    """)
    op.drop_column("extension_sync_workspaces", "source_policy")
