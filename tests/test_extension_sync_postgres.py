"""Exercise workspace-scoped identity, approved writes and capture on PostgreSQL."""

import asyncio
import os
from copy import deepcopy
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from test_collections_postgres import database as database
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import BusinessModel, BusinessObject, BusinessObjectFieldValue
from business_layer.services.data import DataService
from business_layer.services.entities import EntitiesService
from extension_sync.identity import provision
from extension_sync.models import ExternalObjectBinding
from extension_sync.schema import DEFINITIONS, bootstrap
from extraction.schemas.models import FieldObservation
from extraction.schemas.selector_tree import SelectorVersionDefinition
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from sources.schemas.models import Source, SourceSnapshot

pytestmark = pytest.mark.asyncio
PREFIX = "/api/v1/extension-sync"
PAGE = "https://example.org/project"


@pytest_asyncio.fixture
async def workspace(database, monkeypatch):
    _, factory, _ = database
    namespace, other = uuid4(), uuid4()
    async with factory.begin() as session:
        preview = await bootstrap(session)
        assert preview["changes"] and preview["businessModelId"] is None
        assert await session.scalar(select(func.count()).select_from(BusinessModel)) == 0
        initialized = await bootstrap(session, apply=True)
        again = await bootstrap(session, apply=True)
        assert initialized["revisionId"] == again["revisionId"] and again["changes"] == []
        source = Source(type="HTML", url=PAGE, state="ACTIVE")
        session.add(source)
        await session.flush()
        snapshot = SourceSnapshot(source_id=source.id, page_url=PAGE, mime_type="text/html")
        session.add(snapshot)
        await session.flush()
        token = await provision(
            session,
            namespace,
            can_create=True,
            can_bind_existing=True,
            can_commit=True,
            source_ids=[source.id],
        )
        readonly = await provision(
            session,
            other,
            can_create=False,
            can_bind_existing=False,
            can_commit=False,
            source_ids=[],
        )

    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    from extension_sync.api import router
    from shared.database import get_session

    app = FastAPI()
    app.include_router(router)

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fixture") as client:
        yield client, factory, str(namespace), str(other), token, readonly, source.id, snapshot.id


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def identity(key="PR_DOL_004", kind="project", target=None):
    row = {"localObjectId": key, "localType": kind}
    if target:
        row["target"] = target
    return row


