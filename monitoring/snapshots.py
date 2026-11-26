"""Read an owned snapshot and build a passive browser preview of its HTML."""

from base64 import b64encode
from hashlib import sha256
from html import escape

from lxml import etree, html
from sqlalchemy import select

from monitoring.contracts import (
    MAX_BYTES,
    MIME_TYPE,
    ReviewedSource,
    SnapshotArtifactDetails,
    SnapshotContent,
)
from monitoring.presentation import source_record
from monitoring.security import MonitoringError
from monitoring.storage import storage_from_env
from sources.schemas.api import SourceSnapshotResponse
from sources.schemas.models import SourceSnapshot, StoredFile

PREVIEW_CSS = """html{color-scheme:light dark}
body{margin:1.25rem;font:16px/1.5 system-ui,sans-serif;overflow-wrap:anywhere}
pre,table{max-width:100%;overflow:auto}table{border-collapse:collapse}
td,th{padding:.25em .5em;border:1px solid GrayText}"""
STYLE_HASH = b64encode(sha256(PREVIEW_CSS.encode()).digest()).decode()
PREVIEW_POLICY = (
    f"default-src 'none'; base-uri 'none'; form-action 'none'; style-src 'sha256-{STYLE_HASH}'"
)
SNAPSHOT_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": f"{PREVIEW_POLICY}; sandbox; frame-ancestors 'self'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
}

PASSIVE_TAGS = frozenset(
    """
    a abbr address article aside b bdi bdo blockquote br caption cite code dd del div dl dt em
    figcaption figure footer h1 h2 h3 h4 h5 h6 header hr i kbd li main mark nav ol p pre q s
    samp section small span strong sub sup table tbody td tfoot th thead time tr u ul var
""".split()
)
OMIT_CONTENT = frozenset(
    """
    applet audio canvas embed head iframe math noscript object script style svg template video
""".split()
)
PASSIVE_ATTRIBUTES = ("id", "class", "lang", "dir", "colspan", "rowspan", "scope")


async def snapshot_record(session, source_id, snapshot_id):
    record = (
        await session.execute(
            select(SourceSnapshot, StoredFile)
            .outerjoin(StoredFile, StoredFile.id == SourceSnapshot.file_id)
            .where(SourceSnapshot.id == snapshot_id, SourceSnapshot.source_id == source_id)
        )
    ).one_or_none()
    if record is None:
        raise MonitoringError(404, "SNAPSHOT_NOT_FOUND")
    return record


async def artifact_bytes(file, *, max_bytes=MAX_BYTES):
    if file is None:
        raise MonitoringError(404, "SNAPSHOT_ARTIFACT_NOT_FOUND")
    if file.mime_type.partition(";")[0].strip().lower() != MIME_TYPE:
        raise MonitoringError(415, "SNAPSHOT_NOT_HTML")
    return await storage_from_env().read_snapshot(file, max_bytes=max_bytes)


async def snapshot_content(session, source_id, snapshot_id, *, metadata_only):
    snapshot, file = await snapshot_record(session, source_id, snapshot_id)
    source = await source_record(session, source_id)
    # Monitoring serializes the captured DOM as UTF-8. The download serves the stored bytes.
    original = None if metadata_only else (await artifact_bytes(file)).decode("utf-8", "replace")
    return SnapshotContent(
        source=ReviewedSource.model_validate(source),
        snapshot=SourceSnapshotResponse.model_validate(snapshot),
        artifact=SnapshotArtifactDetails(
            mimeType=file.mime_type, sizeBytes=file.size_bytes, sha256=file.sha256
        )
        if file is not None
        else None,
        html=original,
    )


def append_passive(node, markup):
    # Serialize only known HTML tags and inert attributes. Unknown wrappers can retain their text.
    tag = node.tag
    if not isinstance(tag, str) or tag in OMIT_CONTENT:
        return
    if tag in PASSIVE_TAGS:
        attributes = "".join(
            f' {name}="{escape(node.attrib[name], quote=True)}"'
            for name in PASSIVE_ATTRIBUTES
            if name in node.attrib
        )
        markup.append(f"<{tag}{attributes}>")
    if node.text:
        markup.append(escape(node.text, quote=False))
    for child in node:
        append_passive(child, markup)
        if child.tail:
            markup.append(escape(child.tail, quote=False))
    if tag in PASSIVE_TAGS and tag not in {"br", "hr"}:
        markup.append(f"</{tag}>")


def sanitized_preview(body):
    parser = html.HTMLParser(encoding="utf-8", no_network=True, remove_comments=True)
    markup = []
    try:
        document = html.document_fromstring(body, parser=parser)
    except etree.ParserError:
        pass  # An empty capture still has a valid, isolated preview document.
    else:
        content = document.find("body")
        if content is not None:
            append_passive(content, markup)
    policy = escape(PREVIEW_POLICY, quote=True)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{policy}">'
        f"<style>{PREVIEW_CSS}</style></head><body>{''.join(markup)}</body></html>"
    )
