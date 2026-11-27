"""Exercise archive uploads, policy transitions and authorized replay with real MinIO."""

from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_monitoring_postgres import (
    OPERATOR,
    add_tree,
    agent,
    claim,
    complete,
    enqueue,
    history,
    operation,
    prepare,
    process,
    put,
    source,
)
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_selector_tree import css, part, recipe, tree
from test_snapshot_open_commands import AGENT, open_command
from test_snapshot_open_commands import claim as claim_snapshot

from extraction.schemas.common import utc_now
from extraction.schemas.models import FieldObservation
from extraction.services.repositories import ExtractionRepository
from monitoring.archives import blob_key
from monitoring.models import MonitoringArchiveUpload, MonitoringJob
from monitoring.queue import MonitoringQueue
from monitoring.security import MonitoringError
from monitoring.snapshot_config import FULL_ARCHIVE_VERSION, MIB, snapshot_policy

MODE = "BURBOT_MONITORING_SNAPSHOT_MODE"
TOTAL = "BURBOT_MONITORING_FULL_SNAPSHOT_MAX_MB"
RESOURCE = "BURBOT_MONITORING_FULL_RESOURCE_MAX_MB"
EVIDENCE = b'<!doctype html><main id="value">Current value</main>'
MARKUP = b'<link rel="stylesheet" href="/style.css"><main>Current value</main>'
CSS = b"main{color:navy}"


@pytest.mark.parametrize(
    ("mode", "total", "resource"),
    [
        ("unknown", "256", "32"),
        ("full", "0", "1"),
        ("full", "2", "3"),
        ("full", "513", "32"),
        ("full", "256", "garbage"),
    ],
)
def test_invalid_archive_settings(monkeypatch, mode, total, resource):
    monkeypatch.setenv(MODE, mode)
    monkeypatch.setenv(TOTAL, total)
    monkeypatch.setenv(RESOURCE, resource)
    with pytest.raises(MonitoringError, match="SNAPSHOT_CONFIG_INVALID"):
        snapshot_policy()


