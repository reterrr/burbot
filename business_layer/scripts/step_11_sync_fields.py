from ._common import demo_model, object_fields, run, seed_ids


async def main(business, key):
    """Create missing object-field slots while preserving the existing slots."""
    model = await demo_model(business, key)
    project_id = seed_ids(model)["project"]
    result = await business.data.sync_object_fields(project_id)
    return {"slots": result, "values": await object_fields(business, project_id),
            "note": (
                "New slots are empty; existing values are preserved. "
                "No defaults are backfilled."
            )}


if __name__ == "__main__":
    run(main)
