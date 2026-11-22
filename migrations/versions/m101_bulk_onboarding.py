"""Persist resumable monitoring onboarding runs and per-origin rate limits."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m101_bulk_onboarding"
down_revision = "x101_bulk_source_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "monitoring_agent_sources",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_monitoring_agent_sources_coverage",
        "monitoring_agent_sources",
        ["source_id", "agent_id"],
        postgresql_where=sa.text("enabled"),
    )
    op.create_index("ix_sources_type_state_id", "sources", ["type", "state", "id"])
    op.create_index(
        "ix_source_check_schedules_due",
        "source_check_schedules",
        ["next_check_at", "source_id"],
        postgresql_where=sa.text("enabled"),
    )
    op.create_table(
        "monitoring_onboarding_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_name", sa.String(48), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("continuous", sa.Boolean(), nullable=False),
        sa.Column("after_source_id", sa.BigInteger(), nullable=False),
        sa.Column("through_source_id", sa.BigInteger(), nullable=True),
        sa.Column("scan_complete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_serviced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_monitoring_onboarding_continuous_policy",
        "monitoring_onboarding_runs",
        ["policy_name"],
        unique=True,
        postgresql_where=sa.text("continuous"),
    )
    op.create_index(
        "ix_monitoring_onboarding_run_service",
        "monitoring_onboarding_runs",
        [sa.text("coalesce(last_serviced_at, created_at)"), "created_at", "id"],
    )
    op.create_table(
        "monitoring_onboarding_items",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("monitoring_onboarding_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_state_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="onboarding_attempts_nonnegative"),
    )
    op.create_index(
        "ix_monitoring_onboarding_items_pending",
        "monitoring_onboarding_items",
        ["run_id", "available_at", "source_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "monitoring_discovery_origins",
        sa.Column("origin", sa.String(260), primary_key=True),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    # Rows suppressed by an operator must stay out of the restored scope.
    op.execute("DELETE FROM monitoring_agent_sources WHERE NOT enabled")
    op.drop_table("monitoring_discovery_origins")
    op.drop_table("monitoring_onboarding_items")
    op.drop_table("monitoring_onboarding_runs")
    op.drop_index("ix_source_check_schedules_due", table_name="source_check_schedules")
    op.drop_index("ix_sources_type_state_id", table_name="sources")
    op.drop_index("ix_monitoring_agent_sources_coverage", table_name="monitoring_agent_sources")
    op.drop_column("monitoring_agent_sources", "enabled")
