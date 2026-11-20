"""Normalize portable selector definitions, evaluations and legacy links."""

import sqlalchemy as sa
from alembic import op

revision = "e103_selector_tree"
down_revision = "b203_value_field_owner"
branch_labels = None
depends_on = None


def upgrade():
    _restore_tracking_versions()
    op.create_unique_constraint(
        "uq_extraction_runs_snapshot_owner", "extraction_runs", ["id", "source_snapshot_id"]
    )
    op.execute("""
        CREATE TABLE selectors (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            source_id BIGINT,
            business_entity_field_id BIGINT NOT NULL,
            business_object_field_id BIGINT,
            active_version_id BIGINT,
            legacy_scope_name TEXT,
            revision BIGINT DEFAULT '0' NOT NULL,
            metadata_json JSONB NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT fk_selectors_object_field_owner FOREIGN KEY(business_object_field_id,
            business_entity_field_id) REFERENCES business_object_fields (id,
            business_entity_field_id) ON DELETE RESTRICT,
            CONSTRAINT uq_selectors_legacy_identity UNIQUE (source_id, legacy_scope_name,
            business_entity_field_id),
            CONSTRAINT selector_revision_nonnegative CHECK (revision >= 0),
            UNIQUE (uuid),
            FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT,
            FOREIGN KEY(business_entity_field_id) REFERENCES business_entity_fields (id) ON DELETE
            RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE selector_versions (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            selector_id BIGINT NOT NULL,
            version_no BIGINT NOT NULL,
            status TEXT NOT NULL,
            created_from_snapshot_id BIGINT,
            metadata_json JSONB NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_selector_versions_number UNIQUE (selector_id, version_no),
            CONSTRAINT uq_selector_versions_owner UNIQUE (selector_id, id),
            CONSTRAINT selector_versions_safe_number CHECK (version_no BETWEEN 1 AND
            9007199254740991),
            CONSTRAINT selector_versions_status CHECK (status IN
            ('draft','active','superseded','rejected')),
            UNIQUE (uuid),
            FOREIGN KEY(selector_id) REFERENCES selectors (id) ON DELETE RESTRICT,
            FOREIGN KEY(created_from_snapshot_id) REFERENCES source_snapshots (id) ON DELETE
            RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE selector_recipes (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            selector_version_id BIGINT NOT NULL,
            position BIGINT NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_selector_recipes_order UNIQUE (selector_version_id, position),
            CONSTRAINT selector_recipes_safe_order CHECK (position BETWEEN 0 AND 9007199254740991),
            UNIQUE (uuid),
            FOREIGN KEY(selector_version_id) REFERENCES selector_versions (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE selector_parts (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            recipe_id BIGINT NOT NULL,
            position BIGINT NOT NULL,
            extraction_json JSONB NOT NULL,
            join_with TEXT,
            PRIMARY KEY (id),
            CONSTRAINT uq_selector_parts_order UNIQUE (recipe_id, position),
            CONSTRAINT selector_parts_safe_order CHECK (position BETWEEN 0 AND 9007199254740991),
            UNIQUE (uuid),
            FOREIGN KEY(recipe_id) REFERENCES selector_recipes (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE selector_locators (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            part_id BIGINT NOT NULL,
            position BIGINT NOT NULL,
            kind TEXT NOT NULL,
            payload_json JSONB NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_selector_locators_order UNIQUE (part_id, position),
            CONSTRAINT selector_locators_safe_order CHECK (position BETWEEN 0 AND
            9007199254740991),
            CONSTRAINT selector_locators_kind CHECK (kind IN
            ('css_path','xpath','element_id','text_quote','dom_path','dom_range','exact_pos','text_position','text_fragment')),
            UNIQUE (uuid),
            FOREIGN KEY(part_id) REFERENCES selector_parts (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE selector_evaluations (
            id BIGSERIAL NOT NULL,
            uuid UUID NOT NULL,
            selector_version_id BIGINT NOT NULL,
            source_snapshot_id BIGINT,
            extraction_run_id BIGINT,
            execution_key TEXT,
            evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            page_url TEXT NOT NULL,
            provenance TEXT NOT NULL,
            result_json JSONB NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT fk_selector_evaluations_run_snapshot FOREIGN KEY(extraction_run_id,
            source_snapshot_id) REFERENCES extraction_runs (id, source_snapshot_id) ON DELETE
            RESTRICT,
            CONSTRAINT uq_selector_evaluation_evidence UNIQUE (id, selector_version_id,
            extraction_run_id),
            CONSTRAINT uq_selector_evaluation_execution UNIQUE (extraction_run_id, execution_key),
            CONSTRAINT selector_evaluations_provenance CHECK ((provenance = 'backend_verified' AND
            extraction_run_id IS NOT NULL AND source_snapshot_id IS NOT NULL AND execution_key IS
            NOT NULL) OR (provenance = 'client_reported' AND extraction_run_id IS NULL AND
            execution_key IS NULL)),
            UNIQUE (uuid),
            FOREIGN KEY(selector_version_id) REFERENCES selector_versions (id) ON DELETE RESTRICT,
            FOREIGN KEY(source_snapshot_id) REFERENCES source_snapshots (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_selector_versions_active ON selector_versions (selector_id) WHERE
            status = 'active'
    """)
    op.execute("""
        CREATE INDEX ix_selector_evaluations_version ON selector_evaluations (selector_version_id,
            id)
    """)
    op.execute("""
        ALTER TABLE selectors ADD CONSTRAINT fk_selectors_active_version_owner FOREIGN KEY(id,
            active_version_id) REFERENCES selector_versions (selector_id, id) DEFERRABLE INITIALLY
            DEFERRED
    """)
    op.add_column("field_selectors", sa.Column("selector_version_id", sa.BigInteger()))
    op.create_foreign_key(
        "fk_legacy_rule_selector_version",
        "field_selectors",
        "selector_versions",
        ["selector_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("field_observations", sa.Column("selector_version_id", sa.BigInteger()))
    op.add_column("field_observations", sa.Column("selector_evaluation_id", sa.BigInteger()))
    op.create_check_constraint(
        "observations_selector_evidence_pair",
        "field_observations",
        "(selector_evaluation_id IS NULL) = (selector_version_id IS NULL)",
    )
    op.create_foreign_key(
        "fk_observations_selector_evidence",
        "field_observations",
        "selector_evaluations",
        ["selector_evaluation_id", "selector_version_id", "extraction_run_id"],
        ["id", "selector_version_id", "extraction_run_id"],
        ondelete="RESTRICT",
    )
    _protect_definitions()
    _map_legacy_rules()


def _protect_definitions():
    op.execute("""
        CREATE FUNCTION check_selector_active_pointer() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            owner_id bigint;
        BEGIN
            IF TG_TABLE_NAME = 'selectors' THEN owner_id := NEW.id;
            ELSE owner_id := NEW.selector_id;
            END IF;
            IF EXISTS (
                SELECT 1 FROM selectors AS s
                WHERE s.id = owner_id AND s.active_version_id IS DISTINCT FROM
                    (SELECT v.id FROM selector_versions AS v
                     WHERE v.selector_id = s.id AND v.status = 'active')
            ) THEN
                RAISE EXCEPTION 'Selector active pointer does not match its active version'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER selector_active_pointer
        AFTER INSERT OR UPDATE OF active_version_id ON selectors
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_selector_active_pointer()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER selector_version_active_pointer
        AFTER INSERT OR UPDATE OF status ON selector_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_selector_active_pointer()
    """)
    op.execute("""
        CREATE FUNCTION protect_selector_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Selector version history cannot be removed'
                    USING ERRCODE = '23514';
            END IF;
            IF (NEW.id, NEW.uuid, NEW.selector_id, NEW.version_no) IS DISTINCT FROM
               (OLD.id, OLD.uuid, OLD.selector_id, OLD.version_no) THEN
                RAISE EXCEPTION 'Selector version identity is immutable' USING ERRCODE = '23514';
            END IF;
            IF OLD.status <> 'draft' AND NEW IS DISTINCT FROM OLD AND NOT (
                OLD.status = 'active' AND NEW.status = 'superseded' AND
                (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status')
            ) THEN
                RAISE EXCEPTION 'Approved selector version is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER selector_version_immutable BEFORE UPDATE OR DELETE ON selector_versions
        FOR EACH ROW EXECUTE FUNCTION protect_selector_version()
    """)
    op.execute("""
        CREATE FUNCTION protect_selector_children() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            parent_id bigint;
            version_id bigint;
            version_status text;
        BEGIN
            FOREACH parent_id IN ARRAY ARRAY[
                (to_jsonb(OLD)->>TG_ARGV[0])::bigint, (to_jsonb(NEW)->>TG_ARGV[0])::bigint
            ] LOOP
                IF parent_id IS NULL THEN CONTINUE; END IF;
                IF TG_TABLE_NAME = 'selector_recipes' THEN
                    version_id := parent_id;
                ELSIF TG_TABLE_NAME = 'selector_parts' THEN
                    SELECT selector_version_id INTO version_id
                    FROM selector_recipes WHERE id = parent_id;
                ELSE
                    SELECT r.selector_version_id INTO version_id
                    FROM selector_parts AS p JOIN selector_recipes AS r ON r.id = p.recipe_id
                    WHERE p.id = parent_id;
                END IF;
                SELECT status INTO version_status FROM selector_versions
                WHERE id = version_id FOR SHARE;
                IF version_status <> 'draft' THEN
                    RAISE EXCEPTION 'Approved selector content is immutable'
                        USING ERRCODE = '23514';
                END IF;
            END LOOP;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    for table, owner in (
        ("selector_recipes", "selector_version_id"),
        ("selector_parts", "recipe_id"),
        ("selector_locators", "part_id"),
    ):
        op.execute(
            "CREATE TRIGGER selector_children_immutable BEFORE INSERT OR UPDATE OR DELETE "
            f"ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION protect_selector_children('{owner}')"
        )


def _map_legacy_rules():
    op.execute("""
        CREATE FUNCTION legacy_selector_uuid(key text) RETURNS uuid LANGUAGE sql IMMUTABLE AS $$
            SELECT overlay(overlay(digest placing '3' from 13 for 1)
                placing translate(substr(digest,17,1),'0123456789abcdef','89ab89ab89ab89ab')
                from 17 for 1)::uuid
            FROM (SELECT md5('burbot-field-selector/' || key) AS digest) AS hash
        $$
    """)
    # Keep the existing capture's IDs and scope semantics. Conversion is also used
    # for new compatibility requests, so retrying them cannot fork selector history.
    op.execute("""
        CREATE FUNCTION map_legacy_field_selector(rule_id bigint) RETURNS void
        LANGUAGE plpgsql AS $$
        DECLARE
            rule record;
            owner_id bigint;
            version_id bigint;
            recipe_id bigint;
            part_id bigint;
            version_number bigint;
            operation jsonb;
            locator_payload jsonb;
            locator_kind text;
            base_key text;
            created_at_text text;
        BEGIN
            SELECT f.*, s.source_id, s.name AS scope_name, t.business_entity_field_id,
                   b.persistent_key, src.type AS source_type
            INTO rule
            FROM field_selectors AS f
            JOIN source_scopes AS s ON s.id = f.scope_id
            JOIN source_field_trackings AS t ON t.id = f.source_field_tracking_id
            JOIN business_entity_fields AS b ON b.id = t.business_entity_field_id
            JOIN sources AS src ON src.id = s.source_id
            WHERE f.id = rule_id AND t.source_id = s.source_id;
            IF NOT FOUND OR rule.selector_version_id IS NOT NULL
                OR rule.source_type <> 'HTML' OR rule.selector_type IS NULL
                OR rule.selector_type NOT IN ('CSS', 'XPATH')
                OR coalesce(length(trim(rule.selector_string)), 0) = 0 THEN RETURN;
            END IF;

            CASE rule.extraction_json->>'type'
                WHEN 'text' THEN
                    IF rule.extraction_json <> '{"type":"text"}'::jsonb THEN RETURN; END IF;
                    operation := rule.extraction_json;
                WHEN 'attribute' THEN
                    IF coalesce(rule.extraction_json->>'attribute','') NOT IN
                       ('href','src','datetime','title','alt','content')
                       OR rule.extraction_json - 'attribute' <> '{"type":"attribute"}'::jsonb
                    THEN RETURN; END IF;
                    operation := jsonb_build_object(
                        'type','attribute','name',rule.extraction_json->'attribute'
                    );
                WHEN 'selection' THEN
                    IF rule.extraction_json - 'quote' <> '{"type":"selection"}'::jsonb
                       OR jsonb_typeof(rule.extraction_json->'quote') IS DISTINCT FROM 'object'
                       OR jsonb_typeof(rule.extraction_json#>'{quote,exact}')
                          IS DISTINCT FROM 'string'
                       OR coalesce(length(rule.extraction_json#>>'{quote,exact}'),0) = 0
                       OR jsonb_typeof(rule.extraction_json#>'{quote,prefix}')
                          IS DISTINCT FROM 'string'
                       OR jsonb_typeof(rule.extraction_json#>'{quote,suffix}')
                          IS DISTINCT FROM 'string'
                       OR (rule.extraction_json->'quote') - 'exact' - 'prefix' - 'suffix'
                          <> '{}'::jsonb
                    THEN RETURN; END IF;
                    operation := rule.extraction_json;
                ELSE RETURN;
            END CASE;

            base_key := format('owner/%s/%s/%s', rule.source_id, rule.business_entity_field_id,
                               rule.scope_name);
            created_at_text := to_char(rule.valid_from AT TIME ZONE 'UTC',
                                       'YYYY-MM-DD"T"HH24:MI:SS.US"Z"');
            INSERT INTO selectors (uuid, source_id, business_entity_field_id,
                                   legacy_scope_name, metadata_json)
            VALUES (
                legacy_selector_uuid(base_key), rule.source_id, rule.business_entity_field_id,
                rule.scope_name, jsonb_build_object(
                    'target', jsonb_build_object(
                        'objectId', format('legacy-scope/%s/%s', rule.source_id, rule.scope_name),
                        'field', rule.persistent_key
                    ),
                    'activeVersionUuid', NULL, 'createdAt', created_at_text,
                    'migration', jsonb_build_object(
                        'legacyRuleId', rule.id::text, 'provenance', 'unverified'
                    )
                )
            ) ON CONFLICT ON CONSTRAINT uq_selectors_legacy_identity DO NOTHING;
            SELECT id INTO owner_id FROM selectors
            WHERE uuid = legacy_selector_uuid(base_key) FOR UPDATE;

            SELECT coalesce(max(version_no),0) + 1 INTO version_number
            FROM selector_versions WHERE selector_id = owner_id;
            base_key := format('rule/%s/', rule.id);
            INSERT INTO selector_versions (uuid,selector_id,version_no,status,metadata_json)
            VALUES (
                legacy_selector_uuid(base_key || 'version'), owner_id, version_number, 'draft',
                jsonb_build_object(
                    'createdAt',created_at_text,'createdFromSnapshotUuid',NULL,'artifactType',NULL
                )
            ) RETURNING id INTO version_id;
            INSERT INTO selector_recipes (uuid,selector_version_id,position)
            VALUES (legacy_selector_uuid(base_key || 'recipe'), version_id, 0) RETURNING id
            INTO recipe_id;
            INSERT INTO selector_parts (uuid,recipe_id,position,extraction_json)
            VALUES (legacy_selector_uuid(base_key || 'part'), recipe_id, 0, operation) RETURNING id
            INTO part_id;
            IF rule.selector_type = 'CSS' THEN
                locator_kind := 'css_path';
                locator_payload := jsonb_build_object('selector',rule.selector_string);
            ELSE
                locator_kind := 'xpath';
                locator_payload := jsonb_build_object('expression',rule.selector_string);
            END IF;
            INSERT INTO selector_locators (uuid,part_id,position,kind,payload_json)
            VALUES (legacy_selector_uuid(base_key || 'locator'), part_id, 0,
                    locator_kind, locator_payload);
            IF operation->>'type' = 'selection' THEN
                INSERT INTO selector_locators (uuid,part_id,position,kind,payload_json)
                VALUES (legacy_selector_uuid(base_key || 'quote'), part_id, 1, 'text_quote',
                        jsonb_build_object('quote',operation->'quote'));
            END IF;
            IF rule.valid_to IS NOT NULL THEN
                UPDATE selector_versions SET status = 'superseded' WHERE id = version_id;
            END IF;
            UPDATE field_selectors SET selector_version_id = version_id WHERE id = rule.id;
            UPDATE selectors SET revision = revision + 1 WHERE id = owner_id;
        END $$
    """)
    op.execute("""
        DO $$
        DECLARE row_id bigint;
        BEGIN
            FOR row_id IN SELECT id FROM field_selectors ORDER BY valid_from, id LOOP
                PERFORM map_legacy_field_selector(row_id);
            END LOOP;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION attach_legacy_selector_tree() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.selector_version_id IS NULL THEN
                PERFORM map_legacy_field_selector(NEW.id);
            END IF;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER field_selector_tree AFTER INSERT ON field_selectors
        FOR EACH ROW EXECUTE FUNCTION attach_legacy_selector_tree()
    """)


def _restore_tracking_versions():
    # The restored capture pipeline already uses the Sources versioned tracking model.
    # Older databases have one row per binding. Keep its ID and evidence pointers.
    op.execute("""
        ALTER TABLE source_object_field_trackings
            ADD COLUMN IF NOT EXISTS tracking_id UUID,
            ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS change_reason TEXT,
            ADD COLUMN IF NOT EXISTS desired_refresh_seconds INTEGER
    """)
    op.execute("""
        UPDATE source_object_field_trackings SET
            tracking_id = coalesce(tracking_id, md5('legacy-tracking/' || id::text)::uuid),
            valid_from = coalesce(valid_from, created_at)
        WHERE tracking_id IS NULL OR valid_from IS NULL
    """)
    op.execute("""
        ALTER TABLE source_object_field_trackings
            ALTER COLUMN tracking_id SET NOT NULL,
            ALTER COLUMN tracking_id SET DEFAULT gen_random_uuid(),
            ALTER COLUMN valid_from SET NOT NULL,
            ALTER COLUMN valid_from SET DEFAULT now(),
            DROP CONSTRAINT IF EXISTS uq_source_object_field_trackings_field
    """)
    for name, clause in (
        ("uq_source_object_field_trackings_version", "UNIQUE (tracking_id, version)"),
        ("source_object_field_trackings_version_positive", "CHECK (version > 0)"),
        (
            "source_object_field_trackings_valid_period",
            "CHECK (valid_to IS NULL OR valid_to > valid_from)",
        ),
        (
            "source_object_field_trackings_refresh_positive",
            "CHECK (desired_refresh_seconds IS NULL OR desired_refresh_seconds > 0)",
        ),
    ):
        op.execute(f"""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{name}' AND conrelid =
                        'source_object_field_trackings'::regclass
                ) THEN
                    ALTER TABLE source_object_field_trackings ADD CONSTRAINT {name} {clause};
                END IF;
            END $$
        """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_source_object_field_trackings_current_field
        ON source_object_field_trackings(source_field_tracking_id, business_object_field_id)
        WHERE valid_to IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_source_object_field_trackings_current
        ON source_object_field_trackings(tracking_id) WHERE valid_to IS NULL
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM selectors) THEN
                RAISE EXCEPTION 'Cannot downgrade SelectorTree with stored definition history';
            END IF;
            IF EXISTS (
                SELECT 1 FROM source_object_field_trackings
                WHERE version <> 1 OR valid_to IS NOT NULL OR change_reason IS NOT NULL
                   OR desired_refresh_seconds IS NOT NULL OR valid_from <> created_at
                   OR tracking_id <> md5('legacy-tracking/' || id::text)::uuid
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade with native source tracking versions';
            END IF;
        END $$
    """)
    op.execute("DROP TRIGGER field_selector_tree ON field_selectors")
    op.execute("DROP FUNCTION attach_legacy_selector_tree()")
    op.execute("DROP FUNCTION map_legacy_field_selector(bigint)")
    op.execute("DROP FUNCTION legacy_selector_uuid(text)")
    op.drop_constraint("fk_legacy_rule_selector_version", "field_selectors", type_="foreignkey")
    op.drop_column("field_selectors", "selector_version_id")
    op.drop_constraint(
        "fk_observations_selector_evidence", "field_observations", type_="foreignkey"
    )
    op.drop_constraint("observations_selector_evidence_pair", "field_observations", type_="check")
    op.drop_column("field_observations", "selector_evaluation_id")
    op.drop_column("field_observations", "selector_version_id")
    op.drop_constraint("fk_selectors_active_version_owner", "selectors", type_="foreignkey")
    for table in (
        "selector_evaluations",
        "selector_locators",
        "selector_parts",
        "selector_recipes",
        "selector_versions",
        "selectors",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION protect_selector_children()")
    op.execute("DROP FUNCTION protect_selector_version()")
    op.execute("DROP FUNCTION check_selector_active_pointer()")
    op.drop_constraint("uq_extraction_runs_snapshot_owner", "extraction_runs", type_="unique")
    op.execute("""
        ALTER TABLE source_object_field_trackings
            ADD CONSTRAINT uq_source_object_field_trackings_field
                UNIQUE (source_field_tracking_id, business_object_field_id),
            DROP COLUMN tracking_id, DROP COLUMN version, DROP COLUMN valid_from,
            DROP COLUMN valid_to, DROP COLUMN change_reason, DROP COLUMN desired_refresh_seconds
    """)
