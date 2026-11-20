"""Resolve scoped external identities and their current field slots."""

import hashlib
import json
import secrets

from fastapi import HTTPException
from sqlalchemy import select

from business_layer.schemas.models import BusinessModel, BusinessObject
from business_layer.services.data import DataService
from business_layer.services.entities import EntitiesService
from extension_sync.models import ExternalObjectBinding, SyncSourceGrant, SyncWorkspace
from extension_sync.schema import ALIASES, DEFINITIONS, local_type, wire_id
from sources.schemas.models import Source


def reject(status, code, **detail):
    raise HTTPException(status, detail={"code": code, **detail})


def token_digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def authenticate(session, token, workspace_uuid=None, *, lock=True):
    if not token or len(token) != 43:
        reject(401, "INVALID_SYNC_TOKEN")
    query = select(SyncWorkspace).where(
        SyncWorkspace.token_digest == token_digest(token), SyncWorkspace.enabled.is_(True)
    )
    workspace = await session.scalar(query.with_for_update() if lock else query)
    if workspace is None:
        reject(401, "INVALID_SYNC_TOKEN")
    if workspace_uuid is not None and workspace.id != workspace_uuid:
        reject(403, "WORKSPACE_ACCESS_DENIED")
    return workspace


async def provision(
    session, workspace_id, *, can_create, can_bind_existing, can_commit, source_ids, rotate=False
):
    model = await session.scalar(select(BusinessModel).where(BusinessModel.key == "burbot"))
    if model is None or model.current_revision_id is None:
        raise ValueError("Apply the Burbot schema before provisioning a workspace.")
    workspace = await session.get(SyncWorkspace, workspace_id, with_for_update=True)
    if workspace is not None and (not rotate or workspace.business_model_id != model.id):
        raise ValueError("Workspace already exists. Explicitly rotate to issue a new token.")
    token = secrets.token_urlsafe(32)
    if workspace is None:
        workspace = SyncWorkspace(id=workspace_id, business_model_id=model.id)
        session.add(workspace)
    workspace.token_digest = token_digest(token)
    workspace.enabled = True
    workspace.can_create = can_create
    workspace.can_bind_existing = can_bind_existing
    workspace.can_commit = can_commit
    await session.flush()
    existing = {
        row.source_id: row
        for row in await session.scalars(
            select(SyncSourceGrant).where(SyncSourceGrant.workspace_id == workspace_id)
        )
    }
    for source_id in set(source_ids) - existing.keys():
        if await session.get(Source, source_id) is None:
            raise ValueError(f"Unknown source {source_id}")
        session.add(SyncSourceGrant(workspace_id=workspace_id, source_id=source_id))
    for source_id in existing.keys() - set(source_ids):
        await session.delete(existing[source_id])
    return token


