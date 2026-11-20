"""Collection lifecycle and DB invariants against real PostgreSQL migrations.

COLLECTIONS_TEST_DATABASE_URL must name a disposable PostgreSQL database. Each
case creates and drops its own schema and never uses an application's database.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import func, null, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from business_layer.schemas.models import (
    BusinessCollection,
    BusinessCollectionItem,
    BusinessCollectionItemVersion,
    BusinessObjectFieldValue,
)
from business_layer.services.business import BusinessService

pytestmark = pytest.mark.asyncio
BASE = """class Operator(Entity):
    name: String(nullable=False)
class Project(Entity):
    name: String(nullable=False)
    operators: List(Reference("Operator"), persistent_key="operators", unique_items=True)
    tags: List(String())
    scores: List(Integer(ge=0, le=100), min_items=1, max_items=3, unique_items=True)
    sources: List(Source())
    payloads: List(JSON())
"""
ROOT = Path(__file__).resolve().parents[1]


def migrate(connection, schema, target, downgrade=False):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes.update(connection=connection, version_table_schema=schema)
    (command.downgrade if downgrade else command.upgrade)(config, target)


@pytest_asyncio.fixture
async def database(request, monkeypatch):
    url = os.environ.get("COLLECTIONS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set COLLECTIONS_TEST_DATABASE_URL to run real PostgreSQL integration tests")
    monkeypatch.setenv("HOST_DATABASE_URL", url)
    schema = f"collections_test_{uuid4().hex}"
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(
            text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")
        )
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: migrate(conn, schema, getattr(request, "param", "head"))
            )
        yield engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False), schema
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


class Domain:
    def __init__(self, factory):
        self.factory = factory

    async def call(self, action):
        async with self.factory() as session:
            result = await action(BusinessService(session))
            await session.commit()
            return result

    async def make(self, **values):
        supplied = {
            self.fields[key]: value for key, value in {"name": uuid4().hex, **values}.items()
        }
        created = await self.call(
            lambda service: service.data.create_object(self.entity_id, supplied)
        )
        return await self.call(lambda service: service.data.get_object(created.object_id))

    def slot(self, obj, key):
        return next(
            field for field in obj.fields if field.business_entity_field_id == self.fields[key]
        )

    async def read(self, identity, **options):
        return await self.call(
            lambda service: service.data.collections.get_collection(identity, **options)
        )

    async def edit(self, operation, identity, *args, **options):
        if "expected_revision" not in options:
            options["expected_revision"] = (await self.read(identity))["revision"]
        return await self.call(
            lambda service: getattr(service.data.collections, operation)(identity, *args, **options)
        )

    async def count(self, model, **filters):
        async with self.factory() as session:
            return await session.scalar(
                select(func.count()).select_from(model).filter_by(**filters)
            )


@pytest_asyncio.fixture
async def domain(database):
    _, factory, _ = database
    domain = Domain(factory)
    model = await domain.call(
        lambda service: service.entities.create_model(key=uuid4().hex, name="Collections")
    )
    domain.model_id = model.id
    await domain.call(lambda service: service.execute(model.id, code=BASE))
    definition = await domain.call(
        lambda service: service.entities.resolve_entity(model.id, "Project")
    )
    domain.entity_id = definition.entity_id
    domain.fields = {field.key: field.field_id for field in definition.fields}
    domain.definition = definition
    yield domain


async def assert_http(status, action):
    with pytest.raises(HTTPException) as raised:
        await action
    assert raised.value.status_code == status, raised.value.detail
    return raised.value


def values(collection):
    return [item["value"] for item in collection["items"]]


def identities(collection):
    return [item["id"] for item in collection["items"]]


async def test_null_empty_unset_and_independent_owners(domain):
    absent, explicit, empty = (
        await domain.make(),
        await domain.make(tags=None),
        await domain.make(tags=[]),
    )
    assert domain.slot(absent, "tags").value_id is None
    assert domain.slot(explicit, "tags").value_id is not None
    assert domain.slot(explicit, "tags").collection_id is None
    slot = domain.slot(empty, "tags")
    assert slot.collection_id is not None and slot.value == []
    another = domain.slot(await domain.make(tags=[]), "tags")
    assert slot.collection_id != another.collection_id
    await domain.edit("append_item", slot.collection_id, "a")
    assert values(await domain.read(another.collection_id)) == []
    async with domain.factory() as session:
        assert await session.scalar(
            text(
                "SELECT value_json IS NOT NULL AND value_json='null'::jsonb FROM "
                "business_object_field_values WHERE id=:id"
            ),
            {"id": domain.slot(explicit, "tags").value_id},
        )
        assert await session.scalar(
            text("SELECT value_json IS NULL FROM business_object_field_values WHERE id=:id"),
            {"id": slot.value_id},
        )


async def test_addressed_edits_preserve_ids_and_field_version(domain):
    obj = await domain.make(tags=["a", "b", "c"])
    slot = domain.slot(obj, "tags")
    original = await domain.read(slot.collection_id)
    ids = identities(original)
    untouched_version = original["items"][2]["version_id"]
    updated = await domain.edit("set_item_value", slot.collection_id, ids[1], "B")
    assert identities(updated) == ids
    assert updated["items"][2]["version_id"] == untouched_version
    moved = await domain.edit("move_item", slot.collection_id, ids[1], 0)
    assert identities(moved) == [ids[1], ids[0], ids[2]]
    reordered = await domain.edit("reorder_items", slot.collection_id, list(reversed(ids)))
    assert identities(reordered) == list(reversed(ids))
    assert (
        await domain.count(BusinessObjectFieldValue, business_object_field_id=slot.object_field_id)
        == 1
    )
    before_count = await domain.count(
        BusinessCollectionItemVersion, collection_id=slot.collection_id
    )
    same = await domain.edit("reorder_items", slot.collection_id, list(reversed(ids)))
    assert same["revision"] == reordered["revision"]
    assert (
        await domain.count(BusinessCollectionItemVersion, collection_id=slot.collection_id)
        == before_count
    )
    inserted = await domain.edit("insert_item", slot.collection_id, 1, "inserted")
    assert values(inserted) == ["c", "inserted", "B", "a"]
    await assert_http(422, domain.edit("reorder_items", slot.collection_id, ids))


async def test_remove_restore_and_audit_history(domain):
    slot = domain.slot(await domain.make(tags=["a", "b"]), "tags")
    before = await domain.read(slot.collection_id)
    known = datetime.now(UTC)
    first, second = identities(before)
    removed = await domain.edit("remove_item", slot.collection_id, first)
    assert identities(removed) == [second]
    assert values(await domain.read(slot.collection_id, at=known, known_at=known)) == ["a", "b"]
    history = await domain.call(
        lambda service: service.data.collections.item_history(slot.collection_id, first)
    )
    assert any(not row["present"] for row in history)
    assert any(row["transaction_to"] is not None for row in history)
    again = await domain.edit("remove_item", slot.collection_id, first)
    assert again["revision"] == removed["revision"]
    restored = await domain.edit("restore_item", slot.collection_id, first, "a", position=0)
    assert identities(restored) == [first, second]


async def test_backdated_correction_preserves_later_unrelated_items(domain):
    slot = domain.slot(await domain.make(tags=[]), "tags")
    first = await domain.edit("append_item", slot.collection_id, "old")
    effective = first["items"][0]["valid_from"] + timedelta(microseconds=1)
    second = await domain.edit("append_item", slot.collection_id, "later")
    known_before = datetime.now(UTC)
    corrected = await domain.edit(
        "set_item_value",
        slot.collection_id,
        identities(first)[0],
        "corrected",
        effective_at=effective,
    )
    assert values(corrected) == ["corrected"]
    assert values(await domain.read(slot.collection_id)) == ["corrected", "later"]
    assert values(
        await domain.read(slot.collection_id, at=known_before, known_at=known_before)
    ) == ["old", "later"]
    assert values(await domain.read(slot.collection_id, at=first["items"][0]["valid_from"])) == [
        "old"
    ]
    await domain.edit(
        "remove_item", slot.collection_id, identities(first)[0], effective_at=effective
    )
    assert values(await domain.read(slot.collection_id)) == ["later"]
    assert identities(await domain.read(slot.collection_id)) == [identities(second)[1]]


async def test_bounds_and_duplicates_roll_back_atomically(domain):
    slot = domain.slot(await domain.make(scores=[50]), "scores")
    state = await domain.read(slot.collection_id)
    first_id = identities(state)[0]
    for value in [50, -1, 101, None]:
        await assert_http(422, domain.edit("append_item", slot.collection_id, value))
    await assert_http(422, domain.edit("clear_collection", slot.collection_id))
    await assert_http(422, domain.edit("remove_item", slot.collection_id, first_id))
    assert values(await domain.read(slot.collection_id)) == [50]
    await domain.edit("append_item", slot.collection_id, 60)
    await domain.edit("append_item", slot.collection_id, 70)
    await assert_http(422, domain.edit("append_item", slot.collection_id, 80))
    # Valid now would leave two items, but the earlier slice would become empty.
    await assert_http(
        422,
        domain.edit(
            "remove_item",
            slot.collection_id,
            first_id,
            effective_at=state["items"][0]["valid_from"] + timedelta(microseconds=1),
        ),
    )
    assert values(await domain.read(slot.collection_id)) == [50, 60, 70]


async def test_replace_clear_null_transition_and_field_preconditions(domain):
    obj = await domain.make(tags=["a", "b"])
    slot = domain.slot(obj, "tags")
    original = await domain.read(slot.collection_id)
    replaced = await domain.edit("replace_collection", slot.collection_id, ["A", "B", "C"])
    assert identities(replaced)[:2] == identities(original)
    await domain.edit("clear_collection", slot.collection_id)
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id, {slot.object_field_id: None}
            )
        ),
    )
    token = (await domain.read(slot.collection_id))["revision"]
    null_obj = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {slot.object_field_id: None},
            expected_value_ids={slot.object_field_id: slot.value_id},
            expected_collection_revisions={slot.object_field_id: token},
        )
    )
    assert domain.slot(null_obj, "tags").value is None
    new_obj = await domain.call(
        lambda service: service.data.assign_object_fields_values(obj.id, {slot.object_field_id: []})
    )
    new_slot = domain.slot(new_obj, "tags")
    assert new_slot.collection_id != slot.collection_id
    assert not (await domain.read(slot.collection_id))["active"]
    await assert_http(409, domain.edit("append_item", slot.collection_id, "detached"))
    assert domain.slot(new_obj, "tags").value == []
    history = await domain.call(
        lambda service: service.data.get_object_field_value_history(slot.object_field_id)
    )
    assert len(history) >= 3
    assert any(row.collection_id == slot.collection_id for row in history)


async def test_reference_integrity_source_channel_and_foreign_items(domain):
    operator = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Operator")
    )
    name = next(field.field_id for field in operator.fields if field.key == "name")
    target = await domain.call(
        lambda service: service.data.create_object(operator.entity_id, {name: "Operator"})
    )
    obj = await domain.make(operators=[], sources=[])
    slot = domain.slot(obj, "operators")
    for invalid in [obj.id, 10**10]:
        await assert_http(422, domain.edit("append_item", slot.collection_id, invalid))
    accepted = await domain.edit("append_item", slot.collection_id, target.object_id)
    await assert_http(422, domain.edit("append_item", slot.collection_id, target.object_id))
    async with domain.factory() as session:
        row = await session.get(BusinessCollectionItemVersion, accepted["items"][0]["version_id"])
        assert row.reference_object_id == target.object_id and row.value_json is None
    await domain.call(lambda service: service.data.archive_object(target.object_id))
    await assert_http(422, domain.edit("append_item", slot.collection_id, target.object_id))
    other = domain.slot(await domain.make(tags=["other"]), "tags")
    foreign = identities(await domain.read(other.collection_id))[0]
    await assert_http(
        404, domain.edit("set_item_value", slot.collection_id, foreign, target.object_id)
    )
    from sources.schemas.enums import SourceType
    from sources.schemas.models import Source

    async with domain.factory() as session:
        source = Source(type=SourceType.HTML, url=f"https://example.com/{uuid4().hex}")
        session.add(source)
        await session.commit()
        source_id = source.id
    source_slot = domain.slot(obj, "sources")
    source_result = await domain.edit("append_item", source_slot.collection_id, source_id)
    async with domain.factory() as session:
        row = await session.get(
            BusinessCollectionItemVersion, source_result["items"][0]["version_id"]
        )
        assert row.source_id == source_id and row.reference_object_id is None
    await assert_http(422, domain.edit("append_item", source_slot.collection_id, 10**10))


async def test_concurrent_writers_and_stale_whole_field_update(domain):
    obj = await domain.make(tags=[])
    slot = domain.slot(obj, "tags")
    results = await asyncio.gather(
        *[
            domain.edit("append_item", slot.collection_id, value, expected_revision=0)
            for value in ["first", "second"]
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert (
        sum(isinstance(result, HTTPException) and result.status_code == 409 for result in results)
        == 1
    )
    state = await domain.read(slot.collection_id)
    assert len(state["items"]) == 1 and state["revision"] == 1
    await assert_http(
        409,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id,
                {slot.object_field_id: ["stale"]},
                expected_value_ids={slot.object_field_id: slot.value_id},
                expected_collection_revisions={slot.object_field_id: 0},
            )
        ),
    )
    assert (await domain.read(slot.collection_id))["revision"] == 1


async def test_field_rename_evolution_and_definition_history(domain):
    obj = await domain.make(tags=["keep"])
    slot = domain.slot(obj, "tags")
    before = datetime.now(UTC)
    renamed = BASE.replace("tags: List(String())", 'labels: List(String(), persistent_key="tags")')
    result = await domain.call(lambda service: service.execute(domain.model_id, code=renamed))
    assert result.schema_changed
    definition = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Project")
    )
    field = next(field for field in definition.fields if field.key == "labels")
    assert field.field_id == slot.business_entity_field_id and field.persistent_key == "tags"
    read = await domain.call(lambda service: service.data.get_object(obj.id))
    assert domain.slot(read, "tags").collection_id == slot.collection_id
    old = await domain.call(
        lambda service: service.entities.get_entity(domain.entity_id, at=before, known_at=before)
    )
    assert any(field.key == "tags" for field in old.fields)
    history = await domain.call(lambda service: service.entities.get_field_history(field.field_id))
    assert {row.key for row in history} == {"tags", "labels"}
    await assert_http(
        409,
        domain.call(
            lambda service: service.execute(
                domain.model_id,
                code=renamed.replace(
                    'List(String(), persistent_key="tags")',
                    'List(Integer(), persistent_key="tags")',
                ),
            )
        ),
    )
    await assert_http(
        409,
        domain.call(
            lambda service: service.execute(
                domain.model_id,
                code=renamed.replace(
                    'persistent_key="tags")', 'persistent_key="tags", max_items=0)'
                ),
            )
        ),
    )
    allowed = await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=renamed.replace(
                'persistent_key="tags")', 'persistent_key="tags", label="Labels")'
            ),
        )
    )
    assert allowed.schema_changed
    assert values(await domain.read(slot.collection_id)) == ["keep"]


async def test_tightening_uniqueness_rejects_existing_duplicates(domain):
    obj = await domain.make(tags=["duplicate", "duplicate"])
    await assert_http(
        409,
        domain.call(
            lambda service: service.execute(
                domain.model_id,
                code=BASE.replace(
                    "tags: List(String())", "tags: List(String(), unique_items=True)"
                ),
            )
        ),
    )
    assert domain.slot(
        await domain.call(lambda service: service.data.get_object(obj.id)), "tags"
    ).value == ["duplicate", "duplicate"]


async def test_reference_entity_rename_uses_durable_identity_and_no_inverse_relation(domain):
    operator = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Operator")
    )
    name = next(field.field_id for field in operator.fields if field.key == "name")
    first = await domain.call(
        lambda service: service.data.create_object(operator.entity_id, {name: "First"})
    )
    obj = await domain.make(operators=[first.object_id])
    slot = domain.slot(obj, "operators")
    before = await domain.read(slot.collection_id)
    renamed = BASE.replace(
        "class Operator(Entity):", f'class Vendor(Entity, tablename="{operator.table_name}"):'
    ).replace('Reference("Operator")', 'Reference("Vendor")')
    await domain.call(lambda service: service.execute(domain.model_id, code=renamed))
    vendor = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Vendor")
    )
    assert vendor.entity_id == operator.entity_id
    second = await domain.call(
        lambda service: service.data.create_object(vendor.entity_id, {name: "Second"})
    )
    after = await domain.edit("append_item", slot.collection_id, second.object_id)
    assert identities(after)[0] == identities(before)[0]
    assert values(after) == [first.object_id, second.object_id]
    from business_layer.schemas.models import BusinessEntityRelationVersion

    assert (
        await domain.count(
            BusinessEntityRelationVersion, from_field_id=slot.business_entity_field_id
        )
        == 0
    )


async def test_scalar_types_defaults_references_and_bitemporal_regression(domain):
    scalar_code = (
        BASE
        + """class State(Enum):
    OPEN = "open"
