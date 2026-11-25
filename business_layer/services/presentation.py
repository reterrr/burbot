"""Read presentation metadata for effective business values in batches."""

from datetime import UTC, datetime

from sqlalchemy import and_, func, select

from business_layer.schemas.enums import BusinessDefinitionStatus
from business_layer.schemas.models import (
    BusinessEntityField,
    BusinessEntityFieldVersion,
    BusinessEntityRelationVersion,
    BusinessEntityVersion,
    BusinessObjectField,
)
from business_layer.schemas.models.dtos import ValueDisplay, ValueDisplayTarget
from business_layer.services.data import DataService
from business_layer.services.schema_language import Sema
from business_layer.services.value_history import temporal_predicates
from sources.schemas.models import Source

FieldType = Sema.Type


def _valid_id(value):
    return type(value) is int and 0 < value < 2**63


def _item_definition(definition):
    if definition.get("type") != FieldType.LIST:
        return definition
    item = definition.get("item")
    return item if isinstance(item, dict) else {}


class BusinessPresentation:
    def __init__(self, session):
        self.session = session
        self.data = DataService(session)
        self.now = datetime.now(UTC)

    async def _fields(self, ids):
        if not ids:
            return {}
        field = BusinessEntityField
        version = BusinessEntityFieldVersion
        rows = await self.session.execute(
            select(field, version)
            .outerjoin(
                version,
                and_(
                    version.business_entity_field_id == field.id,
                    version.status == BusinessDefinitionStatus.ACTIVE,
                    *temporal_predicates(version, self.now, self.now),
                ),
            )
            .where(field.id.in_(ids))
        )
        return {identity.id: (identity, definition) for identity, definition in rows}

    async def _reference_entities(self, versions):
        entities = {}
        by_relation = set()
        for version in versions.values():
            definition = _item_definition(version.definition_json)
            if definition.get("type") != FieldType.REFERENCE:
                continue
            target = definition.get("reference_entity_id")
            if _valid_id(target):
                entities[version.id] = target
            elif target is None:
                by_relation.add(version.id)
        if by_relation:
            field = BusinessEntityFieldVersion
            relation = BusinessEntityRelationVersion
            # Scalar Reference definitions store their target in the relation snapshot.
            # Read that snapshot as it stood when the value's field version was recorded.
            rows = await self.session.execute(
                select(field.id, func.min(relation.to_entity_id))
                .join(
                    relation,
                    and_(
                        relation.from_field_id == field.business_entity_field_id,
                        relation.business_model_revision_id == field.business_model_revision_id,
                        relation.status == BusinessDefinitionStatus.ACTIVE,
                        *temporal_predicates(relation, field.valid_from, field.transaction_from),
                    ),
                )
                .where(field.id.in_(by_relation))
                .group_by(field.id)
                .having(func.count(relation.to_entity_id.distinct()) == 1)
            )
            entities.update(rows.all())
        return entities

    async def _object_names(self, objects, fields):
        fields = {
            **fields,
            **await self._fields(
                {item.business_entity_field_id for obj in objects.values() for item in obj.fields}
                - fields.keys()
            ),
        }
        names = {}
        for obj in objects.values():
            labels = {}
            for item in obj.fields:
                identity, version = fields.get(item.business_entity_field_id, (None, None))
                if (
                    version is not None
                    and version.definition_json.get("type") in (FieldType.STRING, FieldType.TEXT)
                    and isinstance(item.value, str)
                    and item.value.strip()
                ):
                    key = identity.persistent_key.lower()
                    if key in ("name", "title") and (
                        key == identity.persistent_key or key not in labels
                    ):
                        labels[key] = item.value.strip()
            # Business Layer currently has no display-field setting. Use conventional
            # persistent keys so a logical field rename doesn't change the display rule.
            names[obj.id] = labels.get("name") or labels.get("title")
        return names

    def _display(self, value, definition, entity_id, objects, names, sources, entities):
        kind = definition.get("type")
        display = ValueDisplay(kind=kind if isinstance(kind, str) else None, raw_value=value)
        if kind == FieldType.LIST and isinstance(value, list):
            item = _item_definition(definition)
            item_kind = item.get("type")
            display.item_kind = item_kind if isinstance(item_kind, str) else None
            display.items = [
                self._display(raw, item, entity_id, objects, names, sources, entities)
                for raw in value
            ]
        if kind == FieldType.BIG_INTEGER and type(value) is int:
            # JSON numbers above JS's safe integer range need an exact display string.
            display.label = str(value)
        if kind not in (FieldType.REFERENCE, FieldType.SOURCE) or value is None:
            return display

        display.resolved = False
        if not _valid_id(value):
            return display
        if kind == FieldType.REFERENCE:
            obj = objects.get(value)
            display.target = ValueDisplayTarget(type="business_object", id=value)
            display.label = f"BusinessObject #{value}"
            if obj is not None and obj.business_entity_id == entity_id:
                display.resolved = True
                display.target.entity_id = entity_id
                display.target.entity_name = entities.get(entity_id)
                if names.get(value):
                    display.label = names[value]
                    display.label_is_current = True
        else:
            display.target = ValueDisplayTarget(type="source", id=value)
            display.label = sources.get(value) or f"Source #{value}"
            display.resolved = value in sources
            if sources.get(value):
                display.label_is_current = True
        return display

    async def business_contexts(self, bindings):
        """Read canonical values and labels keyed by (slot ID, expected field ID)."""
        bindings = set(bindings)
        slot_ids = {slot_id for slot_id, _ in bindings if _valid_id(slot_id)}
        slots = (
            {
                slot.id: slot
                for slot in await self.session.scalars(
                    select(BusinessObjectField).where(BusinessObjectField.id.in_(slot_ids))
                )
            }
            if slot_ids
            else {}
        )
        bound = {}
        for key in bindings:
            slot_id, field_id = key
            slot = slots.get(slot_id)
            if slot is not None and field_id not in (None, slot.business_entity_field_id):
                slot = None
            bound[key] = (slot, slot.business_entity_field_id if slot else field_id)

        objects = {
            obj.id: obj
            for obj in await self.data.get_objects(
                {slot.business_object_id for slot, _ in bound.values() if slot is not None},
                at=self.now,
                known_at=self.now,
            )
        }
        values = {item.object_field_id: item for obj in objects.values() for item in obj.fields}
        fields = await self._fields({field_id for _, field_id in bound.values() if field_id})
        versions = {version.id: version for _, version in fields.values() if version is not None}
        recorded = (
            {
                values[slot.id].validated_against_field_version_id
                for slot, _ in bound.values()
                if slot is not None and slot.id in values
            }
            - versions.keys()
            - {None}
        )
        if recorded:
            version = BusinessEntityFieldVersion
            versions.update(
                (row.id, row)
                for row in await self.session.scalars(
                    select(version).where(version.id.in_(recorded))
                )
            )
        targets = await self._reference_entities(versions)
        entities = {}
        if targets:
            entity = BusinessEntityVersion
            entities = dict(
                (
                    await self.session.execute(
                        select(entity.business_entity_id, entity.label).where(
                            entity.business_entity_id.in_(set(targets.values())),
                            entity.status == BusinessDefinitionStatus.ACTIVE,
                            *temporal_predicates(entity, self.now, self.now),
                        )
                    )
                ).all()
            )

        contexts, definitions, reference_ids, source_ids = {}, {}, set(), set()
        for key, (slot, field_id) in bound.items():
            identity, active = fields.get(field_id, (None, None))
            canonical = values.get(slot.id) if slot is not None else None
            version = (
                versions.get(canonical.validated_against_field_version_id)
                if canonical is not None and canonical.value_id is not None
                else active
            )
            definition = version.definition_json if version is not None else {}
            kind = definition.get("type")
            entity_id = targets.get(version.id) if version is not None else None
            item_kind = _item_definition(definition).get("type")
            value = canonical.value if canonical is not None else None
            candidates = value if kind == FieldType.LIST and isinstance(value, list) else [value]
            if item_kind == FieldType.REFERENCE and entity_id is not None:
                reference_ids.update(item for item in candidates if _valid_id(item))
            if item_kind == FieldType.SOURCE:
                source_ids.update(item for item in candidates if _valid_id(item))
            definitions[key] = definition, entity_id
            persistent_key = identity.persistent_key if identity is not None else None
            contexts[key] = {
                "businessField": {
                    "id": field_id,
                    "name": (active.label if active else None) or persistent_key,
                    "persistentKey": persistent_key,
                    "type": kind if isinstance(kind, str) else None,
                    "referenceEntity": {"id": entity_id, "name": entities.get(entity_id)}
                    if entity_id is not None
                    else None,
                }
                if field_id is not None
                else None,
                "businessObjectFieldId": slot.id if slot is not None else None,
                "businessObject": {"id": slot.business_object_id, "name": None}
                if slot is not None
                else None,
                "canonicalValueId": canonical.value_id if canonical is not None else None,
                "canonicalValue": value,
                "canonicalValueScope": "current",
                "canonicalDisplay": None,
            }

        objects.update(
            (obj.id, obj)
            for obj in await self.data.get_objects(
                reference_ids - objects.keys(), at=self.now, known_at=self.now
            )
        )
        names = await self._object_names(objects, fields)
        sources = (
            dict(
                (
                    await self.session.execute(
                        select(Source.id, Source.url).where(Source.id.in_(source_ids))
                    )
                ).all()
            )
            if source_ids
            else {}
        )

        for key, context in contexts.items():
            if context["businessObject"] is not None:
                owner = context["businessObject"]
                owner["name"] = names.get(owner["id"])
            if context["canonicalValueId"] is not None:
                definition, entity_id = definitions[key]
                display = self._display(
                    context["canonicalValue"],
                    definition,
                    entity_id,
                    objects,
                    names,
                    sources,
                    entities,
                )
                context["canonicalDisplay"] = display.model_dump(by_alias=True, exclude_unset=True)
        return contexts
