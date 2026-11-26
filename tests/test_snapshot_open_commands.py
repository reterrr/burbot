"""Exercise the operator-to-agent bridge through REST, PostgreSQL, and MinIO."""

import asyncio
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_monitoring_postgres import (
    OPERATOR,
    add_tree,
    agent,
    complete,
    enqueue,
    history,
    monitor,
    operation,
    prepare,
    process,
    put,
    source,
)
from test_monitoring_postgres import claim as claim_job
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_monitoring_snapshots import CAPTURE, store_capture
from test_monitoring_workspace import change_locator
from test_selector_tree import css, part, recipe, tree

from extraction.schemas.common import utc_now
from monitoring.contracts import VISUAL_ARCHIVE_VERSION
from monitoring.models import (
    MonitoringAgent,
    MonitoringJob,
    MonitoringVisualArchive,
    SnapshotOpenCommand,
)

pytestmark = pytest.mark.asyncio
COMMANDS = "/monitoring/snapshots/open-commands"
AGENT = "/monitoring/agents/snapshot-commands"


async def fixture_snapshot(domain, client, minio, **options):
    owner = await source(domain, client)
    options = {"size": len(CAPTURE), "digest": sha256(CAPTURE).hexdigest(), **options}
    path, key = await store_capture(domain, minio, owner.id, **options)
    return (
        owner.id,
        {
            "requestId": str(uuid4()),
            "sourceId": owner.id,
            "snapshotId": int(path.rsplit("/", 1)[1]),
        },
        key,
    )


async def claim(client, auth, expected=200):
    response = await client.post(AGENT + "/claim", headers=auth)
    assert response.status_code == expected, response.text
    return response.json() if expected != 204 else None


async def open_command(client, body, expected=200, *, headers=OPERATOR):
    response = await client.post(COMMANDS, json=body, headers=headers)
    assert response.status_code == expected, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


async def test_visual_archive_is_separate_and_never_replaces_evidence(domain, client, minio):
    owner = await source(domain, client)
    credentials, agent_id = await agent(client, owner.id)
    evidence = b"<p>Captured evidence</p>"
    visual = b"<style>p{color:blue}</style><p>Captured evidence</p>"

    async def capture(evidence, archive, *, digest=None):
        await enqueue(client, owner.id)
        job = await claim_job(client, credentials)
        assert job["visualArchiveVersion"] == VISUAL_ARCHIVE_VERSION
        grant, completion = await prepare(client, credentials, job, evidence, "a" * 64)
        response = await client.post(
            operation(job, "archive-uploads"),
            headers=credentials,
            json={
                "leaseId": job["leaseId"],
                "contentSize": len(archive),
                "contentHash": digest or sha256(archive).hexdigest(),
                "mimeType": "text/html",
            },
        )
        assert response.status_code == 200, response.text
        archive_grant = response.json()
        assert archive_grant["uploadIntentId"] != grant["uploadIntentId"]
        await put(grant, evidence)
        await put(archive_grant, archive)
        completion["visualArchiveUploadId"] = archive_grant["uploadIntentId"]
        assert await complete(client, credentials, job, completion) == await complete(
            client, credentials, job, completion
        )
        await process(domain, job)
        return (await history(client, owner.id))[0]["sourceSnapshotId"]

    snapshot_id = await capture(evidence, visual)
    assert await capture(evidence, visual.replace(b"blue", b"red")) == snapshot_id
    newer = await capture(b"<p>New evidence</p>", visual, digest="0" * 64)
    assert newer != snapshot_id
    assert await domain.count(MonitoringVisualArchive) == 1

    download = await client.get(
        f"/monitoring/sources/{owner.id}/snapshots/{snapshot_id}/download", headers=OPERATOR
    )
    assert download.content == evidence
    await claim(client, credentials, 204)
    command = await open_command(
        client,
        {
            "requestId": str(uuid4()),
            "sourceId": owner.id,
            "snapshotId": snapshot_id,
            "targetAgentId": agent_id,
        },
    )
    await claim(client, credentials)
    path = f"{AGENT}/{command['commandId']}/artifact"
    requested = {**credentials, "X-Burbot-Snapshot-Accept": VISUAL_ARCHIVE_VERSION}
    saved = await client.get(path, headers=requested)
    assert saved.status_code == 200, saved.text
    assert saved.content == visual
    assert saved.headers["X-Burbot-Snapshot-Format"] == VISUAL_ARCHIVE_VERSION
    assert saved.headers["X-Burbot-Snapshot-SHA256"] == sha256(visual).hexdigest()
    default = await client.get(path, headers=credentials)
    assert default.content == evidence
    assert "X-Burbot-Snapshot-Format" not in default.headers


