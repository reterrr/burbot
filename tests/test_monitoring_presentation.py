"""Regression tests for typed monitoring reads against the Business Layer schema."""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select, text, update
from test_collections_postgres import Domain
from test_collections_postgres import database as database
from test_monitoring_postgres import OPERATOR, agent, monitor, review, source
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import (
    BusinessEntityFieldVersion,
    BusinessEntityVersion,
    BusinessObjectFieldValue,
)
from monitoring.presentation import field_presentations
from sources.schemas.models import Source, StoredFile
from tasks.services.task import TasksService

pytestmark = pytest.mark.asyncio
PROJECT_NAME = (
    "Podmiotowy System Finansowania - realizacja usług rozwojowych "
    "w województwie podlaskim 2024 - 2029"
)
PROGRAM = """
class Project(Entity):
    name: String()
    title: Text()
    public_title: Text()

class Application(Entity):
    name: String()
    project_id: Reference("Project", label="Projekt")
    page: Source()
    count: Integer()
    large_number: BigInteger()
    amount: Decimal()
    approved: Boolean()
    deadline: Date()
    checked: DateTime()
    projects: List(Reference("Project"))
    sources: List(Source())
    tags: List(String())
    payload: JSON()
"""


@pytest_asyncio.fixture
async def domain(database):
    _, factory, _ = database
    domain = Domain(factory)
    model = await domain.call(
        lambda service: service.entities.create_model(key=uuid4().hex, name="Monitoring display")
    )
    await domain.call(lambda service: service.execute(model.id, code=PROGRAM))
    application = await domain.call(
        lambda service: service.entities.resolve_entity(model.id, "Application")
    )
    project = await domain.call(
        lambda service: service.entities.resolve_entity(model.id, "Project")
    )
    domain.entity_id = application.entity_id
    domain.fields = {field.key: field.field_id for field in application.fields}
    domain.project = project
    return domain


async def make_project(domain, **values):
    fields = {field.key: field.field_id for field in domain.project.fields}
    return await domain.call(
        lambda service: service.data.create_object(
            domain.project.entity_id, {fields[key]: value for key, value in values.items()}
        )
    )


async def present(domain, obj, *keys):
    pairs = {key: (domain.fields[key], domain.slot(obj, key).object_field_id) for key in keys}
    async with domain.factory() as session:
        responses = await field_presentations(session, pairs.values())
    return {key: responses[pair]["canonicalDisplay"] for key, pair in pairs.items()}


async def test_typed_values_use_schema_and_separate_source_and_object_ids(domain):
    async with domain.factory.begin() as session:
        # Reproduce the same identity as the supplied example on both tables.
        await session.execute(
            text("SELECT setval(pg_get_serial_sequence('business_objects', 'id'), 290)")
        )
    project = await make_project(domain, name=PROJECT_NAME, title="Alternate title")
    assert project.object_id == 291
    async with domain.factory.begin() as session:
        session.add(Source(id=291, type="HTML", url="https://example.org/291"))
        file = StoredFile(
            storage_key="file", original_name="Programme.pdf", mime_type="application/pdf"
        )
        session.add(file)
        await session.flush()
        session.add(Source(id=292, type="PDF", file_id=file.id))

    values = dict(
        name="Application 1",
        project_id=291,
        page=291,
        count=291,
        large_number=9_223_372_036_854_775_807,
        amount="9007199254740993.12345",
        approved=False,
        deadline="2026-11-25",
        checked="2026-11-24T16:05:00+01:00",
        projects=[291],
        sources=[291, 292],
        tags=[],
        payload={"unknown": [None, False]},
    )
    obj = await domain.make(**values)
    display = await present(domain, obj, *values)
    assert display["project_id"] == {
        "kind": "reference",
        "label": PROJECT_NAME,
        "labelBasis": "current",
        "rawValue": 291,
        "resolved": True,
        "target": {"type": "business_object", "id": 291, "entityId": domain.project.entity_id},
    }
    assert display["page"] == {
        "kind": "source",
        "label": "https://example.org/291",
        "labelBasis": "current",
        "rawValue": 291,
        "resolved": True,
        "target": {"type": "source", "id": 291},
    }
    assert display["projects"]["items"] == [display["project_id"]]
    assert [item["label"] for item in display["sources"]["items"]] == [
        "https://example.org/291",
        "Programme.pdf",
    ]
    assert display["tags"]["items"] == []
    assert display["tags"]["itemKind"] == "string"
    assert display["large_number"] == {
        "kind": "biginteger",
        "rawValue": values["large_number"],
        "label": "9223372036854775807",
    }
    for key, kind in {
        "name": "string",
        "count": "integer",
        "amount": "decimal",
        "approved": "boolean",
        "deadline": "date",
        "checked": "datetime",
        "payload": "json",
    }.items():
        assert display[key] == {"kind": kind, "rawValue": values[key]}

    explicit_null = await domain.make(project_id=None)
    assert (await present(domain, explicit_null, "project_id"))["project_id"] == {
        "kind": "reference",
        "rawValue": None,
    }


