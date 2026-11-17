from ._common import demo_model, find_model, remember, run


async def main(business, key):
    """Create an empty model so you can inspect it before the deletion step."""
    model = await demo_model(business, key)
    empty_key = key + "_empty"
    empty = await find_model(business, empty_key)
    if empty is None:
        empty = await business.entities.create_model(
            empty_key, "Empty model — delete in step 19", metadata_json={"script_demo": True},
        )
    elif not (empty.metadata_json or {}).get("script_demo"):
        raise RuntimeError("The empty-model key belongs to a non-demo model")
    await remember(business, model.id, empty_model_id=empty.id)
    return {"empty_model": empty}


if __name__ == "__main__":
    run(main)
