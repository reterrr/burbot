"""Add authenticated workspace namespaces and external business identities."""

from alembic import op

revision = "x100_extension_identity"
down_revision = "m100_source_monitoring"
branch_labels = None
depends_on = None

OWNERSHIP = (
    ("business_entities", "uq_business_entity_model_owner", ["id", "business_model_id"]),
    ("business_objects", "uq_business_object_entity_owner", ["id", "business_entity_id"]),
)


def upgrade():
    for table, name, columns in OWNERSHIP:
        op.create_unique_constraint(name, table, columns)
    op.execute("""
CREATE TABLE extension_sync_workspaces (
    id UUID NOT NULL,
    business_model_id BIGINT NOT NULL,
    token_digest VARCHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL,
    can_create BOOLEAN NOT NULL,
    can_bind_existing BOOLEAN NOT NULL,
    can_commit BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_sync_workspace_model UNIQUE (id, business_model_id),
    FOREIGN KEY(business_model_id) REFERENCES business_models (id),
    UNIQUE (token_digest)
)
    """)
    op.execute("""
CREATE TABLE extension_sync_source_grants (
    workspace_id UUID NOT NULL,
    source_id BIGINT NOT NULL,
    PRIMARY KEY (workspace_id, source_id),
    FOREIGN KEY(workspace_id) REFERENCES extension_sync_workspaces (id),
    FOREIGN KEY(source_id) REFERENCES sources (id)
)
    """)
    op.execute("""
CREATE TABLE extension_sync_object_bindings (
    workspace_id UUID NOT NULL,
    external_object_id TEXT NOT NULL,
    business_model_id BIGINT NOT NULL,
    business_entity_id BIGINT NOT NULL,
    business_object_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (workspace_id, external_object_id),
    CONSTRAINT fk_sync_object_workspace_model FOREIGN KEY(workspace_id, business_model_id)
        REFERENCES extension_sync_workspaces (id, business_model_id),
    CONSTRAINT fk_sync_object_entity_model FOREIGN KEY(business_entity_id, business_model_id)
        REFERENCES business_entities (id, business_model_id),
    CONSTRAINT fk_sync_object_object_entity FOREIGN KEY(business_object_id, business_entity_id)
        REFERENCES business_objects (id, business_entity_id),
    CONSTRAINT uq_sync_workspace_object UNIQUE (workspace_id, business_object_id)
)
    """)
    op.execute("""
CREATE TABLE extension_sync_receipts (
    workspace_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    digest VARCHAR(64) NOT NULL,
    result JSONB NOT NULL,
    PRIMARY KEY (workspace_id, operation_id),
    FOREIGN KEY(workspace_id) REFERENCES extension_sync_workspaces (id)
)
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM extension_sync_workspaces) THEN
                RAISE EXCEPTION 'Cannot downgrade while extension workspace identities exist';
            END IF;
        END $$;
    """)
    op.drop_table("extension_sync_receipts")
    op.drop_table("extension_sync_object_bindings")
    op.drop_table("extension_sync_source_grants")
    op.drop_table("extension_sync_workspaces")
    for table, name, _ in reversed(OWNERSHIP):
        op.drop_constraint(name, table, type_="unique")
