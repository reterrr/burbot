from uuid import uuid4

import pytest
from sqlalchemy import event
from test_collections_postgres import BASE
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_monitoring_postgres import agent, monitor, review, source
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_monitoring_workspace import read
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import (
    BusinessEntityFieldVersion,
    BusinessObject,
    BusinessObjectFieldValue,
)
from business_layer.services.business import BusinessService
from business_layer.services.presentation import BusinessPresentation
from sources.schemas.models import Source

pytestmark = pytest.mark.asyncio
SCHEMA = (
    BASE
    + """
class Finding(Entity):
    title: Text()
    project_id: Reference("Project", label="Projekt")
    source_id: Source()
    count: Integer()
    active: Boolean()
    day: Date()
    checked: DateTime()
    amount: Decimal()
    wide: BigInteger()
    projects: List(Reference("Project"))
    payload: JSON()
"""
)
PROJECT_ID = 291
PROJECT_NAME = "Regional Programme – development services 2024–2029"


async def findings(domain):
    await domain.call(lambda service: service.execute(domain.model_id, code=SCHEMA))
    return await domain.call(
        lambda service: service.entities.resolve_entity(domain.model_id, "Finding")
    )


async def make(service, definition, **values):
    supplied = {
        field.field_id: values[field.key] for field in definition.fields if field.key in values
    }
    created = await service.data.create_object(definition.entity_id, supplied)
    return await service.data.get_object(created.object_id)


def slot(definition, obj, key):
    field_id = next(field.field_id for field in definition.fields if field.key == key)
    return next(field for field in obj.fields if field.business_entity_field_id == field_id)


def binding(slot):
    return slot.object_field_id, slot.business_entity_field_id


async def project(domain):
    async with domain.factory.begin() as session:
        session.add(BusinessObject(id=PROJECT_ID, business_entity_id=domain.entity_id))
    synced = await domain.call(lambda service: service.data.sync_object_fields(PROJECT_ID))
    name_slot = synced.object_fields[domain.fields["name"]]
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            PROJECT_ID, {name_slot: PROJECT_NAME}
        )
    )
    return name_slot


async def test_task_and_source_review_share_current_reference_display(domain, client, minio):
    finding = await findings(domain)
    name_slot = await project(domain)
    obj = await domain.call(
        lambda service: make(service, finding, title="Funding notice", project_id=PROJECT_ID)
    )
    project_slot = slot(finding, obj, "project_id")
    row = await source(domain, client)
    response = await client.post(
        "/extraction/selectors/import",
        json={
            "tree": tree(recipe(part(css("#programme")))),
            "binding": {
                "sourceId": row.id,
                "businessEntityFieldId": project_slot.business_entity_field_id,
                "businessObjectFieldId": project_slot.object_field_id,
            },
        },
    )
    assert response.status_code == 200, response.text
    headers, _ = await agent(client, row.id)
    first = await monitor(
        client, domain, headers, row.id, b'<p id="programme">Regional Programme</p>'
    )
    task_id = first["fields"][0]["taskId"]
    task = await review(client, task_id)
    source_path = f"/monitoring/sources/{row.id}/review"
    tracked = (await read(client, source_path))["fields"][0]
    assert (
        task["businessField"]
        == tracked["businessField"]
        == {
            "id": project_slot.business_entity_field_id,
            "name": "Projekt",
            "persistentKey": "project_id",
            "type": "reference",
            "referenceEntity": {"id": domain.entity_id, "name": "Project"},
        }
    )
    assert (
        task["businessObject"]
        == tracked["businessObject"]
        == {
            "id": obj.id,
            "name": "Funding notice",
        }
    )
    assert task["canonicalValue"] == tracked["canonicalValue"] == PROJECT_ID
    assert task["canonicalValueId"] == tracked["canonicalValueId"] == project_slot.value_id
    assert (
        task["canonicalDisplay"]
        == tracked["canonicalDisplay"]
        == {
            "kind": "reference",
            "rawValue": PROJECT_ID,
            "label": PROJECT_NAME,
            "target": {
                "type": "business_object",
                "id": PROJECT_ID,
                "entityId": domain.entity_id,
                "entityName": "Project",
            },
            "resolved": True,
            "labelIsCurrent": True,
        }
    )
    assert task["canonicalValueScope"] == tracked["canonicalValueScope"] == "current"
    assert task["currentEvidence"] == tracked["currentEvidence"] == "Regional Programme"
    assert task["previousEvidence"] is None
    assert task["source"]["url"] == row.url
    assert task["snapshot"]["fetched_at"]
    assert task["extractionRunStatus"] == "succeeded"
    assert task["evaluation"]["result"]["status"] == "success"

    # A schema revision closes the original relation version. The canonical record
    # continues to use the reference target from its validating field version.
    updated_schema = SCHEMA.replace('label="Projekt"', 'label="Project link"')
    await domain.call(lambda service: service.execute(domain.model_id, code=updated_schema))
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            PROJECT_ID, {name_slot: "Renamed programme"}
        )
    )
    await monitor(client, domain, headers, row.id, b'<p id="programme">New raw evidence</p>')
    historical = (await read(client, source_path, checkId=first["jobId"]))["fields"][0]
    older_task = await review(client, task_id)
    assert (
        older_task["canonicalDisplay"]
        == historical["canonicalDisplay"]
        == {
            **task["canonicalDisplay"],
            "label": "Renamed programme",
        }
    )
    assert older_task["canonicalValueScope"] == historical["canonicalValueScope"] == "current"
    assert older_task["canonicalValueId"] == historical["canonicalValueId"] == project_slot.value_id
    assert older_task["currentEvidence"] == historical["currentEvidence"] == task["currentEvidence"]
    assert older_task["evaluation"] == task["evaluation"]


