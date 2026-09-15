"""Add snapshot captures, reusable definitions, and unresolved evidence.

Revision ID: e101_extraction_capture
Revises: e100_extraction_legacy

Frozen DDL: migrations do not import runtime models. Historical workflow evidence
is preserved with nullable capture-only columns, and normalized baselines are not
inferred for legacy multi-literal observations.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e101_extraction_capture"
down_revision = "e100_extraction_legacy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'XLSX'
    """)
    for value in ("pending", "succeeded", "partial"):
        op.execute("ALTER TYPE extraction_run_status ADD VALUE IF NOT EXISTS '" + value + "'")

    op.execute("""
CREATE TYPE extraction_element_from AS ENUM ('HTML', 'PDF', 'XLSX')
    """)
    op.execute("""
CREATE TYPE extraction_anchor_relation AS ENUM ('SAME_ROW', 'SAME_COLUMN', 'NEXT_SIBLING',
'PREVIOUS_SIBLING', 'PARENT', 'CHILD')
    """)
    op.execute("""
CREATE TYPE extraction_selector_type AS ENUM ('CSS', 'XPATH', 'ANCHOR_RELATIVE', 'TEXT_PATTERN',
'INDEX_ABSOLUTE', 'PDF_REGION', 'XLSX_RANGE')
    """)
    op.execute("""
CREATE TYPE extraction_discovery_method AS ENUM ('MANUAL', 'AUTOMATIC', 'PATTERN')
    """)
    op.execute("""
CREATE TYPE extraction_issue_code AS ENUM ('VALUE_NOT_FOUND', 'SELECTOR_BROKEN', 'AMBIGUOUS_MATCH')
    """)
    op.execute("""
CREATE TYPE extraction_observation_status AS ENUM ('DETECTED', 'VALIDATED', 'BOUND', 'ACCEPTED',
'REJECTED', 'SUPERSEDED')
    """)
    op.execute("""
CREATE TABLE source_snapshots (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    source_id BIGINT NOT NULL, 
    file_id BIGINT, 
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    mime_type VARCHAR, 
    content_hash VARCHAR(64), 
    structure_hash VARCHAR(64), 
    parser_version VARCHAR, 
    PRIMARY KEY (id), 
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT, 
    FOREIGN KEY(file_id) REFERENCES stored_files (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX ix_source_snapshots_source_fetched ON source_snapshots (source_id, fetched_at)
    """)
    op.execute("""
CREATE TABLE token_classes (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id VARCHAR(150) NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    validation_regex TEXT, 
    parser_name VARCHAR, 
    description TEXT, 
    PRIMARY KEY (id), 
    UNIQUE (name)
)
    """)
    op.execute("""
CREATE TABLE elements (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    extraction_run_id BIGINT NOT NULL, 
    parent_element_id BIGINT, 
    child_index INTEGER, 
    depth INTEGER, 
    element_from extraction_element_from NOT NULL, 
    text_content TEXT, 
    structural_hash VARCHAR(64), 
    PRIMARY KEY (id), 
    CONSTRAINT elements_child_index CHECK (child_index IS NULL OR child_index >= 0), 
    CONSTRAINT elements_depth CHECK (depth IS NULL OR depth >= 0), 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE RESTRICT, 
    FOREIGN KEY(parent_element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX ix_elements_run_parent ON elements (extraction_run_id, parent_element_id)
    """)
    op.execute("""
CREATE INDEX ix_elements_structural_hash ON elements (structural_hash)
    """)
    op.execute("""
CREATE TABLE source_scopes (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    source_id BIGINT NOT NULL, 
    parent_scope_id BIGINT, 
    business_entity_id BIGINT, 
    name VARCHAR(150) NOT NULL, 
    selector_type extraction_selector_type NOT NULL, 
    selector_string TEXT NOT NULL, 
    confidence_score FLOAT NOT NULL, 
    discovered_by extraction_discovery_method NOT NULL, 
    version INTEGER NOT NULL, 
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    valid_to TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_scope_version UNIQUE (source_id, name, version), 
    CONSTRAINT scope_version_positive CHECK (version > 0), 
    CONSTRAINT scope_validity CHECK (valid_to IS NULL OR valid_to > valid_from), 
    CONSTRAINT scope_confidence CHECK (confidence_score BETWEEN 0 AND 1), 
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT, 
    FOREIGN KEY(parent_scope_id) REFERENCES source_scopes (id) ON DELETE RESTRICT, 
    FOREIGN KEY(business_entity_id) REFERENCES business_entities (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE UNIQUE INDEX uq_scope_current ON source_scopes (source_id, name) WHERE valid_to IS NULL
    """)
    op.execute("""
CREATE TABLE ground_truth (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    field_observation_id BIGINT NOT NULL, 
    confirmed_by VARCHAR NOT NULL, 
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (field_observation_id), 
    FOREIGN KEY(field_observation_id) REFERENCES field_observations (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE extraction_captures (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    run_id BIGINT NOT NULL, 
    capture_key VARCHAR(150) NOT NULL, 
    payload_hash VARCHAR(64) NOT NULL, 
    result_json JSONB NOT NULL, 
    PRIMARY KEY (run_id), 
    FOREIGN KEY(run_id) REFERENCES extraction_runs (id) ON DELETE RESTRICT, 
    UNIQUE (capture_key)
)
    """)
    op.execute("""
CREATE TABLE elements_html (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    element_id BIGINT NOT NULL, 
    dom_path TEXT, 
    absolute_xpath TEXT, 
    css_path TEXT, 
    tag_name VARCHAR, 
    attributes_json JSONB, 
    PRIMARY KEY (element_id), 
    FOREIGN KEY(element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE elements_pdf (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    element_id BIGINT NOT NULL, 
    page_number INTEGER NOT NULL, 
    x0 FLOAT, 
    y0 FLOAT, 
    x1 FLOAT, 
    y1 FLOAT, 
    block_number INTEGER, 
    line_number INTEGER, 
    word_number INTEGER, 
    font_name VARCHAR, 
    font_size FLOAT, 
    ocr_confidence FLOAT, 
    PRIMARY KEY (element_id), 
    CONSTRAINT pdf_page_number CHECK (page_number > 0), 
    CONSTRAINT pdf_x_bounds CHECK (x1 IS NULL OR x0 IS NULL OR x1 >= x0), 
    CONSTRAINT pdf_y_bounds CHECK (y1 IS NULL OR y0 IS NULL OR y1 >= y0), 
    CONSTRAINT pdf_ocr_confidence CHECK (ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1), 
    FOREIGN KEY(element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE elements_xlsx (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    element_id BIGINT NOT NULL, 
    sheet_name VARCHAR NOT NULL, 
    cell_range VARCHAR NOT NULL, 
    PRIMARY KEY (element_id), 
    FOREIGN KEY(element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE anchor_element_references (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    anchor_element_id BIGINT NOT NULL, 
    target_element_id BIGINT NOT NULL, 
    relation_kind extraction_anchor_relation NOT NULL, 
    relative_offset INTEGER, 
    confidence FLOAT, 
    PRIMARY KEY (anchor_element_id, target_element_id, relation_kind), 
    CONSTRAINT anchor_confidence CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1), 
    FOREIGN KEY(anchor_element_id) REFERENCES elements (id) ON DELETE RESTRICT, 
    FOREIGN KEY(target_element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX ix_anchor_target ON anchor_element_references (target_element_id)
    """)
    op.execute("""
CREATE TABLE scope_instances (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    scope_id BIGINT NOT NULL, 
    extraction_run_id BIGINT NOT NULL, 
    parent_scope_instance_id BIGINT, 
    root_element_id BIGINT NOT NULL, 
    occurrence_index INTEGER NOT NULL, 
    instance_hash VARCHAR(64), 
    confidence FLOAT NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_scope_instance_root UNIQUE (extraction_run_id, scope_id, root_element_id), 
    CONSTRAINT scope_occurrence_nonnegative CHECK (occurrence_index >= 0), 
    CONSTRAINT scope_instance_confidence CHECK (confidence BETWEEN 0 AND 1), 
    FOREIGN KEY(scope_id) REFERENCES source_scopes (id) ON DELETE RESTRICT, 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE RESTRICT, 
    FOREIGN KEY(parent_scope_instance_id) REFERENCES scope_instances (id) ON DELETE RESTRICT, 
    FOREIGN KEY(root_element_id) REFERENCES elements (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX ix_scope_instances_hash ON scope_instances (instance_hash)
    """)
    op.execute("""
CREATE INDEX ix_scope_instances_parent ON scope_instances (parent_scope_instance_id)
    """)
    op.execute("""
CREATE TABLE field_selectors (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    scope_id BIGINT NOT NULL, 
    source_field_tracking_id BIGINT NOT NULL, 
    selector_type extraction_selector_type NOT NULL, 
    selector_string TEXT NOT NULL, 
    confidence_score FLOAT NOT NULL, 
    discovered_by extraction_discovery_method NOT NULL, 
    version INTEGER NOT NULL, 
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    valid_to TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_selector_version UNIQUE (scope_id, source_field_tracking_id, version), 
    CONSTRAINT selector_version_positive CHECK (version > 0), 
    CONSTRAINT selector_confidence CHECK (confidence_score BETWEEN 0 AND 1), 
    CONSTRAINT selector_validity CHECK (valid_to IS NULL OR valid_to > valid_from), 
    FOREIGN KEY(scope_id) REFERENCES source_scopes (id) ON DELETE RESTRICT, 
    FOREIGN KEY(source_field_tracking_id) REFERENCES source_field_trackings (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE UNIQUE INDEX uq_selector_current ON field_selectors (scope_id, source_field_tracking_id)
WHERE valid_to IS NULL
    """)
    op.execute("""
CREATE TABLE extraction_issues (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id BIGSERIAL NOT NULL, 
    extraction_run_id BIGINT NOT NULL, 
    code extraction_issue_code NOT NULL, 
    scope_instance_id BIGINT, 
    business_entity_field_id BIGINT, 
    message TEXT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE RESTRICT, 
    FOREIGN KEY(scope_instance_id) REFERENCES scope_instances (id) ON DELETE RESTRICT, 
    FOREIGN KEY(business_entity_field_id) REFERENCES business_entity_fields (id) ON DELETE RESTRICT
)
    """)
    op.alter_column("extraction_runs", "workflow_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column(
        "extraction_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.add_column("extraction_runs", sa.Column("extractor_version", sa.String(150), nullable=True))
    for column in (
        "source_object_field_tracking_id",
        "business_object_id",
        "business_object_field_id",
    ):
        op.alter_column("field_observations", column, existing_type=sa.BigInteger(), nullable=True)
    op.add_column(
        "field_observations", sa.Column("scope_instance_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "field_observations", sa.Column("concrete_value_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "field_observations",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
    )
    op.add_column(
        "field_observations",
        sa.Column(
            "status",
            postgresql.ENUM(
                "DETECTED",
                "VALIDATED",
                "BOUND",
                "ACCEPTED",
                "REJECTED",
                "SUPERSEDED",
                name="extraction_observation_status",
                create_type=False,
            ),
            nullable=False,
            server_default="DETECTED",
        ),
    )
    op.add_column(
        "field_observations", sa.Column("supersedes_observation_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "field_observations", sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("field_observations", sa.Column("notes", sa.Text(), nullable=True))
    op.drop_constraint(
        "uq_field_observations_run_object_field", "field_observations", type_="unique"
    )
    op.create_foreign_key(
        "fk_observation_scope",
        "field_observations",
        "scope_instances",
        ["scope_instance_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_observation_concrete_value",
        "field_observations",
        "extraction_concrete_values",
        ["concrete_value_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_observation_supersedes",
        "field_observations",
        "field_observations",
        ["supersedes_observation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column(
        "extraction_concrete_values",
        "field_observation_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    for column in ("char_start", "char_end"):
        op.alter_column(
            "extraction_concrete_values", column, existing_type=sa.Integer(), nullable=True
        )
    op.add_column(
        "extraction_concrete_values", sa.Column("element_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "extraction_concrete_values", sa.Column("normalized_value", sa.Text(), nullable=True)
    )
    op.add_column(
        "extraction_concrete_values",
        sa.Column("is_semantic_null", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "extraction_concrete_values", sa.Column("value_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "extraction_concrete_values",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
    )
    op.add_column(
        "extraction_concrete_values",
        sa.Column("discovered_by", sa.String(30), nullable=False, server_default="MANUAL"),
    )
    op.create_foreign_key(
        "fk_value_element",
        "extraction_concrete_values",
        "elements",
        ["element_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute("""
ALTER TABLE field_observations ADD CONSTRAINT observations_bound_status CHECK (status NOT IN
('BOUND', 'ACCEPTED') OR business_object_id IS NOT NULL)
    """)
    op.execute("""
ALTER TABLE field_observations ADD CONSTRAINT observations_binding CHECK ((business_object_id IS
NULL AND business_object_field_id IS NULL AND source_object_field_tracking_id IS NULL) OR
(business_object_id IS NOT NULL AND business_object_field_id IS NOT NULL AND
source_object_field_tracking_id IS NOT NULL))
    """)
    op.execute("""
ALTER TABLE field_observations ADD CONSTRAINT observations_no_self_supersession CHECK
(supersedes_observation_id IS NULL OR supersedes_observation_id <> id)
    """)
    op.execute("""
ALTER TABLE field_observations ADD CONSTRAINT observations_confidence CHECK (confidence BETWEEN
0 AND 1)
    """)
    op.execute("""
ALTER TABLE extraction_concrete_values ADD CONSTRAINT values_explicit_null CHECK (NOT
is_semantic_null OR normalized_value IS NULL)
    """)
    op.execute("""
ALTER TABLE extraction_concrete_values ADD CONSTRAINT values_confidence CHECK (confidence
BETWEEN 0 AND 1)
    """)
    op.execute("""
ALTER TABLE extraction_concrete_values ADD CONSTRAINT values_provenance CHECK (element_id IS NOT
NULL OR field_observation_id IS NOT NULL)
    """)
    op.execute("""
ALTER TABLE extraction_concrete_values ADD CONSTRAINT values_complete_range CHECK ((char_start
IS NULL) = (char_end IS NULL))
    """)
    op.execute("""
CREATE INDEX ix_observations_scope_field ON field_observations (scope_instance_id,
source_field_tracking_id)
    """)
    op.execute("""
CREATE UNIQUE INDEX uq_field_observations_run_object_field ON field_observations
(extraction_run_id, business_object_field_id) WHERE scope_instance_id IS NULL
    """)
    op.execute("""
CREATE INDEX ix_extraction_values_hash ON extraction_concrete_values (value_hash)
    """)
    op.execute("""
CREATE INDEX ix_extraction_values_element ON extraction_concrete_values (element_id)
    """)
    op.execute("""
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid =
'source_object_field_trackings'::regclass AND conname =
'fk_source_object_field_trackings_baseline_observation_id') THEN ALTER TABLE
source_object_field_trackings ADD CONSTRAINT
fk_source_object_field_trackings_baseline_observation_id FOREIGN KEY(baseline_observation_id)
REFERENCES field_observations (id) ON DELETE RESTRICT; END IF; END $$;
    """)
    op.execute("""
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid =
'source_object_field_trackings'::regclass AND conname =
'fk_source_object_field_trackings_last_observation_id') THEN ALTER TABLE
source_object_field_trackings ADD CONSTRAINT
fk_source_object_field_trackings_last_observation_id FOREIGN KEY(last_observation_id) REFERENCES
field_observations (id) ON DELETE RESTRICT; END IF; END $$;
    """)

    op.execute("""
INSERT INTO token_classes (id, name) SELECT DISTINCT token_class_id, token_class_id FROM
extraction_concrete_values
    """)
    op.create_foreign_key(
        "fk_value_token_class",
        "extraction_concrete_values",
        "token_classes",
        ["token_class_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    # Capture evidence cannot be represented by the old mandatory object/offset
    # schema. Abort before any DDL rather than silently deleting that evidence.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM extraction_captures)
           OR EXISTS (SELECT 1 FROM extraction_runs WHERE workflow_id IS NULL)
        THEN RAISE EXCEPTION 'Cannot downgrade while snapshot captures or workflow-free runs exist';
        END IF;
    END $$""")
    for name in ("last_observation_id", "baseline_observation_id"):
        op.drop_constraint(
            "fk_source_object_field_trackings_" + name,
            "source_object_field_trackings",
            type_="foreignkey",
        )
    for name in (
        "fk_observation_scope",
        "fk_observation_concrete_value",
        "fk_observation_supersedes",
    ):
        op.drop_constraint(name, "field_observations", type_="foreignkey")
    op.drop_constraint("fk_value_token_class", "extraction_concrete_values", type_="foreignkey")
    op.drop_constraint("fk_value_element", "extraction_concrete_values", type_="foreignkey")

    op.drop_constraint("observations_bound_status", "field_observations", type_="check")
    op.drop_constraint("observations_binding", "field_observations", type_="check")
    op.drop_constraint("observations_no_self_supersession", "field_observations", type_="check")
    op.drop_constraint("observations_confidence", "field_observations", type_="check")
    op.drop_constraint("values_explicit_null", "extraction_concrete_values", type_="check")
    op.drop_constraint("values_confidence", "extraction_concrete_values", type_="check")
    op.drop_constraint("values_provenance", "extraction_concrete_values", type_="check")
    op.drop_constraint("values_complete_range", "extraction_concrete_values", type_="check")
    op.drop_index("uq_field_observations_run_object_field", table_name="field_observations")
    op.drop_index("ix_observations_scope_field", table_name="field_observations")
    op.drop_index("ix_extraction_values_element", table_name="extraction_concrete_values")
    op.drop_index("ix_extraction_values_hash", table_name="extraction_concrete_values")
    for column in (
        "scope_instance_id",
        "concrete_value_id",
        "confidence",
        "status",
        "supersedes_observation_id",
        "validated_at",
        "notes",
    ):
        op.drop_column("field_observations", column)
    for column in (
        "element_id",
        "normalized_value",
        "is_semantic_null",
        "value_hash",
        "confidence",
        "discovered_by",
    ):
        op.drop_column("extraction_concrete_values", column)
    for column in (
        "source_object_field_tracking_id",
        "business_object_id",
        "business_object_field_id",
    ):
        op.alter_column("field_observations", column, existing_type=sa.BigInteger(), nullable=False)
    op.create_unique_constraint(
        "uq_field_observations_run_object_field",
        "field_observations",
        ["extraction_run_id", "business_object_field_id"],
    )
    op.alter_column(
        "extraction_concrete_values",
        "field_observation_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    for column in ("char_start", "char_end"):
        op.alter_column(
            "extraction_concrete_values", column, existing_type=sa.Integer(), nullable=False
        )
    op.drop_column("extraction_runs", "extractor_version")
    op.alter_column("extraction_runs", "workflow_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column(
        "extraction_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    op.drop_table("extraction_issues")
    op.drop_table("field_selectors")
    op.drop_table("scope_instances")
    op.drop_table("anchor_element_references")
    op.drop_table("elements_xlsx")
    op.drop_table("elements_pdf")
    op.drop_table("elements_html")
    op.drop_table("extraction_captures")
    op.drop_table("ground_truth")
    op.drop_table("source_scopes")
    op.drop_table("elements")
    op.drop_table("token_classes")
    op.drop_table("source_snapshots")
    op.execute("""
DROP TYPE extraction_observation_status
    """)
    op.execute("""
DROP TYPE extraction_issue_code
    """)
    op.execute("""
DROP TYPE extraction_discovery_method
    """)
    op.execute("""
DROP TYPE extraction_selector_type
    """)
    op.execute("""
DROP TYPE extraction_anchor_relation
    """)
    op.execute("""
DROP TYPE extraction_element_from
    """)
    # PostgreSQL cannot remove individual run-status labels; old labels remain valid.
