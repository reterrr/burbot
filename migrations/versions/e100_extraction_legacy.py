"""Register the pre-existing workflow evidence tables without losing legacy rows.

Revision ID: e100_extraction_legacy
Revises: c67ac5d0c446

The previous implementation shipped no DDL. IF NOT EXISTS also supports an
installation that created these exact legacy tables with SQLModel.create_all.
"""

from alembic import op

revision = "e100_extraction_legacy"
down_revision = "c67ac5d0c446"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
DO $$ BEGIN CREATE TYPE extraction_run_status AS ENUM ('running', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
CREATE TABLE IF NOT EXISTS extraction_runs (
    id BIGSERIAL NOT NULL, 
    workflow_id BIGINT NOT NULL, 
    source_id BIGINT NOT NULL, 
    source_snapshot_id BIGINT NOT NULL, 
    status extraction_run_status DEFAULT 'running' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    error_message TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT extraction_runs_finished_after_started CHECK (finished_at IS NULL OR finished_at >= started_at), 
    FOREIGN KEY(workflow_id) REFERENCES workflows (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_runs_snapshot ON extraction_runs (source_snapshot_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_runs_source ON extraction_runs (source_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_runs_status ON extraction_runs (status)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_runs_workflow ON extraction_runs (workflow_id)
    """)
    op.execute("""
CREATE TABLE IF NOT EXISTS field_observations (
    id BIGSERIAL NOT NULL, 
    extraction_run_id BIGINT NOT NULL, 
    source_field_tracking_id BIGINT NOT NULL, 
    source_object_field_tracking_id BIGINT NOT NULL, 
    business_object_id BIGINT NOT NULL, 
    business_object_field_id BIGINT NOT NULL, 
    observed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_field_observations_run_object_field UNIQUE (extraction_run_id, business_object_field_id), 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE RESTRICT, 
    FOREIGN KEY(source_field_tracking_id) REFERENCES source_field_trackings (id) ON DELETE RESTRICT, 
    FOREIGN KEY(source_object_field_tracking_id) REFERENCES source_object_field_trackings (id) ON DELETE RESTRICT, 
    FOREIGN KEY(business_object_id) REFERENCES business_objects (id) ON DELETE RESTRICT, 
    FOREIGN KEY(business_object_field_id) REFERENCES business_object_fields (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_field_observations_object ON field_observations (business_object_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_field_observations_object_field ON field_observations
(business_object_field_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_field_observations_run ON field_observations (extraction_run_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_field_observations_source_field_tracking ON field_observations
(source_field_tracking_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_field_observations_source_object_field_tracking ON
field_observations (source_object_field_tracking_id)
    """)
    op.execute("""
CREATE TABLE IF NOT EXISTS extraction_concrete_values (
    id BIGSERIAL NOT NULL, 
    field_observation_id BIGINT NOT NULL, 
    source_snapshot_id BIGINT NOT NULL, 
    raw_value TEXT NOT NULL, 
    char_start INTEGER NOT NULL, 
    char_end INTEGER NOT NULL, 
    token_class_id VARCHAR(150) NOT NULL, 
    value_index INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT extraction_values_char_start_nonnegative CHECK (char_start >= 0), 
    CONSTRAINT extraction_values_char_range CHECK (char_end > char_start), 
    CONSTRAINT extraction_values_index_nonnegative CHECK (value_index >= 0), 
    CONSTRAINT uq_extraction_values_observation_index UNIQUE (field_observation_id, value_index), 
    FOREIGN KEY(field_observation_id) REFERENCES field_observations (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_values_observation ON extraction_concrete_values
(field_observation_id)
    """)
    op.execute("""
CREATE INDEX IF NOT EXISTS ix_extraction_values_snapshot ON extraction_concrete_values
(source_snapshot_id)
    """)


def downgrade():
    op.drop_table("extraction_concrete_values")
    op.drop_table("field_observations")
    op.drop_table("extraction_runs")
    op.execute("""
DROP TYPE extraction_run_status
    """)
