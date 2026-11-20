"""Translate the extension manifest into the existing Business Layer schema."""

import json
from dataclasses import asdict
from importlib.resources import files

from fastapi import HTTPException
from sqlalchemy import select, text

from business_layer.schemas.models import BusinessModel
from business_layer.services.entities import EntitiesService
from business_layer.services.schema_language import Sema, SourceLocation
from business_layer.services.schema_parser import table_name

MANIFEST = json.loads(files("extension_sync").joinpath("manifest.json").read_text(encoding="utf-8"))
DEFINITIONS = {entity["localType"]: entity for entity in MANIFEST["entities"]}
ALIASES = MANIFEST["aliases"]
LOCATION = SourceLocation(1, 0, 1, 1)
TYPES = {
    "string": "string",
    "text": "text",
    "integer": "integer",
    "number": "decimal",
    "percentage": "decimal",
    "money": "decimal",
    "date": "date",
    "datetime": "datetime",
    "time": "string",
    "boolean": "boolean",
    "enum": "enum",
    "url": "string",
    "nip": "string",
    "reference": "reference",
    "source": "source",
}
PATTERNS = {
    "time": r"\A(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?\Z",
    "url": r"\Ahttps?://[^/\s?#]+[^\s]*\Z",
    "nip": r"\A[0-9]{10}\Z",
}


def local_type(value):
    return ALIASES[value]["entity"] if value in ALIASES else value


def manifest_field(local, key):
    key = ALIASES.get(local, {}).get("fields", {}).get(key, key)
    return next((f for f in DEFINITIONS[local_type(local)]["fields"] if f["key"] == key), None)


def field_definition(entity, field, names, enums, previous):
    kind = field["type"]
    if kind not in TYPES:
        raise ValueError(f"Unsupported extension field type {kind} on {entity}.{field['key']}")
    options = {"type": "text" if field.get("multiline") else TYPES[kind]}
    for local, server in (("min", "ge"), ("max", "le"), ("maxLength", "max_length")):
        if local in field:
            options[server] = field[local]
    if kind in PATTERNS:
        options["pattern"] = PATTERNS[kind]
    if kind == "enum":
        name = f"Ext_{entity}_{field['persistentKey']}"
        values = [int(key) if field.get("numeric") else key for key in field["options"]]
        enums[name] = Sema.EnumDefinition(
            name=name,
            location=LOCATION,
            members=[
                Sema.EnumMember(name=f"OPTION_{i}", value=value, location=LOCATION)
                for i, value in enumerate(values, 1)
            ],
        )
        options["enum_type"] = name
        for alias in field.get("aliases", {}).values():
            if alias not in values:
                raise ValueError(f"Unknown enum alias target for {name}")
    if kind == "reference":
        options["reference"] = names[field["references"]]
    if kind == "money":
        options.update(precision=20, scale=2)
    if field["cardinality"] == "many":
        options = {"type": "list", "item": options, "unique_items": True}
    return Sema.Field(
        name=previous.name if previous else field["key"],
        persistent_key=field["persistentKey"],
        location=LOCATION,
        label=field["label"],
        description=field.get("description"),
        nullable=field["nullable"],
        default=field.get("default"),
        has_default="default" in field,
        **options,
    )


def desired_schema(current, remembered):
    by_name = {entity.name: entity for entity in current.entities}
    by_table = {entity.tablename: entity for entity in current.entities}
    old = {
        key: by_table.get(remembered.get(key)) or by_name.get(definition["key"])
        for key, definition in DEFINITIONS.items()
    }
    names = {
        key: previous.name if previous else DEFINITIONS[key]["key"] for key, previous in old.items()
    }
    entities = dict(by_table)
    enums = {enum.name: enum for enum in current.enums}
    tables = {}
    for key, definition in DEFINITIONS.items():
        previous = old[key]
        current_fields = {f.persistent_key: f for f in previous.fields} if previous else {}
        fields = dict(current_fields)
        for field in definition["fields"]:
            persistent = field["persistentKey"]
            fields[persistent] = field_definition(
                definition["key"],
                field,
                names,
                enums,
                current_fields.get(persistent),
            )
        table = previous.tablename if previous else table_name(definition["key"], MANIFEST["key"])
        tables[key] = table
        entities[table] = Sema.Entity(
            name=names[key],
            tablename=table,
            location=LOCATION,
            fields=list(fields.values()),
        )
    return Sema().validate(
        Sema.Schema(entities=list(entities.values()), enums=list(enums.values()))
    ), tables


async def bootstrap(session, *, apply=False, expected_revision=None):
    """Run inside a transaction. Existing revisions require explicit acknowledgement."""
    if apply:
        await session.execute(text("SELECT pg_advisory_xact_lock(1465030881, 1)"))
    query = select(BusinessModel).where(BusinessModel.key == MANIFEST["key"])
    model = await session.scalar(query.with_for_update() if apply else query)
    entities = EntitiesService(session)
    if model is None and apply:
        model = await entities.create_model(MANIFEST["key"], MANIFEST["name"])
    current = await entities.get_schema(model.id) if model else Sema.Schema()
    metadata = (model.metadata_json or {}) if model else {}
    desired, tables = desired_schema(current, metadata.get("extensionEntities", {}))
    revision = model.current_revision_id if model else None
    changes = (
        await entities.find_changes(model.id, desired)
        if model
        else entities._find_changes(
            current=Sema.Schema(),
            desired=desired,
        )
    )
    if apply:
        if changes and revision != expected_revision:
            raise HTTPException(
                409,
                detail={
                    "code": "BOOTSTRAP_REVISION_CHANGED",
                    "revisionId": wire_id(revision),
                    "changes": [asdict(change) for change in changes],
                },
            )
        if changes:
            result = await entities.register(
                model.id,
                "Firefox workspace schema",
                {"extensionManifestFormat": MANIFEST["format"]},
                desired,
            )
            revision = result.revision_id or revision
        if metadata.get("extensionEntities") != tables:
            model.metadata_json = {**metadata, "extensionEntities": tables}
            await session.flush()
    return {
        "businessModelId": wire_id(model.id) if model else None,
        "revisionId": wire_id(revision),
        "changes": [asdict(change) for change in changes],
        "applied": bool(apply and changes),
    }


def wire_id(value):
    return str(value) if value is not None else None
