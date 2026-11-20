"""Exercise schema publication, restoration, and value ownership on migrated PostgreSQL."""

import asyncio
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from test_collections_postgres import BASE, assert_http
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain

from business_layer.schemas.models import (
    BusinessCollection,
    BusinessCollectionItem,
    BusinessCollectionItemVersion,
    BusinessDefinitionCodeVersion,
    BusinessEntityField,
    BusinessEntityFieldVersion,
    BusinessModel,
    BusinessModelRevision,
    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)
from business_layer.services.business import BusinessService

pytestmark = pytest.mark.asyncio


async def execute(domain, code):
    return await domain.call(lambda service: service.execute(domain.model_id, code=code))


async def definition(domain, key):
    return await domain.call(lambda service: service.entities.resolve_field(domain.entity_id, key))


async def read(domain, object_id, **times):
    return await domain.call(lambda service: service.data.get_object(object_id, **times))


async def revision_id(domain):
    return (
        await domain.call(lambda service: service.entities.get_model(domain.model_id))
    ).current_revision_id


async def preview(domain, code):
    async def inspect(service):
        program = await service.compile(domain.model_id, code)
        return await service.entities.find_changes(domain.model_id, program.schema)

    return await domain.call(inspect)


async def create_probe(domain, value):
    field = await definition(domain, "probe")
    created = await domain.call(
        lambda service: service.data.create_object(
            domain.entity_id, {domain.fields["name"]: "Project", field.field_id: value}
        )
    )
    slot_id = created.object_fields[field.field_id]
    obj = await read(domain, created.object_id)
    return obj, next(slot for slot in obj.fields if slot.object_field_id == slot_id)


async def test_create_nullable_field_edit_unused_slot_and_repeat_schema(domain):
    obj = await domain.make()
    code = BASE + "\n    probe: Integer()\n"
    assert (await execute(domain, code)).schema_changed
    field = await definition(domain, "probe")
    assert field.field_id not in {
        slot.business_entity_field_id for slot in (await read(domain, obj.id)).fields
    }
    slots = await domain.call(lambda service: service.data.sync_object_fields(obj.id))
    slot_id = slots.object_fields[field.field_id]
    assert not await domain.call(
        lambda service: service.entities.field_has_value_history(field.field_id)
    )

    changed = code.replace("probe: Integer()", "probe: String(max_length=10)")
    changes = await preview(domain, changed)
    probe = next(change for change in changes if change.field == "probe")
    assert probe.structural and probe.allowed and not probe.has_value_history
    result = await execute(domain, changed)
    current = await definition(domain, "probe")
    assert current.field_id == field.field_id and current.version_id != field.version_id
    updated = await domain.call(
        lambda service: service.data.assign_object_fields_values(obj.id, {slot_id: "ready"})
    )
    slot = next(item for item in updated.fields if item.object_field_id == slot_id)
    assert slot.value == "ready" and slot.validated_against_field_version_id == current.version_id
    count = await domain.count(BusinessObjectFieldValue)
    assert not (await execute(domain, changed)).schema_changed
    assert await revision_id(domain) == result.revision_id
    assert await domain.count(BusinessObjectFieldValue) == count
    await execute(domain, BASE)
    await assert_http(409, execute(domain, code))
    await execute(domain, changed)
    restored = await read(domain, obj.id)
    assert next(item for item in restored.fields if item.object_field_id == slot_id) == slot


@pytest.mark.parametrize(
    ("before", "after", "value"),
    [
        ("String()", "Integer()", "text"),
        ("String()", "String(nullable=False)", "text"),
        ('String(default="old")', 'String(default="new")', "text"),
        ("Integer(ge=0)", "Integer(ge=1)", 10),
        ("Decimal(precision=10, scale=2)", "Decimal(precision=15, scale=2)", "12.34"),
        ("String()", "String(unique=True)", "unique"),
        ("String(nullable=False)", "String(nullable=False, primary_key=True)", "key"),
        ("String()", "String(index=True)", None),
        ("String()", "String(max_length=20)", "short"),
        ("List(String())", "List(Integer())", []),
        ("List(String())", "List(String(), max_items=5)", ["fits"]),
        ("List(String())", "List(String(), unique_items=True)", ["unique"]),
    ],
)
async def test_structural_edits_with_canonical_history_require_migration(
    domain, before, after, value
):
    code = BASE + f"\n    probe: {before}\n"
    await execute(domain, code)
    obj, slot = await create_probe(domain, value)
    previous_revision = await revision_id(domain)
    previous_definition = await definition(domain, "probe")
    conflict = await assert_http(409, execute(domain, BASE + f"\n    probe: {after}\n"))
    detail = conflict.detail
    assert detail["code"] == "SCHEMA_MIGRATION_REQUIRED"
    assert detail["entity"] == "Project" and detail["field"] == detail["persistent_key"] == "probe"
    assert detail["previous_definition"] != detail["requested_definition"]
    assert await revision_id(domain) == previous_revision
    assert (await definition(domain, "probe")).version_id == previous_definition.version_id
    assert (
        next(item for item in (await read(domain, obj.id)).fields if item.value_id == slot.value_id)
        == slot
    )