async def test_agent_selection_authorization_and_single_delivery(domain, client, minio):
    source_id, body, key = await fixture_snapshot(domain, client, minio)
    first, first_id = await agent(client, source_id)
    second, second_id = await agent(client, source_id)
    foreign = await source(domain, client)
    denied, denied_id = await agent(client, foreign.id)
    path = f"/monitoring/sources/{source_id}/snapshot-agents"
    assert (await client.get(path, headers=first)).status_code == 401
    assert (await open_command(client, body, 401, headers=first))["detail"][
        "code"
    ] == "INVALID_OPERATOR_TOKEN"
    assert (await open_command(client, body, 409))["detail"]["code"] == "SNAPSHOT_AGENT_OFFLINE"
    assert (await open_command(client, {**body, "sourceId": foreign.id}, 404))["detail"][
        "code"
    ] == "SNAPSHOT_NOT_FOUND"
    assert (await open_command(client, {**body, "snapshotId": body["snapshotId"] + 1}, 404))[
        "detail"
    ]["code"] == "SNAPSHOT_NOT_FOUND"
    await claim(client, OPERATOR, 401)
    await claim(client, first, 204)
    await claim(client, second, 204)
    await claim(client, denied, 204)
    choices = (await client.get(path, headers=OPERATOR)).json()
    assert {row["agentId"] for row in choices} == {first_id, second_id}
    assert all(set(row) == {"agentId", "name"} for row in choices)
    assert (await open_command(client, body, 409))["detail"]["code"] == "SNAPSHOT_AGENT_REQUIRED"
    assert (await open_command(client, {**body, "targetAgentId": denied_id}, 409))["detail"][
        "code"
    ] == "SNAPSHOT_AGENT_OFFLINE"

    targeted = {**body, "targetAgentId": first_id}
    one, two = await asyncio.gather(open_command(client, targeted), open_command(client, targeted))
    assert one == two
    command_id = one["commandId"]
    assert one["state"] == "pending" and one["commandId"] == body["requestId"]
    assert await domain.count(SnapshotOpenCommand) == 1
    assert await domain.count(MonitoringJob) == 0
    assert (await open_command(client, {**targeted, "targetAgentId": second_id}, 409))["detail"][
        "code"
    ] == "SNAPSHOT_COMMAND_CONFLICT"
    artifact_path = f"{AGENT}/{command_id}/artifact"
    ack_path = f"{AGENT}/{command_id}/ack"
    assert (await client.get(artifact_path, headers=first)).status_code == 409
    assert (await client.get(artifact_path, headers=OPERATOR)).status_code == 401
    await claim(client, second, 204)
    c1, c2 = await asyncio.gather(claim(client, first), claim(client, first))
    assert c1 == c2 and c1["commandId"] == command_id and c1["state"] == "claimed"
    assert (
        c1["action"] == "open_snapshot" and c1["sourceUrl"] == "https://example.org/captured-page"
    )
    assert (await client.get(artifact_path, headers=second)).status_code == 404
    assert (
        await client.post(ack_path, json={"state": "opened"}, headers=second)
    ).status_code == 404
    assert (await client.get(f"{COMMANDS}/{command_id}", headers=first)).status_code == 401
    original = await client.get(artifact_path, headers=first)
    assert original.status_code == 200, original.text
    assert original.content == CAPTURE
    assert original.headers["x-burbot-snapshot-mime"] == "text/html"
    assert original.headers["x-burbot-snapshot-sha256"] == sha256(CAPTURE).hexdigest()
    assert original.headers["x-burbot-snapshot-size"] == str(len(CAPTURE))
    assert original.headers["cache-control"] == "no-store" and key not in original.headers.values()
    assert (
        await client.post(
            ack_path, json={"state": "failed", "errorCode": "arbitrary"}, headers=first
        )
    ).status_code == 422
    acknowledged = await client.post(ack_path, json={"state": "opened"}, headers=first)
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["state"] == "opened"
    assert (
        await client.post(ack_path, json={"state": "opened"}, headers=first)
    ).json() == acknowledged.json()
    assert (
        await client.get(f"{COMMANDS}/{command_id}", headers=OPERATOR)
    ).json() == acknowledged.json()
    assert (await client.get(artifact_path, headers=first)).status_code == 409
    await claim(client, first, 204)


