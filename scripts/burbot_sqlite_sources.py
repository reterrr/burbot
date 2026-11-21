"""Source identity and file storage for the offline SQLite import."""

import asyncio
import hashlib
import io
import mimetypes
import re
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
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
    if (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.path.startswith("/files/")
    ):
        return str(UUID(parsed.path.split("/", 3)[2]))
    return None


@dataclass(frozen=True)
class PreservedFile:
    local_id: str
    stored_file_id: int | None
    storage_key: str
    sha256: str
    extraction_type: SourceType | None

    def reference(self):
        return {
            "localFileId": self.local_id,
            "storedFileId": str(self.stored_file_id) if self.stored_file_id else None,
            "storageKey": self.storage_key,
            "sha256": self.sha256,
        }


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
        self.file_links = {}
        self.stored_files = {}

    def artifact(self, key):
        return self.stored_files.get(self.file_links.get(key))

    def add(self, key, raw_url, declared=None):
        blob_id = None
        try:
            if not isinstance(raw_url, str) or not raw_url:
                raise ValueError("MISSING_SOURCE_URL")
            blob_id = local_blob(raw_url)
            if blob_id in self.workspace.blobs:
                self.file_links[key] = blob_id
            suffix = extension(urlsplit(raw_url).path)
            if suffix in UNSUPPORTED_EXTENSIONS:
                raise ValueError("UNSUPPORTED_DOCUMENT_FORMAT")
            if declared is not None and declared not in MIME_TYPES:
                raise ValueError("UNSUPPORTED_SOURCE_TYPE")
            kind = SourceType(declared) if declared is not None else EXTENSIONS.get(suffix)
            if kind is not None and suffix in EXTENSIONS and EXTENSIONS[suffix] != kind:
                raise ValueError("SOURCE_FORMAT_MISMATCH")
            if blob_id is not None:
                if blob_id not in self.workspace.blobs:
                    self.report.add(
                        "pending",
                        "file_preservation",
                        key[1],
                        "LOCAL_BLOB_UNRESOLVED",
                        inputCategory=key[0],
                        url=raw_url,
                        localFileId=blob_id,
                    )
                    return
                canonical = ("blob", blob_id)
            else:
                if re.search(r"%(?![0-9a-fA-F]{2})", raw_url):
                    raise ValueError("MALFORMED_URL_ESCAPE")
                canonical = ("url", str(URL.validate_python(raw_url)))
        except (ValueError, TypeError) as error:
            reason = str(error) if str(error).isupper() else "INVALID_SOURCE_URL_OR_FORMAT"
            format_issue = reason in {
                "UNSUPPORTED_DOCUMENT_FORMAT",
                "UNSUPPORTED_SOURCE_TYPE",
                "SOURCE_FORMAT_MISMATCH",
            }
            self.report.add(
                "unsupported",
                key[0],
                key[1],
                reason,
                url=raw_url,
                type=declared,
                capability="extraction" if format_issue else "source_registration",
            )
            if format_issue and key[0] in {"file_sources", "import_sources"}:
                if key not in self.file_links:
                    self.report.add(
                        "pending",
                        "file_preservation",
                        key[1],
                        "LOCAL_BLOB_UNRESOLVED" if blob_id else "FILE_BYTES_NOT_IN_SQLITE",
                        inputCategory=key[0],
                        url=raw_url,
                        localFileId=blob_id,
                    )
            return
        self.keys[key] = canonical
        self.groups[canonical][key] = kind

    def discover(self):
        for identifier, item in self.workspace.blobs.items():
            kind = EXTENSIONS.get(extension(item["name"]))
            if kind is not None:
                key = ("local_file_blobs", identifier)
                canonical = ("blob", identifier)
                self.groups[canonical][key] = kind
                self.keys[key] = canonical
            else:
                self.report.add(
                    "unsupported",
                    "local_file_blobs",
                    identifier,
                    "UNSUPPORTED_DOCUMENT_FORMAT",
                    capability="extraction",
                    payload=item,
                )
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

    async def preserve_file(self, session, entry):
        identifier, item = entry
        body = self.workspace.db.execute(
            "SELECT content FROM local_file_blobs WHERE file_id = ?", (identifier,)
        ).fetchone()[0]
        if not isinstance(body, bytes) or len(body) != item["size_bytes"]:
            raise ValueError("FILE_CONTENT_SIZE_MISMATCH")
        kind = EXTENSIONS.get(extension(item["name"]))
        mime = (item["mime_type"] or "").split(";", 1)[0].strip().lower()
        if not mime or mime == "application/octet-stream":
            mime = (
                MIME_TYPES[kind]
                if kind
                else mimetypes.guess_file_type(item["name"])[0] or "application/octet-stream"
            )
        if kind is not None and not extractable_file(kind, mime, body):
            self.report.add(
                "unsupported",
                "local_file_blobs",
                identifier,
                "FILE_CONTENT_OR_MEDIA_TYPE_MISMATCH",
                capability="extraction",
                payload=item,
            )
            kind = None
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
                "stored_files",
                identifier,
                "OBJECT_STORAGE_UNAVAILABLE",
                capability="file_preservation",
                payload={**item, "sha256": digest},
            )
            return
        uploaded_at = timestamp(item["uploaded_at"])
        status = "reused" if previous is not None else "would_import"
        if self.apply:
            await asyncio.to_thread(self.storage.ensure_file, key, body, mime, digest)
            if previous is None:
                service = SourcesService(session, commit=False)
                response = await service.register_file(request)
                previous = await session.get(StoredFile, response.id)
                previous.created_at = uploaded_at
                await session.flush()
                status = "imported"
        artifact = PreservedFile(identifier, previous.id if previous else None, key, digest, kind)
        self.stored_files[identifier] = artifact
        self.report.add(
            status,
            "stored_files",
            identifier,
            capability="file_preservation",
            mimeType=mime,
            sizeBytes=len(body),
            **artifact.reference(),
        )

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
            artifact = self.stored_files.get(value)
            if artifact is None or artifact.extraction_type is None:
                return
            if kind is not None and artifact.extraction_type != kind:
                self.report.add(
                    "unsupported",
                    report_key,
                    value,
                    "SOURCE_FORMAT_MISMATCH",
                    capability="extraction",
                    type=kind,
                    **details,
                )
                return
            kind = artifact.extraction_type
            file_id = artifact.stored_file_id
            source = await self.file_source(session, file_id) if file_id is not None else None
            request = SourceCreateRequest(type=kind, file_id=file_id) if self.apply else None
        else:
            source = await service.find_by_url(value, lock=self.apply)
            kind = kind or (source.type if source else SourceType.HTML)
            request = SourceCreateRequest(type=kind, url=value) if self.apply else None
        if source is None and self.apply:
            try:
                created = await service.create_source(request)
            except SourceConflict:
                source = await service.find_by_url(value, lock=True) if locator == "url" else None
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
        self.ids[canonical] = identifier
        self.report.add(
            "reused" if source is not None else "would_import",
            report_key,
            value,
            sourceId=str(identifier) if identifier else None,
            type=kind,
            **details,
        )

    async def file_source(self, session, stored_file_id):
        matches = list(
            await session.scalars(
                select(Source).where(Source.file_id == stored_file_id, Source.url.is_(None))
            )
        )
        if len(matches) > 1:
            raise SourceConflict("Multiple stored-file-only Sources already reference this file")
        return matches[0] if matches else None


def extractable_file(kind, mime, body):
    if not body or (
        mime != MIME_TYPES[kind] and (kind, mime) != (SourceType.HTML, "application/xhtml+xml")
    ):
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
