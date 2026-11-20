"""Durable Firefox source monitoring and versioned rendered DOM snapshots."""

from alembic import op

revision = "m100_source_monitoring"
down_revision = "e103_selector_tree"
branch_labels = None
depends_on = None

SNAPSHOT_COLUMNS = (
    "representation",
    "representation_version",
    "structure_hash_version",
    "hash_algorithm",
)
MONITORING_TABLES = (
    "monitoring_sources",
    "monitoring_agents",
    "monitoring_agent_sources",
    "monitoring_jobs",
    "monitoring_job_selectors",
    "monitoring_uploads",
    "source_check_runs",
)
VERIFIED = (
    "AND extraction_run_id IS NOT NULL AND source_snapshot_id IS NOT NULL "
    "AND execution_key IS NOT NULL) OR (provenance = 'client_reported' "
    "AND extraction_run_id IS NULL AND execution_key IS NULL)"
)


def evaluation_provenance(predicate):
    op.drop_constraint("selector_evaluations_provenance", "selector_evaluations", type_="check")
    op.create_check_constraint(
        "selector_evaluations_provenance",
        "selector_evaluations",
        f"({predicate} {VERIFIED}",
    )


def upgrade():
    for name in SNAPSHOT_COLUMNS:
        op.execute(f"ALTER TABLE source_snapshots ADD COLUMN {name} VARCHAR")
    op.execute("ALTER TYPE task_reference_type ADD VALUE IF NOT EXISTS 'business_object_field'")
    evaluation_provenance("provenance IN ('backend_verified', 'browser_agent_reported')")
    op.execute("""
CREATE TABLE monitoring_sources (
    source_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    origins JSONB NOT NULL,
    enabled BOOLEAN NOT NULL,
    approved_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (source_id),
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE monitoring_agents (
    id UUID NOT NULL,
    name VARCHAR(150) NOT NULL,
    token_digest VARCHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    UNIQUE (token_digest)
)
    """)
    op.execute("""
CREATE TABLE monitoring_agent_sources (
    agent_id UUID NOT NULL,
    source_id BIGINT NOT NULL,
    PRIMARY KEY (agent_id, source_id),
    FOREIGN KEY(agent_id) REFERENCES monitoring_agents (id),
    FOREIGN KEY(source_id) REFERENCES monitoring_sources (source_id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE monitoring_jobs (
    id UUID NOT NULL,
    source_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    origins JSONB NOT NULL,
    reason VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    available_at TIMESTAMP WITH TIME ZONE NOT NULL,
    agent_id UUID,
    lease_id UUID,
    claimed_at TIMESTAMP WITH TIME ZONE,
    lease_expires_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    attempt_count INTEGER NOT NULL,
    processing_attempts INTEGER NOT NULL,
    source_snapshot_id BIGINT,
    extraction_run_id BIGINT,
    completion_key UUID,
    completion_digest VARCHAR(64),
    completion_json JSONB,
    error_code VARCHAR(64),
    PRIMARY KEY (id),
    CONSTRAINT monitoring_job_status CHECK (status IN (
        'pending','retry_pending','claimed','capturing','uploading',
        'uploaded','processing','completed','failed','cancelled'
    )),
    CONSTRAINT monitoring_job_attempts CHECK (attempt_count >= 0 AND processing_attempts >= 0),
    FOREIGN KEY(source_id) REFERENCES monitoring_sources (source_id) ON DELETE RESTRICT,
    FOREIGN KEY(agent_id) REFERENCES monitoring_agents (id),
    FOREIGN KEY(source_snapshot_id) REFERENCES source_snapshots (id) ON DELETE RESTRICT,
    UNIQUE (extraction_run_id),
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id)
)
    """)
    op.execute("CREATE INDEX ix_monitoring_jobs_queue ON monitoring_jobs (status, available_at)")
    op.execute(
        "CREATE UNIQUE INDEX uq_monitoring_jobs_active_source ON monitoring_jobs (source_id) "
        "WHERE status NOT IN ('completed','failed','cancelled')"
    )
    op.execute("""
CREATE TABLE monitoring_job_selectors (
    job_id UUID NOT NULL,
    selector_id BIGINT NOT NULL,
    version_id BIGINT NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    PRIMARY KEY (job_id, selector_id),
    CONSTRAINT fk_monitoring_selector_version_owner FOREIGN KEY(selector_id, version_id)
        REFERENCES selector_versions (selector_id, id) ON DELETE RESTRICT,
    FOREIGN KEY(job_id) REFERENCES monitoring_jobs (id),
    FOREIGN KEY(selector_id) REFERENCES selectors (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE monitoring_uploads (
    id UUID NOT NULL,
    job_id UUID NOT NULL,
    lease_id UUID NOT NULL,
    storage_key TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    content_size BIGINT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sealed_key TEXT,
    cleaned_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT monitoring_upload_positive_size CHECK (content_size > 0),
    CONSTRAINT uq_monitoring_upload_per_attempt UNIQUE (job_id, lease_id),
    FOREIGN KEY(job_id) REFERENCES monitoring_jobs (id),
    UNIQUE (storage_key)
)
    """)
    op.execute(
        "CREATE INDEX ix_monitoring_uploads_cleanup ON monitoring_uploads (expires_at, cleaned_at)"
    )
    op.execute("""
CREATE TABLE source_check_runs (
    job_id UUID NOT NULL,
    scheduling_flow_run_id VARCHAR(64),
    processing_flow_run_id VARCHAR(64),
    acquired_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    change_status VARCHAR(32),
    field_results JSONB,
    PRIMARY KEY (job_id),
    FOREIGN KEY(job_id) REFERENCES monitoring_jobs (id)
)
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM monitoring_jobs)
                OR EXISTS (SELECT 1 FROM monitoring_agents)
                OR EXISTS (SELECT 1 FROM monitoring_sources)
                OR EXISTS (SELECT 1 FROM selector_evaluations
                           WHERE provenance = 'browser_agent_reported')
                OR EXISTS (SELECT 1 FROM source_snapshots WHERE representation IS NOT NULL
                           OR representation_version IS NOT NULL
                           OR structure_hash_version IS NOT NULL
                           OR hash_algorithm IS NOT NULL)
                OR EXISTS (SELECT 1 FROM task_references
                           WHERE reference_type::text = 'business_object_field')
            THEN
                RAISE EXCEPTION 'Cannot downgrade while source monitoring data exists';
            END IF;
        END $$;
    """)
    for name in reversed(MONITORING_TABLES):
        op.drop_table(name)
    evaluation_provenance("provenance = 'backend_verified'")
    for name in SNAPSHOT_COLUMNS:
        op.drop_column("source_snapshots", name)
    # PostgreSQL cannot remove a single enum member without rebuilding the type.
