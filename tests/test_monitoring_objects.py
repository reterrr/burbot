"""Object reviews across captures, workflows, and extension identities."""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from test_collections_postgres import database as database
from test_extension_sync_postgres import identity, resolve
from test_extension_sync_postgres import workspace as workspace
from test_monitoring_postgres import (
    OPERATOR,
    add_tree,
    agent,
    claim,
    complete,
    enqueue,
    field_review,
    history,
    monitor,
    operation,
    prepare,
    put,
    review,
    source,
)
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_monitoring_presentation import PROJECT_NAME, make_project
from test_monitoring_presentation import domain as domain
from test_monitoring_workspace import read
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import BusinessEntityVersion, BusinessObjectFieldValue
from business_layer.services.data import DataService
from extraction.schemas.enums import ObservationStatus
from extraction.schemas.models import FieldObservation
from monitoring.models import MonitoringJob, SourceCheckRun
from monitoring.presentation import object_presentations
from monitoring.processing import MonitoringProcessor
from monitoring.queue import ATTEMPT_LIMIT
from monitoring.security import fingerprint
from sources.schemas.models import SourceObjectFieldTracking
from tasks.api.dto import TaskStatusChangeRequest
from tasks.exceptions.exceptions import TaskConflict
from tasks.schemas.models import Task, TaskReference, TaskType, Workflow
from tasks.services.task import TasksService

pytestmark = pytest.mark.asyncio
INBOX = "/monitoring/objects"


async def bind(client, domain, row, slot, path):
    definition = tree(recipe(part(css(path))))
    await add_tree(client, domain, row.id, slot, definition)
    return definition


