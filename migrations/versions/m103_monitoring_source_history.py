"""Index monitoring check history by source and creation order."""

from alembic import op

revision = "m103_monitoring_source_history"
down_revision = "m102_trusted_monitoring"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_monitoring_jobs_source_created", "monitoring_jobs", ["source_id", "created_at", "id"]
    )


def downgrade():
    op.drop_index("ix_monitoring_jobs_source_created", table_name="monitoring_jobs")