class Scalar(Entity):
    label: String(nullable=False, max_length=100)
    text: Text()
    number: Integer(ge=0)
    big: BigInteger()
    ratio: Float()
    money: Decimal(precision=12, scale=2)
    enabled: Boolean(default=False)
    day: Date()
    moment: DateTime()
    uid: UUID()
    document: JSON()
    operator: Reference("Operator")
    source: Source()
    state: State(default=State.OPEN)
    optional: String()
    empty: String(default=None)
"""
    )
    await domain.call(lambda service: service.execute(domain.model_id, code=scalar_code))
    definition = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Scalar")
    )
    ids = {field.key: field.field_id for field in definition.fields}
    operator = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Operator")
    )
    target = await domain.call(
        lambda service: service.data.create_object(
            operator.entity_id,
            {next(field.field_id for field in operator.fields if field.key == "name"): "Target"},
        )
    )
    from sources.schemas.enums import SourceType
    from sources.schemas.models import Source

    async with domain.factory() as session:
        source = Source(type=SourceType.HTML, url=f"https://example.com/{uuid4().hex}")
        session.add(source)
        await session.commit()
        source_id = source.id
    supplied = {
        "label": "before",
        "text": "body",
        "number": 1,
        "big": 2**40,
        "ratio": 1.25,
        "money": "12.34",
        "day": "2026-11-18",
        "moment": "2026-11-18T12:00:00Z",
        "uid": "11111111-1111-4111-8111-111111111111",
        "document": [None, True, {"a": "b"}],
        "operator": target.object_id,
        "source": source_id,
    }
    created = await domain.call(
        lambda service: service.data.create_object(
            definition.entity_id, {ids[key]: value for key, value in supplied.items()}
        )
    )
    read = await domain.call(lambda service: service.data.get_object(created.object_id))
    fields = {
        next(
            key for key, identity in ids.items() if identity == field.business_entity_field_id
        ): field
        for field in read.fields
    }
    for key, value in {**supplied, "enabled": False, "state": "open", "empty": None}.items():
        assert fields[key].value == value
        assert fields[key].collection_id is None
    assert fields["empty"].value_id is not None and fields["optional"].value_id is None
    known_before = datetime.now(UTC)
    updated = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            created.object_id,
            {fields["label"].object_field_id: "after"},
            expected_value_ids={fields["label"].object_field_id: fields["label"].value_id},
        )
    )
    assert (
        next(
            field for field in updated.fields if field.business_entity_field_id == ids["label"]
        ).value
        == "after"
    )
    old = await domain.call(
        lambda service: service.data.get_object(
            created.object_id, at=known_before, known_at=known_before
        )
    )
    assert (
        next(field for field in old.fields if field.business_entity_field_id == ids["label"]).value
        == "before"
    )
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                created.object_id, {fields["number"].object_field_id: -1}
            )
        ),
    )


async def test_seed_lists_execute_through_canonical_values(domain):
    result = await domain.call(
        lambda service: service.execute(
            domain.model_id,
            code=BASE
            + """
