"""Operator snapshot reads through the real capture storage and REST routes."""

from hashlib import sha256
from uuid import uuid4

import pytest
from lxml import html
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_monitoring_postgres import OPERATOR, agent, monitor, source
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio

from monitoring.contracts import MAX_BYTES
from sources.schemas.models import SourceSnapshot, StoredFile

pytestmark = pytest.mark.asyncio
CAPTURE = """<!doctype html><html><head>
<base href="https://example.invalid/"><meta http-equiv="refresh" content="3600">
<link rel="stylesheet" href="https://example.invalid/style.css">
<script type="application/json">{"data": "captured"}</script><style>p{color:blue}</style>
</head><body><main id="project" class="project" style="color:blue">
<h1>Ogłoszenie archiwalne</h1><p>&lt;example&gt; &amp; more text</p>
<a href="https://example.invalid/page" target="_blank">Link excerpt</a>
<img src="https://example.invalid/image" alt="Captured image">
<iframe src="https://example.invalid/frame"></iframe>
<form method="get" action="https://example.invalid/form"><label>Label</label><input></form>
<svg><title>Decorative content</title></svg>
</main></body></html>\r\n""".encode()


async def store_capture(
    domain, storage, source_id, *, body=CAPTURE, file=True, size=None, digest=None, mime="text/html"
):
    key = f"monitoring/snapshots/{uuid4()}/capture.html"
    if body is not None:
        storage.reader.put_object(Bucket=storage.bucket, Key=key, Body=body, ContentType=mime)
    async with domain.factory.begin() as session:
        artifact = None
        if file:
            artifact = StoredFile(storage_key=key, mime_type=mime, size_bytes=size, sha256=digest)
            session.add(artifact)
            await session.flush()
        snapshot = SourceSnapshot(
            source_id=source_id,
            file_id=artifact.id if artifact else None,
            page_url="https://example.org/captured-page",
            mime_type=mime,
            content_hash="a" * 64,
            structure_hash="b" * 64,
            representation="rendered_dom",
            representation_version="firefox-dom-1",
        )
        session.add(snapshot)
        await session.flush()
    return f"/monitoring/sources/{source_id}/snapshots/{snapshot.id}", key


async def test_owned_snapshot_preview_source_details_and_exact_download(domain, client, minio):
    owner = await source(domain, client)
    other = await source(domain, client)
    digest = sha256(CAPTURE).hexdigest()
    path, storage_key = await store_capture(
        domain, minio, owner.id, size=len(CAPTURE), digest=digest
    )
    metadata = await client.get(path + "/content?metadataOnly=true", headers=OPERATOR)
    assert metadata.status_code == 200, metadata.text
    details = metadata.json()
    assert details["html"] is None
    assert details["source"]["id"] == owner.id
    assert details["source"]["url"] == owner.url
    assert details["snapshot"]["page_url"] == "https://example.org/captured-page"
    assert details["snapshot"]["representation_version"] == "firefox-dom-1"
    assert details["snapshot"]["content_hash"] == "a" * 64 != digest
    assert details["artifact"] == {
        "mimeType": "text/html",
        "sizeBytes": len(CAPTURE),
        "sha256": digest,
    }

    content = await client.get(path + "/content", headers=OPERATOR)
    assert content.status_code == 200, content.text
    assert content.headers["content-type"] == "application/json"
    assert content.json() == {**details, "html": CAPTURE.decode()}

    preview = await client.get(path + "/preview", headers=OPERATOR)
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "text/html; charset=utf-8"
    assert "sandbox" in preview.headers["content-security-policy"].split("; ")
    document = html.fromstring(preview.text)
    meta = document.xpath('//meta[@http-equiv="Content-Security-Policy"]')[0]
    assert "default-src 'none'" in meta.get("content")
    assert "form-action 'none'" in meta.get("content")
    assert document.xpath('//main[@id="project"]/h1/text()') == ["Ogłoszenie archiwalne"]
    assert document.xpath("//p/text()") == ["<example> & more text"]
    assert document.xpath("//a/text()") == ["Link excerpt"]
    assert not document.xpath(
        "//script | //base | //link | //iframe | //form | //input | //img | //svg"
    )
    assert not document.xpath("//*[@href or @src or @style or @action or @target]")

    download = await client.get(path + "/download", headers=OPERATOR)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith('attachment; filename="snapshot-')
    assert download.content == CAPTURE
    for response in (metadata, content, preview, download):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert storage_key not in response.text

    for suffix in ("/preview", "/content", "/content?metadataOnly=true", "/download"):
        rejected = await client.get(path + suffix, headers={"Authorization": "Bearer invalid"})
        assert rejected.status_code == 401
        assert rejected.headers["cache-control"] == "no-store"
        wrong_owner = await client.get(
            path.replace(f"/{owner.id}/snapshots/", f"/{other.id}/snapshots/") + suffix,
            headers=OPERATOR,
        )
        assert wrong_owner.status_code == 404
        assert wrong_owner.json() == {"detail": {"code": "SNAPSHOT_NOT_FOUND"}}


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        ("no_file", 404, "SNAPSHOT_ARTIFACT_NOT_FOUND"),
        ("missing_blob", 404, "SNAPSHOT_ARTIFACT_NOT_FOUND"),
        ("wrong_sha256", 422, "SNAPSHOT_INTEGRITY_MISMATCH"),
        ("wrong_size", 422, "SNAPSHOT_INTEGRITY_MISMATCH"),
        ("large_record", 413, "SNAPSHOT_TOO_LARGE"),
        ("large_blob", 413, "SNAPSHOT_TOO_LARGE"),
        ("not_html", 415, "SNAPSHOT_NOT_HTML"),
    ],
)
async def test_artifact_failures_keep_snapshot_details(
    domain, client, minio, failure, status, code
):
    owner = await source(domain, client)
    options = {
        "no_file": {"file": False, "body": None},
        "missing_blob": {"body": None},
        "wrong_sha256": {"digest": "c" * 64},
        "wrong_size": {"size": len(CAPTURE) + 1},
        "large_record": {"body": None, "size": MAX_BYTES + 1},
        "large_blob": {"body": b" " * (MAX_BYTES + 1)},
        "not_html": {"mime": "application/pdf"},
    }[failure]
    path, _ = await store_capture(domain, minio, owner.id, **options)
    details = await client.get(path + "/content?metadataOnly=true", headers=OPERATOR)
    assert details.status_code == 200, details.text
    for suffix in ("/preview", "/content", "/download"):
        result = await client.get(path + suffix, headers=OPERATOR)
        assert result.status_code == status, result.text
        assert result.json() == {"detail": {"code": code}}
        assert result.headers["cache-control"] == "no-store"


async def test_monitoring_history_reads_the_reused_capture(domain, client, minio):
    monitored = await source(domain, client)
    credentials, _ = await agent(client, monitored.id)
    first = await monitor(client, domain, credentials, monitored.id, CAPTURE)
    reused = await monitor(client, domain, credentials, monitored.id, CAPTURE)
    newer = await monitor(client, domain, credentials, monitored.id, b"<h1>Latest</h1>")
    original_id = first["sourceSnapshotId"]
    assert original_id == reused["sourceSnapshotId"] != newer["sourceSnapshotId"]
    source_review = f"/monitoring/sources/{monitored.id}/review"
    selected = await client.get(
        source_review, params={"checkId": reused["jobId"]}, headers=OPERATOR
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["snapshot"]["id"] == original_id
    url = f"/monitoring/sources/{monitored.id}/snapshots/{original_id}/download"
    assert (await client.get(url, headers=OPERATOR)).content == CAPTURE
