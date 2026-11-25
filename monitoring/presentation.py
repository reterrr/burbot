"""Batch read the current, typed presentation of canonical monitoring values."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, select

from business_layer.schemas.enums import BusinessDefinitionStatus
from business_layer.schemas.models import (
    BusinessEntity,
    BusinessEntityField,
    BusinessEntityFieldVersion,
    BusinessEntityRelationVersion,
    BusinessEntityVersion,
    BusinessModel,
    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)
from business_layer.schemas.models.dtos import (
    BusinessFieldDisplay,
    BusinessValueDisplay,
    BusinessValueTarget,
    DisplayKind,
    ReferenceEntityDisplay,
)
from business_layer.services.data import DataService
from business_layer.services.schema_language import Sema
from business_layer.services.value_history import temporal_predicates
from extension_sync.schema import DEFINITIONS, manifest_field
from monitoring.security import MonitoringError
from sources.schemas.api import SourceResponse
from sources.schemas.models import Source, StoredFile

Type = Sema.Type
NAME_KEYS = ("name", "title")
MAX_SAFE_JS_INTEGER = 2**53 - 1


def recorded_id(value):
    return type(value) is int and 0 < value < 2**63


def display_text(value):
    return value.strip() or None if isinstance(value, str) else None


def source_query():
    return select(Source, StoredFile.original_name).outerjoin(
        StoredFile, StoredFile.id == Source.file_id
    )


async def source_record(session, source_id):
    result = (await session.execute(source_query().where(Source.id == source_id))).one_or_none()
    if result is None:
        raise MonitoringError(404, "SOURCE_NOT_FOUND")
    source, file_name = result
    return {**SourceResponse.model_validate(source).model_dump(), "name": display_text(file_name)}


async def source_labels(session, ids):
    if not ids:
        return {}
    return {
        source.id: display_text(source.url) or display_text(name)
        for source, name in await session.execute(source_query().where(Source.id.in_(ids)))
    }


def object_name_keys(table, model_metadata, definition):
    model_metadata = model_metadata if isinstance(model_metadata, dict) else {}
    tables = model_metadata.get("extensionEntities", {})
    tables = tables if isinstance(tables, dict) else {}
    kind = next((kind for kind in DEFINITIONS if tables.get(kind) == table), None)
    primary = DEFINITIONS[kind].get("primaryLabelField") if kind else None
    manifest = manifest_field(kind, primary) if primary else None
    definition = definition if isinstance(definition, dict) else {}
    names = tuple(
        filter(
            None,
            (
                display_text(definition.get("display_field")),
                manifest["persistentKey"] if manifest else None,
                *NAME_KEYS,
            ),
        )
    )
    codes = tuple(
        filter(
            None,
            (
                display_text(definition.get("code_field")),
                "number" if kind == "project" else None,
                "code",
            ),
        )
    )
    return names, codes


async def object_presentations(session, ids, now=None):
    """Resolve display fields using stable entity tables and persistent field keys."""
    if not ids:
        return {}
    now = now or datetime.now(UTC)
    entity = BusinessEntityVersion
    rows = (
        await session.execute(
            select(
                BusinessObject.id,
                BusinessObject.business_entity_id,
                entity.label,
                BusinessEntity.table_name,
                BusinessModel.metadata_json,
                entity.definition_json,
            )
            .join(BusinessEntity, BusinessEntity.id == BusinessObject.business_entity_id)
            .join(BusinessModel, BusinessModel.id == BusinessEntity.business_model_id)
            .outerjoin(
                entity,
                and_(
                    entity.business_entity_id == BusinessEntity.id,
                    *temporal_predicates(entity, now, now),
                ),
            )
            .where(BusinessObject.id.in_(ids))
        )
    ).all()
    if not rows:
        return {}
    keys = {
        row.id: object_name_keys(row.table_name, row.metadata_json, row.definition_json)
        for row in rows
    }
    wanted = {key.lower() for names, codes in keys.values() for key in (*names, *codes)}
    field, version = BusinessEntityField, BusinessEntityFieldVersion
    slot, value = BusinessObjectField, BusinessObjectFieldValue
    values = {}
    for object_id, key, raw in await session.execute(
        select(slot.business_object_id, field.persistent_key, value.value_json)
        .join(field, field.id == slot.business_entity_field_id)
        .join(
            version,
            and_(
                version.business_entity_field_id == field.id,
                version.status == BusinessDefinitionStatus.ACTIVE,
                version.definition_json["type"].as_string().in_((Type.STRING, Type.TEXT)),
                *temporal_predicates(version, now, now),
            ),
        )
        .join(
            value,
            and_(
                value.business_object_field_id == slot.id,
                *temporal_predicates(value, now, now),
            ),
        )
        .where(slot.business_object_id.in_(keys), func.lower(field.persistent_key).in_(wanted))
        .order_by(field.id)
    ):
        if label := display_text(raw):
            values.setdefault(object_id, {}).setdefault(key.lower(), label)
    objects = {}
    for row in rows:
        names, codes = keys[row.id]
        fields = values.get(row.id, {})
        name = next((fields[key.lower()] for key in names if key.lower() in fields), None)
        code = next((fields[key.lower()] for key in codes if key.lower() in fields), None)
        objects[row.id] = {
            "id": row.id,
            "name": name,
            "code": code if code != name else None,
            "entityId": row.business_entity_id,
            "entityName": row.label,
        }
    return objects


async def object_labels(session, ids, now):
    objects = await object_presentations(session, ids, now)
    return {identity: (obj["entityId"], obj["name"]) for identity, obj in objects.items()}


@dataclass(frozen=True)
class ValueType:
    kind: DisplayKind
    entity_id: int | None = None
    item: "ValueType | None" = None


def definition_type(definition, relation_entity=None):
    definition = definition if isinstance(definition, dict) else {}
    try:
        kind = Type(definition.get("type"))
    except ValueError:
        return ValueType("unknown")
    if kind == Type.LIST:
        return ValueType(kind, item=definition_type(definition.get("item"), relation_entity))
    if kind == Type.REFERENCE:
        entity_id = definition.get("reference_entity_id")
        if entity_id is None:
            entity_id = relation_entity
        return ValueType(kind, entity_id=entity_id if recorded_id(entity_id) else None)
    return ValueType(kind)


async def relation_targets(session, versions):
    # Scalar references normally keep the target in a bitemporal relation.
    ids = {
        version.id
        for version in versions
        if (declared := definition_type(version.definition_json)).kind == Type.REFERENCE
        and declared.entity_id is None
    }
    if not ids:
        return {}
    version = BusinessEntityFieldVersion
    relation = BusinessEntityRelationVersion
    rows = await session.execute(
        select(version.id, relation.to_entity_id)
        .join(relation, relation.from_field_id == version.business_entity_field_id)
        .where(
            version.id.in_(ids),
            relation.status == BusinessDefinitionStatus.ACTIVE,
            *temporal_predicates(relation, version.valid_from, version.transaction_from),
        )
    )
    return dict(rows.all())


def links(declared, value):
    if declared.item and isinstance(value, list):
        for item in value:
            yield from links(declared.item, item)
    elif recorded_id(value) and (
        declared.kind == Type.SOURCE or declared.kind == Type.REFERENCE and declared.entity_id
    ):
        yield declared.kind, value


def value_display(declared, value, objects, sources):
    kind = declared.kind
    if declared.item and isinstance(value, list):
        return BusinessValueDisplay(
            kind=kind,
            rawValue=value,
            itemKind=declared.item.kind,
            items=[value_display(declared.item, item, objects, sources) for item in value],
        )
    if kind == Type.BIG_INTEGER and type(value) is int and abs(value) > MAX_SAFE_JS_INTEGER:
        return BusinessValueDisplay(kind=kind, rawValue=value, label=str(value))
    if kind not in (Type.REFERENCE, Type.SOURCE) or value is None:
        return BusinessValueDisplay(kind=kind, rawValue=value)
    is_source = kind == Type.SOURCE
    name = "Source" if is_source else "BusinessObject"
    if not recorded_id(value):
        return BusinessValueDisplay(
            kind=kind, rawValue=value, label=f"Invalid {name} ID", resolved=False
        )

    target = BusinessValueTarget(type="source" if is_source else "business_object", id=value)
    if value > MAX_SAFE_JS_INTEGER:
        target.idText = str(value)
    if is_source:
        resolved, label = value in sources, sources.get(value)
    else:
        entity_id, label = objects.get(value, (None, None))
        resolved = entity_id is not None and entity_id == declared.entity_id
        if resolved:
            target.entityId = entity_id
        else:
            label = None
    return BusinessValueDisplay(
        kind=kind,
        rawValue=value,
        label=label or f"{name} #{value}",
        labelBasis="current" if label else None,
        target=target,
        resolved=resolved,
    )


async def field_definitions(session, field_ids, validated_ids, now):
    field = BusinessEntityField
    version = BusinessEntityFieldVersion
    current = {}
    if field_ids:
        current = {
            identity: (key, active)
            for identity, key, active in await session.execute(
                select(field.id, field.persistent_key, version)
                .outerjoin(
                    version,
                    and_(
                        version.business_entity_field_id == field.id,
                        *temporal_predicates(version, now, now),
                    ),
                )
                .where(field.id.in_(field_ids))
            )
        }
    versions = {active.id: active for _, active in current.values() if active is not None}
    old_ids = validated_ids - versions.keys()
    if old_ids:
        versions.update(
            (row.id, row)
            for row in await session.scalars(select(version).where(version.id.in_(old_ids)))
        )
    return current, versions


async def field_presentations(session, field_slots):
    """Read monitoring fields by (field ID, slot ID), deriving the field from legacy slots."""
    now = datetime.now(UTC)
    slot_ids = {slot_id for _, slot_id in field_slots if recorded_id(slot_id)}
    slots = {}
    if slot_ids:
        slots = {
            slot.id: slot
            for slot in await session.scalars(
                select(BusinessObjectField).where(BusinessObjectField.id.in_(slot_ids))
            )
        }
    fields = {}
    for field_id, slot_id in field_slots:
        slot = slots.get(slot_id) if recorded_id(slot_id) else None
        if slot is not None and field_id not in (None, slot.business_entity_field_id):
            slot = None
        fields[field_id, slot_id] = (slot.business_entity_field_id if slot else field_id, slot)

    owner_ids = {slot.business_object_id for _, slot in fields.values() if slot is not None}
    owners = await DataService(session).get_objects(owner_ids, at=now, known_at=now)
    slot_values = {item.object_field_id: item for obj in owners for item in obj.fields}
    canonical = {
        pair: slot_values.get(slot.id) if slot else None for pair, (_, slot) in fields.items()
    }
    current, versions = await field_definitions(
        session,
        {field_id for field_id, _ in fields.values() if recorded_id(field_id)},
        {
            value.validated_against_field_version_id
            for value in canonical.values()
            if value is not None and value.validated_against_field_version_id is not None
        },
        now,
    )
    relations = await relation_targets(session, versions.values())

    kinds = {}
    object_ids, source_ids, entity_ids = set(owner_ids), set(), set()
    for pair, (field_id, _) in fields.items():
        value = canonical[pair]
        active = current.get(field_id, (None, None))[1]
        validated = versions.get(value.validated_against_field_version_id) if value else None
        definition = validated if value and value.value_id is not None else active
        declared = (
            definition_type(definition.definition_json, relations.get(definition.id))
            if definition is not None
            else ValueType("unknown")
        )
        kinds[pair] = declared
        entity_id = (declared.item or declared).entity_id
        if entity_id is not None:
            entity_ids.add(entity_id)
        if value is not None:
            for kind, identity in links(declared, value.value):
                (source_ids if kind == Type.SOURCE else object_ids).add(identity)

    objects = await object_labels(session, object_ids, now)
    sources = await source_labels(session, source_ids)
    entity = BusinessEntityVersion
    entity_names = {}
    if entity_ids:
        entity_names = dict(
            (
                await session.execute(
                    select(entity.business_entity_id, entity.label).where(
                        entity.business_entity_id.in_(entity_ids),
                        *temporal_predicates(entity, now, now),
                    )
                )
            ).all()
        )

    result = {}
    for pair, (field_id, slot) in fields.items():
        key, active = current.get(field_id, (None, None))
        value, declared = canonical[pair], kinds[pair]
        entity_id = (declared.item or declared).entity_id
        field_display = (
            BusinessFieldDisplay(
                id=field_id,
                name=(display_text(active.label) if active else None) or key,
                persistentKey=key,
                kind=declared.kind,
                itemKind=declared.item.kind if declared.item else None,
                referenceEntity=(
                    ReferenceEntityDisplay(id=entity_id, name=entity_names.get(entity_id))
                    if entity_id is not None
                    else None
                ),
            )
            if field_id is not None
            else None
        )
        result[pair] = {
            "businessField": field_display.model_dump() if field_display else None,
            "businessObjectFieldId": slot.id if slot else None,
            "businessObject": {
                "id": slot.business_object_id,
                "name": objects.get(slot.business_object_id, (None, None))[1],
            }
            if slot
            else None,
            "canonicalValueId": value.value_id if value else None,
            "canonicalValue": value.value if value else None,
            "canonicalDisplay": (
                value_display(declared, value.value, objects, sources).model_dump(
                    exclude_unset=True
                )
                if value and value.value_id is not None
                else None
            ),
        }
    return result
