"""Selector REST lifecycle and pinned evidence on PostgreSQL migrations."""

import asyncio
import os
from copy import deepcopy
from hashlib import sha256
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_collections_postgres import migrate
from test_selector_tree import PAGE, css, part, recipe, tree, uuid

from business_layer.schemas.models import BusinessObject, BusinessObjectFieldValue
from extraction.schemas.models import ConcreteValue, FieldObservation
from extraction.schemas.selector import Selector, SelectorEvaluation, SelectorVersion
from extraction.schemas.selector_tree import SelectorTree
from extraction.services.selectors import SelectorService
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import Source, SourceSnapshot, StoredFile

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def selector_api(domain, monkeypatch):
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    from extraction.api.routes import capture_router
    from shared.database import get_session

    app = FastAPI()
    app.include_router(capture_router)

    async def sessions():
        async with domain.factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app


async def source(domain, url=PAGE):
    async with domain.factory() as session, session.begin():
        row = Source(type=SourceType.HTML, url=url, state=SourceState.ACTIVE)
        session.add(row)
    return row.id


async def snapshot(domain, source_id, html):
    async with domain.factory() as session, session.begin():
        row = SourceSnapshot(
            source_id=source_id,
            page_url=PAGE,
            mime_type="text/html",
            content_hash=sha256(html.encode()).hexdigest(),
        )
        session.add(row)
    return row.id