async def test_groups_three_fields_and_separates_objects_sources_and_unbound(domain, client, minio):
    project = await make_project(domain, name=PROJECT_NAME)
    obj = await domain.make(name="Grant application", project_id=project.object_id)
    other = await domain.make(name="Grant application")
    main, second, failing = [await source(domain, client) for _ in range(3)]
    headers, _ = await agent(client, main.id, second.id, failing.id)
    fields = {
        name: await bind(client, domain, main, domain.slot(obj, name), selector)
        for name, selector in (("name", "#name"), ("deadline", "#deadline"), ("project_id", "["))
    }
    await bind(client, domain, main, domain.slot(other, "name"), "#other")
    await bind(client, domain, main, None, "#unbound")
    await bind(client, domain, second, domain.slot(obj, "name"), "#name")
    original = b'<p id="name">Observed</p><p id="other">Other</p><p id="unbound">Extra</p>'
    first = await monitor(client, domain, headers, main.id, original)
    result = {row["selectorUuid"]: row for row in first["fields"]}
    bound = {name: result[spec["selector"]["uuid"]] for name, spec in fields.items()}
    task_id = bound["name"]["taskId"]
    assert {row["taskId"] for row in bound.values()} == {task_id}
    assert {key: row["status"] for key, row in bound.items()} == {
        "name": "FIELD_NEW",
        "deadline": "FIELD_MISSING",
        "project_id": "FIELD_EXTRACTION_FAILED",
    }
    assert {row["businessObjectId"] for row in bound.values()} == {obj.id}
    assert all(row["requiresReview"] for row in bound.values())
    unbound = next(row for row in first["fields"] if row["businessObjectId"] is None)
    assert unbound["taskId"] != task_id
    async with domain.factory() as session:
        task = await TasksService(session).get_task(task_id)
        assert task.type == TaskType.REVIEW_BUSINESS_OBJECT
        origin_workflow = task.workflow_id
        assert {
            (ref.reference_type, ref.reference_id)
            for ref in task.references
            if ref.role == "target"
        } == {("business_object", obj.id)}
        contexts = {
            (ref.reference_type, ref.reference_id)
            for ref in task.references
            if ref.role == "context"
        }
        assert {
            ("source", main.id),
            ("source_snapshot", first["sourceSnapshotId"]),
            ("extraction_run", first["extractionRunId"]),
            ("observation", bound["name"]["observationId"]),
            *(
                ("business_object_field", domain.slot(obj, field).object_field_id)
                for field in fields
            ),
        } <= contexts
        assert (await session.get(Task, unbound["taskId"])).type == TaskType.RESOLVE_OBSERVATION

    second_check = await monitor(client, domain, headers, second.id, original)
    await enqueue(client, failing.id)
    failed = await claim(client, headers)
    async with domain.factory.begin() as session:
        (await session.get(MonitoringJob, UUID(failed["jobId"]))).attempt_count = ATTEMPT_LIMIT
    response = await client.post(
        operation(failed, "fail"),
        json={"leaseId": failed["leaseId"], "code": "HTTP_ERROR"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    attention = await read(client, "/monitoring/attention/sources", issue="job_failed")
    assert [item["id"] for item in attention["items"]] == [failing.id]
    assert attention["items"][0]["openTaskCount"] == 0

    first_page = await read(client, INBOX, limit=1)
    second_page = await read(client, INBOX, limit=1, offset=1)
    assert first_page["total"] == second_page["total"] == 2
    assert (await read(client, INBOX, limit=1, offset=2))["items"] == []
    entry = first_page["items"][0]
    assert entry["object"]["id"] == obj.id
    assert (
        entry["object"]["name"] == second_page["items"][0]["object"]["name"] == "Grant application"
    )
    assert second_page["items"][0]["object"]["id"] == other.id
    assert (entry["fieldCount"], entry["taskCount"], entry["sourceCount"], entry["severity"]) == (
        3,
        2,
        2,
        "high",
    )
    assert datetime.fromisoformat(entry["lastCheckedAt"]) == datetime.fromisoformat(
        second_check["completedAt"]
    )
    path = f"{INBOX}/{obj.id}/review"
    detail = await read(client, path)
    assert {item["source"]["id"] for item in detail["tasks"]["items"]} == {main.id, second.id}
    assert len((await read(client, path, limit=1, offset=1))["tasks"]["items"]) == 1
    assert (await read(client, path, taskId=unbound["taskId"]))["tasks"]["items"] == []
    main_task = (await read(client, path, taskId=task_id))["tasks"]["items"][0]
    assert main_task["type"] == "review_business_object"
    assert {field["businessField"]["name"] for field in main_task["fields"]} == {
        "name",
        "deadline",
        "Projekt",
    }
    assert all(
        field["selectorVersionUuid"] and field["evaluationId"] for field in main_task["fields"]
    )
    reference = await field_review(client, main.id, first, bound["project_id"])
    assert reference["businessObject"]["id"] == obj.id
    assert reference["canonicalDisplay"]["target"]["id"] == project.object_id
    assert reference["canonicalDisplay"]["label"] == PROJECT_NAME
    assert reference["evaluation"]["result"]["status"] == "error"

    changed = await monitor(
        client, domain, headers, main.id, original.replace(b"Observed", b"Changed")
    )
    changed_field = next(row for row in changed["fields"] if row["status"] == "FIELD_CHANGED")
    assert changed_field["taskId"] == task_id
    ledger = f"/monitoring/object-reviews/{task_id}/history"
    recorded = await read(client, ledger, limit=1)
    earlier = await read(client, ledger, limit=1, offset=1)
    assert recorded["total"] == earlier["total"] == 2
    assert earlier["items"][0]["checkId"] == first["jobId"]
    assert len(earlier["items"][0]["fields"]) == 3
    assert recorded["items"][0]["checkId"] == changed["jobId"]
    assert {field["status"] for field in recorded["items"][0]["fields"]} == {
        "FIELD_CHANGED",
        "FIELD_MISSING",
        "FIELD_EXTRACTION_FAILED",
    }
    historic = await field_review(client, main.id, first, bound["name"])
    assert historic["currentEvidence"] == "Observed"
    assert historic["selector"]["version"]["uuid"] == fields["name"]["versions"][0]["uuid"]
    snapshot = await read(
        client, f"/monitoring/sources/{main.id}/snapshots/{first['sourceSnapshotId']}/content"
    )
    assert snapshot["html"].encode() == original
    for url in (INBOX, path, ledger):
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=headers)).status_code == 401
        assert (await client.patch(url, headers=OPERATOR)).status_code == 405

    async with domain.factory() as session:
        task = await session.get(Task, task_id)
        workflow = await session.get(Workflow, task.workflow_id)
        assert task.workflow_id != origin_workflow
        assert workflow.source_snapshot_id == changed["sourceSnapshotId"]
        await TasksService(session).change_task_status(
            task_id, TaskStatusChangeRequest(status="in_progress")
        )
    assert (await read(client, INBOX))["items"][0]["status"] == "in_progress"
    async with domain.factory() as session:
        await TasksService(session).change_task_status(
            task_id, TaskStatusChangeRequest(status="completed")
        )
    assert (await read(client, path, taskId=task_id))["tasks"]["items"][0]["status"] == "completed"
    items = (await read(client, INBOX))["items"]
    assert next(item for item in items if item["object"]["id"] == obj.id)["sourceCount"] == 1
    async with domain.factory() as session:
        canonical = await session.get(BusinessObjectFieldValue, domain.slot(obj, "name").value_id)
        assert canonical.value_json == "Grant application"
        assert (
            await session.get(FieldObservation, changed_field["observationId"])
        ).status == ObservationStatus.DETECTED
        assert not await session.scalar(
            select(SourceObjectFieldTracking.id).where(
                SourceObjectFieldTracking.baseline_observation_id.is_not(None)
            )
        )

    repeated = await monitor(
        client, domain, headers, main.id, original.replace(b"Observed", b"Changed") + b" "
    )
    assert {row["taskId"] for row in repeated["fields"] if row["businessObjectId"] == obj.id} == {
        None,
        task_id,
    }
    assert not any(
        row["requiresReview"] for row in repeated["fields"] if row["businessObjectId"] == obj.id
    )
    new = await monitor(client, domain, headers, main.id, original)
    reopened = next(
        row for row in new["fields"] if row["selectorUuid"] == bound["name"]["selectorUuid"]
    )
    assert reopened["taskId"] != task_id and reopened["requiresReview"]
    assert (await read(client, ledger))["total"] == 2
    bound_observation = await client.post(
        f"/extraction/observations/{unbound['observationId']}/resolve-object",
        json={"business_object_id": other.id},
    )
    assert bound_observation.status_code == 200, bound_observation.text
    assert bound_observation.json()["business_object_id"] == other.id