async def test_closed_history_blocks_changes_without_an_effective_value(domain):
    code = BASE + "\n    probe: String()\n"
    await execute(domain, code)
    obj, slot = await create_probe(domain, None)
    closed_at = datetime.now(UTC)
    async with domain.factory() as session, session.begin():
        await session.execute(
            update(BusinessObjectFieldValue)
            .where(BusinessObjectFieldValue.id == slot.value_id)
            .values(valid_to=closed_at, transaction_to=closed_at)
        )
        await session.execute(
            update(BusinessObjectField)
            .where(BusinessObjectField.id == slot.object_field_id)
            .values(effective_value_id=None)
        )
    await domain.call(lambda service: service.data.archive_object(obj.id))
    fields = (await read(domain, obj.id)).fields
    assert (
        next(item for item in fields if item.object_field_id == slot.object_field_id).value_id
        is None
    )
    assert await domain.call(
        lambda service: service.entities.field_has_value_history(slot.business_entity_field_id)
    )
    await assert_http(409, execute(domain, code.replace("probe: String()", "probe: Integer()")))


@pytest.mark.parametrize("field_type,value", [("Stage", "open"), ("List(Stage)", ["open"])])
async def test_enum_declaration_edits_reach_fields_and_reactivation(domain, field_type, value):
    declaration = f"    probe: {field_type}\n"
    enum = 'class Stage(Enum):\n    OPEN = "open"\n    CLOSED = "closed"\n'
    code = enum + BASE + declaration
    await execute(domain, code)
    await create_probe(domain, value)
    reordered = (
        'class Stage(Enum):\n    CLOSED = "closed"\n    OPEN = "open"\n' + BASE + declaration
    )
    assert not (await execute(domain, reordered)).schema_changed

    member_renamed = code.replace("    OPEN =", "    ACTIVE =")
    changes = await preview(domain, member_renamed)
    field = next(change for change in changes if change.field == "probe")
    assert field.structural and field.has_value_history and not field.allowed
    await assert_http(409, execute(domain, member_renamed))
    await assert_http(409, execute(domain, code.replace('CLOSED = "closed"', 'CLOSED = "done"')))
    await execute(domain, BASE)
    conflict = await assert_http(409, execute(domain, member_renamed))
    assert conflict.detail["code"] == "SCHEMA_MIGRATION_REQUIRED"
    assert (await execute(domain, code)).schema_changed


@pytest.mark.parametrize("collection", [False, True])
async def test_reference_target_rename_allowed_but_retarget_blocked(domain, collection):
    target = 'Reference("Operator")'
    probe_type = f"List({target})" if collection else target
    code = BASE + f"    probe: {probe_type}\n\nclass Alternate(Entity):\n    pass\n"
    await execute(domain, code)
    obj, canonical = await create_probe(domain, [] if collection else None)
    operator = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Operator")
    )
    renamed = code.replace(
        "class Operator(Entity):", f'class Vendor(Entity, tablename="{operator.table_name}"):'
    ).replace('Reference("Operator")', 'Reference("Vendor")')
    assert (await execute(domain, renamed)).schema_changed
    vendor = await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Vendor")
    )
    assert vendor.entity_id == operator.entity_id
    current = next(
        slot for slot in (await read(domain, obj.id)).fields if slot.value_id == canonical.value_id
    )
    assert current == canonical
    retargeted = renamed.replace(
        f"    probe: {probe_type.replace('Operator', 'Vendor')}",
        f"    probe: {probe_type.replace('Operator', 'Alternate')}",
    )
    await assert_http(409, execute(domain, retargeted))


