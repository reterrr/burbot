"""Pin archive policy and store manifests independently of canonical evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "m106_monitoring_archive_modes"
down_revision = "m105_monitoring_visual_archives"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("monitoring_jobs", sa.Column("snapshot_policy", JSONB))
    op.add_column("monitoring_jobs", sa.Column("archive_result", JSONB))
    op.add_column(
        "monitoring_snapshot_open_commands",
        sa.Column("check_id", sa.Uuid(), sa.ForeignKey("monitoring_jobs.id", ondelete="SET NULL")),
    )
    op.create_table(
        "monitoring_archive_uploads",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("monitoring_jobs.id"), primary_key=True),
        sa.Column("lease_id", sa.Uuid(), primary_key=True),
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sealed", sa.Boolean(), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("cleaned_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("size_bytes > 0", name="monitoring_archive_positive_size"),
    )
    op.create_index(
        "ix_monitoring_archive_cleanup", "monitoring_archive_uploads", ["expires_at", "cleaned_at"]
    )


def downgrade():
    op.drop_table("monitoring_archive_uploads")
    op.drop_column("monitoring_snapshot_open_commands", "check_id")
    op.drop_column("monitoring_jobs", "archive_result")
    op.drop_column("monitoring_jobs", "snapshot_policy")