async def registry(workspace):
    client, _, _, _, token, _, _, _ = workspace
    response = await client.get(PREFIX + "/schema", headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


async def resolve(workspace, target=None, *, status=200, **options):
    client, _, namespace, _, token, _, _, _ = workspace
    response = await client.post(
        PREFIX + "/objects/resolve",
        headers=auth(token),
        json={
            "workspaceUuid": namespace,
            "identity": target or identity(),
            **options,
        },
    )
    assert response.status_code == status, response.text
    return response.json()


def entity(schema, kind):
    return next(item for item in schema["entities"] if item["localType"] == kind)


def field(entry, key):
    return next(f for f in entry["fields"] if f["persistentKey"] == key)


async def test_bootstrap_registry_current_versions_and_verified_type_mappings(workspace):
    schema = await registry(workspace)
    assert {row["localType"] for row in schema["entities"]} == DEFINITIONS.keys()
    for row in schema["entities"]:
        assert len(row["fields"]) == len(DEFINITIONS[row["localType"]]["fields"])
    assert schema["aliases"]["nabor"]["fields"]["title"] == "external_number"
    project = entity(schema, "project")
    status = field(project, "status")
    assert status["aliases"]["CLOSED"] == "ZAKONCZONY"
    assert status["definition"]["enum_values"] == [
        "PLANOWANY",
        "AKTYWNY",
        "ZAWIESZONY",
        "ZAKONCZONY",
    ]
    assert field(entity(schema, "funding"), "max_amount_pln")["definition"]["scale"] == 2
    assert field(entity(schema, "recruitment"), "godzinaRozpoczecia")["definition"]["pattern"]
    _, factory, *_ = workspace
    async with factory.begin() as session:
        service = EntitiesService(session)
        model_id = int(schema["businessModelId"])
        desired = await service.get_schema(model_id)
        definition = next(row for row in desired.entities if row.name == "Project")
        next(
            f for f in definition.fields if f.persistent_key == "status"
        ).label = "Zmieniona etykieta"
        changes = await service.register(model_id, "label update", None, desired)
        assert changes.changed
    latest = await registry(workspace)
    updated = field(entity(latest, "project"), "status")
    assert updated["businessEntityFieldId"] == status["businessEntityFieldId"]
    assert updated["fieldVersionId"] != status["fieldVersionId"]


async def test_identity_resolve_concurrency_scope_and_exact_bigint(workspace):
    client, factory, namespace, other, token, read, _, _ = workspace
    assert (await client.get(PREFIX + "/schema")).status_code == 401
    bad = await client.post(
        PREFIX + "/objects/resolve",
        headers=auth(token),
        json={
            "workspaceUuid": other,
            "identity": identity(),
        },
    )
    assert bad.status_code == 403
    refused = await client.post(
        PREFIX + "/objects/resolve",
        headers=auth(read),
        json={
            "workspaceUuid": other,
            "identity": identity(),
            "action": "create",
        },
    )
    assert refused.status_code == 403
    assert (await resolve(workspace))["status"] == "LOCAL_ONLY"
    async with factory.begin() as session:
        await session.execute(
            text("SELECT setval(pg_get_serial_sequence('business_objects','id'), 9007199254740994)")
        )
    left, right = await asyncio.gather(
        resolve(workspace, action="create"),
        resolve(workspace, action="create"),
    )
    assert left == right and left["businessObjectId"] == "9007199254740995"
    assert left["objectFields"]["status"]["valueId"] is None
    assert left["identity"]["localObjectId"] == "PR_DOL_004"
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(BusinessObject)) == 1
        assert await session.scalar(select(func.count()).select_from(ExternalObjectBinding)) == 1
    legacy = identity("legacy-1", "nabor")
    assert (await resolve(workspace, legacy))["reason"] == "EXPLICIT_LEGACY_MATCH_REQUIRED"
    wrong = await resolve(
        workspace,
        legacy,
        action="bind",
        existingBusinessObjectId=left["businessObjectId"],
        status=409,
    )
    assert wrong["detail"]["code"] == "EXISTING_OBJECT_TYPE_OR_MODEL_CONFLICT"

    schema = await registry(workspace)
    async with factory.begin() as session:
        existing = await DataService(session).create_object(
            int(entity(schema, "recruitment")["businessEntityId"])
        )
    adopted = await resolve(
        workspace, legacy, action="bind", existingBusinessObjectId=str(existing.object_id)
    )
    assert adopted["businessEntityId"] == entity(schema, "recruitment")["businessEntityId"]
    assert adopted["objectFields"]["external_number"]["businessObjectFieldId"]
    duplicate = await resolve(
        workspace,
        identity("another-legacy", "nabor"),
        action="bind",
        existingBusinessObjectId=str(existing.object_id),
        status=409,
    )
    assert duplicate["detail"]["code"] == "OBJECT_ALREADY_BOUND"


def commit_payload(namespace, schema, bound, key, value):
    slot = bound["objectFields"][key]
    patch = {
        "persistentKey": key,
        "businessObjectFieldId": slot["businessObjectFieldId"],
        "fieldVersionId": slot["fieldVersionId"],
        "expectedValueId": slot["valueId"],
        "value": value,
    }
    if slot["collectionRevision"] is not None or key == "source_file_source_ids":
        patch["expectedCollectionRevision"] = slot["collectionRevision"] or 0
    return {
        "workspaceUuid": namespace,
        "operationId": str(uuid4()),
        "schemaRevisionId": schema["revisionId"],
        "changes": [
            {
                "identity": bound["identity"],
                "businessObjectId": bound["businessObjectId"],
                "fields": [patch],
            }
        ],
    }


async def test_commit_replay_history_and_conflict(workspace):
    client, factory, namespace, _, token, _, _, _ = workspace
    schema = await registry(workspace)
    bound = await resolve(workspace, action="create")
    body = commit_payload(namespace, schema, bound, "status", "AKTYWNY")

    async def send(data, expected=200):
        result = await client.post(PREFIX + "/commits", headers=auth(token), json=data)
        assert result.status_code == expected, result.text
        return result.json()

    first = await send(body)
    assert first == await send(body)
    first_slot = first["objects"][0]["objectFields"]["status"]
    assert first_slot["value"] == "AKTYWNY"
    late = commit_payload(namespace, schema, bound, "status", "PLANOWANY")
    conflict = await send(late, 409)
    assert conflict["detail"]["code"] == "CANONICAL_VALUE_CHANGED"
    assert conflict["detail"]["object"]["objectFields"]["status"]["value"] == "AKTYWNY"
    second = await send(
        commit_payload(namespace, schema, first["objects"][0], "status", "ZAKONCZONY")
    )
    assert second["objects"][0]["objectFields"]["status"]["value"] == "ZAKONCZONY"
    async with factory() as session:
        history = list(
            await session.scalars(
                select(BusinessObjectFieldValue).where(
                    BusinessObjectFieldValue.business_object_field_id
                    == int(first_slot["businessObjectFieldId"]),
                )
            )
        )
        assert {value.value_json for value in history} == {"AKTYWNY", "ZAKONCZONY"}
        assert all(
            str(value.validated_against_field_version_id) == first_slot["fieldVersionId"]
            for value in history
        )


