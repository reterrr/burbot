"""Deliver authorized snapshot viewer commands to one Firefox agent."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "m104_snapshot_open_commands"
down_revision = "m103_monitoring_source_history"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("monitoring_agents", sa.Column("snapshot_seen_at", sa.DateTime(timezone=True)))
    op.create_table(
        "monitoring_snapshot_open_commands",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("source_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_agent_id",
            sa.Uuid(),
            sa.ForeignKey("monitoring_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("selector_context", JSONB()),
        sa.CheckConstraint(
            "state IN ('pending','claimed','opened','failed','expired')",
            name="monitoring_snapshot_command_state",
        ),
    )
    op.create_index(
        "ix_monitoring_snapshot_commands_agent",
        "monitoring_snapshot_open_commands",
        ["target_agent_id", "created_at", "id"],
        postgresql_where=sa.text("state IN ('pending','claimed')"),
    )


def downgrade():
    op.drop_table("monitoring_snapshot_open_commands")
    op.drop_column("monitoring_agents", "snapshot_seen_at")