async def test_retire_and_restore_scalar_and_list_without_rewriting_history(domain):
    obj = await domain.make(name="original", tags=["kept"])
    name, tags = (domain.slot(obj, key) for key in ("name", "tags"))
    models = (
        BusinessEntityField,
        BusinessObjectField,
        BusinessObjectFieldValue,
        BusinessCollection,
        BusinessCollectionItem,
        BusinessCollectionItemVersion,
    )
    counts = [await domain.count(model) for model in models]
    before = datetime.now(UTC)
    retired = BASE.replace(
        "class Project(Entity):\n    name: String(nullable=False)\n", "class Project(Entity):\n"
    ).replace("    tags: List(String())\n", "")
    await execute(domain, retired)
    gap = datetime.now(UTC)
    hidden = {name.object_field_id, tags.object_field_id}
    for view in [
        await read(domain, obj.id),
        (await domain.call(lambda service: service.data.list_objects(domain.entity_id)))[0],
    ]:
        assert hidden.isdisjoint(slot.object_field_id for slot in view.fields)
    assert [await domain.count(model) for model in models] == counts
    old = await read(domain, obj.id, at=before, known_at=gap)
    assert domain.slot(old, "name") == name and domain.slot(old, "tags") == tags
    previous_belief = await read(domain, obj.id, at=gap, known_at=before)
    assert domain.slot(previous_belief, "tags") == tags
    for slot in [name, tags]:
        history = await domain.call(
            lambda service, slot_id=slot.object_field_id: (
                service.data.get_object_field_value_history(slot_id)
            )
        )
        assert [row.id for row in history] == [slot.value_id]
        assert (
            history[0].validated_against_field_version_id == slot.validated_against_field_version_id
        )
    assert not (await domain.read(tags.collection_id))["active"]
    assert (await domain.read(tags.collection_id))["items"][0]["value"] == "kept"
    await assert_http(
        422,
        domain.call(
            lambda service: service.data.assign_object_fields_values(
                obj.id,
                {tags.object_field_id: []},
                expected_collection_revisions={tags.object_field_id: tags.collection_revision},
            )
        ),
    )

    errors = [
        BASE.replace("name: String(nullable=False)", "name: Integer(nullable=False)"),
        BASE.replace("tags: List(String())", "tags: List(Integer())"),
    ]
    for code in errors:
        conflict = await assert_http(409, execute(domain, code))
        assert conflict.detail["code"] == "SCHEMA_MIGRATION_REQUIRED"

    renamed = BASE.replace(
        "    tags: List(String())",
        '    labels: List(String(), persistent_key="tags", '
        'label="Labels", description="Kept tags")',
    )
    assert (await execute(domain, renamed)).schema_changed
    current = await definition(domain, "labels")
    assert current.field_id == tags.business_entity_field_id
    assert current.version_id != tags.validated_against_field_version_id
    assert current.label == "Labels" and current.description == "Kept tags"
    restored = await read(domain, obj.id)
    assert domain.slot(restored, "name") == name and domain.slot(restored, "tags") == tags
    assert hidden.isdisjoint(
        slot.object_field_id for slot in (await read(domain, obj.id, at=gap)).fields
    )
    assert [await domain.count(model) for model in models] == counts
    assert (await domain.read(tags.collection_id))["active"]


async def test_entity_deactivation_preserves_objects_slots_and_values(domain):
    obj = await domain.make(tags=["preserved"])
    before = datetime.now(UTC)
    await execute(domain, BASE.split("class Project(Entity):")[0])
    assert (await read(domain, obj.id)).fields == []
    assert (await read(domain, obj.id, at=before)).fields == obj.fields
    assert await domain.count(BusinessObject) == 1
    await execute(domain, BASE)
    current = await read(domain, obj.id)
    assert current.business_entity_id == obj.business_entity_id and current.fields == obj.fields


@pytest.mark.parametrize("existing_slot", [False, True])
async def test_required_field_needs_backfill_even_with_default(domain, existing_slot):
    code = BASE + "\n    probe: Integer()\n" if existing_slot else BASE
    if existing_slot:
        await execute(domain, code)
    await domain.make()
    desired = BASE + "\n    probe: Integer(nullable=False, default=1)\n"
    before = await revision_id(domain)
    conflict = await assert_http(409, execute(domain, desired))
    assert conflict.detail["code"] == "SCHEMA_MIGRATION_REQUIRED"
    assert "backfill" in conflict.detail["reason"]
    assert await revision_id(domain) == before


async def test_required_field_cannot_restore_over_objects_created_during_gap(domain):
    obj = await domain.make()
    reduced = BASE.replace(
        "class Project(Entity):\n    name: String(nullable=False)\n", "class Project(Entity):\n"
    )
    await execute(domain, reduced)
    await domain.call(lambda service: service.data.create_object(domain.entity_id))
    conflict = await assert_http(409, execute(domain, BASE))
    assert conflict.detail["persistent_key"] == "name"
    assert "backfill" in conflict.detail["reason"]
    assert (await read(domain, obj.id)).fields