async def test_expiry_scope_revocation_and_offline_presence(domain, client, minio):
    source_id, body, _ = await fixture_snapshot(domain, client, minio)
    headers, agent_id = await agent(client, source_id)
    await claim(client, headers, 204)
    opened = await open_command(client, body)
    assert opened["targetAgentId"] == agent_id
    command_id = (await claim(client, headers))["commandId"]
    async with domain.factory.begin() as session:
        command = await session.get(SnapshotOpenCommand, UUID(command_id))
        command.expires_at = utc_now() - timedelta(seconds=1)
    assert (await client.get(f"{AGENT}/{command_id}/artifact", headers=headers)).status_code == 410
    assert (
        await client.post(f"{AGENT}/{command_id}/ack", json={"state": "opened"}, headers=headers)
    ).status_code == 410
    assert (await client.get(f"{COMMANDS}/{command_id}", headers=OPERATOR)).json()[
        "state"
    ] == "expired"
    assert (await open_command(client, body))["state"] == "expired"
    await claim(client, headers, 204)

    current = await open_command(client, {**body, "requestId": str(uuid4())})
    await claim(client, headers)
    updated = await client.put(
        f"/monitoring/agents/{agent_id}/sources",
        headers=OPERATOR,
        json={"removeSourceIds": [source_id]},
    )
    assert updated.status_code == 200, updated.text
    assert (
        await client.get(f"{AGENT}/{current['commandId']}/artifact", headers=headers)
    ).status_code == 403
    await claim(client, headers, 204)

    await client.put(
        f"/monitoring/agents/{agent_id}/sources",
        headers=OPERATOR,
        json={"addSourceIds": [source_id]},
    )
    async with domain.factory.begin() as session:
        agent_record = await session.get(MonitoringAgent, UUID(agent_id))
        agent_record.snapshot_seen_at = utc_now() - timedelta(minutes=2)
    assert (await open_command(client, {**body, "requestId": str(uuid4())}, 409))["detail"][
        "code"
    ] == "SNAPSHOT_AGENT_OFFLINE"


@pytest.mark.parametrize(
    ("options", "status", "code"),
    [
        ({"body": None}, 404, "SNAPSHOT_ARTIFACT_NOT_FOUND"),
        ({"digest": "c" * 64}, 422, "SNAPSHOT_INTEGRITY_MISMATCH"),
    ],
)
async def test_bad_storage_artifact_and_failed_ack(domain, client, minio, options, status, code):
    source_id, body, _ = await fixture_snapshot(domain, client, minio, **options)
    headers, _ = await agent(client, source_id)
    await claim(client, headers, 204)
    await open_command(client, body)
    command_id = (await claim(client, headers))["commandId"]
    missing = await client.get(f"{AGENT}/{command_id}/artifact", headers=headers)
    assert missing.status_code == status, missing.text
    assert missing.json()["detail"]["code"] == code
    outcome = {"state": "failed", "errorCode": code}
    ack = f"{AGENT}/{command_id}/ack"
    first = await client.post(ack, json=outcome, headers=headers)
    second = await client.post(ack, json=outcome, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert outcome.items() <= first.json().items()


async def test_command_carries_the_historical_selector_and_diagnostics(domain, client, minio):
    row = await source(domain, client)
    obj = await domain.make(name="Canonical")
    spec = tree(recipe(part(css("#archive"))))
    slot = domain.slot(obj, "name")
    etag = await add_tree(client, domain, row.id, slot, spec)
    credentials, _ = await agent(client, row.id)
    capture = await monitor(client, domain, credentials, row.id, b'<h1 id="archive">Archived</h1>')
    historical = capture["fields"][0]
    updated = await change_locator(client, historical["selectorUuid"], etag, "#updated")
    await claim(client, credentials, 204)
    context = {
        "extractionRunId": capture["extractionRunId"],
        "selectorUuid": historical["selectorUuid"],
        "selectorVersionUuid": historical["selectorVersionUuid"],
    }
    body = {
        "requestId": str(uuid4()),
        "sourceId": row.id,
        "snapshotId": capture["sourceSnapshotId"],
        "selectorContext": context,
    }
    bad = {**body, "selectorContext": {**context, "selectorVersionUuid": updated}}
    assert (await open_command(client, bad, 422))["detail"][
        "code"
    ] == "SNAPSHOT_SELECTOR_CONTEXT_INVALID"
    await open_command(client, body)
    got = await claim(client, credentials)
    assert got["selectorContext"] == context
    assert got["selector"]["version"]["uuid"] == historical["selectorVersionUuid"]
    assert got["selector"]["version"]["status"] == "superseded"
    assert got["evaluation"]["result"]["rawValue"] == "Archived"
    assert await domain.count(MonitoringJob) == 1
