"""Add the Sources registry alongside the business layer.

Revision ID: c2e49d17a803
Revises: 7f479e3befc3
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c2e49d17a803"
down_revision = "7f479e3befc3"
branch_labels = None
depends_on = None

# Keep this migration independent from changing application enums.
source_type = postgresql.ENUM("HTML", "PDF", name="source_type", create_type=False)
source_state = postgresql.ENUM(
    "ADDING",
    "UNDISCOVERED",
    "DISCOVERING",
    "VALIDATING",
    "ACTIVE",
    "DEGRADED",
    "REDISCOVERING",
    "NEEDS_REVIEW",
    "FAILED",
    "SUSPENDED",
    "ARCHIVED",
    "BLOCKED_BY_POLICY",
    name="source_state",
    create_type=False,
)
source_trigger = postgresql.ENUM(
    "USER",
    "SCHEDULER",
    "CRAWLER",
    "PARSER",
    "VALIDATOR",
    "DISCOVERY_ENGINE",
    "POLICY_CHECK",
    "SYSTEM",
    name="source_state_trigger",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (source_type, source_state, source_trigger):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "stored_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("storage_key", sa.String(), nullable=False, unique=True),
        sa.Column("original_name", sa.String(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_bytes_non_negative"),
    )
    op.create_index("ix_stored_files_sha256", "stored_files", ["sha256"])

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("state", source_state, nullable=False, server_default=sa.text("'UNDISCOVERED'")),
        sa.Column(
            "last_state_change_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("url", name="uq_sources_url"),
    )
    op.create_index("ix_sources_state", "sources", ["state"])
    op.create_index("ix_sources_source_type", "sources", ["source_type"])

    op.create_table(
        "source_state_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_state", source_state, nullable=True),
        sa.Column("to_state", source_state, nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "triggered_by", source_trigger, nullable=False, server_default=sa.text("'SYSTEM'")
        ),
    )
    op.create_index(
        "ix_source_state_history_source_changed",
        "source_state_history",
        ["source_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_state_history_source_changed", table_name="source_state_history")
    op.drop_table("source_state_history")
    op.drop_index("ix_sources_source_type", table_name="sources")
    op.drop_index("ix_sources_state", table_name="sources")
    op.drop_table("sources")
    op.drop_index("ix_stored_files_sha256", table_name="stored_files")
    op.drop_table("stored_files")
    for enum in (source_trigger, source_state, source_type):
        enum.drop(op.get_bind(), checkfirst=True)