async def test_bound_selector_and_reported_capture_use_existing_evidence(workspace):
    client, factory, namespace, _, token, _, source, snapshot = workspace
    bound = await resolve(workspace, action="create")
    original = tree(recipe(part(css("title"))))
    original["selector"]["target"] = {"objectId": "PR_DOL_004", "field": "name"}
    original["selector"]["pageUrl"] = PAGE
    payload = {
        "workspaceUuid": namespace,
        "identity": identity(),
        "sourceId": str(source),
        "tree": original,
    }
    refused = await client.post(PREFIX + "/selectors", headers=auth(token), json=payload)
    assert refused.status_code == 409
    selector = await client.post(
        PREFIX + "/selectors",
        headers=auth(token),
        json={
            **payload,
            "publishReviewed": True,
        },
    )
    assert selector.status_code == 200, selector.text
    assert (
        selector.json()["field"]["businessObjectFieldId"]
        == bound["objectFields"]["name"]["businessObjectFieldId"]
    )
    assert selector.json()["selectorUuid"] == original["selector"]["uuid"]
    version = SelectorVersionDefinition.model_validate(original["versions"][0])
    result = evaluate_selector_version(version, HtmlSelectorRuntime("<title>Example</title>", PAGE))
    report = {
        "workspaceUuid": namespace,
        "operationId": str(uuid4()),
        "identity": identity(),
        "selectorUuid": original["selector"]["uuid"],
        "sourceSnapshotId": str(snapshot),
        "pageUrl": PAGE,
        "result": result.portable(),
    }
    response = await client.post(PREFIX + "/captures", headers=auth(token), json=report)
    assert response.status_code == 200, response.text
    replay = await client.post(PREFIX + "/captures", headers=auth(token), json=deepcopy(report))
    assert replay.json() == response.json()
    observation_id = int(response.json()["observationIds"][0])
    async with factory() as session:
        obs = await session.get(FieldObservation, observation_id)
        assert obs.status == "DETECTED"
        assert (
            str(obs.business_object_field_id) == selector.json()["field"]["businessObjectFieldId"]
        )
        assert await session.scalar(select(func.count()).select_from(FieldObservation)) == 1
    assert (await resolve(workspace))["objectFields"]["name"]["valueId"] is None


async def test_nested_identity_ownership_and_ordered_file_references(workspace):
    client, _, namespace, _, token, _, _, _ = workspace
    schema = await registry(workspace)
    await resolve(workspace, action="create")
    wrong_parent = await resolve(workspace, identity("another-project"), action="create")
    doc = await resolve(
        workspace,
        identity(target={"kind": "document", "id": "doc-1"}),
        action="create",
    )
    files = [
        await resolve(
            workspace,
            identity(target={"kind": "file_source", "id": f"file-{number}"}),
            action="create",
        )
        for number in (1, 2)
    ]
    invalid = commit_payload(
        namespace, schema, doc, "project_owner", wrong_parent["businessObjectId"]
    )
    rejected = await client.post(PREFIX + "/commits", headers=auth(token), json=invalid)
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "NESTED_OWNER_CONFLICT"

    expected = [row["businessObjectId"] for row in files]
    body = commit_payload(namespace, schema, doc, "source_file_source_ids", expected)
    accepted = await client.post(PREFIX + "/commits", headers=auth(token), json=body)
    assert accepted.status_code == 200, accepted.text
    slot = accepted.json()["objects"][0]["objectFields"]["source_file_source_ids"]
    assert slot["value"] == expected
    assert slot["collectionRevision"] > 0
    stale = commit_payload(namespace, schema, doc, "source_file_source_ids", expected[::-1])
    denied = await client.post(PREFIX + "/commits", headers=auth(token), json=stale)
    assert denied.status_code == 409
