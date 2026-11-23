"""Persist trusted enrollment, agent designation, and per-job navigation policy."""

import sqlalchemy as sa
from alembic import op

revision = "m102_trusted_monitoring"
down_revision = "m101_bulk_onboarding"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("monitoring_sources", sa.Column("trusted_url", sa.Text()))
    op.add_column("monitoring_sources", sa.Column("trusted_origin", sa.Text()))
    op.add_column(
        "monitoring_agents",
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "monitoring_jobs",
        sa.Column("navigation_policy", sa.String(24), nullable=False, server_default="strict"),
    )
    op.create_check_constraint(
        "monitoring_job_navigation",
        "monitoring_jobs",
        "navigation_policy IN ('strict','public_https','public_http_https')",
    )


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM monitoring_jobs WHERE navigation_policy <> 'strict'
            ) THEN
                RAISE EXCEPTION 'Trusted job history requires the trusted monitoring schema';
            END IF;
        END $$;
    """)
    op.drop_constraint("monitoring_job_navigation", "monitoring_jobs", type_="check")
    op.drop_column("monitoring_jobs", "navigation_policy")
    op.drop_column("monitoring_agents", "trusted")
    op.drop_column("monitoring_sources", "trusted_origin")
    op.drop_column("monitoring_sources", "trusted_url")
