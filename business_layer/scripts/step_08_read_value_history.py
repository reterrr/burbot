from datetime import datetime

from ._common import demo_model, run


async def main(business, key):
    """Compare earlier beliefs with current knowledge at the same business time."""
    model = await demo_model(business, key)
    update = (model.metadata_json or {}).get("last_update")
    if not update:
        raise RuntimeError("Run step_07_update_values first")
    at = datetime.fromisoformat(update["effective_at"])
    before = datetime.fromisoformat(update["known_before"])
    after = datetime.fromisoformat(update["known_after"])
    return {
        "history": await business.data.get_object_field_value_history(update["slot_id"]),
        "believed_before": await business.data.get_object_field_value_history(
            update["slot_id"], at=at, known_at=before,
        ),
        "believed_after": await business.data.get_object_field_value_history(
            update["slot_id"], at=at, known_at=after,
        ),
        "object_before": await business.data.get_object(
            update["object_id"], at=at, known_at=before,
        ),
        "object_after": await business.data.get_object(
            update["object_id"], at=at, known_at=after,
        ),
    }


if __name__ == "__main__":
    run(main, write=False)
