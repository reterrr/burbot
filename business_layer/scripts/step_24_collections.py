"""Persist three references, reorder/remove/append them, read history, and rename a List field."""

from datetime import UTC, datetime

from business_layer.scripts._common import find_model, run

SCHEMA = """class Operator(Entity):
    name: String(nullable=False)
class Project(Entity):
    name: String(nullable=False)
    operators: List(Reference("Operator"), persistent_key="operators", unique_items=True)
    tags: List(String())
    scores: List(Integer(ge=0, le=100))
"""
SEEDS = """
first = Operator(name="First operator")
second = Operator(name="Second operator")
third = Operator(name="Third operator")
project = Project(
    name="Collection walkthrough", operators=[first, second, third], tags=[], scores=[10]
)
"""


async def operation(business, key):
    """Use a separate walkthrough model; successful writes remain committed."""
    collection_key = f"{key}_collections"
    model = await find_model(business, collection_key)
    if model is None:
        model = await business.entities.create_model(
            key=collection_key,
            name="Collections walkthrough",
            metadata_json={"script_demo": True, "collections_demo": True},
        )
    elif not (model.metadata_json or {}).get("collections_demo"):
        raise RuntimeError("Choose a different --model-key; this is not a Collections demo model")
    # Each run deliberately creates new demo objects, as constructor execution does.
    execution = await business.execute(model.id, code=SCHEMA + SEEDS)
    obj = await business.data.get_object(execution.objects["project"])
    definition = await business.entities.resolve_entity(model.id, "Project")
    field = next(field for field in definition.fields if field.key == "operators")
    slot = next(slot for slot in obj.fields if slot.business_entity_field_id == field.field_id)
    collections = business.data.collections
    original = await collections.get_collection(slot.collection_id)
    before = datetime.now(UTC)
    ids = [item["id"] for item in original["items"]]
    reordered = await collections.reorder_items(
        slot.collection_id, ids[::-1], expected_revision=original["revision"]
    )
    removed = await collections.remove_item(
        slot.collection_id, ids[0], expected_revision=reordered["revision"]
    )
    appended = await collections.append_item(
        slot.collection_id, execution.objects["first"], expected_revision=removed["revision"]
    )
    historical = await collections.get_collection(slot.collection_id, at=before, known_at=before)
    renamed = SCHEMA.replace("    operators: List(", "    partners: List(")
    plan = await business.compile(model.id, renamed)
    await business.entities.register_program(model.id, plan, reason="Rename with persistent_key")
    after_definition = await business.entities.resolve_entity(model.id, "Project")
    after_field = next(field for field in after_definition.fields if field.key == "partners")
    if (
        after_field.field_id != field.field_id
        or [item["id"] for item in historical["items"]] != ids
    ):
        raise RuntimeError("Collection identity/history invariant failed")
    return {
        "model_id": model.id,
        "object_id": obj.id,
        "collection_id": slot.collection_id,
        "original": original,
        "reordered": reordered,
        "removed": removed,
        "appended": appended,
        "historical": historical,
        "renamed_field_id": after_field.field_id,
        "item_history": await collections.item_history(slot.collection_id, ids[0]),
    }


if __name__ == "__main__":
    run(operation)