async def test_concurrent_processing_and_legacy_field_review(domain, client, minio):
    obj = await domain.make(name="Example")
    slot = domain.slot(obj, "name")
    row = await source(domain, client)
    await bind(client, domain, row, slot, "#name")
    headers, _ = await agent(client, row.id)
    identity = UUID(await enqueue(client, row.id))
    job = await claim(client, headers)
    html = b"<p>Unavailable</p>"
    grant, report = await prepare(client, headers, job, html, "a" * 64)
    await put(grant, html)
    await complete(client, headers, job, report)
    async with domain.factory.begin() as session:
        assert await MonitoringProcessor(session).acquire(identity)

    async def process():
        async with domain.factory.begin() as session:
            return await MonitoringProcessor(session).process(identity)

    assert sorted(await asyncio.wait_for(asyncio.gather(process(), process()), timeout=10)) == [
        False,
        True,
    ]
    assert not await process()
    assert await domain.count(Task, type=TaskType.REVIEW_BUSINESS_OBJECT) == 1

    first = (await history(client, row.id))[0]
    task_id = first["fields"][0]["taskId"]
    # Model a persisted field-level review from before object-grouped processing.
    async with domain.factory.begin() as session:
        task = await session.get(Task, task_id)
        task.type = TaskType.REVIEW_SOURCE_CHANGE
        task.metadata_json = {
            "monitoringJobId": first["jobId"],
            "monitoringKey": fingerprint([row.id, slot.object_field_id, "FIELD_MISSING", ()]),
            "evidenceStatus": "MISSING",
        }
        await session.execute(
            delete(TaskReference).where(
                TaskReference.task_id == task.id, TaskReference.role == "target"
            )
        )
        check = await session.get(SourceCheckRun, identity)
        check.field_results = [
            {
                key: value
                for key, value in check.field_results[0].items()
                if key
                not in {
                    "businessObjectId",
                    "businessObjectFieldId",
                    "businessFieldId",
                    "findingKey",
                }
            }
        ]
    before = await review(client, task_id)
    assert before["evidenceStatus"] == "MISSING"
    again = await monitor(client, domain, headers, row.id, b"<p>Still unavailable</p>")
    assert again["fields"][0]["taskId"] == task_id
    new = await monitor(client, domain, headers, row.id, b'<p id="name">New evidence</p>')
    assert new["fields"][0]["taskId"] != task_id
    tasks = (await read(client, f"{INBOX}/{obj.id}/review"))["tasks"]["items"]
    assert {item["type"] for item in tasks} == {"review_source_change", "review_business_object"}
    legacy = next(item for item in tasks if item["id"] == task_id)
    assert legacy["fields"][0]["businessObjectFieldId"] == slot.object_field_id
    preserved = await review(client, task_id)
    for key in ("snapshot", "selector", "evaluation", "referenceDisplays", "evidenceStatus"):
        assert preserved[key] == before[key]


