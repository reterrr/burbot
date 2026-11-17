from ._common import demo_model, run


async def main(business, key):
    """Update model metadata without creating a schema revision."""
    model = await demo_model(business, key)
    metadata = {**(model.metadata_json or {}), "reviewed": True}
    result = await business.entities.update_model(model.id, {
        "name": "Business walkthrough — reviewed", "description": "Manually inspected examples",
        "metadata_json": metadata,
    })
    count = await business.entities.get_revisions_count(model.id)
    return {"model": result, "revision_count": count}


if __name__ == "__main__":
    run(main)
