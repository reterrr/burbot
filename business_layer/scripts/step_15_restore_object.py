from ._common import demo_model, run, seed_ids


async def main(business, key):
    """Restore the archived project without changing its value history."""
    model = await demo_model(business, key)
    restored = await business.data.restore_object(seed_ids(model)["project"])
    return {"restored": restored,
            "default_listing": await business.data.list_objects(restored.business_entity_id)}


if __name__ == "__main__":
    run(main)
