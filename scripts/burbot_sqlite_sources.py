"""Source identity and file storage for the offline SQLite import."""

import asyncio
import hashlib
import io
import re
from collections import defaultdict
from contextlib import closing
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from pydantic import TypeAdapter
from sqlalchemy import select

from scripts.burbot_sqlite_input import timestamp
from sources.exceptions import SourceConflict
from sources.schemas.api import SourceCreateRequest, SourceURL, StoredFileCreateRequest
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import Source, StoredFile
from sources.services.sources import SourcesService

URL = TypeAdapter(SourceURL)
MIME_TYPES = {
    SourceType.HTML: "text/html",
    SourceType.PDF: "application/pdf",
    SourceType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSIONS = {
    "htm": SourceType.HTML,
    "html": SourceType.HTML,
    "pdf": SourceType.PDF,
    "xlsx": SourceType.XLSX,
}
UNSUPPORTED_EXTENSIONS = {
    "doc",
    "docx",
    "zip",
    "xls",
    "ods",
    "odt",
    "rtf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "rar",
    "7z",
    "tar",
    "gz",
    "tgz",
    "csv",
    "ppt",
    "pptx",
}
UNAVAILABLE = {SourceState.ARCHIVED, SourceState.BLOCKED_BY_POLICY}


def extension(path):
    return PurePosixPath(path).suffix.lstrip(".").lower()


def local_blob(url):
    parsed = urlsplit(url)
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.path.startswith("/files/"):
        return str(UUID(parsed.path.split("/", 3)[2]))
    return None


class SourceCatalog:
    def __init__(self, workspace, namespace, *, apply, storage):
        self.workspace = workspace
        self.report = workspace.report
        self.namespace = namespace
        self.apply = apply
        self.storage = storage
        self.groups = defaultdict(dict)
        self.keys = {}
        self.ids = {}
        self.import_keys = defaultdict(set)

    def add(self, key, raw_url, declared=None):
        try:
            if not isinstance(raw_url, str) or not raw_url:
                raise ValueError("MISSING_SOURCE_URL")
            suffix = extension(urlsplit(raw_url).path)
            if suffix in UNSUPPORTED_EXTENSIONS:
                raise ValueError("UNSUPPORTED_DOCUMENT_FORMAT")
            if declared is not None and declared not in MIME_TYPES:
                raise ValueError("UNSUPPORTED_SOURCE_TYPE")
            kind = SourceType(declared) if declared is not None else EXTENSIONS.get(suffix)
            if kind is not None and suffix in EXTENSIONS and EXTENSIONS[suffix] != kind:
                raise ValueError("SOURCE_FORMAT_MISMATCH")
            blob_id = local_blob(raw_url)
            if blob_id is not None:
                if blob_id not in self.workspace.blobs:
                    self.report.add("failed", key[0], key[1], "LOCAL_BLOB_UNRESOLVED", url=raw_url)
                    return
                canonical = ("blob", blob_id)
            else:
                if re.search(r"%(?![0-9a-fA-F]{2})", raw_url):
                    raise ValueError("MALFORMED_URL_ESCAPE")
                canonical = ("url", str(URL.validate_python(raw_url)))
        except (ValueError, TypeError) as error:
            reason = str(error) if str(error).isupper() else "INVALID_SOURCE_URL_OR_FORMAT"
            self.report.add("unsupported", key[0], key[1], reason, url=raw_url, type=declared)
            return
        self.keys[key] = canonical
        self.groups[canonical][key] = kind

    def discover(self):
        for identifier, item in self.workspace.blobs.items():
            kind = EXTENSIONS.get(extension(item["name"]))
            if kind is None:
                self.report.add(
                    "unsupported",
                    "local_file_blobs",
                    identifier,
                    "UNSUPPORTED_DOCUMENT_FORMAT",
                    payload=item,
                )
                continue
            key = ("local_file_blobs", identifier)
            canonical = ("blob", identifier)
            self.groups[canonical][key] = kind
            self.keys[key] = canonical
        for identifier, item in self.workspace.imports.items():
            key = ("import_sources", identifier)
            self.add(key, item.get("url"), item.get("type"))
            if item.get("importKey") and key in self.keys:
                self.import_keys[item["importKey"]].add(self.keys[key])
        for item in self.workspace.objects.values():
            if item.kind is None:
                if item.payload.get("sourceUrl"):
                    self.add(("object_source", item.owner), item.payload["sourceUrl"])
            elif item.kind == "file_source":
                self.add(
                    ("file_sources", item.ref), item.values.get("url"), item.values.get("fileType")
                )
                if item.values.get("sourcePageUrl"):
                    self.add(("file_page", item.ref), item.values["sourcePageUrl"])
            if item.kind in {"file_source", "document"} and item.values.get("source_url"):
                self.add((f"{item.kind}_provenance", item.ref), item.values["source_url"])
        for identifier, item in self.workspace.evidence.items():
            self.add(("field_evidence", identifier), item.get("pageUrl"))
        for identifier, rule in self.workspace.rules.items():
            page = rule.get("pageUrl")
            if page:
                self.add(("extraction_rule_page", identifier), page)
        for identifier, tree in self.workspace.trees.items():
            header = tree["selector"]
            if header.get("pageUrl"):
                self.add(("selector_page", identifier), header["pageUrl"])

    def source_id(self, key):
        canonical = self.keys.get(key)
        return self.ids.get(canonical)

    def selector_source(self, identifier, header, rule):
        keys = set()
        for key in (("selector_page", identifier), ("extraction_rule_page", rule)):
            if key in self.keys:
                keys.add(self.keys[key])
        source_uuid = header.get("sourceUuid")
        if source_uuid:
            if ("import_sources", source_uuid) in self.keys:
                keys.add(self.keys[("import_sources", source_uuid)])
            keys.update(self.import_keys.get(source_uuid, ()))
        if len(keys) > 1:
            raise SourceConflict("Selector references conflicting canonical Sources")
        if not keys:
            return None, False
        key = next(iter(keys))
        return self.ids.get(key), key in self.ids

    async def register(self, session, canonical, refs):
        locator, value = canonical
        report_key = "local_file_blobs" if locator == "blob" else "sources"
        details = {"references": [list(key) for key in refs]}
        types = set(refs.values()) - {None}
        if len(types) > 1:
            self.report.add(
                "conflict",
                report_key,
                value,
                "CANONICAL_SOURCE_TYPE_CONFLICT",
                **details,
                types=sorted(t.value for t in types),
            )
            return
        kind = next(iter(types), None)
        service = SourcesService(session, commit=False)
        if locator == "blob":
            if kind is None:
                raise ValueError("UNKNOWN_STORED_FILE_FORMAT")
            source, usable, created_file_source = await self.local_file(
                session, service, value, kind
            )
            if not usable:
                return
        else:
            source = await service.find_by_url(value, lock=self.apply)
            kind = kind or (source.type if source else SourceType.HTML)
            if source is None and self.apply:
                try:
                    created = await service.create_source(SourceCreateRequest(type=kind, url=value))
                except SourceConflict:
                    source = await service.find_by_url(value, lock=True)
                    if source is None:
                        raise
                else:
                    await session.flush()
                    self.ids[canonical] = created.id
                    self.report.add(
                        "imported",
                        report_key,
                        value,
                        sourceId=str(created.id),
                        type=kind,
                        **details,
                    )
                    return
        if source is not None and (source.type != kind or source.state in UNAVAILABLE):
            self.report.add(
                "conflict",
                report_key,
                value,
                "SOURCE_UNAVAILABLE_OR_TYPE_MISMATCH",
                sourceId=str(source.id),
                type=kind,
                actualType=source.type,
                sourceState=source.state,
                **details,
            )
            return
        identifier = source.id if source is not None else None
        await session.flush()
        self.ids[canonical] = identifier
        status = "would_import" if source is None else "reused"
        if locator == "blob" and created_file_source:
            status = "imported"
        self.report.add(
            status,
            report_key,
            value,
            sourceId=str(identifier) if identifier else None,
            type=kind,
            **details,
        )

    async def local_file(self, session, service, identifier, kind):
        item = self.workspace.blobs[identifier]
        body = self.workspace.db.execute(
            "SELECT content FROM local_file_blobs WHERE file_id = ?", (identifier,)
        ).fetchone()[0]
        mime = (item["mime_type"] or "").split(";", 1)[0].strip().lower()
        if not mime or mime == "application/octet-stream":
            mime = MIME_TYPES[kind]
        if kind == SourceType.HTML and mime == "application/xhtml+xml":
            expected_mime = mime
        else:
            expected_mime = MIME_TYPES[kind]
        if mime != expected_mime or not valid_file(kind, body, item["size_bytes"]):
            self.report.add(
                "failed",
                "local_file_blobs",
                identifier,
                "FILE_CONTENT_OR_MEDIA_TYPE_MISMATCH",
                payload=item,
            )
            return None, False, False
        digest = hashlib.sha256(body).hexdigest()
        key = f"sqlite-seed/{self.namespace}/{UUID(identifier)}"
        request = StoredFileCreateRequest(
            storage_key=key,
            original_name=item["name"],
            mime_type=mime,
            size_bytes=len(body),
            sha256=digest,
        )
        previous = await session.scalar(select(StoredFile).where(StoredFile.storage_key == key))
        if previous is not None and any(
            getattr(previous, field) != value for field, value in request.model_dump().items()
        ):
            raise SourceConflict("Stored file identity already has different metadata")
        if self.storage is None:
            self.report.add(
                "pending",
                "local_file_blobs",
                identifier,
                "OBJECT_STORAGE_UNAVAILABLE",
                payload={**item, "sha256": digest},
            )
            return None, False, False
        uploaded_at = timestamp(item["uploaded_at"])
        if self.apply:
            await asyncio.to_thread(self.storage.ensure_file, key, body, mime, digest)
        if previous is None:
            if not self.apply:
                return None, True, False
            response = await service.register_file(request)
            previous = await session.get(StoredFile, response.id)
            previous.created_at = uploaded_at
            await session.flush()
        matches = list(
            await session.scalars(
                select(Source).where(
                    Source.file_id == previous.id,
                    Source.url.is_(None),
                )
            )
        )
        if len(matches) > 1:
            raise SourceConflict("Multiple stored-file-only Sources already reference this file")
        if matches or not self.apply:
            return (matches[0] if matches else None), True, False
        created = await service.create_source(SourceCreateRequest(type=kind, file_id=previous.id))
        return await session.get(Source, created.id), True, True


def valid_file(kind, body, declared_size):
    if not isinstance(body, bytes) or len(body) != declared_size or not body:
        return False
    if kind == SourceType.PDF:
        return b"%PDF-" in body[:1024]
    if kind == SourceType.XLSX:
        try:
            with ZipFile(io.BytesIO(body)) as book:
                return {"[Content_Types].xml", "xl/workbook.xml"}.issubset(book.namelist())
        except BadZipFile:
            return False
    return True


class S3Files:
    """Write once to the existing private StoredFile bucket using a stable key."""

    def __init__(self, storage):
        self.storage = storage

    def ensure_file(self, key, body, mime, digest):
        from botocore.exceptions import BotoCoreError, ClientError

        client, bucket = self.storage.reader, self.storage.bucket
        try:
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=body,
                    ContentType=mime,
                    ContentDisposition="attachment",
                    IfNoneMatch="*",
                )
                return
            except ClientError as error:
                if error.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                    raise
            stored = client.get_object(Bucket=bucket, Key=key)
            stored_digest = hashlib.sha256()
            with closing(stored["Body"]) as existing:
                for chunk in iter(lambda: existing.read(1024 * 1024), b""):
                    stored_digest.update(chunk)
            if stored_digest.hexdigest() != digest or stored["ContentType"] != mime:
                raise SourceConflict("Object storage key contains different bytes or media type")
        except (BotoCoreError, ClientError) as error:
            raise ValueError(
                "Could not verify or store the file in the configured bucket"
            ) from error
