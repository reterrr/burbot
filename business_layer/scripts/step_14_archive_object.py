from ._common import demo_model, run, seed_ids


async def main(business, key):
    """Archive the project; retain its values and exclude it from default listings."""
    model = await demo_model(business, key)
    object_id = seed_ids(model)["project"]
    archived = await business.data.archive_object(object_id)
    return {"archived": archived,
            "default_listing": await business.data.list_objects(archived.business_entity_id),
            "including_archived": await business.data.list_objects(
                archived.business_entity_id, include_archived=True,
            )}


if __name__ == "__main__":
    run(main)
