"""Apply the offline import through the registered Burbot service owners."""

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from pydantic import AnyHttpUrl, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLTimeout

from business_layer.schemas.models import (
    BusinessEntity,
    BusinessModel,
    BusinessObject,
)
from business_layer.services.data import DataService
from business_layer.services.validation import validate_value, value_key
from extension_sync.contracts import Identity
from extension_sync.identity import IdentityService, external_key
from extension_sync.models import ExternalObjectBinding, SyncReceipt, SyncWorkspace
from extension_sync.schema import MANIFEST, TYPES, manifest_field
from extraction.exceptions import ExtractionConflict, ExtractionError
from extraction.schemas.selector import Selector, SelectorEvaluation, SelectorVersion
from extraction.schemas.selector_api import ClientEvaluation, SelectorBinding
from extraction.schemas.selector_tree import SelectorTree, validate_selector_evaluation
from extraction.services.capture import CaptureService
from extraction.services.selector_execution import SelectorExecutionService
from extraction.services.selectors import SelectorService
from scripts.burbot_sqlite_input import (
    NESTED,
    ROOT_TABLES,
    Report,
    Workspace,
    open_sqlite,
    timestamp,
)
from scripts.burbot_sqlite_sources import SourceCatalog
from sources.exceptions import SourceConflict, SourceError
from sources.schemas.models import SourceBusinessObject, SourceSnapshot

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE = 50
UNNAMED_WORKSPACE = uuid5(NAMESPACE_URL, "https://github.com/reterrr/burbot#legacy-sqlite-seed")
READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
WEBSITE_SEPARATOR = re.compile(r"\s*;\s*(?=https?://)", re.IGNORECASE)


class SeedError(ValueError):
    """An unresolved mapping or import precondition."""


@dataclass(frozen=True)
class PlannedReference:
    local_id: str


@dataclass
class Binding:
    business_object_id: int | None
    fields: dict
    slots: dict
    project_reference: int | PlannedReference | None = None


def message(error):
    if isinstance(error, SQLAlchemyError):
        original = getattr(error, "orig", None)
        diagnostic = getattr(original, "diag", None) or getattr(original, "__cause__", None)
        return getattr(diagnostic, "constraint_name", None) or type(error).__name__
    if isinstance(error, ValidationError):
        return error.errors(include_url=False, include_context=False, include_input=False)
    if isinstance(error, HTTPException):
        return error.detail
    return str(error)


def identity(item):
    target = {"kind": item.kind, "id": item.local_id} if item.kind else None
    return Identity(localObjectId=item.owner, localType=item.root_type, target=target)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def same_value(previous, proposed, definition):
    if isinstance(proposed, PlannedReference):
        return False
    if previous is None or proposed is None:
        return previous is proposed
    if definition["type"] == "list":
        return len(previous) == len(proposed) and all(
            same_value(a, b, definition["item"]) for a, b in zip(previous, proposed, strict=True)
        )
    return value_key(previous, definition) == value_key(proposed, definition)


def compatible_field(config, field):
    expected = "text" if config.get("multiline") else TYPES[config["type"]]
    definition = field["definition"]
    if definition.get("system"):
        return False
    if config["cardinality"] == "many":
        return definition["type"] == "list" and definition["item"]["type"] == expected
    return definition["type"] == expected


def website_url(value):
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value
    ):
        return None
    try:
        url = AnyHttpUrl(value)
    except ValidationError:
        return None
    return str(url) if url.username is None and url.password is None else None


def operator_website_list(value):
    if not isinstance(value, str):
        return None
    separators = list(WEBSITE_SEPARATOR.finditer(value))
    if not separators:
        return None
    if all(match.group() == ";" for match in separators) and website_url(value):
        # An unspaced semicolon in a query or fragment can be part of a single URL.
        url = urlsplit(value)
        if WEBSITE_SEPARATOR.search(url.query) or WEBSITE_SEPARATOR.search(url.fragment):
            return None
    urls = [item.strip() for item in WEBSITE_SEPARATOR.split(value)]
    canonical = {website_url(item) for item in urls}
    primary = urls[0] if len(canonical) == 1 and None not in canonical else None
    return {"original": value, "urls": urls, "primary": primary}