async def run(client, snapshot_id):
    response = await client.post(
        "/extraction/runs",
        json={"snapshot_id": snapshot_id, "extractor_version": "tree-test"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def binding(domain, source_id, slot=None):
    result = {"businessEntityFieldId": domain.fields["name"], "sourceId": source_id}
    if slot:
        result["businessObjectFieldId"] = slot.object_field_id
    return result


async def import_tree(client, definition, resolved, **extra):
    body = {"tree": definition, "binding": resolved, **extra}
    response = await client.post("/extraction/selectors/import", json=body)
    assert response.status_code == 200, response.text
    assert response.json() == definition
    return f"/extraction/selectors/{definition['selector']['uuid']}", response.headers["etag"]


async def test_export_import_preserves_nested_uuids_order_and_explicit_snapshot_binding(
    domain, selector_api
):
    client, _ = selector_api
    source_id = await source(domain)
    snapshot_id = await snapshot(domain, source_id, "<p>snapshot</p>")
    external = uuid()
    definition = tree(
        recipe(part(css("#year"), css(".year", 1)), part(css("#quarter"), order=1, joinWith=" ")),
        recipe(part(css("#full")), order=1),
    )
    definition["selector"]["sourceUuid"] = uuid()
    definition["versions"][0]["createdFromSnapshotUuid"] = external
    path, token = await import_tree(
        client,
        definition,
        binding(domain, source_id),
        snapshotBindings={external: snapshot_id},
    )
    exported = await client.get(path + "/export")
    assert exported.json() == definition
    replayed = await client.post("/extraction/selectors/import", json={"tree": exported.json()})
    assert replayed.status_code == 200 and replayed.headers["etag"] == token
    version_uuid = definition["versions"][0]["uuid"]
    assert (await client.get(path + f"/versions/{version_uuid}")).json() == definition["versions"][
        0
    ]
    assert (await client.get(path + "/versions")).json() == definition["versions"]
    assert await domain.count(BusinessObject) == 0
    async with domain.factory() as session:
        stored = await session.scalar(
            select(SelectorVersion).where(SelectorVersion.uuid == UUID(version_uuid))
        )
        assert stored.created_from_snapshot_id == snapshot_id
        assert stored.metadata_json["createdFromSnapshotUuid"] == external
    page = await client.get("/extraction/selectors", params={"limit": 1, "source_id": source_id})
    assert page.json()["items"] == [definition["selector"]]
    assert (await client.get("/extraction/selectors/" + uuid())).status_code == 404


async def test_draft_save_review_and_immutable_history(domain, selector_api):
    client, _ = selector_api
    source_id = await source(domain)
    initial = tree(status="draft")
    response = await client.post(
        "/extraction/selectors", json={"tree": initial, "binding": binding(domain, source_id)}
    )
    assert response.status_code == 201, response.text
    path = f"/extraction/selectors/{initial['selector']['uuid']}"
    original = initial["versions"][0]
    draft_path = path + f"/drafts/{original['uuid']}"
    changed = deepcopy(original)
    changed["recipes"][0]["parts"][0]["locators"][0]["selector"] = "#new"
    tag = {"If-Match": response.headers["etag"]}
    saved = await client.put(draft_path, json=changed, headers=tag)
    assert saved.status_code == 200, saved.text
    assert (await client.put(draft_path, json=changed, headers=tag)).status_code == 409
    approved = await client.post(
        draft_path + "/approve",
        headers={"If-Match": saved.headers["etag"]},
        json={"reviewedBy": "operator"},
    )
    assert approved.status_code == 200, approved.text
    approved_tree = approved.json()
    assert approved_tree["versions"][0]["reviewedBy"] == "operator"
    tag = {"If-Match": approved.headers["etag"]}
    assert (await client.put(draft_path, json=changed, headers=tag)).status_code == 409
    second = await client.post(path + "/drafts", headers=tag)
    assert second.status_code == 200, second.text
    versions = second.json()["versions"]
    assert versions[1]["status"] == "draft" and versions[1]["versionNo"] == 2
    for old, new in zip(versions, versions[1:], strict=False):
        assert old["uuid"] != new["uuid"]
        a, b = old["recipes"][0], new["recipes"][0]
        assert a["uuid"] != b["uuid"] and a["parts"][0]["uuid"] != b["parts"][0]["uuid"]
        assert a["parts"][0]["locators"][0]["uuid"] != b["parts"][0]["locators"][0]["uuid"]
    tag = {"If-Match": second.headers["etag"]}
    deleted = deepcopy(second.json())
    deleted["versions"] = deleted["versions"][1:]
    deleted["selector"]["activeVersionUuid"] = None
    assert (
        await client.post("/extraction/selectors/import", json={"tree": deleted}, headers=tag)
    ).status_code == 409
    rejected = await client.post(path + f"/drafts/{versions[1]['uuid']}/reject", headers=tag)
    assert rejected.json()["versions"][1]["status"] == "rejected"
    assert rejected.json()["selector"]["activeVersionUuid"] == original["uuid"]
    assert (
        await client.post(
            path + f"/drafts/{versions[1]['uuid']}/approve",
            headers={"If-Match": rejected.headers["etag"]},
        )
    ).status_code == 409


async def test_concurrent_approval_serializes_and_database_preserves_approved_content(
    domain, selector_api
):
    client, _ = selector_api
    definition = tree()
    path, token = await import_tree(client, definition, binding(domain, await source(domain)))
    first = await client.post(path + "/drafts", headers={"If-Match": token})
    second = await client.post(path + "/drafts", headers={"If-Match": first.headers["etag"]})
    drafts = second.json()["versions"][1:]
    results = await asyncio.gather(
        *[
            client.post(
                path + f"/drafts/{item['uuid']}/approve",
                headers={"If-Match": second.headers["etag"]},
            )
            for item in drafts
        ]
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    current = (await client.get(path)).json()
    assert sorted(version["status"] for version in current["versions"]) == [
        "active",
        "draft",
        "superseded",
    ]
    original_locator = definition["versions"][0]["recipes"][0]["parts"][0]["locators"][0]["uuid"]
    async with domain.factory() as session:
        with pytest.raises(IntegrityError, match="immutable"):
            await session.execute(
                text("UPDATE selector_locators SET position=5 WHERE uuid=:uuid"),
                {"uuid": UUID(original_locator)},
            )
        await session.rollback()
        # SQL writes themselves cannot nominate a draft as the active version.
        with pytest.raises(IntegrityError, match="active pointer"):
            async with session.begin():
                await session.execute(
                    text("""
                    UPDATE selectors AS s SET active_version_id = v.id
                    FROM selector_versions AS v WHERE s.id=v.selector_id AND v.status='draft'
                """)
                )
    assert (await client.get(path)).json() == current


async def test_backend_evaluation_uses_snapshot_bytes_and_pins_capture_to_version(
    domain, selector_api
):
    client, _ = selector_api
    source_id = await source(domain)
    obj = await domain.make(name="Project")
    slot = domain.slot(obj, "name")
    definition = tree(recipe(part(css("#funding"), css(".missing", 1))))
    path, token = await import_tree(client, definition, binding(domain, source_id, slot))
    await client.post("/extraction/token-classes", json={"id": "text", "name": "Text"})
    html = '<p id="funding">IV kwartał 😀</p>'
    snapshot_id = await snapshot(domain, source_id, html)
    run_id = await run(client, snapshot_id)
    params = {"runId": run_id, "captureKey": "first", "sourceSnapshotId": snapshot_id}
    assert (await client.post(path + "/evaluate", json=params)).status_code == 501
    wrong = await client.post(path + "/evaluate", json={**params, "html": "<p>wrong</p>"})
    assert wrong.status_code == 422
    canonical_count = await domain.count(BusinessObjectFieldValue)
    executed = await client.post(path + "/evaluate", json={**params, "html": html})
    assert executed.status_code == 200, executed.text
    result = executed.json()
    evaluation = result["evaluation"]
    assert evaluation["provenance"] == "backend_verified"
    assert evaluation["sourceSnapshotId"] == snapshot_id
    assert evaluation["result"]["rawValue"] == "IV kwartał 😀"
    assert (
        evaluation["result"]["recipeResults"][0]["partResults"][0]["locatorResults"][1]["status"]
        == "not_found"
    )
    observed = result["capture"]["observation_ids_by_client_key"]["selector-value"]
    detail = (await client.get(f"/extraction/observations/{observed}")).json()
    assert detail["business_object_field_id"] == slot.object_field_id
    assert detail["concrete_values"][0]["raw_value"] == "IV kwartał 😀"
    assert detail["concrete_values"][0]["normalized_value"] is None
    assert (await client.get(f"/extraction/runs/{run_id}/capture")).json() == result["capture"]
    as_report = {
        "pageUrl": PAGE,
        "result": evaluation["result"],
        "sourceSnapshotId": snapshot_id,
        "uuid": uuid(),
    }
    assert (
        await client.post(
            path + "/evaluations", json={**as_report, "provenance": "backend_verified"}
        )
    ).status_code == 422
    reported = await client.post(path + "/evaluations", json=as_report)
    assert reported.status_code == 201 and reported.json()["provenance"] == "client_reported"
    incomplete = deepcopy(as_report)
    incomplete["result"]["recipeResults"][0]["partResults"][0]["locatorResults"].pop()
    assert (await client.post(path + "/evaluations", json=incomplete)).status_code == 422
    assert await domain.count(FieldObservation) == 1
    draft = await client.post(path + "/drafts", headers={"If-Match": token})
    draft_uuid = draft.json()["versions"][1]["uuid"]
    approved = await client.post(
        path + f"/drafts/{draft_uuid}/approve",
        headers={"If-Match": draft.headers["etag"]},
    )
    assert approved.json()["versions"][0]["status"] == "superseded"
    # Replaying the first run still returns the original evaluation and exact receipt.
    assert (await client.post(path + "/evaluate", json=params)).json() == result
    html2 = '<p id="funding">III kwartał</p>'
    second_snapshot = await snapshot(domain, source_id, html2)
    second_run = await run(client, second_snapshot)
    later = await client.post(
        path + "/evaluate",
        json={"runId": second_run, "captureKey": "later", "html": html2},
    )
    assert later.status_code == 200, later.text
    assert later.json()["evaluation"]["result"]["selectorVersionUuid"] == draft_uuid
    assert later.json()["evaluation"]["result"]["rawValue"] == "III kwartał"
    async with domain.factory() as session:
        old = await session.get(FieldObservation, observed)
        eval_row = await session.get(SelectorEvaluation, old.selector_evaluation_id)
        version = await session.get(SelectorVersion, old.selector_version_id)
        assert eval_row.selector_version_id == version.id
        assert str(version.uuid) == definition["versions"][0]["uuid"]
        assert eval_row.source_snapshot_id == snapshot_id
    page = await client.get(path + "/evaluations", params={"limit": 1, "offset": 1})
    assert page.json()["total"] == 3 and len(page.json()["items"]) == 1
    assert await domain.count(ConcreteValue) == 2
    assert await domain.count(BusinessObjectFieldValue) == canonical_count


async def test_failed_evaluation_persists_diagnostics_without_evidence_or_review(
    domain, selector_api
):
    client, _ = selector_api
    source_id = await source(domain)
    definition = tree(recipe(part(css(".ambiguous"))))
    path, token = await import_tree(client, definition, binding(domain, source_id))
    html = '<p class="ambiguous">1</p><p class="ambiguous">2</p>'
    run_id = await run(client, await snapshot(domain, source_id, html))
    params = {"runId": run_id, "captureKey": "ambiguous", "html": html}
    failed = await client.post(path + "/evaluate", json=params)
    assert failed.status_code == 200, failed.text
    assert failed.json()["capture"] is None
    assert failed.json()["evaluation"]["result"]["status"] == "ambiguous"
    assert (await client.get(f"/extraction/runs/{run_id}")).json()["status"] == "failed"
    assert (await client.post(path + "/evaluate", json=params)).json() == failed.json()
    read = await client.get(path)
    assert read.headers["etag"] == token and read.json() == definition
    assert await domain.count(FieldObservation) == 0
    assert await domain.count(ConcreteValue) == 0
    assert await domain.count(BusinessObject) == 0


async def test_registered_file_reader_preserves_literal_and_unresolved_target(domain, selector_api):
    client, app = selector_api
    source_id = await source(domain)
    local_match = await domain.make(name="Existing")
    definition = tree(
        recipe(part(css("#funding"), extraction={"type": "attribute", "name": "title"}))
    )
    definition["selector"]["target"]["objectId"] = str(local_match.id)
    path, _ = await import_tree(client, definition, binding(domain, source_id))
    token = await client.post("/extraction/token-classes", json={"id": "text", "name": "Text"})
    assert token.status_code == 201
    content = b'<p id="funding" title="  ">Whitespace</p>'
    async with domain.factory() as session, session.begin():
        file = StoredFile(
            storage_key="snapshot-artifact",
            mime_type="text/html",
            sha256=sha256(content).hexdigest(),
        )
        session.add(file)
        await session.flush()
        stored = SourceSnapshot(source_id=source_id, page_url=PAGE, file_id=file.id)
        session.add(stored)
    run_id = await run(client, stored.id)
    requested = []

    async def reader(snapshot, artifact):
        requested.append((snapshot.id, artifact.id))
        return content

    app.state.selector_snapshot_reader = reader
    result = await client.post(
        path + "/evaluate", json={"runId": run_id, "captureKey": "stored-file"}
    )
    assert result.status_code == 200, result.text
    assert requested == [(stored.id, file.id)]
    [observation] = result.json()["capture"]["unresolved_observations"]
    detail = (await client.get(f"/extraction/observations/{observation}")).json()
    assert detail["business_object_id"] is None
    assert detail["concrete_values"][0]["raw_value"] == "  "
    assert await domain.count(BusinessObject) == 1


@pytest.mark.parametrize("database", ["b203_value_field_owner"], indirect=True)
async def test_existing_legacy_rule_history_is_mapped_once_without_guessing_review(
    domain, database
):
    engine, _, schema = database
    source_id = await source(domain)
    async with engine.begin() as conn:
        tracker = await conn.scalar(
            text("""
            INSERT INTO source_field_trackings(source_id,business_entity_field_id)
            VALUES(:s,:f) RETURNING id
        """),
            {"s": source_id, "f": domain.fields["name"]},
        )
        scope = await conn.scalar(
            text("""
            INSERT INTO source_scopes(source_id,name,selector_type,selector_string,
              confidence_score,discovered_by,version,valid_from)
            VALUES(:s,'ROOT','CSS','body',1,'MANUAL',1,'2026-01-01Z') RETURNING id
        """),
            {"s": source_id},
        )
        await conn.execute(
            text("""
            INSERT INTO field_selectors(scope_id,source_field_tracking_id,selector_type,
                selector_string,extraction_json,confidence_score,discovered_by,version,
                valid_from,valid_to)
            VALUES(:p,:t,'CSS','#old','{"type": "text"}',1,'MANUAL',1,'2026-01-01Z','2026-01-02Z'),
                  (:p,:t,'XPATH','//p','{"type": "text"}',1,'MANUAL',2,'2026-01-02Z',NULL)
        """),
            {"p": scope, "t": tracker},
        )
        await conn.run_sync(lambda c: migrate(c, schema, "head"))
        mapping = (
            await conn.execute(
                text("""
            SELECT id,selector_version_id FROM field_selectors ORDER BY id
        """)
            )
        ).all()
        assert len(mapping) == 2 and all(row.selector_version_id for row in mapping)
        await conn.execute(text("SELECT map_legacy_field_selector(id) FROM field_selectors"))
        assert await conn.scalar(text("SELECT count(*) FROM selector_versions")) == 2
    async with domain.factory() as session:
        row = await session.scalar(select(Selector).where(Selector.source_id == source_id))
        service = SelectorService(session)
        graph, _ = await service.tree(row)
        assert graph.selector.migration.provenance == "unverified"
        assert graph.selector.active_version_uuid is None
        assert [version.status for version in graph.versions] == ["superseded", "draft"]
        assert all(version.created_from_snapshot_uuid is None for version in graph.versions)
        assert SelectorTree.model_validate(graph.portable()) == graph
        portable = graph.portable()
        portable["selector"].pop("migration")
        imported, token = await service.import_tree(SelectorTree.model_validate(portable))
        assert imported == graph and token == row.revision
    assert await domain.count(FieldObservation) == 0