@pytest.mark.asyncio
async def test_archive_modes_keep_evidence_and_replay_scoped(domain, client, minio, monkeypatch):
    monkeypatch.delenv(MODE, raising=False)
    monkeypatch.delenv(TOTAL, raising=False)
    monkeypatch.delenv(RESOURCE, raising=False)
    row = await source(domain, client)
    owner = await domain.make(name="Canonical")
    await add_tree(
        client, domain, row.id, domain.slot(owner, "name"), tree(recipe(part(css("#value"))))
    )
    auth, agent_id = await agent(client, row.id)
    other, _ = await agent(client, row.id)

    async def capture(evidence=EVIDENCE):
        await enqueue(client, row.id)
        job = await claim(client, auth)
        grant, completion = await prepare(client, auth, job, evidence, "a" * 64)
        await put(grant, evidence)
        return job, completion

    async def finish(job, completion):
        accepted = await complete(client, auth, job, completion)
        assert accepted == await complete(client, auth, job, completion)
        await process(domain, job)
        return next(item for item in await history(client, row.id) if item["jobId"] == job["jobId"])

    async def post(job, action, data, status=200):
        response = await client.post(
            operation(job, "full-archive" + action),
            json={"leaseId": job["leaseId"], **data},
            headers=auth,
        )
        assert response.status_code == status, response.text
        return response.json()

    first, initial = await capture()
    assert first["snapshotMode"] == "minimal"
    assert "fullArchive" not in first and "visualArchiveVersion" not in first
    await post(first, "/uploads", {"sha256": sha256(CSS).hexdigest(), "sizeBytes": len(CSS)}, 409)
    baseline = await finish(first, initial)
    plain, plain_completion = await capture()
    minimal = await finish(plain, plain_completion)
    assert minimal["archive"] == {"mode": "minimal", "status": "minimal"}
    assert await domain.count(MonitoringArchiveUpload) == 0

    monkeypatch.setenv(MODE, "full")
    monkeypatch.setenv(TOTAL, "2")
    monkeypatch.setenv(RESOURCE, "1")
    full, full_completion = await capture()
    assert full["snapshotMode"] == "full"
    assert full["fullArchive"] == {
        "version": FULL_ARCHIVE_VERSION,
        "maxBytes": 2 * MIB,
        "maxResourceBytes": MIB,
    }
    # Subsequent claims will use minimal. This lease continues to use full and its pinned limits.
    monkeypatch.setenv(MODE, "minimal")
    too_large = await post(full, "/uploads", {"sha256": "0" * 64, "sizeBytes": MIB + 1}, 413)
    assert too_large["detail"] == {"code": "ARCHIVE_OBJECT_TOO_LARGE"}

    async def store(job, payload, *, interrupt=False, reused=False):
        obj = {"sha256": sha256(payload).hexdigest(), "sizeBytes": len(payload)}
        target = await post(job, "/uploads", obj)
        if reused:
            assert target["stored"] and target["url"] is None
            return obj
        assert target["stored"] is False
        async with AsyncClient() as wire:
            if interrupt:
                bad = await wire.put(
                    target["url"],
                    content=b"!" * len(payload),
                    headers={"Content-Type": "application/octet-stream"},
                )
                assert bad.status_code == 200
                assert (await post(job, "/seal", obj, 422))["detail"] == {
                    "code": "UPLOAD_HASH_MISMATCH"
                }
                target = await post(job, "/uploads", obj)
            result = await wire.put(
                target["url"],
                content=payload,
                headers={"Content-Type": "application/octet-stream"},
            )
            assert result.status_code == 200, result.text
        assert (await post(job, "/seal", obj))["stored"]
        assert (await post(job, "/seal", obj))["stored"]
        assert (await post(job, "/uploads", obj))["stored"]
        return obj

    document = await store(full, MARKUP)
    resource = await store(full, CSS, interrupt=True)
    origin = "https://example.org"
    manifest = {
        "archiveVersion": FULL_ARCHIVE_VERSION,
        "mode": "full",
        "pageUrl": full_completion["pageUrl"],
        "baseUrl": full_completion["pageUrl"],
        "capturedAt": full_completion["capturedAt"],
        "document": document,
        "resources": [
            {
                "originalUrl": origin + "/redirect.css",
                "responseUrl": origin + "/style.css",
                "mediaType": "text/css",
                "status": "captured",
                **resource,
            },
            {
                "originalUrl": origin + "/style.css",
                "mediaType": "text/css",
                "status": "captured",
                **resource,
            },
            {
                "originalUrl": origin + "/missing.png",
                "status": "missing",
                "reason": "response_unavailable",
            },
            {
                "originalUrl": origin + "/large.png",
                "status": "truncated",
                "sizeBytes": MIB + 1,
                "reason": "resource_limit",
            },
        ],
    }
    unavailable = {**manifest, "document": {**document, "sha256": "0" * 64}}
    assert (await post(full, "", {"manifest": unavailable}, 422))["detail"] == {
        "code": "UNVERIFIED_ARCHIVE_OBJECT"
    }
    archived = await post(full, "", {"manifest": manifest})
    assert archived["status"] == "partial"
    assert archived["captured"] == 2 and archived["missing"] == 1 and archived["truncated"] == 1
    assert archived["sizeBytes"] == len(MARKUP) + len(CSS)
    assert (await post(full, "", {"manifest": manifest})) == archived
    succeeded = await finish(full, full_completion)
    assert succeeded["archive"]["status"] == "partial"

    switched_back, switched_completion = await capture()
    assert switched_back["snapshotMode"] == "minimal"
    switched = await finish(switched_back, switched_completion)

    monkeypatch.setenv(MODE, "full")
    failed, failed_completion = await capture()
    await store(failed, CSS, reused=True)
    await post(failed, "", {"failure": "upload_failed"})
    isolated = await finish(failed, failed_completion)
    assert isolated["archive"]["status"] == "failed"
    assert isolated["archive"]["failure"] == "upload_failed"

    assert plain_completion["evaluations"] == full_completion["evaluations"]
    assert plain_completion["contentHash"] == full_completion["contentHash"]
    assert plain_completion["structureHash"] == full_completion["structureHash"]
    for check in (minimal, succeeded, switched, isolated):
        assert check["sourceSnapshotId"] == baseline["sourceSnapshotId"]
        assert check["changeStatus"] == "UNCHANGED"
        assert check["fields"][0]["status"] == "FIELD_UNCHANGED"
        assert check["fields"][0]["taskId"] is None
        async with domain.factory() as session:
            repo = ExtractionRepository(session)
            evidence = await repo.get(FieldObservation, check["fields"][0]["observationId"])
            assert (await repo.observation_value(evidence)).raw_value == "Current value"

    async with domain.factory.begin() as session:
        await session.execute(
            update(MonitoringArchiveUpload).values(expires_at=utc_now() - timedelta(seconds=1))
        )
        assert await MonitoringQueue(session).cleanup_uploads() >= 3
    assert (
        minio.reader.list_objects_v2(Bucket=minio.bucket, Prefix="monitoring/archive-resources/")[
            "KeyCount"
        ]
        == 2
    )
    assert (
        minio.reader.list_objects_v2(Bucket=minio.bucket, Prefix="monitoring/archive-pending/")[
            "KeyCount"
        ]
        == 0
    )
    assert minio.reader.head_object(Bucket=minio.bucket, Key=blob_key(resource["sha256"]))[
        "ContentLength"
    ] == len(CSS)
    async with domain.factory() as session:
        persisted = await session.get(MonitoringJob, UUID(full["jobId"]))
        assert persisted.snapshot_policy["mode"] == "full"

    review = await client.get(
        f"/monitoring/sources/{row.id}/review", headers=OPERATOR, params={"checkId": full["jobId"]}
    )
    assert review.json()["selectedCheck"]["archive"]["status"] == "partial"
    await claim_snapshot(client, auth, 204)
    request = {
        "requestId": str(uuid4()),
        "sourceId": row.id,
        "targetAgentId": agent_id,
        "snapshotId": baseline["sourceSnapshotId"],
        "checkId": full["jobId"],
    }
    command = await open_command(client, request)
    assert (await claim_snapshot(client, auth))["archiveVersion"] == FULL_ARCHIVE_VERSION
    path = f"{AGENT}/{command['commandId']}"
    metadata = await client.get(path + "/archive-manifest", headers=auth)
    assert metadata.json()["completeness"] == {"captured": 2, "missing": 1, "truncated": 1}
    assert metadata.headers["X-Burbot-Snapshot-SHA256"] == sha256(metadata.content).hexdigest()
    css_response = await client.get(path + "/archive-objects/" + resource["sha256"], headers=auth)
    assert css_response.content == CSS and css_response.headers["cache-control"] == "no-store"
    assert (await client.get(path + "/archive-manifest", headers=other)).status_code == 404
    assert (
        await client.get(path + "/archive-objects/" + "0" * 64, headers=auth)
    ).status_code == 404
    assert (await client.get(path + "/artifact", headers=auth)).content == EVIDENCE
    await client.post(path + "/ack", json={"state": "opened"}, headers=auth)
    minimal_command = await open_command(
        client,
        {
            **request,
            "requestId": str(uuid4()),
            "checkId": plain["jobId"],
        },
    )
    assert (await claim_snapshot(client, auth)).get("archiveVersion") is None
    path = f"{AGENT}/{minimal_command['commandId']}"
    assert (await client.get(path + "/archive-manifest", headers=auth)).status_code == 404
    assert (await client.get(path + "/artifact", headers=auth)).content == EVIDENCE

    edited, edited_completion = await capture(EVIDENCE.replace(b"Current", b"Updated"))
    assert edited["snapshotMode"] == "full"
    changed = await finish(edited, edited_completion)
    assert changed["archive"]["failure"] == "agent_incomplete"
    assert changed["changeStatus"] == "CONTENT_CHANGED"
    assert changed["fields"][0]["status"] == "FIELD_CHANGED"
    assert changed["fields"][0]["taskId"] is not None
    assert edited_completion["evaluations"][0]["result"]["rawValue"] == "Updated value"
    current = await domain.call(lambda service: service.data.get_object(owner.id))
    assert domain.slot(current, "name").value == "Canonical"
