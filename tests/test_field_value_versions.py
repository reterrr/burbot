"""Validation-version provenance through the real business services and migrations."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_collections_postgres import (
    BASE,
    assert_http,
    migrate,
)
from test_collections_postgres import (
    database as database,
)
from test_collections_postgres import (
    domain as domain,
)

from business_layer.schemas.models import BusinessObjectField, BusinessObjectFieldValue

pytestmark = pytest.mark.asyncio


async def field_version(domain, key):
    definition = await domain.call(lambda service: service.entities.get_entity(domain.entity_id))
    return next(field.version_id for field in definition.fields if field.key == key)


async def history(domain, slot):
    return await domain.call(
        lambda service: service.data.get_object_field_value_history(slot.object_field_id)
    )


async def test_initial_values_defaults_nulls_and_seeds_use_active_definitions(domain):
    result = await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE.replace(
                "    tags: List(String())",
                "    tags: List(String())\n    enabled: Boolean(default=False)"
                "\n    note: String(default=None)",
            )
            + '\nproject = Project(name="Seeded", tags=[])\n',
        )
    )
    definition = await domain.call(lambda service: service.entities.get_entity(domain.entity_id))
    definitions = {field.field_id: field.version_id for field in definition.fields}
    for obj in [
        await domain.call(lambda service: service.data.get_object(result.objects["project"])),
        await domain.make(tags=None),
    ]:
        for field in obj.fields:
            if field.value_id is None:
                assert field.validated_against_field_version_id is None
            else:
                assert (
                    field.validated_against_field_version_id
                    == definitions[field.business_entity_field_id]
                )
                rows = await history(domain, field)
                assert (
                    rows[0].validated_against_field_version_id
                    == definitions[field.business_entity_field_id]
                )
        values = {field.business_entity_field_id: field.value for field in obj.fields}
        assert values[next(f.field_id for f in definition.fields if f.key == "enabled")] is False
        assert values[next(f.field_id for f in definition.fields if f.key == "note")] is None


async def test_same_value_after_schema_change_is_a_new_validation_decision(domain):
    obj = await domain.make(name="same")
    original = domain.slot(obj, "name")
    old_version = original.validated_against_field_version_id
    before = datetime.now(UTC)
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE.replace(
                "name: String(nullable=False)", 'name: String(nullable=False, label="Name")'
            ),
        )
    )
    current_version = await field_version(domain, "name")
    assert current_version != old_version
    # Publishing a definition does not rewrite accepted value provenance.
    unchanged = await domain.call(lambda service: service.data.get_object(obj.id))
    assert domain.slot(unchanged, "name").validated_against_field_version_id == old_version

    async def assign():
        return await domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id, {original.object_field_id: "same"}
            )
        )

    accepted = domain.slot(await assign(), "name")
    assert accepted.value_id != original.value_id
    assert accepted.validated_against_field_version_id == current_version
    assert domain.slot(await assign(), "name").value_id == accepted.value_id
    old = await domain.call(
        lambda service: service.data.get_object(obj.id, at=before, known_at=before)
    )
    assert domain.slot(old, "name").validated_against_field_version_id == old_version
    rows = await history(domain, original)
    assert {row.validated_against_field_version_id for row in rows} == {
        old_version,
        current_version,
    }
    assert all(
        row.validated_against_field_version_id == old_version
        for row in rows
        if row.valid_from == original.valid_from
    )


async def test_backdated_scalar_uses_current_definition_and_preserves_prefix(domain):
    bounded = BASE.replace(
        "name: String(nullable=False)", "name: String(nullable=False, max_length=5)"
    )
    await domain.call(lambda service: service.execute(domain.model_id, code=bounded))
    obj = await domain.make(name="old")
    original = domain.slot(obj, "name")
    effective = original.valid_from + timedelta(microseconds=1)
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=bounded.replace(
                "name: String(nullable=False, max_length=5)",
                'name: String(nullable=False, max_length=5, label="Name")',
            ),
        )
    )
    current_version = await field_version(domain, "name")
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id, {original.object_field_id: "too long"}, effective_at=effective
            )
        ),
    )
    changed = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id, {original.object_field_id: "new"}, effective_at=effective
        )
    )
    assert domain.slot(changed, "name").validated_against_field_version_id == current_version
    earlier = await domain.call(
        lambda service: service.data.get_object(obj.id, at=original.valid_from)
    )
    assert domain.slot(earlier, "name").value == "old"
    assert domain.slot(earlier, "name").validated_against_field_version_id == (
        original.validated_against_field_version_id
    )


@pytest.mark.parametrize("initial", [None, [], ["a"]])
async def test_whole_list_and_null_revalidation_use_current_field_version(domain, initial):
    obj = await domain.make(tags=initial)
    original = domain.slot(obj, "tags")
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE.replace(
                "tags: List(String())", 'labels: List(String(), persistent_key="tags")'
            ),
        )
    )
    current_version = await field_version(domain, "labels")
    result = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {original.object_field_id: initial},
            expected_value_ids={original.object_field_id: original.value_id},
            expected_collection_revisions=(
                {original.object_field_id: original.collection_revision}
                if original.collection_id is not None
                else None
            ),
        )
    )
    accepted = domain.slot(result, "tags")
    assert accepted.value_id != original.value_id
    assert accepted.validated_against_field_version_id == current_version
    assert accepted.collection_id == original.collection_id
    assert accepted.value == initial


async def test_addressed_item_edit_revalidates_pointer_only_for_new_schema(domain):
    bounded = BASE.replace("tags: List(String())", "tags: List(String(max_length=3))")
    await domain.call(lambda service: service.execute(domain.model_id, code=bounded))
    obj = await domain.make(tags=["a"])
    original = domain.slot(obj, "tags")
    before = datetime.now(UTC)
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=bounded.replace(
                "tags: List(String(max_length=3))", 'tags: List(String(max_length=3), label="Tags")'
            ),
        )
    )
    current_version = await field_version(domain, "tags")
    await assert_http(
        422,
        domain.edit(
            "append_item",
            original.collection_id,
            "too long",
            effective_at=original.valid_from + timedelta(microseconds=1),
        ),
    )
    assert (
        await domain.count(
            BusinessObjectFieldValue, business_object_field_id=original.object_field_id
        )
        == 1
    )
    await domain.edit("append_item", original.collection_id, "b")
    updated = domain.slot(
        await domain.call(lambda service: service.data.get_object(obj.id)), "tags"
    )
    assert updated.value == ["a", "b"]
    assert updated.value_id != original.value_id
    assert updated.validated_against_field_version_id == current_version
    async with domain.factory() as session:
        slot = await session.get(BusinessObjectField, original.object_field_id)
        assert slot.effective_value_id == updated.value_id
    await domain.edit("append_item", original.collection_id, "c")
    after = domain.slot(await domain.call(lambda service: service.data.get_object(obj.id)), "tags")
    assert after.value_id == updated.value_id
    old = await domain.call(
        lambda service: service.data.get_object(obj.id, at=before, known_at=before)
    )
    assert domain.slot(old, "tags").validated_against_field_version_id == (
        original.validated_against_field_version_id
    )


async def test_historical_collection_revalidation_preserves_later_pointer_segments(domain):
    obj = await domain.make(tags=["old"])
    original = domain.slot(obj, "tags")
    effective = original.valid_from + timedelta(microseconds=1)
    nulled = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {original.object_field_id: None},
            expected_value_ids={original.object_field_id: original.value_id},
            expected_collection_revisions={original.object_field_id: original.collection_revision},
        )
    )
    null_slot = domain.slot(nulled, "tags")
    later = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id, {original.object_field_id: ["later"]}
        )
    )
    later_slot = domain.slot(later, "tags")
    known_before = datetime.now(UTC)
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE.replace("tags: List(String())", 'tags: List(String(), label="Tags")'),
        )
    )
    await domain.edit("append_item", original.collection_id, "extra", effective_at=effective)

    async def read(**times):
        return domain.slot(
            await domain.call(lambda service: service.data.get_object(obj.id, **times)), "tags"
        )

    corrected = await read(at=effective)
    assert corrected.value == ["old", "extra"]
    assert corrected.validated_against_field_version_id == await field_version(domain, "tags")
    null_read = await read(at=null_slot.valid_from)
    assert null_read.value is None and null_read.collection_id is None
    assert (
        null_read.validated_against_field_version_id == null_slot.validated_against_field_version_id
    )
    current = await read()
    assert current.collection_id == later_slot.collection_id and current.value == ["later"]
    assert (
        current.validated_against_field_version_id == later_slot.validated_against_field_version_id
    )
    old_belief = await read(at=effective, known_at=known_before)
    assert old_belief.value == ["old"]
    assert (
        old_belief.validated_against_field_version_id == original.validated_against_field_version_id
    )


@pytest.mark.parametrize("explicit_null", [False, True])
async def test_create_collection_endpoint_service_uses_current_definition(domain, explicit_null):
    obj = await domain.make(**({"tags": None} if explicit_null else {}))
    original = domain.slot(obj, "tags")
    await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE.replace("tags: List(String())", 'tags: List(String(), label="Tags")'),
        )
    )
    await domain.call(
        lambda service: service.data.collections.create_collection(
            original.object_field_id, ["a"], expected_value_id=original.value_id
        )
    )
    read = domain.slot(await domain.call(lambda service: service.data.get_object(obj.id)), "tags")
    assert read.validated_against_field_version_id == await field_version(domain, "tags")


async def legacy_value(connection):
    for statement in [
        "INSERT INTO business_models(id,key,name) VALUES(10,'legacy','Legacy')",
        "INSERT INTO business_model_revisions(id,business_model_id) VALUES(11,10),(12,10)",
        "INSERT INTO business_entities(id,business_model_id,table_name) VALUES(20,10,'legacy')",
        "INSERT INTO business_entity_fields(id,business_entity_id,persistent_key) "
        "VALUES(30,20,'name')",
        "INSERT INTO business_objects(id,business_entity_id) VALUES(40,20)",
        "INSERT INTO business_object_fields(id,business_object_id,business_entity_field_id) "
        "VALUES(50,40,30)",
        """INSERT INTO business_object_field_values(
            id,business_object_field_id,value_json,valid_from,transaction_from,transaction_to)
            VALUES(60,50,'"old"','2026-01-02Z','2026-01-02Z','2026-01-04Z')""",
    ]:
        await connection.execute(text(statement))


@pytest.mark.parametrize("database", ["b201_collections"], indirect=True)
async def test_migration_backfills_original_decisions_and_copied_prefixes(database):
    engine, _, schema = database
    async with engine.begin() as connection:
        await legacy_value(connection)
        await connection.execute(
            text("""
            INSERT INTO business_entity_field_versions(id,business_entity_field_id,
                business_model_revision_id,key,label,definition_json,valid_from,valid_to,
                transaction_from,transaction_to)
            VALUES
                (101,30,11,'name','Name','{"type":"string"}',
                    '2026-01-01Z',NULL,'2026-01-01Z','2026-01-03Z'),
                (102,30,11,'name','Name','{"type":"string"}',
                    '2026-01-01Z','2026-01-03Z','2026-01-03Z',NULL),
                (103,30,12,'name','Name','{"type": "string", "max_length": 5}',
                    '2026-01-03Z',NULL,'2026-01-03Z',NULL)
        """)
        )
        await connection.execute(
            text("INSERT INTO business_objects(id,business_entity_id) VALUES(41,20)")
        )
        await connection.execute(
            text(
                "INSERT INTO business_object_fields("
                "id,business_object_id,business_entity_field_id) "
                "VALUES(51,41,30)"
            )
        )
        # A backdated decision was validated against the definition current
        # when recorded, rather than the one current at its valid-time start.
        await connection.execute(
            text("""
            INSERT INTO business_object_field_values(id,business_object_field_id,
                value_json,valid_from,transaction_from)
            VALUES(63,51,'"late"','2026-01-02Z','2026-01-04Z')
        """)
        )
        await connection.execute(
            text("""
            INSERT INTO business_object_field_values(id,business_object_field_id,
                value_json,valid_from,valid_to,transaction_from)
            VALUES(61,50,'"old"','2026-01-02Z','2026-01-04Z','2026-01-04Z'),
                  (62,50,'"new"','2026-01-04Z',NULL,'2026-01-04Z')
        """)
        )
        await connection.run_sync(lambda conn: migrate(conn, schema, "head"))
        rows = (
            await connection.execute(
                text(
                    "SELECT id,validated_against_field_version_id,business_entity_field_id "
                    "FROM business_object_field_values ORDER BY id"
                )
            )
        ).all()
        assert rows == [(60, 101, 30), (61, 101, 30), (62, 103, 30), (63, 103, 30)]
        await connection.run_sync(lambda conn: migrate(conn, schema, "b201_collections", True))
        await connection.run_sync(lambda conn: migrate(conn, schema, "head"))
        assert (
            await connection.scalar(
                text(
                    "SELECT validated_against_field_version_id "
                    "FROM business_object_field_values WHERE id=61"
                )
            )
            == 101
        )


@pytest.mark.parametrize("database", ["b201_collections"], indirect=True)
async def test_migration_refuses_to_invent_missing_definition_history(database):
    engine, _, schema = database
    async with engine.begin() as connection:
        await legacy_value(connection)
    with pytest.raises(
        DBAPIError, match="no active field definition at the original decision time"
    ):
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: migrate(conn, schema, "head"))
    async with engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "b201_collections"
        )
        assert (
            await connection.scalar(text("SELECT count(*) FROM business_object_field_values")) == 1
        )


async def test_value_validation_version_is_required_and_references_a_real_definition(domain):
    obj = await domain.make(name="checked")
    slot = domain.slot(obj, "name")
    for invalid in [None, 10**12]:
        async with domain.factory() as session:
            row = await session.get(BusinessObjectFieldValue, slot.value_id)
            row.validated_against_field_version_id = invalid
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
    async with domain.factory() as session:
        assert (
            await session.scalar(
                select(BusinessObjectFieldValue.validated_against_field_version_id).where(
                    BusinessObjectFieldValue.id == slot.value_id
                )
            )
            == slot.validated_against_field_version_id
        )