def external_key(identity):
    target = identity.target
    return json.dumps(
        [identity.local_object_id, target.kind if target else None, target.id if target else None],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def transport_value(value, definition):
    if value is None:
        return None
    if definition["type"] in {"reference", "source", "biginteger"}:
        return str(value)
    if definition["type"] == "list":
        return [transport_value(item, definition["item"]) for item in value]
    return value


class IdentityService:
    def __init__(self, session, workspace):
        self.session = session
        self.workspace = workspace
        self.entities = EntitiesService(session)
        self.data = DataService(session)
        self._registry = None

    async def model(self, *, write=False):
        # Share the revision lock with schema registration and canonical writes.
        model = await self.session.scalar(
            select(BusinessModel)
            .where(BusinessModel.id == self.workspace.business_model_id)
            .with_for_update(read=not write)
            .execution_options(populate_existing=True)
        )
        if model is None or model.current_revision_id is None:
            reject(409, "SCHEMA_UNAVAILABLE")
        return model

    async def source(self, source_id, *, lock=False):
        if await self.session.get(SyncSourceGrant, (self.workspace.id, source_id)) is None:
            reject(403, "SOURCE_ACCESS_DENIED")
        source = (
            await self.session.scalar(
                select(Source).where(Source.id == source_id).with_for_update(read=True)
            )
            if lock
            else await self.session.get(Source, source_id)
        )
        if source is None or source.state == "ARCHIVED":
            reject(409, "SOURCE_UNAVAILABLE")
        return source

    async def registry(self, model):
        if self._registry is not None:
            return self._registry
        tables = (model.metadata_json or {}).get("extensionEntities", {})
        schema = await self.entities.get_schema(model.id)
        schema_tables = {item.tablename: item for item in schema.entities}
        entries = {
            item.table_name: item
            for item in await self.entities.list_entities(
                model.id,
                limit=500,
            )
            if item.status == "ACTIVE"
        }
        registry = {}
        for kind, definition in DEFINITIONS.items():
            entity = entries.get(tables.get(kind))
            if entity is None:
                continue
            fields = {
                item.persistent_key: item for item in entity.fields if item.status == "ACTIVE"
            }
            declared = {
                field.persistent_key: field for field in schema_tables[entity.table_name].fields
            }
            compatible = []
            for config in definition["fields"]:
                field = fields.get(config["persistentKey"])
                if field is None:
                    continue
                metadata = declared[field.persistent_key]
                compatible.append(
                    {
                        **config,
                        "localKey": config["key"],
                        "key": field.key,
                        "label": field.label,
                        "description": field.description,
                        "businessEntityFieldId": str(field.field_id),
                        "fieldVersionId": str(field.version_id),
                        "definition": field.definition,
                        "reference": metadata.reference
                        or (metadata.item.reference if metadata.item else None),
                    }
                )
            registry[kind] = {
                "localType": kind,
                "key": entity.key,
                "label": definition["label"],
                "businessEntityId": str(entity.entity_id),
                "entityVersionId": str(entity.version_id),
                "parents": definition.get("parents"),
                "fields": compatible,
                "unavailableLocalKeys": [
                    config["key"]
                    for config in definition["fields"]
                    if config["persistentKey"] not in fields
                ],
            }
        self._registry = registry
        return registry

    async def schema(self):
        model = await self.model()
        sources = (
            await self.session.execute(
                select(Source.id, Source.url, Source.type)
                .join(SyncSourceGrant, SyncSourceGrant.source_id == Source.id)
                .where(
                    SyncSourceGrant.workspace_id == self.workspace.id, Source.state != "ARCHIVED"
                )
                .order_by(Source.id)
            )
        ).all()
        return {
            "workspaceUuid": str(self.workspace.id),
            "businessModelId": str(model.id),
            "name": model.name,
            "revisionId": str(model.current_revision_id),
            "entities": list((await self.registry(model)).values()),
            "aliases": ALIASES,
            "sources": [
                {"sourceId": str(row.id), "url": row.url, "type": row.type} for row in sources
            ],
            "sourcePolicy": self.workspace.source_policy,
            "permissions": {
                "create": self.workspace.can_create,
                "bindExisting": self.workspace.can_bind_existing,
                "commit": self.workspace.can_commit,
            },
        }

    async def entity(self, model, identity):
        root = local_type(identity.local_type)
        target = identity.target
        kind = target.kind if target else root
        definition = DEFINITIONS.get(kind)
        if (
            root not in {"project", "recruitment", "operator"}
            or definition is None
            or (target is not None and root not in definition.get("parents", []))
        ):
            reject(422, "UNSUPPORTED_IDENTITY_TYPE")
        result = (await self.registry(model)).get(kind)
        if result is None:
            reject(409, "ENTITY_DEFINITION_UNRESOLVED")
        return result

    async def binding(self, model, identity):
        entry = await self.entity(model, identity)
        row = await self.session.get(
            ExternalObjectBinding, (self.workspace.id, external_key(identity))
        )
        if row is not None and str(row.business_entity_id) != entry["businessEntityId"]:
            reject(409, "IDENTITY_TYPE_CONFLICT")
        return row, entry

    async def parent(self, model, identity):
        parent, _ = await self.binding(model, identity.model_copy(update={"target": None}))
        if parent is None:
            reject(409, "PARENT_IDENTITY_UNRESOLVED")
        if (await self.session.get(BusinessObject, parent.business_object_id)).archived_at:
            reject(409, "PARENT_OBJECT_ARCHIVED")
        return parent

    async def describe(self, model, identity, binding, entity, *, reason=None):
        result = {
            "identity": identity.portable(),
            "businessModelId": str(model.id),
            "schemaRevisionId": str(model.current_revision_id),
            "businessEntityId": entity["businessEntityId"],
            "businessObjectId": None,
            "status": "LOCAL_ONLY",
            "objectFields": {},
            "reason": reason,
        }
        if binding is None:
            return result
        obj = await self.data.get_object(binding.business_object_id)
        if obj.archived_at is not None:
            reject(409, "OBJECT_ARCHIVED")
        slots = {str(field.business_entity_field_id): field for field in obj.fields}
        if identity.target:
            parent = await self.parent(model, identity)
            owner_key = local_type(identity.local_type) + "_owner"
            for definition in entity["fields"]:
                field = slots.get(definition["businessEntityFieldId"])
                if (
                    definition["persistentKey"].endswith("_owner")
                    and field is not None
                    and field.value is not None
                    and (
                        definition["persistentKey"] != owner_key
                        or field.value != parent.business_object_id
                    )
                ):
                    reject(409, "NESTED_OWNER_CONFLICT")
        result.update(status="SYNCED", businessObjectId=str(obj.id))
        for definition in entity["fields"]:
            field = slots.get(definition["businessEntityFieldId"])
            if field is not None:
                result["objectFields"][definition["persistentKey"]] = {
                    "businessEntityFieldId": definition["businessEntityFieldId"],
                    "fieldVersionId": definition["fieldVersionId"],
                    "businessObjectFieldId": str(field.object_field_id),
                    "valueId": wire_id(field.value_id),
                    "value": transport_value(field.value, definition["definition"]),
                    "collectionRevision": field.collection_revision,
                }
        return result

    async def resolve(self, request):
        model = await self.model(write=request.action != "preview")
        identity = request.identity
        binding, entity = await self.binding(model, identity)
        if (
            binding is not None
            and request.action == "bind"
            and (str(binding.business_object_id) != request.existing_business_object_id)
        ):
            reject(409, "BINDING_IMMUTABLE")
        if binding is None and request.action in {"bind", "create"}:
            if identity.target is not None:
                await self.parent(model, identity)
            entity_id = int(entity["businessEntityId"])
            if request.action == "bind":
                if not self.workspace.can_bind_existing:
                    reject(403, "BIND_PERMISSION_REQUIRED")
                object_id = int(request.existing_business_object_id)
                existing = await self.session.get(BusinessObject, object_id)
                if existing is None or existing.business_entity_id != entity_id:
                    reject(409, "EXISTING_OBJECT_TYPE_OR_MODEL_CONFLICT")
                assigned = await self.session.scalar(
                    select(ExternalObjectBinding).where(
                        ExternalObjectBinding.workspace_id == self.workspace.id,
                        ExternalObjectBinding.business_object_id == object_id,
                    )
                )
                if assigned is not None:
                    reject(409, "OBJECT_ALREADY_BOUND")
            else:
                if not self.workspace.can_create:
                    reject(403, "CREATE_PERMISSION_REQUIRED")
                object_id = (
                    await self.data.create_object(entity_id, apply_defaults=False)
                ).object_id
            binding = ExternalObjectBinding(
                workspace_id=self.workspace.id,
                external_object_id=external_key(identity),
                business_model_id=model.id,
                business_entity_id=entity_id,
                business_object_id=object_id,
            )
            self.session.add(binding)
            await self.session.flush()
        if binding is not None and request.action != "preview":
            await self.data.sync_object_fields(binding.business_object_id)
        return await self.describe(
            model,
            identity,
            binding,
            entity,
            reason="EXPLICIT_LEGACY_MATCH_REQUIRED"
            if identity.local_type == "nabor" and not binding
            else None,
        )
