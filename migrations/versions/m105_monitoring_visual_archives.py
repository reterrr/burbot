"""Associate an optional visual archive with each newly captured snapshot."""

import sqlalchemy as sa
from alembic import op

revision = "m105_monitoring_visual_archives"
down_revision = "m104_snapshot_open_commands"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "monitoring_uploads",
        sa.Column("kind", sa.String(8), nullable=False, server_default="evidence"),
    )
    op.drop_constraint("uq_monitoring_upload_per_attempt", "monitoring_uploads", type_="unique")
    op.create_unique_constraint(
        "uq_monitoring_upload_per_artifact", "monitoring_uploads", ["job_id", "lease_id", "kind"]
    )
    op.create_check_constraint(
        "monitoring_upload_kind", "monitoring_uploads", "kind IN ('evidence','visual')"
    )
    op.create_table(
        "monitoring_visual_archives",
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("source_snapshots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "file_id",
            sa.BigInteger(),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("file_id", name="uq_monitoring_visual_archive_file"),
    )


def downgrade():
    op.drop_table("monitoring_visual_archives")
    op.execute("DELETE FROM monitoring_uploads WHERE kind = 'visual'")
    op.drop_constraint("monitoring_upload_kind", "monitoring_uploads", type_="check")
    op.drop_constraint("uq_monitoring_upload_per_artifact", "monitoring_uploads", type_="unique")
    op.create_unique_constraint(
        "uq_monitoring_upload_per_attempt", "monitoring_uploads", ["job_id", "lease_id"]
    )
    op.drop_column("monitoring_uploads", "kind")
