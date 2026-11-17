from ._common import demo_model, remember, run


async def main(business, key):
    """Delete only the empty model created in step 18."""
    model = await demo_model(business, key)
    empty_id = (model.metadata_json or {}).get("empty_model_id")
    if not empty_id:
        raise RuntimeError("Run step_18_create_empty_model first")
    empty = await business.entities.get_model(empty_id)
    if empty.key != key + "_empty" or not (empty.metadata_json or {}).get("script_demo"):
        raise RuntimeError("The recorded ID does not belong to this walkthrough's empty model")
    await business.entities.delete_model(empty_id)
    await remember(business, model.id, empty_model_deleted=True)
    return {"deleted_empty_model_id": empty_id, "main_demo_model_id": model.id}


if __name__ == "__main__":
    run(main)