async def test_type_display_uses_separate_target_namespaces_and_handles_legacy_values(domain):
    finding = await findings(domain)
    await project(domain)
    url = "https://example.org/programme"
    async with domain.factory.begin() as session:
        session.add(Source(id=PROJECT_ID, type="HTML", url=url))
    unknown = {"currency": "PLN", "amount": 291}
    supplied = {
        "title": "Readable title",
        "project_id": PROJECT_ID,
        "source_id": PROJECT_ID,
        "count": 291,
        "active": False,
        "day": "2026-11-25",
        "checked": "2026-11-25T16:05:00+01:00",
        "amount": "9007199254.740991",
        "wide": 9007199254740993,
        "projects": [PROJECT_ID],
        "payload": unknown,
    }
    obj = await domain.call(lambda service: make(service, finding, **supplied))
    nullable = await domain.call(lambda service: make(service, finding, title=None))
    empty = await domain.call(lambda service: make(service, finding))
    keys = {key: binding(slot(finding, obj, key)) for key in supplied}
    null_key, empty_key = (binding(slot(finding, row, "title")) for row in (nullable, empty))
    async with domain.factory() as session:
        values = await BusinessPresentation(session).business_contexts(
            [*keys.values(), null_key, empty_key]
        )
    for key, raw in supplied.items():
        assert values[keys[key]]["canonicalValue"] == raw
        assert values[keys[key]]["canonicalDisplay"]["rawValue"] == raw
    assert values[keys["project_id"]]["canonicalDisplay"]["label"] == PROJECT_NAME
    source_display = values[keys["source_id"]]["canonicalDisplay"]
    assert source_display["label"] == url
    assert source_display["target"] == {"type": "source", "id": PROJECT_ID}
    assert values[keys["count"]]["canonicalDisplay"] == {"kind": "integer", "rawValue": 291}
    assert values[keys["title"]]["canonicalDisplay"]["kind"] == "text"
    assert values[keys["active"]]["canonicalDisplay"]["kind"] == "boolean"
    assert values[keys["day"]]["canonicalDisplay"]["kind"] == "date"
    assert values[keys["checked"]]["canonicalDisplay"]["kind"] == "datetime"
    assert values[keys["amount"]]["canonicalDisplay"]["kind"] == "decimal"
    assert values[keys["wide"]]["canonicalDisplay"]["label"] == "9007199254740993"
    assert values[keys["projects"]]["canonicalDisplay"]["items"] == [
        values[keys["project_id"]]["canonicalDisplay"]
    ]
    assert values[null_key]["canonicalDisplay"] == {"kind": "text", "rawValue": None}
    assert values[empty_key]["canonicalDisplay"] is None

    # Simulate legacy rows whose JSON predates validation or whose definitions are unknown.
    project_value = slot(finding, obj, "project_id")
    payload_value = slot(finding, obj, "payload")
    async with domain.factory.begin() as session:
        value = await session.get(BusinessObjectFieldValue, project_value.value_id)
        value.value_json = obj.id  # Present BusinessObject, but attached to the wrong entity.
        version = await session.get(
            BusinessEntityFieldVersion, payload_value.validated_against_field_version_id
        )
        version.definition_json = {"type": "legacy"}
    async with domain.factory() as session:
        values = await BusinessPresentation(session).business_contexts(keys.values())
    assert values[keys["project_id"]]["canonicalDisplay"] == {
        "kind": "reference",
        "rawValue": obj.id,
        "label": f"BusinessObject #{obj.id}",
        "target": {"type": "business_object", "id": obj.id},
        "resolved": False,
    }
    assert values[keys["payload"]]["canonicalDisplay"] == {"kind": "legacy", "rawValue": unknown}

    async with domain.factory.begin() as session:
        value = await session.get(BusinessObjectFieldValue, project_value.value_id)
        value.value_json = 999999
    async with domain.factory() as session:
        key = keys["project_id"]
        missing = (await BusinessPresentation(session).business_contexts([key]))[key]
    assert missing["canonicalDisplay"]["label"] == "BusinessObject #999999"
    assert missing["canonicalDisplay"]["resolved"] is False


async def test_reference_queries_do_not_grow_per_field_or_target(domain, database):
    finding = await findings(domain)
    bindings = []
    async with domain.factory.begin() as session:
        service = BusinessService(session)
        for _ in range(12):
            target = await service.data.create_object(
                domain.entity_id, {domain.fields["name"]: uuid4().hex}
            )
            row = await make(service, finding, project_id=target.object_id)
            bindings.append(binding(slot(finding, row, "project_id")))

    engine, _, _ = database
    statements = []

    def record(_conn, _cursor, statement, *_):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        async with domain.factory() as session:
            await BusinessPresentation(session).business_contexts(bindings[:1])
        single = len(statements)
        statements.clear()
        async with domain.factory() as session:
            values = await BusinessPresentation(session).business_contexts(bindings)
        assert len(statements) == single
        assert len(values) == len(bindings)
        assert all(value["canonicalDisplay"]["resolved"] for value in values.values())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
