"""Exercise the read models against real captured evidence, PostgreSQL, and MinIO."""

from uuid import UUID

import pytest
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_monitoring_postgres import OPERATOR, add_tree, agent, enqueue, monitor, source
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_selector_tree import css, part, recipe, tree

from extraction.schemas.common import utc_now
from monitoring.models import MonitoringJob, SourceCheckRun
from monitoring.queue import MonitoringQueue
from tasks.api.dto import TaskStatusChangeRequest
from tasks.schemas.models import Task, Workflow, WorkflowStatus
from tasks.services.task import TasksService

pytestmark = pytest.mark.asyncio
ATTENTION = "/monitoring/attention/sources"


async def read(client, path, **params):
    response = await client.get(path, params=params, headers=OPERATOR)
    assert response.status_code == 200, response.text
    return response.json()


async def change_locator(client, selector, etag, css_selector):
    path = f"/extraction/selectors/{selector}/drafts"
    draft = await client.post(path, headers={"If-Match": etag})
    assert draft.status_code == 200, draft.text
    version = draft.json()["versions"][-1]
    version["recipes"][0]["parts"][0]["locators"][0]["selector"] = css_selector
    path += "/" + version["uuid"]
    saved = await client.put(path, json=version, headers={"If-Match": draft.headers["etag"]})
    assert saved.status_code == 200, saved.text
    approved = await client.post(path + "/approve", headers={"If-Match": saved.headers["etag"]})
    assert approved.status_code == 200, approved.text
    return version["uuid"]


async def test_workspace_groups_tasks_and_reads_the_selected_capture(domain, client, minio):
    row = await source(domain, client)
    other = await source(domain, client)
    obj = await domain.make(name="Original")
    slot = domain.slot(obj, "name")
    definition = tree(recipe(part(css("#first"), css("#same-as-first", order=1))))
    uuid = definition["selector"]["uuid"]
    etag = await add_tree(client, domain, row.id, slot, definition)
    headers, _ = await agent(client, row.id, other.id)
    html = b'<p id="first">Original</p><p id="second">Updated</p>'
    first = await monitor(client, domain, headers, row.id, html)
    first_task = first["fields"][0]["taskId"]
    initial = await read(client, ATTENTION, search=row.id)
    assert initial["items"][0]["counts"]["initial"] == 1
    assert initial["items"][0]["counts"]["changed"] == 0
    assert initial["items"][0]["severity"] == "normal"

    next_version = await change_locator(client, uuid, etag, "#second")
    second = await monitor(client, domain, headers, row.id, html)
    second_task = second["fields"][0]["taskId"]
    assert first_task != second_task
    assert first["sourceSnapshotId"] == second["sourceSnapshotId"]
    assert second["changeStatus"] == "UNCHANGED"
    failed = tree(recipe(part(css("["))))
    missing = tree(recipe(part(css("#missing"))))
    await add_tree(client, domain, other.id, None, failed)
    await add_tree(client, domain, other.id, None, missing)
    await monitor(client, domain, headers, other.id, b"<p>Nothing to extract</p>")
    await add_tree(client, domain, other.id, None, tree(recipe(part(css("#not-run-yet")))))

    first_page = await read(client, ATTENTION, limit=1)
    next_page = await read(client, ATTENTION, limit=1, offset=1)
    assert first_page["total"] == next_page["total"] == 2
    a, b = sorted(first_page["items"] + next_page["items"], key=lambda item: item["id"])
    assert a["id"] == row.id and a["openTaskCount"] == 2
    assert a["counts"]["changed"] == 1 and a["counts"]["problems"] == 1
    assert b["id"] == other.id and b["counts"]["missing"] == b["counts"]["extractionFailed"] == 1
    assert b["counts"]["unchanged"] == 0 and b["counts"]["problems"] == 2
    assert (await read(client, ATTENTION, issue="missing"))["items"] == [b]
    assert (await read(client, ATTENTION, search=row.url[-16:]))["items"] == [a]
    past_end = await read(client, ATTENTION, limit=1, offset=2)
    assert past_end["total"] == 2 and past_end["items"] == []

    path = f"/monitoring/sources/{row.id}/review"
    current = await read(client, path)
    field = current["fields"][0]
    assert field["businessField"]["name"] == "name"
    assert field["businessObject"] == {"id": obj.id, "name": "Original"}
    assert field["canonicalValue"] == field["previousEvidence"] == "Original"
    assert field["currentEvidence"] == "Updated"
    assert field["selectorVersionUuid"] == next_version
    assert "selector" not in field and "evaluation" not in field
    assert current["latestCheck"]["id"] == second["jobId"]
    assert field["task"]["originCheckId"] == second["jobId"]
    assert current["earlierTasks"]["items"][0]["id"] == first_task

    historic = await read(client, path, checkId=first["jobId"])
    assert historic["latestCheck"]["id"] == second["jobId"]
    assert historic["selectedCheck"]["id"] == first["jobId"]
    assert historic["fields"][0]["status"] == "FIELD_NEW"
    old_path = f"{path}/{first['jobId']}/{uuid}"
    old = await read(client, old_path)
    new = await read(client, f"{path}/{second['jobId']}/{uuid}")
    assert old["selector"]["version"]["uuid"] == definition["versions"][0]["uuid"]
    assert old["selector"]["version"]["status"] == "superseded"
    assert new["selector"]["version"]["uuid"] == next_version
    locators = old["evaluation"]["result"]["recipeResults"][0]["partResults"][0]["locatorResults"]
    assert [(result["status"], result["matchCount"]) for result in locators] == [
        ("success", 1),
        ("not_found", 0),
    ]
    other_review = await read(client, f"/monitoring/sources/{other.id}/review")
    assert {f["status"] for f in other_review["fields"]} == {
        None,
        "FIELD_MISSING",
        "FIELD_EXTRACTION_FAILED",
    }
    assert all(f["canonicalValueId"] is None for f in other_review["fields"])
    for url in (ATTENTION, path, old_path):
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=headers)).status_code == 401
        assert (await client.patch(url, headers=OPERATOR)).status_code == 405
    assert (
        await client.get(
            f"/monitoring/sources/{other.id}/review/{first['jobId']}/{uuid}",
            headers=OPERATOR,
        )
    ).status_code == 404
    async with domain.factory.begin() as session:
        check = await session.get(SourceCheckRun, UUID(first["jobId"]))
        check.field_results = [{**check.field_results[0], "evaluationId": None}]
    no_evaluation = await read(client, old_path)
    assert no_evaluation["selector"] == old["selector"]
    assert no_evaluation["evaluation"] is None

    async with domain.factory() as session:
        await TasksService(session).change_task_status(
            first_task, TaskStatusChangeRequest(status="completed")
        )
    updated = await read(client, path)
    assert updated["earlierTasks"]["total"] == 0
    assert updated["fields"][0]["canonicalValueId"] == slot.value_id
    assert updated["fields"][0]["canonicalValue"] == "Original"
    async with domain.factory.begin() as session:
        task = await session.get(Task, second_task)
        workflow = await session.get(Workflow, task.workflow_id)
        workflow.status = WorkflowStatus.SUPERSEDED
        workflow.superseded_at = utc_now()
    latest = await read(client, path)
    assert latest["fields"][0]["task"]["workflowStatus"] == "superseded"
    assert not latest["fields"][0]["task"]["requiresReview"]
    assert (await read(client, ATTENTION, search=row.id))["total"] == 0


