"""Run an approved tree over a pinned SourceSnapshot and use the existing capture writer."""

import asyncio
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from sqlalchemy import func, select

from business_layer.schemas.models import BusinessObjectField
from extraction.exceptions import (
    ExtractionConflict,
    ExtractionNotConfigured,
    ExtractionValidationError,
)
from extraction.schemas import capture as dto
from extraction.schemas.enums import DiscoveryMethod, ExtractionRunStatus
from extraction.schemas.selector import SelectorEvaluation, SelectorVersion
from extraction.schemas.selector_api import (
    MAX_SNAPSHOT_BYTES,
    SelectorExecutionResult,
    StoredEvaluation,
)
from extraction.schemas.selector_tree import SelectorEvaluationResult, validate_selector_evaluation
from extraction.services.capture import CaptureService
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from extraction.services.selectors import SelectorService
from sources.schemas.models import SourceSnapshot, StoredFile


class SnapshotReader(Protocol):
    async def __call__(self, snapshot: SourceSnapshot, file: StoredFile) -> bytes:
        """Load the existing immutable artifact from configured storage."""
        ...


def response(row):
    return StoredEvaluation(
        uuid=row.uuid,
        evaluated_at=row.evaluated_at,
        page_url=row.page_url,
        source_snapshot_id=row.source_snapshot_id,
        extraction_run_id=row.extraction_run_id,
        provenance=row.provenance,
        result=SelectorEvaluationResult.model_validate(row.result_json),
    )


def evaluate_html(version, html, page_url):
    runtime = HtmlSelectorRuntime(html, page_url)
    return evaluate_selector_version(version, runtime), runtime.root.tag