async def test_retry_cannot_create_two_open_reviews_for_one_object_and_source(
    domain, client, minio
):
    obj = await domain.make(name="Example")
    row = await source(domain, client)
    await bind(client, domain, row, domain.slot(obj, "name"), "#missing")
    headers, _ = await agent(client, row.id)
    html = b"<p>Unavailable</p>"
    first = await monitor(client, domain, headers, row.id, html)
    failed_id = first["fields"][0]["taskId"]
    async with domain.factory() as session:
        await TasksService(session).change_task_status(
            failed_id, TaskStatusChangeRequest(status="failed")
        )
    second = await monitor(client, domain, headers, row.id, html)
    assert first["sourceSnapshotId"] == second["sourceSnapshotId"]
    assert failed_id != second["fields"][0]["taskId"]
    async with domain.factory() as session:
        with pytest.raises(TaskConflict):
            await TasksService(session).change_task_status(
                failed_id, TaskStatusChangeRequest(status="pending")
            )
        assert (await TasksService(session).get_task(failed_id)).allowed_statuses == ["cancelled"]
    path = f"{INBOX}/{obj.id}/review"
    old = (await read(client, path, taskId=failed_id))["tasks"]["items"][0]
    assert old["status"] == "failed" and old["allowedStatuses"] == ["cancelled"]
    assert (await read(client, INBOX))["items"][0]["taskCount"] == 1


async def test_names_use_extension_identity_and_explicit_display_field(workspace):
    _, factory, *_ = workspace
    first = await resolve(workspace, identity("local-project-1"), action="create")
    second = await resolve(workspace, identity("local-project-2"), action="create")
    unnamed = await resolve(workspace, identity("local-project-3"), action="create")
    recruitment = await resolve(
        workspace, identity("local-recruitment", "recruitment"), action="create"
    )
    a, b, c, d = (int(row["businessObjectId"]) for row in (first, second, unnamed, recruitment))
    async with factory.begin() as session:
        data = DataService(session)
        for row, name, code in (
            (first, PROJECT_NAME, "PR_POD_001"),
            (second, PROJECT_NAME, "PR_POD_002"),
        ):
            slots = row["objectFields"]
            await data.assign_object_fields_values(
                int(row["businessObjectId"]),
                {
                    int(slots["name"]["businessObjectFieldId"]): name,
                    int(slots["number"]["businessObjectFieldId"]): code,
                },
            )
        await data.assign_object_fields_values(
            d,
            {
                int(
                    recruitment["objectFields"]["external_number"]["businessObjectFieldId"]
                ): "PSF/01/2026"
            },
        )
    async with factory() as session:
        objects = await object_presentations(session, [a, b, c, d])
        assert objects[a]["name"] == objects[b]["name"] == PROJECT_NAME
        assert (objects[a]["code"], objects[b]["code"]) == ("PR_POD_001", "PR_POD_002")
        assert objects[c]["name"] is None and objects[c]["code"] is None
        assert objects[d]["name"] == "PSF/01/2026"

    async with factory.begin() as session:
        version = await session.scalar(
            select(BusinessEntityVersion).where(
                BusinessEntityVersion.business_entity_id == int(first["businessEntityId"])
            )
        )
        version.definition_json = {**(version.definition_json or {}), "display_field": "number"}
    async with factory() as session:
        assert (await object_presentations(session, [a]))[a]["name"] == "PR_POD_001"