async def test_workspace_distinguishes_source_change_coverage_and_job_failure(
    domain, client, minio
):
    tracked = await source(domain, client)
    untracked = await source(domain, client)
    obj = await domain.make(name="Long canonical " + "example " * 256)
    slot = domain.slot(obj, "name")
    await add_tree(client, domain, tracked.id, slot, tree(recipe(part(css("#tracked")))))
    headers, _ = await agent(client, tracked.id, untracked.id)
    first = await monitor(client, domain, headers, tracked.id, b'<p id="tracked">Same</p>')
    async with domain.factory() as session:
        await TasksService(session).change_task_status(
            first["fields"][0]["taskId"],
            TaskStatusChangeRequest(status="completed"),
        )
    same = b'<p id="tracked">Same</p><span>New unrelated text</span>'
    await monitor(client, domain, headers, tracked.id, same)
    info = (await read(client, ATTENTION, search=tracked.id))["items"][0]
    assert info["reason"] == "source_changed_fields_unchanged"
    assert info["severity"] == "informational"
    assert info["counts"]["unchanged"] == 1 and info["counts"]["changed"] == 0
    path = f"/monitoring/sources/{tracked.id}/review"
    current = await read(client, path)
    assert current["fields"][0]["canonicalValue"] == slot.value
    initial = await read(client, path, checkId=first["jobId"])
    assert initial["snapshot"]["id"] != current["snapshot"]["id"]
    assert initial["fields"][0]["task"]["status"] == "completed"

    await monitor(client, domain, headers, untracked.id, b"<p>Before</p>")
    previous = await monitor(client, domain, headers, untracked.id, b"<p>After</p>")
    no_fields = (await read(client, ATTENTION, search=untracked.id))["items"][0]
    assert no_fields["reason"] == "source_changed_incomplete_coverage"
    assert no_fields["severity"] == "normal"
    assert no_fields["counts"]["unchanged"] == no_fields["counts"]["changed"] == 0
    path = f"/monitoring/sources/{untracked.id}/review"
    assert (await read(client, path))["fields"] == []

    await add_tree(client, domain, untracked.id, None, tree(recipe(part(css("#before-failure")))))
    job_id = await enqueue(client, untracked.id)
    async with domain.factory.begin() as session:
        job = await session.get(MonitoringJob, UUID(job_id))
        MonitoringQueue._finish(job, "failed", "CAPTURE_FAILED")
    failed = await read(client, path)
    assert failed["selectedCheck"]["status"] == "failed"
    assert failed["selectedCheck"]["errorCode"] == "CAPTURE_FAILED"
    assert failed["latestCompletedCheck"]["id"] == previous["jobId"]
    assert len(failed["fields"]) == 1 and failed["fields"][0]["status"] is None
    assert failed["snapshot"] is None
    page = await read(client, f"/monitoring/sources/{untracked.id}/history", summary=True, limit=1)
    assert len(page) == 1 and page[0]["id"] == job_id and "fields" not in page[0]
    after_failure = (await read(client, ATTENTION, issue="job_failed"))["items"][0]
    assert after_failure["reason"] == "job_failed"
    assert after_failure["severity"] == "high"
    assert after_failure["counts"]["extractionFailed"] == 0