async def test_reference_fallback_and_declared_display_field(domain):
    project = await make_project(domain, name="Preferred name", public_title="Published title")
    unnamed = await make_project(domain, public_title="Non-display text")
    obj = await domain.make(project_id=project.object_id, payload={"key": 291})
    assert (await present(domain, obj, "project_id"))["project_id"]["label"] == "Preferred name"
    no_name = await domain.make(project_id=unnamed.object_id)
    display = (await present(domain, no_name, "project_id"))["project_id"]
    assert display["resolved"] and display["label"] == f"BusinessObject #{unnamed.object_id}"

    async with domain.factory.begin() as session:
        await session.execute(
            update(BusinessEntityVersion)
            .where(BusinessEntityVersion.business_entity_id == domain.project.entity_id)
            .values(definition_json={"display_field": "public_title"})
        )
    assert (await present(domain, obj, "project_id"))["project_id"]["label"] == "Published title"

    value_id = domain.slot(obj, "project_id").value_id
    for bad_target in (obj.id, 99_999, True):
        # Simulate a legacy record that predates reference validation.
        async with domain.factory.begin() as session:
            await session.execute(
                update(BusinessObjectFieldValue)
                .where(BusinessObjectFieldValue.id == value_id)
                .values(value_json=bad_target)
            )
        display = (await present(domain, obj, "project_id"))["project_id"]
        assert display["rawValue"] == bad_target and not display["resolved"]
        assert display["label"] == (
            "Invalid BusinessObject ID" if bad_target is True else f"BusinessObject #{bad_target}"
        )
        assert "entityId" not in display.get("target", {})

    version_id = domain.slot(obj, "payload").validated_against_field_version_id
    async with domain.factory.begin() as session:
        await session.execute(
            update(BusinessEntityFieldVersion)
            .where(BusinessEntityFieldVersion.id == version_id)
            .values(definition_json={"type": "unrecognized"})
        )
    assert (await present(domain, obj, "payload"))["payload"] == {
        "kind": "unknown",
        "rawValue": {"key": 291},
    }


async def test_field_presentations_use_constant_queries_for_many_references(database, domain):
    engine, _, _ = database
    pairs = []
    for i in range(16):
        project = await make_project(domain, name=f"Project {i}")
        obj = await domain.make(project_id=project.object_id, projects=[project.object_id])
        pairs.extend(
            (domain.fields[key], domain.slot(obj, key).object_field_id)
            for key in ("project_id", "projects")
        )

    async def read_batch(batch):
        statements = []

        def track(_connection, _cursor, statement, *_args):
            statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", track)
        try:
            async with domain.factory() as session:
                response = await field_presentations(session, batch)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", track)
        assert len(response) == len(batch)
        assert response[batch[-2]]["canonicalDisplay"]["resolved"]
        return len(statements)

    assert await read_batch(pairs[:2]) == await read_batch(pairs)


async def test_task_and_source_review_share_presentation_for_recorded_evidence(
    domain, client, minio
):
    monitored = await source(domain, client)
    project = await make_project(domain, name="Name at capture")
    application = await domain.make(name="Application A", project_id=project.object_id)
    slot = domain.slot(application, "project_id")
    definition = tree(recipe(part(css("#project"))))
    imported = await client.post(
        "/extraction/selectors/import",
        json={
            "tree": definition,
            "binding": {
                "sourceId": monitored.id,
                "businessEntityFieldId": slot.business_entity_field_id,
                "businessObjectFieldId": slot.object_field_id,
            },
        },
    )
    assert imported.status_code == 200, imported.text
    headers, _ = await agent(client, monitored.id)
    observation = "Podmiotowy System Finansowania"
    first = await monitor(
        client, domain, headers, monitored.id, f'<p id="project">{observation}</p>'.encode()
    )
    task_id = first["fields"][0]["taskId"]
    before = await review(client, task_id)
    assert before["canonicalDisplay"]["label"] == "Name at capture"

    project_name = next(field for field in domain.project.fields if field.key == "name")
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            project.object_id,
            {project.object_fields[project_name.field_id]: PROJECT_NAME},
        )
    )
    await monitor(client, domain, headers, monitored.id, b'<p id="project">Different evidence</p>')
    now = await review(client, task_id)
    assert now["canonicalValue"] == before["canonicalValue"] == project.object_id
    assert now["canonicalValueId"] == before["canonicalValueId"] == slot.value_id
    assert now["currentEvidence"] == before["currentEvidence"] == observation
    assert now["previousEvidence"] is None
    assert now["canonicalDisplay"]["label"] == PROJECT_NAME
    assert now["canonicalDisplay"]["labelBasis"] == "current"
    assert "match" not in now["canonicalDisplay"]
    assert now["businessField"]["name"] == "Projekt"
    assert now["businessField"]["referenceEntity"]["name"] == "Project"
    assert now["selector"] == before["selector"]
    assert now["evaluation"] == before["evaluation"]
    assert now["evaluation"]["result"]["status"] == "success"

    path = f"/monitoring/sources/{monitored.id}/review"
    response = await client.get(path, params={"checkId": first["jobId"]}, headers=OPERATOR)
    assert response.status_code == 200, response.text
    historic = response.json()
    assert historic["selectedCheck"]["id"] != historic["latestCheck"]["id"]
    field = historic["fields"][0]
    for key in ("canonicalDisplay", "businessField", "businessObject", "currentEvidence"):
        assert field[key] == now[key]

    async with domain.factory() as session:
        task = await TasksService(session).get_task(task_id)
        persisted = await session.scalar(
            select(BusinessObjectFieldValue).where(BusinessObjectFieldValue.id == slot.value_id)
        )
        assert persisted.value_json == project.object_id
    refs = {
        ref.reference_type: now["referenceDisplays"][str(ref.id)]
        for ref in task.references
        if str(ref.id) in now["referenceDisplays"]
    }
    assert refs["source"]["label"] == monitored.url
    assert refs["source_snapshot"]["capturedAt"] == now["snapshot"]["fetched_at"]
    assert refs["extraction_run"]["status"] == "succeeded"
    assert refs["observation"]["label"] == observation
    assert refs["business_field"]["label"] == "Projekt"
    assert refs["business_object_field"]["label"] == "Projekt · Application A"
    assert (await client.get(f"/monitoring/reviews/{task_id}")).status_code == 401