async def test_preview_and_rejected_execute_leave_schema_code_and_data_unchanged(
    domain, monkeypatch
):
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
    await domain.make()
    draft = BASE.replace(
        "    tags: List(String())", "    tags: List(String())\n    extra: String()"
    )
    draft = (
        draft.replace(
            "class Project(Entity):\n    name: String(nullable=False)",
            "class Project(Entity):\n    name: Integer(nullable=False)",
        )
        + "\nproject = Project(name=42)\n"
    )
    models = (
        BusinessModelRevision,
        BusinessEntityField,
        BusinessEntityFieldVersion,
        BusinessDefinitionCodeVersion,
        BusinessObject,
        BusinessObjectFieldValue,
    )
    previous_revision = await revision_id(domain)
    before = [await domain.count(model) for model in models]
    program = await domain.call(lambda service: service.compile(domain.model_id, draft))
    payload = {"schema": program.schema.model_dump(mode="json")}
    path = f"/api/v1/business/models/{domain.model_id}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path + "/changes", json=payload)
        assert response.status_code == 200, response.text
        changes = response.json()
        blocked = next(
            change
            for change in changes
            if change["field"] == "name" and change["entity"] == "Project"
        )
        assert blocked["structural"] and blocked["has_value_history"] and not blocked["allowed"]
        assert blocked["reason"] == "SCHEMA_MIGRATION_REQUIRED"
        assert next(change for change in changes if change["field"] == "extra")["allowed"]
        assert [await domain.count(model) for model in models] == before
        json_response = await client.post(path + "/revisions", json=payload)
        dsl_response = await client.post(path + "/execute", json={"code": draft})
        assert json_response.status_code == dsl_response.status_code == 409
        detail = dsl_response.json()["detail"]
        assert json_response.json()["detail"] == detail
        assert detail["code"] == "SCHEMA_MIGRATION_REQUIRED"
        assert detail["previous_definition"]["type"] == "string"
        assert detail["requested_definition"]["type"] == "integer"
    assert [await domain.count(model) for model in models] == before
    assert await revision_id(domain) == previous_revision


@pytest.mark.parametrize(
    "change_owner,constraint",
    [
        (False, "fk_business_values_validated_field_version"),
        (True, "fk_business_values_slot_field"),
    ],
)
async def test_postgres_rejects_a_validation_version_from_another_field(
    domain, change_owner, constraint
):
    obj = await domain.make(tags=[])
    name, tags = (domain.slot(obj, key) for key in ("name", "tags"))
    async with domain.factory() as session:
        value = await session.get(BusinessObjectFieldValue, name.value_id)
        assert value.business_entity_field_id == name.business_entity_field_id
        value.validated_against_field_version_id = tags.validated_against_field_version_id
        if change_owner:
            value.business_entity_field_id = tags.business_entity_field_id
        with pytest.raises(IntegrityError, match=constraint):
            await session.flush()
        await session.rollback()
    current = await read(domain, obj.id)
    assert domain.slot(current, "name") == name


@pytest.mark.parametrize("first", ["write", "schema"])
async def test_write_and_schema_registration_serialize_on_model(domain, first):
    obj = await domain.make()
    slot = domain.slot(obj, "tags")
    draft = BASE.replace("tags: List(String())", "tags: Integer()")
    schema = (await domain.call(lambda service: service.compile(domain.model_id, draft))).schema

    async def assign(service):
        return await service.data.assign_object_fields_values(
            obj.id, {slot.object_field_id: ["old"]}
        )

    async def register(service):
        return await service.entities.register(domain.model_id, None, None, schema)

    leading, following = (assign, register) if first == "write" else (register, assign)
    async with domain.factory() as holder, domain.factory() as waiter:
        # Cache the original model, then verify the blocked transaction's real lock.
        original = await waiter.get(BusinessModel, domain.model_id)
        pid = await waiter.scalar(text("SELECT pg_backend_pid()"))
        old_revision = original.current_revision_id
        async with holder.begin():
            await leading(BusinessService(holder))
            task = asyncio.create_task(following(BusinessService(waiter)))
            try:
                for _ in range(100):
                    async with domain.factory() as monitor:
                        if await monitor.scalar(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}
                        ):
                            break
                    await asyncio.sleep(0.01)
                else:
                    pytest.fail("The competing writer did not wait for the model lock")
            except BaseException:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
        await assert_http(409 if first == "write" else 422, asyncio.wait_for(task, timeout=5))

    current = domain.slot(await read(domain, obj.id), "tags")
    if first == "write":
        assert current.value == ["old"]
        assert await revision_id(domain) == old_revision
    else:
        assert current.value_id is None
        assert (await definition(domain, "tags")).definition["type"] == "integer"
    assert await domain.count(
        BusinessObjectFieldValue, business_object_field_id=slot.object_field_id
    ) == (1 if first == "write" else 0)
