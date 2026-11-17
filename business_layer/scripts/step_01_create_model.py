from ._common import find_model, run


async def main(business, key):
    """Create the persistent demo model namespace."""
    model = await find_model(business, key)
    if model is not None:
        if not (model.metadata_json or {}).get("script_demo"):
            raise RuntimeError("Choose another --model-key; this key belongs to a non-demo model")
        return {"already_exists": True, "model": model}
    model = await business.entities.create_model(
        key, "Business service walkthrough", description="Committed manual service examples",
        metadata_json={"script_demo": True},
    )
    return {"model": model}


if __name__ == "__main__":
    run(main)