operator = Operator(name="Seeded operator")
project = Project(name="Seeded project", operators=[operator], tags=["one", "two"], scores=[10])
""",
        )
    )
    read = await domain.call(lambda service: service.data.get_object(result.objects["project"]))
    assert domain.slot(read, "operators").value == [result.objects["operator"]]
    assert domain.slot(read, "tags").value == ["one", "two"]
    assert domain.slot(read, "scores").value == [10]


async def test_postgres_channel_owner_position_and_overlap_constraints(domain):
    obj = await domain.make(tags=["one"])
    slot = domain.slot(obj, "tags")
    collection = await domain.read(slot.collection_id)
    item_id = identities(collection)[0]
    now = datetime.now(UTC)
    async with domain.factory() as session:
        # The scalar and collection channels are mutually exclusive.
        session.add(
            BusinessObjectFieldValue(
                business_object_field_id=slot.object_field_id,
                business_entity_field_id=slot.business_entity_field_id,
                validated_against_field_version_id=slot.validated_against_field_version_id,
                collection_id=slot.collection_id,
                value_json="invalid",
                valid_from=now - timedelta(days=2),
                valid_to=now - timedelta(days=1),
                transaction_from=now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    other = domain.slot(await domain.make(tags=[]), "tags")
    async with domain.factory() as session:
        session.add(
            BusinessObjectFieldValue(
                business_object_field_id=other.object_field_id,
                business_entity_field_id=other.business_entity_field_id,
                validated_against_field_version_id=other.validated_against_field_version_id,
                collection_id=slot.collection_id,
                value_json=null(),
                valid_from=now - timedelta(days=2),
                valid_to=now - timedelta(days=1),
                transaction_from=now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with domain.factory() as session:
        session.add(BusinessCollection(root_field_id=slot.object_field_id, parent_item_id=item_id))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with domain.factory() as session:
        new_item = BusinessCollectionItem(collection_id=slot.collection_id)
        session.add(new_item)
        await session.flush()
        session.add(
            BusinessCollectionItemVersion(
                item_id=new_item.id,
                collection_id=slot.collection_id,
                position=0,
                value_json="collision",
                present=True,
                valid_from=now,
                transaction_from=now,
            )
        )
        await session.flush()
        with pytest.raises(IntegrityError):
            await session.execute(
                text("SET CONSTRAINTS ex_business_collection_versions_position_overlap IMMEDIATE")
            )
        await session.rollback()
    async with domain.factory() as session:
        session.add(
            BusinessCollectionItemVersion(
                item_id=item_id,
                collection_id=slot.collection_id,
                position=1,
                value_json="overlap",
                present=True,
                valid_from=now,
                transaction_from=now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    assert values(await domain.read(slot.collection_id)) == ["one"]


async def test_migration_downgrade_is_safe_when_empty(database):
    engine, _, schema = database
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: migrate(conn, schema, "b200_business_baseline", True)
        )
        assert (
            await connection.scalar(
                text("SELECT to_regclass(current_schema() || '.business_collections')")
            )
            is None
        )
        await connection.run_sync(lambda conn: migrate(conn, schema, "head"))
        assert await connection.scalar(
            text("SELECT to_regclass(current_schema() || '.business_collections')")
        )


async def test_migration_refuses_to_drop_collection_history(domain, database):
    await domain.make(tags=[])
    engine, _, schema = database
    with pytest.raises(RuntimeError, match="without losing"):
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: migrate(conn, schema, "b200_business_baseline", True)
            )
    async with engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "b203_value_field_owner"
        )


@pytest.mark.parametrize("database", ["e102_extraction_recipes"], indirect=True)
async def test_upgrade_preserves_existing_scalar_json_and_backfills_keys(database):
    engine, _, schema = database
    async with engine.begin() as connection:
        for statement in [
            "INSERT INTO business_models(id,key,name) VALUES(10,'legacy','Legacy')",
            "INSERT INTO business_model_revisions(id,business_model_id) VALUES(11,10)",
            "INSERT INTO business_entities(id,business_model_id,table_name) VALUES(20,10,'legacy')",
            (
                "INSERT INTO business_entity_fields(id,business_entity_id,physical_name) "
                "VALUES(30,20,'payload')"
            ),
            (
                "INSERT INTO business_entity_field_versions(business_entity_field_id,revision_id,"
                "key,label,definition_json,valid_from) "
                "VALUES(30,11,'payload','Payload','{\"type\":\"json\"}'::jsonb,now())"
            ),
            "INSERT INTO business_objects(id,business_entity_id) VALUES(40,20)",
            (
                "INSERT INTO "
                "business_object_fields(id,business_object_id,business_entity_field_id) "
                "VALUES(50,40,30)"
            ),
            (
                "INSERT INTO "
                "business_object_field_values(id,business_object_field_id,value_json,valid_from)"
                " VALUES(60,50,'{\"old\":[true,null,1]}'::jsonb,now())"
            ),
        ]:
            await connection.execute(text(statement))
        await connection.run_sync(lambda conn: migrate(conn, schema, "head"))
        row = (
            await connection.execute(
                text(
                    "SELECT value_json, collection_id FROM business_object_field_values WHERE id=60"
                )
            )
        ).one()
        assert row.value_json == {"old": [True, None, 1]} and row.collection_id is None
        assert (
            await connection.scalar(
                text("SELECT persistent_key FROM business_entity_fields WHERE id=30")
            )
            == "payload"
        )


async def test_business_api_preconditions_temporal_reads_and_membership(domain, monkeypatch):
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from business_layer.api.database import get_session
    from business_layer.api.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def sessions():
        async with domain.factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    obj = await domain.make()
    slot = domain.slot(obj, "tags")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            f"/api/v1/business/object-fields/{slot.object_field_id}/collection", json={"values": []}
        )
        assert created.status_code == 201, created.text
        collection = created.json()
        path = f"/api/v1/business/collections/{collection['id']}"
        known_before = datetime.now(UTC)
        assert (await client.post(path + "/items", json={"value": "a"})).status_code == 422
        assert (
            await client.post(path + "/items", json={"value": "a", "expected_revision": 99})
        ).status_code == 409
        added = await client.post(path + "/items", json={"value": "a", "expected_revision": 0})
        assert added.status_code == 201, added.text
        current = added.json()
        item = current["items"][0]["id"]
        invalid = await client.patch(
            path + f"/items/{item}", json={"value": None, "expected_revision": current["revision"]}
        )
        assert invalid.status_code == 422
        assert (
            await client.patch(
                path + f"/items/{item}", json={"expected_revision": current["revision"]}
            )
        ).status_code == 422
        before = await client.get(
            path, params={"at": known_before.isoformat(), "known_at": known_before.isoformat()}
        )
        assert before.status_code == 200 and before.json()["items"] == []
        assert (await client.get(path, params={"at": "2026-11-18T12:00:00"})).status_code == 422
        changed = await client.patch(
            path + f"/items/{item}", json={"value": "A", "expected_revision": current["revision"]}
        )
        assert changed.status_code == 200
        assert changed.json()["items"][0]["id"] == item
        foreign = domain.slot(await domain.make(tags=["foreign"]), "tags")
        foreign_id = identities(await domain.read(foreign.collection_id))[0]
        assert (
            await client.patch(
                path + f"/items/{foreign_id}",
                json={"value": "x", "expected_revision": changed.json()["revision"]},
            )
        ).status_code == 404
        history = await client.get(path + f"/items/{item}/history")
        assert history.status_code == 200 and any(row["transaction_to"] for row in history.json())
        page = await client.get(path + "/items", params={"offset": 0, "limit": 1})
        assert page.status_code == 200 and page.json()["total"] == 1
        removed = await client.request(
            "DELETE",
            path + f"/items/{item}",
            json={"expected_revision": changed.json()["revision"]},
        )
        assert removed.status_code == 200 and removed.json()["items"] == []
        restored = await client.post(
            path + f"/items/{item}/restore",
            json={"value": "A", "expected_revision": removed.json()["revision"]},
        )
        assert restored.status_code == 200 and restored.json()["items"][0]["id"] == item
        replaced = await client.put(
            path + "/items",
            json={"values": ["x", "y"], "expected_revision": restored.json()["revision"]},
        )
        assert replaced.status_code == 200
        ids = [row["id"] for row in replaced.json()["items"]]
        reordered = await client.post(
            path + "/reorder",
            json={"item_ids": ids[::-1], "expected_revision": replaced.json()["revision"]},
        )
        assert (
            reordered.status_code == 200
            and [row["id"] for row in reordered.json()["items"]] == ids[::-1]
        )
        root = await domain.call(lambda service: service.data.get_object(obj.id))
        root_slot = domain.slot(root, "tags")
        canonical = await client.patch(
            f"/api/v1/business/objects/{obj.id}/values",
            json={
                "field_values": {str(slot.object_field_id): ["canonical"]},
                "expected_value_ids": {str(slot.object_field_id): root_slot.value_id},
                "expected_collection_revisions": {
                    str(slot.object_field_id): reordered.json()["revision"]
                },
            },
        )
        assert canonical.status_code == 200, canonical.text
        result = next(
            field
            for field in canonical.json()["fields"]
            if field["object_field_id"] == slot.object_field_id
        )
        assert result["collection_id"] == collection["id"] and result["value"] == ["canonical"]
        field_version = next(
            field.version_id for field in domain.definition.fields if field.key == "tags"
        )
        assert result["validated_against_field_version_id"] == field_version
        field_history = await client.get(
            f"/api/v1/business/object-fields/{slot.object_field_id}/history"
        )
        assert field_history.status_code == 200
        assert all(
            row["validated_against_field_version_id"] == field_version
            for row in field_history.json()
        )


async def test_field_value_precondition_prevents_aba_after_null_and_new_container(domain):
    obj = await domain.make(tags=[])
    original = domain.slot(obj, "tags")
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {original.object_field_id: None},
            expected_value_ids={original.object_field_id: original.value_id},
            expected_collection_revisions={original.object_field_id: 0},
        )
    )
    current = await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id, {original.object_field_id: []}
        )
    )
    replacement = domain.slot(current, "tags")
    assert replacement.collection_id != original.collection_id
    assert replacement.collection_revision == original.collection_revision == 0
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id,
                {original.object_field_id: ["stale"]},
                expected_collection_revisions={original.object_field_id: 0},
            )
        ),
    )
    await assert_http(
        409,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id,
                {original.object_field_id: ["stale"]},
                expected_value_ids={original.object_field_id: original.value_id},
                expected_collection_revisions={original.object_field_id: 0},
            )
        ),
    )
    assert values(await domain.read(replacement.collection_id)) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"position": None, "value_json": "x"},
        {"position": -1, "value_json": "x"},
        {"position": 0},
        {"position": 0, "value_json": "x", "present": False},
        {"position": 0, "reference_object_id": 10**12},
        {"position": 0, "source_id": 10**12},
    ],
)
async def test_postgres_rejects_invalid_item_channels_and_links(domain, bad):
    slot = domain.slot(await domain.make(tags=[]), "tags")
    async with domain.factory() as session:
        item = BusinessCollectionItem(collection_id=slot.collection_id)
        session.add(item)
        await session.flush()
        now = datetime.now(UTC)
        arguments = {"present": True, "position": 0, **bad}
        session.add(
            BusinessCollectionItemVersion(
                item_id=item.id,
                collection_id=slot.collection_id,
                valid_from=now,
                transaction_from=now,
                **arguments,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    assert values(await domain.read(slot.collection_id)) == []


async def test_persistent_collections_walkthrough(database):
    from business_layer.scripts.step_24_collections import operation

    _, factory, _ = database
    async with factory() as session:
        result = await operation(BusinessService(session), uuid4().hex)
        await session.commit()
    assert len(result["original"]["items"]) == 3
    assert identities(result["reordered"]) == identities(result["original"])[::-1]
    assert len(result["removed"]["items"]) == 2
    assert len(result["appended"]["items"]) == 3
    assert identities(result["historical"]) == identities(result["original"])


async def test_archived_owner_and_non_list_field_reject_collection_writes(domain):
    obj = await domain.make(tags=[])
    slot = domain.slot(obj, "tags")
    name_slot = domain.slot(obj, "name")
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.collections.create_collection(
                name_slot.object_field_id, [], expected_value_id=name_slot.value_id
            )
        ),
    )
    await domain.call(lambda service: service.data.archive_object(obj.id))
    await assert_http(409, domain.edit("append_item", slot.collection_id, "archived"))
    assert values(await domain.read(slot.collection_id)) == []


async def test_object_list_materializes_ordered_lists_and_tokens_in_batches(domain):
    objects = [
        await domain.make(tags=[str(index), "tail"], payloads=[{"index": index}])
        for index in range(6)
    ]
    first = domain.slot(objects[0], "tags")
    await domain.edit(
        "reorder_items",
        first.collection_id,
        identities(await domain.read(first.collection_id))[::-1],
    )
    read = await domain.call(lambda service: service.data.list_objects(domain.entity_id))
    by_id = {obj.id: obj for obj in read}
    assert domain.slot(by_id[objects[0].id], "tags").value == ["tail", "0"]
    assert (
        domain.slot(by_id[objects[0].id], "tags").collection_revision
        == first.collection_revision + 1
    )
    for index, obj in enumerate(objects[1:], 1):
        assert domain.slot(by_id[obj.id], "tags").value == [str(index), "tail"]
        assert domain.slot(by_id[obj.id], "payloads").value == [{"index": index}]


async def test_reference_validation_refreshes_cached_archival_state(domain):
    from business_layer.schemas.models import BusinessObject

    definition = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Operator")
    )
    name = next(field.field_id for field in definition.fields if field.key == "name")
    target = await domain.call(
        lambda service: service.data.create_object(definition.entity_id, {name: "Target"})
    )
    slot = domain.slot(await domain.make(operators=[]), "operators")
    async with domain.factory() as session:
        cached = await session.get(BusinessObject, target.object_id)
        assert cached.archived_at is None
        await domain.call(lambda service: service.data.archive_object(target.object_id))
        with pytest.raises(HTTPException) as raised:
            await BusinessService(session).data.collections.append_item(
                slot.collection_id, target.object_id, expected_revision=slot.collection_revision
            )
        assert raised.value.status_code == 422
    assert values(await domain.read(slot.collection_id)) == []


async def test_read_revision_matches_contents_when_writer_commits_during_read(domain, monkeypatch):
    from business_layer.services import CollectionsService

    slot = domain.slot(await domain.make(tags=[]), "tags")
    known_before = datetime.now(UTC)
    async with domain.factory() as session:
        reader = CollectionsService(session)
        identity = reader._identity

        async def interleave(collection_id):
            monkeypatch.setattr(reader, "_identity", identity)
            await domain.edit("append_item", collection_id, "concurrent", expected_revision=0)
            return await identity(collection_id)

        monkeypatch.setattr(reader, "_identity", interleave)
        snapshot = await reader.get_collection(slot.collection_id)
        assert snapshot["revision"] == 1 and values(snapshot) == ["concurrent"]
        historic = await reader.get_collection(slot.collection_id, known_at=known_before)
        assert historic["revision"] == 0 and values(historic) == []
