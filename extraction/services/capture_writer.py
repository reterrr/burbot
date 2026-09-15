"""Registers one capture inside the caller's savepoint and source lock."""

import hashlib
import json
from datetime import timedelta
from graphlib import TopologicalSorter

from extraction.exceptions import ExtractionConflict, ExtractionValidationError
from extraction.schemas import capture as dto
from extraction.schemas.enums import ObservationStatus
from extraction.schemas.evidence import (
    AnchorElementReference,
    Element,
    ElementHTML,
    ElementPDF,
    ElementXLSX,
    ExtractionIssue,
    FieldSelector,
    GroundTruth,
    ScopeInstance,
    SourceScope,
    TokenClass,
)
from extraction.schemas.models import ConcreteValue, FieldObservation, utc_now
from extraction.services.repositories import ExtractionRepository
from extraction.services.tracking import comparable_value, update_tracking_from_observation
from sources.schemas.models import Source, SourceBusinessObject, SourceObjectFieldTracking
from sources.services.tracking import as_utc


class CaptureWriter:
    def __init__(self, repo: ExtractionRepository, run, snapshot):
        self.repo = repo
        self.run = run
        self.snapshot = snapshot
        self.scopes = {}
        self.elements = {}
        self.instances = {}
        self.scope_requests = {}
        self.instance_requests = {}
        self.element_requests = {}
        self.scope_versions_created = 0

    async def _version_definition(self, model, old, values):
        now = utc_now()
        version = 1
        if old is not None:
            if all(getattr(old, k) == v for k, v in values.items()):
                return old
            version = old.version + 1
            now = max(now, as_utc(old.valid_from) + timedelta(microseconds=1))
            old.valid_to = now
            await self.repo.session.flush()
        return await self.repo.add(model(**values, version=version, valid_from=now))

    async def register_scopes(self, requests):
        """Reparent existing descendants and carry selectors on scope rollover."""
        active, selectors, _ = await self.repo.definitions(self.run.source_id)
        old_by_id = {s.id: s for s in active}
        definitions = {
            s.name: (s, old_by_id[s.parent_scope_id].name if s.parent_scope_id else None)
            for s in active
        }
        self.scope_requests = {s.client_key: s for s in requests}
        for request in requests:
            if request.business_entity_id is not None:
                await self.repo.entity(request.business_entity_id)
            parent_name = (
                self.scope_requests[request.parent_client_key].name
                if request.parent_client_key
                else None
            )
            definitions[request.name] = (request, parent_name)
        old_by_name = {s.name: s for s in active}
        new_by_name = {}
        graph = {name: [parent] if parent else [] for name, (_, parent) in definitions.items()}
        for name in TopologicalSorter(graph).static_order():
            definition, parent_name = definitions[name]
            parent = new_by_name.get(parent_name)
            old = old_by_name.get(name)
            if isinstance(definition, dto.ScopeRequest):
                selector_type = definition.selector.type
                selector_string = definition.selector.value
                confidence = definition.selector.confidence
                discovered = definition.selector.discovered_by
            else:
                selector_type, selector_string = (
                    definition.selector_type,
                    definition.selector_string,
                )
                confidence, discovered = definition.confidence_score, definition.discovered_by
            values = dict(
                source_id=self.run.source_id,
                name=name,
                parent_scope_id=parent.id if parent else None,
                business_entity_id=definition.business_entity_id,
                selector_type=selector_type,
                selector_string=selector_string,
                confidence_score=confidence,
                discovered_by=discovered,
            )
            row = await self._version_definition(SourceScope, old, values)
            if old is None or row.id != old.id:
                self.scope_versions_created += 1
                if old is not None and old.business_entity_id == row.business_entity_id:
                    for selector in selectors:
                        if selector.scope_id == old.id:
                            data = selector.model_dump(
                                exclude={"id", "created_at", "valid_from", "valid_to", "version"}
                            )
                            data["scope_id"] = row.id
                            await self.repo.add(FieldSelector(**data, version=1))
            new_by_name[name] = row
        self.scopes = {r.client_key: new_by_name[r.name] for r in requests}

    async def register_elements(self, requests):
        self.element_requests = {e.client_key: e for e in requests}
        for request in dto.ordered(requests, "element"):
            parent = self.elements.get(request.parent_client_key)
            if parent is not None and parent.element_from != request.element_from:
                raise ExtractionValidationError(
                    "An element parent must use the same document format"
                )
            if (
                parent is not None
                and parent.depth is not None
                and request.depth is not None
                and request.depth <= parent.depth
            ):
                raise ExtractionValidationError("Child depth must be greater than parent depth")
            row = await self.repo.add(
                Element(
                    **request.model_dump(
                        exclude={"client_key", "parent_client_key", "html", "pdf", "xlsx"}
                    ),
                    extraction_run_id=self.run.id,
                    parent_element_id=parent.id if parent else None,
                )
            )
            self.elements[request.client_key] = row
            model, metadata = {
                "HTML": (ElementHTML, request.html),
                "PDF": (ElementPDF, request.pdf),
                "XLSX": (ElementXLSX, request.xlsx),
            }[request.element_from]
            await self.repo.add(model(element_id=row.id, **metadata.model_dump()))

    def _within(self, element_key, root_key):
        while element_key is not None:
            if element_key == root_key:
                return True
            element_key = self.element_requests[element_key].parent_client_key
        return False

    async def register_scope_instances(self, requests):
        self.instance_requests = {i.client_key: i for i in requests}
        for request in dto.ordered(requests, "scope instance"):
            scope = self.scopes[request.scope_client_key]
            parent = self.instances.get(request.parent_client_key)
            if parent is not None:
                parent_request = self.instance_requests[request.parent_client_key]
                if not self._within(
                    request.root_element_client_key, parent_request.root_element_client_key
                ):
                    raise ExtractionValidationError("Scope root is outside its parent occurrence")
            if request.business_object_id is not None:
                obj = await self.repo.object(request.business_object_id)
                if (
                    scope.business_entity_id is None
                    or obj.business_entity_id != scope.business_entity_id
                ):
                    raise ExtractionValidationError(
                        "Scope object belongs to the wrong BusinessEntity"
                    )
            self.instances[request.client_key] = await self.repo.add(
                ScopeInstance(
                    scope_id=scope.id,
                    extraction_run_id=self.run.id,
                    parent_scope_instance_id=parent.id if parent else None,
                    root_element_id=self.elements[request.root_element_client_key].id,
                    occurrence_index=request.occurrence_index,
                    instance_hash=request.instance_hash,
                    confidence=request.confidence,
                )
            )
        root = next(r for r in requests if r.parent_client_key is None)
        if any(not self._within(key, root.root_element_client_key) for key in self.elements):
            raise ExtractionValidationError(
                "Every element must belong to the ROOT document element"
            )

    async def resolve_binding(self, field, object_id, source_field):
        obj = await self.repo.object(object_id)
        if obj.business_entity_id != field.business_entity_id:
            raise ExtractionValidationError("Object belongs to a different entity than the field")
        slot = await self.repo.object_field(object_id, field.id)
        if slot.business_entity_field_id != source_field.business_entity_field_id:
            raise ExtractionValidationError("Object field and source field do not match")
        await self.repo.get_or_create(
            SourceBusinessObject,
            {
                "source_id": source_field.source_id,
                "business_object_id": object_id,
            },
        )
        tracking = await self.repo.current_tracking(source_field.id, slot.id)
        if tracking is None:
            # All binding writers lock Source. The partial unique index is the final guard.
            tracking = await self.repo.add(
                SourceObjectFieldTracking(
                    source_field_tracking_id=source_field.id,
                    business_object_field_id=slot.id,
                )
            )
            source_field.tracking_enabled = True
        if not tracking.tracking_enabled:
            raise ExtractionConflict("Source/object/field tracking is disabled")
        return slot, tracking

    async def register_selector(self, scope, source_field, request):
        if scope.source_id != source_field.source_id:
            raise ExtractionValidationError("Scope and tracked field belong to different sources")
        previous = await self.repo.current_selector(scope.id, source_field.id)
        return await self._version_definition(
            FieldSelector,
            previous,
            dict(
                scope_id=scope.id,
                source_field_tracking_id=source_field.id,
                selector_type=request.type,
                selector_string=request.value,
                confidence_score=request.confidence,
                discovered_by=request.discovered_by,
            ),
        )

    async def register_value(self, request, field, source_field, scope, instance):
        element = self.elements[request.element_client_key]
        await self.repo.get(TokenClass, request.token_class_id, validation=True)
        if request.char_start is not None:
            content = element.text_content
            if (
                content is None
                or request.char_end > len(content)
                or content[request.char_start : request.char_end] != request.raw_value
            ):
                raise ExtractionValidationError(
                    "Character range must select raw_value in element text"
                )
        value = ConcreteValue(
            element_id=element.id,
            source_snapshot_id=self.snapshot.id,
            raw_value=request.raw_value,
            normalized_value=request.normalized_value,
            is_semantic_null=request.is_semantic_null,
            char_start=request.char_start,
            char_end=request.char_end,
            token_class_id=request.token_class_id,
            confidence=request.confidence,
            discovered_by=request.discovered_by,
        )
        value.value_hash = hashlib.sha256(
            json.dumps(comparable_value(value), ensure_ascii=False).encode()
        ).hexdigest()
        await self.repo.add(value)
        instance_request = self.instance_requests[request.scope_instance_client_key]
        object_id = request.business_object_id or instance_request.business_object_id
        if (
            request.business_object_id is not None
            and instance_request.business_object_id is not None
            and request.business_object_id != instance_request.business_object_id
        ):
            raise ExtractionValidationError(
                "Value object conflicts with its scope occurrence object"
            )
        slot = tracking = None
        if object_id is not None:
            slot, tracking = await self.resolve_binding(field, object_id, source_field)
        observation = await self.repo.add(
            FieldObservation(
                extraction_run_id=self.run.id,
                source_field_tracking_id=source_field.id,
                scope_instance_id=instance.id,
                concrete_value_id=value.id,
                source_object_field_tracking_id=tracking.id if tracking else None,
                business_object_id=object_id,
                business_object_field_id=slot.id if slot else None,
                confidence=request.confidence,
                status=ObservationStatus.VALIDATED
                if request.confirmed_by_human
                else ObservationStatus.DETECTED,
                observed_at=self.snapshot.fetched_at,
                validated_at=utc_now() if request.confirmed_by_human else None,
                notes=request.notes,
            )
        )
        if request.supersedes_observation_id is not None:
            await self.supersede(observation, request.supersedes_observation_id)
        if request.confirmed_by_human:
            await self.repo.get_or_create(
                GroundTruth,
                {"field_observation_id": observation.id},
                {"confirmed_at": observation.validated_at},
            )
        changed_id = None
        if tracking is not None:
            successor, changed = await update_tracking_from_observation(
                self.repo, tracking, observation
            )
            if changed:
                changed_id = successor.id
        return observation, changed_id

    async def supersede(self, observation, previous_id):
        if observation.status != ObservationStatus.VALIDATED:
            raise ExtractionValidationError("Only validated interpretations can supersede evidence")
        previous = await self.repo.get(FieldObservation, previous_id, lock=True, validation=True)
        if previous.status in {ObservationStatus.SUPERSEDED, ObservationStatus.REJECTED}:
            raise ExtractionConflict("Observation has already been superseded or rejected")
        if (
            previous.source_field_tracking_id != observation.source_field_tracking_id
            or previous.business_object_field_id != observation.business_object_field_id
        ):
            raise ExtractionValidationError(
                "Superseded observation must describe the same source/object/field"
            )
        if previous.business_object_field_id is None:
            # Occurrence indexes and selector positions are not object identities across runs.
            if previous.scope_instance_id != observation.scope_instance_id:
                raise ExtractionValidationError(
                    "Resolve object identity before superseding across occurrences"
                )
        if as_utc(previous.observed_at) > as_utc(observation.observed_at):
            raise ExtractionValidationError("An older snapshot cannot supersede newer evidence")
        previous.status = ObservationStatus.SUPERSEDED
        observation.supersedes_observation_id = previous.id

    async def write(self, request: dto.CaptureRequest) -> dto.CaptureResponse:
        source = await self.repo.get(Source, self.run.source_id)
        mime_types = {
            "text/html": "HTML",
            "application/xhtml+xml": "HTML",
            "application/pdf": "PDF",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
        }
        mime = (self.snapshot.mime_type or "").split(";", 1)[0].strip().lower()
        document_type = mime_types.get(mime, source.type)
        if any(element.element_from != document_type for element in request.elements):
            raise ExtractionValidationError("Element format does not match the source snapshot")
        allowed = {"HTML": {"CSS", "XPATH"}, "PDF": {"PDF_REGION"}, "XLSX": {"XLSX_RANGE"}}
        allowed_types = allowed[document_type] | {
            "ANCHOR_RELATIVE",
            "TEXT_PATTERN",
            "INDEX_ABSOLUTE",
        }
        recipes = [scope.selector for scope in request.scopes]
        recipes.extend(value.selector for value in request.values if value.selector is not None)
        if any(recipe.type not in allowed_types for recipe in recipes):
            raise ExtractionValidationError("Selector type does not support this document format")
        await self.register_scopes(request.scopes)
        await self.register_elements(request.elements)
        await self.register_scope_instances(request.scope_instances)
        observations, resolved, unresolved, reconciliation, changed = {}, [], [], [], []
        selectors_seen = {}
        record_objects = {}
        for value in request.values:
            instance = self.instances[value.scope_instance_client_key]
            instance_request = self.instance_requests[value.scope_instance_client_key]
            scope = self.scopes[instance_request.scope_client_key]
            field = await self.repo.field(value.business_entity_field_id)
            if (
                scope.business_entity_id is not None
                and scope.business_entity_id != field.business_entity_id
            ):
                raise ExtractionValidationError(
                    "Field belongs to a different entity than its scope"
                )
            if not self._within(value.element_client_key, instance_request.root_element_client_key):
                raise ExtractionValidationError("Value element is outside its scope occurrence")
            object_id = value.business_object_id or instance_request.business_object_id
            if object_id is not None:
                record_key = (instance.id, field.business_entity_id)
                if record_key in record_objects and record_objects[record_key] != object_id:
                    raise ExtractionValidationError(
                        "Fields in one record cannot bind to different objects"
                    )
                record_objects[record_key] = object_id
            source_field = await self.repo.source_field(self.run.source_id, field.id)
            if value.selector is not None:
                selector_key = (scope.id, source_field.id)
                signature = (value.selector.type, value.selector.value)
                if selector_key in selectors_seen and selectors_seen[selector_key] != signature:
                    raise ExtractionValidationError(
                        "Repeated records must share one reusable field selector"
                    )
                selectors_seen[selector_key] = signature
                await self.register_selector(scope, source_field, value.selector)
            observation, changed_id = await self.register_value(
                value, field, source_field, scope, instance
            )
            observations[value.client_key] = observation.id
            (resolved if observation.business_object_id else unresolved).append(observation.id)
            if observation.business_object_id and observation.status == ObservationStatus.VALIDATED:
                reconciliation.append(observation.id)
            if changed_id is not None:
                changed.append(changed_id)
        seen_anchors = set()
        for anchor in request.anchors:
            signature = (
                anchor.anchor_element_client_key,
                anchor.target_element_client_key,
                anchor.relation_kind,
            )
            if signature in seen_anchors:
                raise ExtractionValidationError("Duplicate anchor relationship")
            seen_anchors.add(signature)
            await self.repo.add(
                AnchorElementReference(
                    anchor_element_id=self.elements[anchor.anchor_element_client_key].id,
                    target_element_id=self.elements[anchor.target_element_client_key].id,
                    relation_kind=anchor.relation_kind,
                    relative_offset=anchor.relative_offset,
                    confidence=anchor.confidence,
                )
            )
        for issue in request.issues:
            instance = self.instances.get(issue.scope_instance_client_key)
            if issue.business_entity_field_id is not None:
                field = await self.repo.field(issue.business_entity_field_id)
                if instance is not None:
                    scope_request = self.instance_requests[issue.scope_instance_client_key]
                    scope = self.scopes[scope_request.scope_client_key]
                    if (
                        scope.business_entity_id is not None
                        and scope.business_entity_id != field.business_entity_id
                    ):
                        raise ExtractionValidationError(
                            "Issue field belongs to a different entity than its scope"
                        )
            await self.repo.add(
                ExtractionIssue(
                    extraction_run_id=self.run.id,
                    code=issue.code,
                    message=issue.message,
                    scope_instance_id=instance.id if instance else None,
                    business_entity_field_id=issue.business_entity_field_id,
                )
            )
        return dto.CaptureResponse(
            run_id=self.run.id,
            status="partial" if request.issues else "succeeded",
            scopes_created=self.scope_versions_created,
            observations_created=len(observations),
            scope_ids_by_client_key={k: v.id for k, v in self.scopes.items()},
            scope_instance_ids_by_client_key={k: v.id for k, v in self.instances.items()},
            element_ids_by_client_key={k: v.id for k, v in self.elements.items()},
            observation_ids_by_client_key=observations,
            resolved_observations=resolved,
            unresolved_observations=unresolved,
            reconciliation_observations=reconciliation,
            changed_source_object_fields=changed,
            issues=request.issues,
        )