class SelectorExecutionService:
    def __init__(self, capture: CaptureService, snapshot_reader: SnapshotReader | None = None):
        self.capture = capture
        self.session = capture.session
        self.selectors = SelectorService(self.session)
        self.snapshot_reader = snapshot_reader

    async def _read_html(self, snapshot, supplied_html):
        file = await self.session.get(StoredFile, snapshot.file_id) if snapshot.file_id else None
        if (snapshot.mime_type or (file.mime_type if file else "")).split(";", 1)[
            0
        ].lower() not in {
            "",
            "text/html",
            "application/xhtml+xml",
        }:
            raise ExtractionValidationError("SelectorTree execution requires an HTML snapshot")
        expected = {
            value.lower()
            for value in (snapshot.content_hash, file.sha256 if file else None)
            if value
        }
        if supplied_html is not None:
            if not expected:
                raise ExtractionValidationError(
                    "Supplied HTML requires a recorded snapshot SHA-256"
                )
            content = supplied_html.encode("utf-8")
        else:
            if self.snapshot_reader is None or file is None:
                raise ExtractionNotConfigured(
                    "Configure snapshot storage or supply digest-checked HTML"
                )
            if file.size_bytes is not None and file.size_bytes > MAX_SNAPSHOT_BYTES:
                raise ExtractionValidationError("Snapshot HTML exceeds the size limit")
            content = await self.snapshot_reader(snapshot, file)
            if not isinstance(content, bytes):
                raise ExtractionNotConfigured("Snapshot storage must return the recorded bytes")
        if not content or len(content) > MAX_SNAPSHOT_BYTES:
            raise ExtractionValidationError("Snapshot HTML is empty or exceeds the size limit")
        if expected and expected != {sha256(content).hexdigest()}:
            raise ExtractionValidationError("HTML does not match the recorded snapshot SHA-256")
        if supplied_html is not None:
            return supplied_html
        # Stored rendered DOM is usually UTF-8. Keep bytes when it needs HTML encoding detection.
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content

    async def execute(self, uuid, request):
        try:
            # Match capture's lock order (Workflow, Source, Run), then pin the selector.
            run, snapshot = await self.capture._lock_run_context(request.run_id)
            if request.source_snapshot_id is not None and request.source_snapshot_id != snapshot.id:
                raise ExtractionValidationError("Execution snapshot does not match the run")
            selector = await self.selectors.selector(uuid)
            previous = await self.session.execute(
                select(SelectorEvaluation, SelectorVersion.selector_id)
                .join(SelectorVersion, SelectorVersion.id == SelectorEvaluation.selector_version_id)
                .where(
                    SelectorEvaluation.extraction_run_id == run.id,
                    SelectorEvaluation.execution_key == request.capture_key,
                )
            )
            receipt = await self.capture.repo.get_capture(run.id)
            if (row := previous.one_or_none()) is not None:
                evaluation, owner = row
                if owner != selector.id:
                    raise ExtractionConflict("This execution key belongs to a different selector")
                if request.html is not None:
                    await self._read_html(snapshot, request.html)
                capture = (
                    dto.CaptureResponse.model_validate(receipt.result_json)
                    if evaluation.result_json["status"] == "success"
                    and receipt is not None
                    and receipt.capture_key == request.capture_key
                    else None
                )
                await self.session.commit()
                return SelectorExecutionResult(evaluation=response(evaluation), capture=capture)
            if receipt is not None or run.status not in {
                ExtractionRunStatus.PENDING,
                ExtractionRunStatus.FAILED,
            }:
                raise ExtractionConflict("Run already has a capture or is not executable")
            if selector.source_id != snapshot.source_id:
                raise ExtractionValidationError(
                    "Selector requires a binding to the snapshot source"
                )
            if not snapshot.page_url:
                raise ExtractionValidationError(
                    "Selector execution requires a recorded snapshot URL"
                )
            source = await self.capture._source(run.source_id)
            if source.type != "HTML":
                raise ExtractionValidationError("SelectorTree executes HTML only")
            if selector.active_version_id is None:
                raise ExtractionConflict("Selector has no active version")
            version = await self.session.get(SelectorVersion, selector.active_version_id)
            definition = await self.selectors.definition(version, selector.uuid)
            html = await self._read_html(snapshot, request.html)
            result, tag_name = await asyncio.to_thread(
                evaluate_html, definition, html, snapshot.page_url
            )
            evaluation = SelectorEvaluation(
                uuid=uuid4(),
                selector_version_id=version.id,
                source_snapshot_id=snapshot.id,
                extraction_run_id=run.id,
                execution_key=request.capture_key,
                page_url=snapshot.page_url,
                provenance="backend_verified",
                result_json=result.portable(),
            )
            if result.status == "success":
                payload = await self._capture_payload(selector, result.raw_value, request, tag_name)
                captured = await self.capture.register_capture(
                    run.id, payload, selector_evaluation=evaluation
                )
            else:
                await self.capture.repo.add(evaluation)
                await self.capture.fail_run(run.id, result.diagnostic or result.status)
                captured = None
            return SelectorExecutionResult(evaluation=response(evaluation), capture=captured)
        except BaseException:
            await self.session.rollback()
            raise

    async def _capture_payload(self, selector, raw, request, tag_name):
        field = await self.capture.repo.field(selector.business_entity_field_id)
        slot = (
            await self.session.get(BusinessObjectField, selector.business_object_field_id)
            if (selector.business_object_field_id is not None)
            else None
        )
        root = await self.capture.repo.current_scope(selector.source_id, "ROOT")
        scope = {
            "client_key": "document",
            "name": "ROOT",
            "selector": {"type": "CSS", "value": "html", "discovered_by": "AUTOMATIC"},
        }
        if root is not None:
            scope["business_entity_id"] = root.business_entity_id
            scope["selector"] = {
                "type": root.selector_type,
                "value": root.selector_string,
                "confidence": root.confidence_score,
                "discovered_by": root.discovered_by,
            }
        scopes = [scope]
        instances = [
            {
                "client_key": "document",
                "scope_client_key": "document",
                "root_element_client_key": "document",
            }
        ]
        value_scope = "document"
        if root is not None and root.business_entity_id not in {None, field.business_entity_id}:
            # Preserve an existing typed ROOT when a selector observes another entity.
            value_scope = f"selector-{selector.uuid}"
            scopes.append(
                {
                    "client_key": value_scope,
                    "parent_client_key": "document",
                    "name": value_scope,
                    "business_entity_id": field.business_entity_id,
                    "selector": {"type": "CSS", "value": "html", "discovered_by": "AUTOMATIC"},
                }
            )
            instances.append(
                {
                    "client_key": value_scope,
                    "scope_client_key": value_scope,
                    "parent_client_key": "document",
                    "root_element_client_key": "document",
                }
            )
        return dto.CaptureRequest.model_validate(
            {
                "capture_key": request.capture_key,
                "scopes": scopes,
                "scope_instances": instances,
                "elements": [
                    {
                        "client_key": "document",
                        "element_from": "HTML",
                        "html": {"tag_name": tag_name},
                    }
                ],
                "values": [
                    {
                        "client_key": "selector-value",
                        "scope_instance_client_key": value_scope,
                        "element_client_key": "document",
                        "business_entity_field_id": field.id,
                        "business_object_id": slot.business_object_id if slot else None,
                        "token_class_id": request.token_class_id,
                        "raw_value": raw,
                        "discovered_by": DiscoveryMethod.AUTOMATIC,
                    }
                ],
            },
            context={"selector_evidence": True},
        )

    async def record_client(self, uuid, request):
        async with self.selectors.write():
            selector = await self.selectors.selector(uuid, lock=True)
            version = await self.selectors.version(
                selector.id, request.result.selector_version_uuid
            )
            definition = await self.selectors.definition(version, selector.uuid)
            try:
                validate_selector_evaluation(request.result, definition)
            except ValueError as error:
                raise ExtractionValidationError(str(error)) from error
            if request.source_snapshot_id is not None:
                snapshot = await self.capture.repo.get_snapshot(request.source_snapshot_id)
                if selector.source_id != snapshot.source_id or (
                    snapshot.page_url is not None and request.page_url != snapshot.page_url
                ):
                    raise ExtractionValidationError(
                        "Reported evaluation snapshot belongs to another page or source"
                    )
            payload = {
                "selector_version_id": version.id,
                "source_snapshot_id": request.source_snapshot_id,
                "page_url": request.page_url,
                "provenance": "client_reported",
                "result_json": request.result.portable(),
            }
            if request.uuid is not None:
                previous = await self.session.scalar(
                    select(SelectorEvaluation).where(SelectorEvaluation.uuid == request.uuid)
                )
                if previous is not None:
                    if not all(getattr(previous, key) == val for key, val in payload.items()):
                        raise ExtractionConflict("Evaluation UUID already names a different result")
                    return response(previous)
            row = SelectorEvaluation(uuid=request.uuid or uuid4(), **payload)
            await self.capture.repo.add(row)
            return response(row)

    async def page(self, uuid, offset, limit):
        selector = await self.selectors.selector(uuid)
        query = (
            select(SelectorEvaluation)
            .join(SelectorVersion, SelectorVersion.id == SelectorEvaluation.selector_version_id)
            .where(SelectorVersion.selector_id == selector.id)
        )
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.session.scalars(
            query.order_by(SelectorEvaluation.id.desc()).offset(offset).limit(limit)
        )
        return [response(row) for row in rows], total
