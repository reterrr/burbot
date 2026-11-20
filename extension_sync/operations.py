"""Apply reviewed proposals and bind Firefox evidence via the existing service owners."""

import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from extension_sync.contracts import Id
from extension_sync.identity import IdentityService, reject
from extension_sync.models import ExternalObjectBinding, SyncReceipt
from extension_sync.schema import local_type, manifest_field
from extraction.schemas import capture as capture_dto
from extraction.schemas.evidence import TokenClass
from extraction.schemas.selector import SelectorEvaluation
from extraction.schemas.selector_api import SelectorBinding
from extraction.schemas.selector_tree import validate_selector_evaluation
from extraction.services.capture import CaptureService
from extraction.services.selector_execution import SelectorExecutionService
from extraction.services.selectors import SelectorService
from monitoring.queue import sanitize_diagnostics
from monitoring.report import validate_consensus
from sources.schemas.models import SourceSnapshot

parse_id = TypeAdapter(Id)


def digest(kind, request):
    return hashlib.sha256(
        json.dumps(
            [kind, request.model_dump(mode="json")],
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class SyncOperations(IdentityService):
    async def receipt(self, kind, request):
        try:
            key = digest(kind, request)
        except ValueError:
            reject(422, "INVALID_JSON_VALUE")
        found = await self.session.get(SyncReceipt, (self.workspace.id, request.operation_id))
        if found is not None and found.digest != key:
            reject(409, "OPERATION_ID_REUSED")
        return key, found

    def save_receipt(self, operation_id, key, result):
        self.session.add(
            SyncReceipt(
                workspace_id=self.workspace.id,
                operation_id=operation_id,
                digest=key,
                result=result,
            )
        )
        return result

    async def require_binding(self, model, identity):
        binding, entity = await self.binding(model, identity)
        if binding is None:
            reject(409, "OBJECT_IDENTITY_UNRESOLVED")
        return binding, entity

    async def business_value(self, value, definition):
        if value is None:
            return None
        kind = definition["type"]
        if kind == "list":
            if not isinstance(value, list):
                reject(422, "EXPECTED_COLLECTION")
            return [await self.business_value(item, definition["item"]) for item in value]
        if kind not in {"reference", "source", "biginteger"}:
            return value
        try:
            identity = int(parse_id.validate_python(value))
        except ValidationError:
            reject(422, "EXPECTED_DECIMAL_ID")
        if kind == "source":
            await self.source(identity)
        if kind == "reference":
            bound = await self.session.scalar(
                select(ExternalObjectBinding).where(
                    ExternalObjectBinding.workspace_id == self.workspace.id,
                    ExternalObjectBinding.business_object_id == identity,
                )
            )
            if bound is None:
                reject(403, "REFERENCE_ACCESS_DENIED")
        return identity

    async def commit(self, request):
        if not self.workspace.can_commit:
            reject(403, "COMMIT_PERMISSION_REQUIRED")
        key, replay = await self.receipt("commit", request)
        if replay is not None:
            return replay.result
        model = await self.model(write=True)
        if str(model.current_revision_id) != request.schema_revision_id:
            reject(409, "SCHEMA_REVISION_CHANGED", revisionId=str(model.current_revision_id))
        objects = set()
        responses = []
        for entry in request.changes:
            binding, entity = await self.require_binding(model, entry.identity)
            if str(binding.business_object_id) != entry.business_object_id:
                reject(409, "OBJECT_BINDING_CHANGED")
            if binding.business_object_id in objects:
                reject(422, "DUPLICATE_OBJECT_CHANGE")
            objects.add(binding.business_object_id)
            current = await self.describe(model, entry.identity, binding, entity)
            definitions = {f["persistentKey"]: f for f in entity["fields"]}
            values, expected, revisions = {}, {}, {}
            for patch in entry.fields:
                definition = definitions.get(patch.persistent_key)
                field = current["objectFields"].get(patch.persistent_key)
                if not field or (
                    field["businessObjectFieldId"] != patch.business_object_field_id
                    or field["fieldVersionId"] != patch.field_version_id
                ):
                    reject(409, "FIELD_BINDING_CHANGED", object=current)
                if definition.get("readonly") or definition["definition"].get("system"):
                    reject(422, "FIELD_READ_ONLY")
                slot = int(patch.business_object_field_id)
                if slot in values:
                    reject(422, "DUPLICATE_FIELD_CHANGE")
                if field["valueId"] != patch.expected_value_id or (
                    definition["definition"]["type"] == "list"
                    and (field["collectionRevision"] or 0) != patch.expected_collection_revision
                ):
                    reject(409, "CANONICAL_VALUE_CHANGED", object=current)
                values[slot] = await self.business_value(patch.value, definition["definition"])
                if entry.identity.target and patch.persistent_key.endswith("_owner"):
                    parent = await self.parent(model, entry.identity)
                    if (
                        patch.persistent_key != local_type(entry.identity.local_type) + "_owner"
                        or values[slot] != parent.business_object_id
                    ):
                        reject(409, "NESTED_OWNER_CONFLICT")
                expected[slot] = int(patch.expected_value_id) if patch.expected_value_id else None
                if patch.expected_collection_revision is not None:
                    revisions[slot] = patch.expected_collection_revision
            await self.data.assign_object_fields_values(
                binding.business_object_id,
                values,
                expected_value_ids=expected,
                expected_collection_revisions=revisions,
            )
            responses.append(await self.describe(model, entry.identity, binding, entity))
        return self.save_receipt(
            request.operation_id,
            key,
            {
                "status": "SYNCED",
                "schemaRevisionId": request.schema_revision_id,
                "operationId": str(request.operation_id),
                "objects": responses,
            },
        )

    async def sync_selector(self, request):
        model = await self.model()
        binding, entity = await self.require_binding(model, request.identity)
        source = await self.source(int(request.source_id))
        if source.type != "HTML":
            reject(422, "HTML_SOURCE_REQUIRED")
        target = request.tree.selector.target
        identity = request.identity
        if target.object_id != identity.local_object_id or (
            (target.target.kind, target.target.id)
            if target.target and target.target.kind != "object"
            else None
        ) != ((identity.target.kind, identity.target.id) if identity.target else None):
            reject(409, "SELECTOR_LOCAL_TARGET_MISMATCH")
        kind = identity.target.kind if identity.target else identity.local_type
        config = manifest_field(kind, target.field)
        current = await self.describe(model, identity, binding, entity)
        field = current["objectFields"].get(config["persistentKey"]) if config else None
        if field is None:
            reject(409, "SELECTOR_FIELD_UNRESOLVED")
        selectors = SelectorService(self.session)
        row = await selectors.selector(request.tree.selector.uuid, lock=True, required=False)
        wanted = SelectorBinding(
            business_entity_field_id=int(field["businessEntityFieldId"]),
            business_object_field_id=int(field["businessObjectFieldId"]),
            source_id=source.id,
        )
        if row is not None and any(
            getattr(row, name) != value for name, value in wanted.model_dump().items()
        ):
            reject(409, "SELECTOR_SERVER_TARGET_MISMATCH")
        existing = {}
        if row is not None:
            tree, _ = await selectors.tree(row)
            existing = {version.uuid: version.status for version in tree.versions}
        if (
            any(
                version.status != "draft" and existing.get(version.uuid, "draft") == "draft"
                for version in request.tree.versions
            )
            and not request.publish_reviewed
        ):
            reject(409, "SELECTOR_REVIEW_CONFIRMATION_REQUIRED")
        tree, revision = await selectors.import_tree(
            request.tree,
            binding=wanted,
            revision=row.revision if row else None,
        )
        return {
            "status": "SYNCED",
            "selectorUuid": str(tree.selector.uuid),
            "revision": str(revision),
            "sourceId": request.source_id,
            "field": field,
            "businessObjectId": str(binding.business_object_id),
        }

    async def capture(self, request):
        key, replay = await self.receipt("capture", request)
        if replay is not None:
            return replay.result
        model = await self.model()
        binding, entity = await self.require_binding(model, request.identity)
        selectors = SelectorService(self.session)
        # Lock Source before Selector to agree with the monitoring processor.
        snapshot = await self.session.get(SourceSnapshot, int(request.source_snapshot_id))
        if snapshot is None:
            reject(404, "SNAPSHOT_NOT_FOUND")
        source = await self.source(snapshot.source_id)
        if source.type != "HTML" or snapshot.page_url != request.page_url:
            reject(422, "SNAPSHOT_PAGE_MISMATCH")
        capture = CaptureService(self.session, commit=False)
        await capture._source(snapshot.source_id)
        selector = await selectors.selector(request.selector_uuid)
        current = await self.describe(model, request.identity, binding, entity)
        if selector.source_id != source.id or not any(
            str(selector.business_object_field_id) == f["businessObjectFieldId"]
            for f in current["objectFields"].values()
        ):
            reject(403, "SELECTOR_ACCESS_DENIED")
        version = await selectors.version(selector.id, request.result.selector_version_uuid)
        if version is None or version.status not in {"active", "superseded"}:
            reject(409, "SELECTOR_VERSION_UNAPPROVED")
        definition = await selectors.definition(version, selector.uuid)
        try:
            validate_selector_evaluation(request.result, definition)
            validate_consensus(request.result, definition)
        except ValueError:
            reject(422, "INVALID_SELECTOR_EVALUATION")
        if request.result.status != "success":
            reject(422, "CAPTURE_REQUIRES_LITERAL")
        evaluation_result = request.result.portable()
        sanitize_diagnostics(evaluation_result)
        run = await capture.create_run(
            capture_dto.CreateRunRequest(
                snapshot_id=snapshot.id,
                extractor_version="firefox-workspace",
            )
        )
        await capture.repo.get_or_create(TokenClass, {"id": "text"}, {"name": "Text"})
        capture_key = f"extension:{self.workspace.id}:{request.operation_id}"
        payload = await SelectorExecutionService(capture)._capture_payload(
            selector,
            request.result.raw_value,
            SimpleNamespace(
                capture_key=capture_key,
                token_class_id="text",
            ),
            "html",
        )
        evaluation = SelectorEvaluation(
            uuid=uuid4(),
            selector_version_id=version.id,
            source_snapshot_id=snapshot.id,
            extraction_run_id=run.id,
            page_url=snapshot.page_url,
            execution_key=capture_key,
            provenance="browser_agent_reported",
            result_json=evaluation_result,
        )
        result = await capture.register_capture(run.id, payload, selector_evaluation=evaluation)
        return self.save_receipt(
            request.operation_id,
            key,
            {
                "status": "DETECTED",
                "extractionRunId": str(run.id),
                "evaluationId": str(evaluation.id),
                "observationIds": [
                    str(row) for row in result.observation_ids_by_client_key.values()
                ],
            },
        )