class Seeder:
    def __init__(self, factory, workspace, namespace, *, apply, storage):
        self.factory = factory
        self.workspace = workspace
        self.report = workspace.report
        self.namespace = namespace
        self.apply = apply
        self.catalog = SourceCatalog(workspace, namespace, apply=apply, storage=storage)
        self.bindings = {}
        self.versions = {}
        self.rules_by_selector = dict(workspace.tree_rule_ids)
        self.by_local_id = defaultdict(list)
        self.projects_by_import_key = defaultdict(list)
        self.links = set()
        self.catalog.discover()
        for item in workspace.objects.values():
            self.by_local_id[item.entity_type, item.ref].append(item)
            if item.entity_type == "project" and item.payload.get("importKey"):
                self.projects_by_import_key[item.payload["importKey"]].append(item)
        for rule, row in workspace.rules.items():
            tree = row.get("selectorTree")
            if isinstance(tree, dict) and isinstance(tree.get("selector"), dict):
                identifier = tree["selector"].get("uuid")
                if identifier:
                    self.rules_by_selector.setdefault(identifier, rule)
        for identifier, tree in workspace.trees.items():
            legacy = tree["selector"].get("migration", {}).get("legacyRuleId")
            if legacy:
                self.rules_by_selector.setdefault(identifier, legacy)

    @property
    def created_status(self):
        return "imported" if self.apply else "would_import"

    async def check_database(self, session):
        bind = await session.connection()
        if bind.dialect.name != "postgresql":
            raise SeedError("The target must be PostgreSQL")
        heads = await bind.run_sync(
            lambda conn: MigrationContext.configure(conn).get_current_heads()
        )
        expected = tuple(ScriptDirectory(str(ROOT / "migrations")).get_heads())
        self.report.postgresql.update(alembicRevisions=heads, expectedRevisions=expected)
        if sorted(heads) != sorted(expected):
            raise SeedError("PostgreSQL Alembic revisions do not match this checkout")
        model = await session.scalar(
            select(BusinessModel).where(BusinessModel.key == MANIFEST["key"])
        )
        if model is None or model.current_revision_id is None:
            raise SeedError("Register the Burbot business schema before seeding")
        self.model_id, self.revision = model.id, model.current_revision_id
        namespace = await session.get(SyncWorkspace, self.namespace)
        if namespace is not None and namespace.business_model_id != model.id:
            raise SeedError("The SQLite workspace UUID belongs to another BusinessModel")
        registry = IdentityService(session, namespace)
        self.registry = await registry.registry(model)
        if not self.registry:
            raise SeedError("The Burbot BusinessModel has no registered Firefox entities")
        unbound = await session.scalar(
            select(func.count())
            .select_from(BusinessObject)
            .join(BusinessEntity, BusinessEntity.id == BusinessObject.business_entity_id)
            .where(
                BusinessEntity.business_model_id == model.id,
                BusinessObject.archived_at.is_(None),
                ~select(ExternalObjectBinding.business_object_id)
                .where(
                    ExternalObjectBinding.business_object_id == BusinessObject.id,
                )
                .exists(),
            )
        )
        self.report.postgresql.update(
            businessModelId=str(model.id),
            businessSchemaRevisionId=str(self.revision),
            workspaceUuid=str(self.namespace),
            unboundBusinessObjects=unbound,
        )
        if not self.apply:
            status = "would_import" if namespace is None else "reused"
            self.report.add(status, "workspace_identity", str(self.namespace))

    async def lock_model(self, session):
        model = await session.get(BusinessModel, self.model_id, with_for_update=True)
        if model is None or model.current_revision_id != self.revision:
            raise SeedError("The registered Burbot schema changed during the import")
        return model

    async def establish_workspace(self):
        async with self.factory.begin() as session:
            # Serialize creation, including the case where the namespace does not exist yet.
            await session.execute(text("SELECT pg_advisory_xact_lock(1465030881, 102)"))
            namespace = await session.get(SyncWorkspace, self.namespace, with_for_update=True)
            await self.lock_model(session)
            if namespace is not None and namespace.business_model_id != self.model_id:
                raise SeedError("The SQLite workspace UUID belongs to another BusinessModel")
            if namespace is None:
                session.add(
                    SyncWorkspace(
                        id=self.namespace,
                        business_model_id=self.model_id,
                        enabled=False,
                        token_digest=digest(["offline-sqlite-seed", str(self.namespace)]),
                    )
                )
        status = "imported" if namespace is None else "reused"
        self.report.add(status, "workspace_identity", str(self.namespace))

    async def run(self):
        async with self.factory.begin() as session:
            await session.execute(text(READ_ONLY))
            await self.check_database(session)
            if not self.apply:
                await self.run_stages(read_session=session)
                return
        await self.establish_workspace()
        await self.run_stages()

    async def run_stages(self, read_session=None):
        await self.stage(
            "stored_files",
            sorted(self.workspace.blobs.items()),
            self.catalog.preserve_file,
            lambda entry: entry,
            read_session,
        )
        await self.stage(
            "sources",
            sorted(self.catalog.groups.items()),
            lambda session, entry: self.catalog.register(session, *entry),
            lambda entry: (entry[0][1], dict(references=list(entry[1]))),
            read_session,
        )
        for kind in (*ROOT_TABLES, *NESTED):
            records = [item for item in self.workspace.objects.values() if item.entity_type == kind]
            await self.stage(
                kind,
                sorted(records, key=lambda item: (item.owner, item.ref)),
                self.import_object,
                lambda item: (item.ref, item.payload),
                read_session,
            )
        await self.stage(
            "selectors",
            sorted(self.workspace.trees.items()),
            self.import_selector,
            lambda entry: entry,
            read_session,
        )
        await self.stage(
            "selector_evaluations",
            sorted(self.workspace.evaluations.items()),
            self.import_evaluation,
            lambda entry: entry,
            read_session,
        )
        self.collect_provenance()
        await self.stage(
            "source_associations",
            sorted(self.links, key=repr),
            self.link_source,
            lambda entry: (entry[0][0], list(entry[1])),
            read_session,
        )

    async def stage(self, table, rows, consume, describe, read_session):
        for group in batched(rows, BATCH_SIZE, strict=False):
            if read_session is not None:
                for item in group:
                    await self.record(read_session, table, item, consume, describe)
                continue
            start = len(self.report.entries)
            try:
                async with self.factory.begin() as session:
                    namespace = await session.get(
                        SyncWorkspace,
                        self.namespace,
                        with_for_update=True,
                    )
                    if namespace is None or namespace.business_model_id != self.model_id:
                        raise SeedError("The import workspace changed during the import")
                    await self.lock_model(session)
                    for item in group:
                        await self.record(session, table, item, consume, describe)
            except (SQLAlchemyError, SeedError, OSError):
                for entry in self.report.entries[start:]:
                    if entry["status"] == "imported":
                        entry.update(status="failed", reason="BATCH_ROLLED_BACK")
                raise

    async def record(self, session, table, item, consume, describe):
        start = len(self.report.entries)
        try:
            async with session.begin_nested():
                await consume(session, item)
                await session.flush()
        except (
            SourceError,
            ExtractionError,
            HTTPException,
            SQLAlchemyError,
            ValueError,
            TypeError,
            KeyError,
        ) as error:
            if isinstance(error, SQLTimeout) or getattr(error, "connection_invalidated", False):
                raise
            del self.report.entries[start:]
            local_id, payload = describe(item)
            conflict = isinstance(error, (SourceConflict, ExtractionConflict)) or (
                isinstance(error, HTTPException) and error.status_code == 409
            )
            self.report.add(
                "conflict" if conflict else "failed",
                table,
                local_id,
                message(error),
                payload=payload,
            )

    async def receipt(self, session, category, key, payload):
        identifier = uuid5(self.namespace, f"sqlite-seed:{category}:{key}")
        existing = await session.get(SyncReceipt, (self.namespace, identifier))
        signature = digest(payload)
        if existing is not None and existing.digest != signature:
            self.report.add(
                "conflict",
                category,
                key,
                "LOCAL_PROVENANCE_CHANGED",
                existing=existing.result,
                payload=payload,
            )
        elif self.apply and existing is None:
            session.add(
                SyncReceipt(
                    workspace_id=self.namespace,
                    operation_id=identifier,
                    digest=signature,
                    result={"operation": "sqlite-seed", **payload},
                )
            )
        return str(identifier)

    async def object_binding(self, session, item, key):
        if item.kind == "operator_assignment" and item.values.get("operatorId"):
            assignment = json.dumps(
                [item.owner, str(item.values["operatorId"])],
                ensure_ascii=True,
                separators=(",", ":"),
            )
            op_id = uuid5(self.namespace, f"sqlite-seed:operator_assignment:{assignment}")
            previous = await session.get(SyncReceipt, (self.namespace, op_id))
            if previous is not None and previous.result["externalObjectId"] != key:
                # The normalized-only and serialized representations can have different
                # local keys for the same (owner, operator) pair.
                old_key = previous.result["externalObjectId"]
                self.report.add(
                    "conflict",
                    item.table,
                    item.ref,
                    "ASSIGNMENT_ID_CHANGED",
                    externalObjectId=key,
                    existingExternalObjectId=old_key,
                )
                key = old_key
        else:
            assignment = None
        row = await session.get(ExternalObjectBinding, (self.namespace, key))
        return row, key, assignment

    async def import_object(self, session, item):
        if item.kind and (item.owner, None, None) not in self.bindings:
            raise SeedError("PARENT_OBJECT_UNRESOLVED")
        entry = self.registry.get(item.entity_type)
        if entry is None:
            raise SeedError("ENTITY_NOT_REGISTERED")
        fields = {field["persistentKey"]: field for field in entry["fields"]}
        artifact = (
            self.catalog.artifact(("file_sources", item.ref))
            if item.kind == "file_source"
            else None
        )
        if item.kind == "file_source" and item.root_type == "operator":
            owner_field = fields.get("operator_owner")
            if (
                owner_field is None
                or not compatible_field(
                    manifest_field("file_source", "operator_owner"), owner_field
                )
                or owner_field["reference"] != self.registry["operator"]["key"]
            ):
                self.report.add(
                    "pending",
                    item.table,
                    item.ref,
                    "OPERATOR_FILE_OWNER_FIELD_UNREGISTERED",
                    localObjectId=item.owner,
                    requiredField="DocumentFile.operator_owner",
                    payload=item.payload,
                    storedFile=artifact.reference() if artifact else None,
                )
                return
        entity_id = int(entry["businessEntityId"])
        key = external_key(identity(item))
        bound, key, assignment = await self.object_binding(session, item, key)
        if bound is not None and bound.business_entity_id != entity_id:
            raise SeedError("EXTERNAL_ID_ENTITY_MISMATCH")
        service = DataService(session)
        existing = await service.get_object(bound.business_object_id) if bound else None
        if existing is not None and existing.archived_at is not None:
            raise HTTPException(409, "EXTERNAL_OBJECT_IS_ARCHIVED")
        slots = (
            {field.business_entity_field_id: field for field in existing.fields}
            if existing is not None
            else {}
        )
        project_owner = await self.funding_project_owner(service, item)
        changes, metadata = self.plan_fields(item, fields, slots, project_owner)
        project_reference = (
            self.business_field_value(fields, slots, "project_id", changes)
            if (item.entity_type == "recruitment")
            else None
        )
        created = bound is None
        object_id = bound.business_object_id if bound else None
        created_at = None
        if item.payload.get("createdAt"):
            try:
                created_at = timestamp(item.payload["createdAt"])
            except (ValueError, TypeError):
                self.report.add(
                    "unsupported",
                    item.table,
                    item.ref,
                    "INVALID_ORIGINAL_CREATED_AT",
                    value=item.payload["createdAt"],
                )
        if self.apply:
            if created:
                result = await service.create_object(entity_id, apply_defaults=False)
                object_id = result.object_id
                if created_at is not None:
                    row = await session.get(BusinessObject, object_id)
                    row.created_at = created_at
                session.add(
                    ExternalObjectBinding(
                        workspace_id=self.namespace,
                        external_object_id=key,
                        business_model_id=self.model_id,
                        business_entity_id=entity_id,
                        business_object_id=object_id,
                    )
                )
                await session.flush()
                slot_ids = result.object_fields
            else:
                active_ids = {int(field["businessEntityFieldId"]) for field in fields.values()}
                if active_ids - slots.keys():
                    slot_ids = (await service.sync_object_fields(object_id)).object_fields
                else:
                    slot_ids = {field_id: slot.object_field_id for field_id, slot in slots.items()}
            if changes:
                write = {slot_ids[field_id]: value for field_id, value in changes.items()}
                expected = dict.fromkeys(write)
                collections = {
                    slot_ids[int(field["businessEntityFieldId"])]: 0
                    for field in fields.values()
                    if field["definition"]["type"] == "list"
                    and int(field["businessEntityFieldId"]) in changes
                }
                await service.assign_object_fields_values(
                    object_id,
                    write,
                    expected_value_ids=expected,
                    expected_collection_revisions=collections,
                )
        else:
            slot_ids = {field_id: slot.object_field_id for field_id, slot in slots.items()}
        provenance = {
            "externalObjectId": key,
            "identity": identity(item).portable(),
            "businessObjectId": str(object_id) if object_id is not None else None,
            "metadata": {
                name: value for name, value in metadata.items() if name != "operatorWebsite"
            },
        }
        receipt_id = (
            await self.receipt(
                session,
                "operator_assignment" if assignment else "object_provenance",
                assignment or key,
                provenance,
            )
            if object_id is not None
            else None
        )
        websites = metadata.get("operatorWebsite")
        if websites and object_id is not None:
            await self.receipt(
                session,
                "operator_websites",
                key,
                {
                    "externalObjectId": key,
                    "businessObjectId": str(object_id),
                    "operatorWebsite": websites,
                },
            )
        stored_file = artifact.reference() if artifact else None
        if stored_file and object_id is not None:
            url_field = fields.get("url")
            url_field_id = int(url_field["businessEntityFieldId"]) if url_field else None
            slot = slots.get(url_field_id)
            if url_field_id in changes or (slot and slot.value == item.values.get("url")):
                await self.receipt(
                    session,
                    "file_artifact",
                    key,
                    {
                        "externalObjectId": key,
                        "businessObjectId": str(object_id),
                        "originalUrl": item.values["url"],
                        "storedFile": stored_file,
                    },
                )
        await session.flush()
        self.bindings[item.key] = Binding(object_id, fields, slot_ids, project_reference)
        status = self.created_status if created or changes else "reused"
        self.report.add(
            status,
            item.table,
            item.ref,
            localObjectId=item.owner,
            kind=item.entity_type,
            externalObjectId=key,
            importKey=item.payload.get("importKey"),
            businessObjectId=provenance["businessObjectId"],
            createdObject=created,
            fieldWrites=len(changes),
            provenanceReceipt=receipt_id,
            preservedMetadata=metadata,
            **({"storedFile": stored_file} if stored_file else {}),
        )

    def project_record(self, value):
        if value in (None, ""):
            return None
        key = str(value)
        exact = self.workspace.objects.get((key, None, None))
        if exact is not None and exact.entity_type == "project":
            return exact
        candidates = self.projects_by_import_key.get(key, [])
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def business_field_value(fields, slots, key, changes=None):
        field = fields.get(key)
        if field is None:
            return None
        field_id = int(field["businessEntityFieldId"])
        if changes is not None and field_id in changes:
            return changes[field_id]
        slot = slots.get(field_id)
        return slot.value if slot else None

    def object_reference(self, item):
        destination = self.bindings[item.key].business_object_id
        return destination if destination is not None else PlannedReference(item.ref)

    async def funding_project_owner(self, service, item):
        category_id = item.values.get("service_category_id")
        if item.kind != "funding" or not category_id:
            return None
        owner = self.workspace.objects[(item.owner, None, None)]
        if owner.entity_type != "recruitment":
            return None
        project = self.project_record(owner.values.get("project_id"))
        if project is None or project.key not in self.bindings:
            return None
        category = self.bindings.get((project.owner, "service_category", str(category_id)))
        if category is None:
            return None
        expected_project = self.object_reference(project)
        bound_owner = self.bindings[owner.key]
        if not self.apply:
            return project.owner if bound_owner.project_reference == expected_project else None

        # The batch holds the model lock used by canonical field writes.
        actual = await service.get_object(bound_owner.business_object_id)
        if actual.archived_at is not None:
            raise SeedError("PARENT_OBJECT_UNRESOLVED")
        slots = {field.business_entity_field_id: field for field in actual.fields}
        if self.business_field_value(bound_owner.fields, slots, "project_id") != expected_project:
            return None
        actual_category = await service.get_object(category.business_object_id)
        slots = {field.business_entity_field_id: field for field in actual_category.fields}
        if (
            actual_category.archived_at is None
            and self.business_field_value(category.fields, slots, "project_owner")
            == expected_project
        ):
            return project.owner
        return None

    def plan_fields(self, item, fields, slots, project_owner):
        metadata = {
            key: value
            for key, value in item.payload.items()
            if key not in {"id", "type", "values", "objectId"}
            and (not item.kind or not manifest_field(item.entity_type, key))
        }
        values = dict(item.values)
        if item.entity_type == "operator":
            for old, new in (("adres", "address"), ("telefon", "phone")):
                if old in values:
                    values.setdefault(new, values[old])
                    metadata[old] = values.pop(old)
            websites = operator_website_list(values.get("website"))
            if websites is not None:
                metadata["operatorWebsite"] = websites
                values.pop("website")
                if websites["primary"] is not None:
                    values["website"] = websites["primary"]
                self.report.add(
                    "preserved",
                    item.table,
                    item.ref,
                    "OPERATOR_WEBSITE_LIST",
                    field="website",
                    urlCount=len(websites["urls"]),
                    primarySelected=websites["primary"] is not None,
                )
        if item.kind:
            owner_name = self.workspace.objects[(item.owner, None, None)].entity_type + "_owner"
            for key in fields:
                if not key.endswith("_owner"):
                    continue
                current = slots.get(int(fields[key]["businessEntityFieldId"]))
                if key != owner_name and (
                    values.get(key) is not None
                    or (current is not None and current.value is not None)
                ):
                    raise HTTPException(409, "NESTED_OBJECT_HAS_DIFFERENT_OWNER")
            if owner_name not in fields or values.get(owner_name) not in (None, item.owner):
                raise HTTPException(409, "NESTED_OWNER_FIELD_UNAVAILABLE_OR_CONFLICTING")
            values[owner_name] = item.owner
        else:
            owner_name = None
        if item.kind == "document" and values.get("original_file_source_id"):
            original, related = (
                values["original_file_source_id"],
                values.get("source_file_source_ids"),
            )
            if related is None or (isinstance(related, list) and original not in related):
                values["source_file_source_ids"] = [*(related or []), original]
        if item.kind == "file_source":
            if "source" in values:
                metadata["localSourceValue"] = values.pop("source")
            link = ("file_sources", item.ref)
            if self.catalog.keys.get(link) in self.catalog.ids:
                value = self.catalog.source_id(link)
                values["source"] = value if value is not None else PlannedReference(item.ref)
        selected = {}
        for key, raw in values.items():
            config = manifest_field(item.kind or item.root_type, key)
            if config is None:
                if key not in {"id", "objectId"}:
                    metadata[key] = raw
                continue
            persistent = config["persistentKey"]
            if persistent not in fields or not compatible_field(config, fields[persistent]):
                retained = raw.local_id if isinstance(raw, PlannedReference) else raw
                self.report.add(
                    "unsupported",
                    item.table,
                    item.ref,
                    "FIELD_UNAVAILABLE",
                    field=key,
                    value=retained,
                )
                metadata.setdefault("unmappedValues", {})[key] = retained
                continue
            if persistent in selected and selected[persistent] != raw:
                self.report.add(
                    "conflict",
                    item.table,
                    item.ref,
                    "ALIASED_VALUES_DIFFER",
                    field=persistent,
                    value=raw,
                    other=selected[persistent],
                )
                metadata.setdefault("unmappedValues", {})[key] = raw
                continue
            selected[persistent] = raw
        required = {owner_name} if owner_name else set()
        if item.kind == "operator_assignment":
            required.update(("operatorId", "operatorType"))
        if item.kind == "geography":
            required.update(("type", "role", "value"))
            if values.get("operatorId"):
                required.add("operatorId")
        if item.kind == "funding" and values.get("service_category_id"):
            required.add("service_category_id")
        unresolved = sorted(key for key in required if selected.get(key) in (None, ""))
        if unresolved:
            raise SeedError(f"REQUIRED_MAPPING_UNAVAILABLE: {', '.join(unresolved)}")
        changes = {}
        for key, raw in selected.items():
            field = fields[key]
            definition = field["definition"]
            identifier = int(field["businessEntityFieldId"])
            try:
                value = self.transform(item, field, definition, raw, project_owner)
            except (ValueError, TypeError) as error:
                if key in required:
                    raise SeedError(f"{key}: {error}") from error
                self.report.add(
                    "failed", item.table, item.ref, message(error), field=key, value=raw
                )
                continue
            current = slots.get(identifier)
            if current is not None and current.value_id is not None:
                if not same_value(current.value, value, definition):
                    if key == owner_name:
                        raise HTTPException(409, "NESTED_OBJECT_HAS_DIFFERENT_OWNER")
                    self.report.add(
                        "conflict",
                        item.table,
                        item.ref,
                        "CANONICAL_VALUE_DIFFERS",
                        field=key,
                        localValue=raw,
                        canonicalValue=current.value,
                        businessObjectFieldId=str(current.object_field_id),
                    )
            else:
                changes[identifier] = value
        return changes, metadata

    def transform(self, item, field, definition, value, project_owner):
        kind = definition["type"]
        if value == "" and kind not in {"string", "text"}:
            value = None  # The extension uses an empty control to clear typed fields.
        if value is not None:
            if kind == "list" and isinstance(value, list):
                value = [
                    self.transform(item, field, definition["item"], entry, project_owner)
                    for entry in value
                ]
                if any(isinstance(entry, PlannedReference) for entry in value):
                    if len(value) != len(set(value)):
                        raise SeedError("DUPLICATE_COLLECTION_REFERENCE")
                    return value
            elif kind == "reference":
                target = field["references"]
                candidates = self.by_local_id.get((target, str(value)), [])
                if item.entity_type == "recruitment" and field["persistentKey"] == "project_id":
                    project = self.project_record(value)
                    candidates = [project] if project is not None else []
                if target in NESTED:
                    owners = {item.owner}
                    if (
                        project_owner
                        and item.kind == "funding"
                        and field["persistentKey"] == "service_category_id"
                    ):
                        owners.add(project_owner)
                    candidates = [entry for entry in candidates if entry.owner in owners]
                if len(candidates) != 1 or candidates[0].key not in self.bindings:
                    raise SeedError(f"UNRESOLVED_{target.upper()}_REFERENCE")
                value = self.object_reference(candidates[0])
            elif kind == "source" and field["persistentKey"] != "source":
                raise SeedError("UNMAPPED_SOURCE_REFERENCE")
            elif kind == "enum":
                value = field.get("aliases", {}).get(str(value), value)
                if (
                    field.get("numeric")
                    and isinstance(value, str)
                    and value.isascii()
                    and value.isdigit()
                ):
                    value = int(value)
            elif kind == "boolean" and type(value) is int and value in (0, 1):
                value = bool(value)
            elif kind == "decimal" and type(value) in (float, int):
                value = str(value)
        if not isinstance(value, PlannedReference):
            validate_value(value, definition)
        return value

    async def import_selector(self, session, entry):
        identifier, payload = entry
        tree = SelectorTree.model_validate(payload).canonical_order()
        header = tree.selector
        target = header.target
        nested = target.target if target.target and target.target.kind != "object" else None
        key = (target.object_id, nested.kind if nested else None, nested.id if nested else None)
        item = self.workspace.objects.get(key)
        legacy_document = nested and nested.kind == "document" and item is None
        resolved_target = {}
        if legacy_document:
            # Firefox's legacy capture path locates a document by owner and type key.
            candidates = [
                row
                for row in self.workspace.objects.values()
                if row.kind == "document"
                and row.owner == target.object_id
                and row.values.get("document_type_key") == nested.id
            ]
            if len(candidates) == 1:
                item = candidates[0]
                key = item.key
                resolved_target = {"documentTypeKey": nested.id, "resolvedDocumentId": item.ref}
            if key not in self.bindings:
                self.report.add(
                    "pending",
                    "selectors",
                    identifier,
                    "LEGACY_DOCUMENT_TARGET_UNRESOLVED",
                    candidateDocumentIds=sorted(row.ref for row in candidates),
                    payload=payload,
                )
                return
        binding = self.bindings.get(key)
        if binding is None:
            raise SeedError("SELECTOR_TARGET_OBJECT_UNRESOLVED")
        config = manifest_field(item.kind or item.root_type, target.field)
        field = binding.fields.get(config["persistentKey"]) if config is not None else None
        if field is None or not compatible_field(config, field):
            if legacy_document:
                self.report.add(
                    "pending",
                    "selectors",
                    identifier,
                    "LEGACY_DOCUMENT_TARGET_FIELD_UNAVAILABLE",
                    payload=payload,
                    **resolved_target,
                )
                return
            raise SeedError("SELECTOR_TARGET_FIELD_UNRESOLVED")
        entity_field_id = int(field["businessEntityFieldId"])
        object_field_id = binding.slots.get(entity_field_id)
        source_id, source_available = self.catalog.selector_source(
            identifier,
            header.portable(),
            self.rules_by_selector.get(identifier),
        )
        if (header.page_url or header.source_uuid) and not source_available:
            raise SeedError("SELECTOR_SOURCE_UNRESOLVED")
        service = SelectorService(session)
        query = select(Selector).where(Selector.uuid == header.uuid)
        row = await session.scalar(query.with_for_update() if self.apply else query)
        if row is not None:
            before, versions = await service.tree(row)
            if (
                row.business_entity_field_id != entity_field_id
                or row.business_object_field_id != object_field_id
                or row.source_id != source_id
                or before.model_dump(mode="json") != tree.model_dump(mode="json")
            ):
                raise ExtractionConflict("Existing SelectorTree or target differs")
        else:
            versions = []
            snapshots = await self.find_snapshots(session, source_id, tree)
            if self.apply:
                if object_field_id is None:
                    raise SeedError("SELECTOR_TARGET_SLOT_UNRESOLVED")
                await service.import_tree(
                    tree,
                    binding=SelectorBinding(
                        business_entity_field_id=entity_field_id,
                        business_object_field_id=object_field_id,
                        source_id=source_id,
                    ),
                    snapshots=snapshots,
                )
                stored = await service.selector(header.uuid)
                _, versions = await service.tree(stored)
        if row is not None or self.apply:
            snapshots = {
                definition.created_from_snapshot_uuid: stored.created_from_snapshot_id
                for definition, stored in zip(tree.versions, versions, strict=True)
                if stored.created_from_snapshot_id is not None
            }
        version_ids = {stored.uuid: stored.id for stored in versions}
        for definition in tree.versions:
            snapshot = definition.created_from_snapshot_uuid
            if snapshot and snapshot not in snapshots:
                self.report.add(
                    "pending",
                    "selector_versions",
                    str(definition.uuid),
                    "SNAPSHOT_UUID_UNRESOLVED",
                    snapshotUuid=str(snapshot),
                )
            self.versions[str(definition.uuid)] = (
                header.uuid,
                version_ids.get(definition.uuid),
                definition,
            )
        self.report.add(
            "reused" if row is not None else self.created_status,
            "selectors",
            identifier,
            businessObjectFieldId=str(object_field_id) if object_field_id is not None else None,
            sourceId=str(source_id) if source_id is not None else None,
            versionUuids=[str(version.uuid) for version in tree.versions],
            activeVersionUuid=str(header.active_version_uuid)
            if header.active_version_uuid
            else None,
            **resolved_target,
        )

    async def find_snapshots(self, session, source_id, tree):
        result = {}
        if source_id is not None:
            for uuid in {version.created_from_snapshot_uuid for version in tree.versions} - {None}:
                matches = list(
                    await session.scalars(
                        select(SourceSnapshot.id)
                        .distinct()
                        .join(
                            SelectorVersion,
                            SelectorVersion.created_from_snapshot_id == SourceSnapshot.id,
                        )
                        .where(
                            SourceSnapshot.source_id == source_id,
                            SelectorVersion.metadata_json["createdFromSnapshotUuid"].as_string()
                            == str(uuid),
                        )
                    )
                )
                if len(matches) == 1:
                    result[uuid] = matches[0]
        return result

    async def import_evaluation(self, session, entry):
        identifier, payload = entry
        request = ClientEvaluation(
            uuid=identifier, page_url=payload["pageUrl"], result=payload["result"]
        )
        evaluated_at = timestamp(payload["evaluatedAt"])
        version_uuid = str(request.result.selector_version_uuid)
        if payload.get("versionUuid", version_uuid) != version_uuid:
            raise SeedError("EVALUATION_VERSION_DIFFERS_FROM_SQLITE_REFERENCE")
        target = self.versions.get(version_uuid)
        if target is None:
            raise SeedError("EVALUATION_VERSION_UNRESOLVED")
        selector_uuid, version_id, definition = target
        validate_selector_evaluation(request.result, definition)
        query = select(SelectorEvaluation).where(SelectorEvaluation.uuid == request.uuid)
        existing = await session.scalar(query.with_for_update() if self.apply else query)
        if existing is not None:
            if (
                existing.provenance != "client_reported"
                or existing.selector_version_id != version_id
                or existing.evaluated_at != evaluated_at
                or existing.page_url != request.page_url
                or existing.result_json != request.result.portable()
            ):
                raise ExtractionConflict("Existing evaluation has different provenance or result")
        elif self.apply:
            service = SelectorExecutionService(CaptureService(session, commit=False))
            await service.record_client(selector_uuid, request)
            row = await session.scalar(query)
            row.evaluated_at = evaluated_at
        self.report.add(
            "reused" if existing is not None else self.created_status,
            "selector_evaluations",
            identifier,
            provenance="client_reported",
            selectorVersionUuid=version_uuid,
        )

    def collect_provenance(self):
        object_sources = defaultdict(set)
        linked_rules = {rule for rule in self.rules_by_selector.values()}
        for identifier, item in self.workspace.imports.items():
            key = ("import_sources", identifier)
            artifact = self.catalog.artifact(key)
            self.report.add(
                "pending",
                "import_sources",
                identifier,
                "IMPORT_CAPTURE_IS_NOT_A_SOURCE_SNAPSHOT",
                sourceId=self.catalog.source_id(key),
                payload=item,
                **({"storedFile": artifact.reference()} if artifact else {}),
            )
        for identifier, rule in self.workspace.rules.items():
            if identifier not in linked_rules:
                self.report.add(
                    "pending",
                    "extraction_rules",
                    identifier,
                    "NO_PORTABLE_SELECTOR_TREE",
                    payload=rule,
                )
            elif set(rule) - {"id", "objectId", "field", "selectorTree", "selectorEvaluations"}:
                payload = {
                    key: value
                    for key, value in rule.items()
                    if key not in {"selectorTree", "selectorEvaluations"}
                }
                self.report.add("preserved", "extraction_rules", identifier, payload=payload)
        for key, item in self.workspace.objects.items():
            if item.kind is None:
                object_sources[key].add(("object_source", item.owner))
                for evidence in (item.payload.get("evidence") or {}).values():
                    for proof in evidence:
                        object_sources[key].add(("import_sources", proof.get("sourceId")))
                if item.payload.get("evidence"):
                    self.report.add(
                        "pending",
                        "workspace_objects.evidence",
                        item.owner,
                        "NO_VERIFIABLE_SNAPSHOT_OR_OBSERVATION",
                        payload=item.payload["evidence"],
                    )
            elif item.kind == "file_source":
                object_sources[key].update(
                    {
                        ("file_sources", item.ref),
                        ("file_page", item.ref),
                        ("file_source_provenance", item.ref),
                    }
                )
                object_sources[(item.owner, None, None)].update(object_sources[key])
            elif item.kind == "document":
                object_sources[key].add(("document_provenance", item.ref))
        for table, entries in (
            ("field_evidence", self.workspace.evidence),
            ("workspace_state.importTargetEvidence", self.workspace.target_evidence),
        ):
            for identifier, proof in entries.items():
                owner = str(proof.get("objectId"))
                target = proof.get("target") or {}
                key = (
                    (owner, target["kind"], str(target["id"]))
                    if target.get("kind")
                    not in (
                        None,
                        "object",
                    )
                    else (owner, None, None)
                )
                source_key = (
                    ("field_evidence", identifier)
                    if table == "field_evidence"
                    else (
                        "import_sources",
                        proof.get("sourceId"),
                    )
                )
                object_sources[key].add(source_key)
                self.report.add(
                    "pending",
                    table,
                    identifier,
                    "NO_VERIFIABLE_SNAPSHOT_OR_OBSERVATION",
                    sourceId=self.catalog.source_id(source_key),
                    payload=proof,
                )
        for item, keys in object_sources.items():
            for source in keys:
                canonical = self.catalog.keys.get(source)
                if item in self.bindings and canonical in self.catalog.ids:
                    self.links.add((item, canonical))

    async def link_source(self, session, entry):
        key, source = entry
        object_id = self.bindings[key].business_object_id
        source_id = self.catalog.ids[source]
        present = (
            await session.get(SourceBusinessObject, (source_id, object_id))
            if source_id is not None and object_id is not None
            else None
        )
        created = present is None
        if created and self.apply:
            row = (
                insert(SourceBusinessObject)
                .values(
                    source_id=source_id,
                    business_object_id=object_id,
                )
                .on_conflict_do_nothing()
                .returning(SourceBusinessObject.source_id)
            )
            created = await session.scalar(row) is not None
        self.report.add(
            self.created_status if created else "reused",
            "source_associations",
            key[0],
            target=list(key),
            source=list(source),
            sourceId=str(source_id) if source_id else None,
            businessObjectId=str(object_id) if object_id else None,
        )


async def seed(factory, path, *, apply=False, workspace_uuid=None, storage=None, report=None):
    report = report if report is not None else Report(apply=apply)
    try:
        with open_sqlite(path) as db:
            workspace = Workspace(db, report)
            workspace.read()
            if (
                workspace_uuid
                and workspace.workspace_uuid
                and workspace_uuid != workspace.workspace_uuid
            ):
                raise SeedError("--workspace-uuid conflicts with the UUID recorded in SQLite")
            namespace = workspace_uuid or workspace.workspace_uuid or UNNAMED_WORKSPACE
            report.sqlite["workspaceUuidOrigin"] = (
                "sqlite"
                if workspace.workspace_uuid
                else "argument"
                if workspace_uuid
                else "legacy-default"
            )
            await Seeder(factory, workspace, namespace, apply=apply, storage=storage).run()
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, SQLAlchemyError) as error:
        report.add("failed", "preflight_or_batch", reason=message(error))
    return report
