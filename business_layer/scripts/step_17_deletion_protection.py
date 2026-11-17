from ._common import demo_model, expect_error, run, seed_ids


async def main(business, key):
    """Demonstrate that objects and models with history cannot be hard deleted."""
    model = await demo_model(business, key)
    checks = [await expect_error("object has value history",
        business.data.delete_object(seed_ids(model)["project"]), 409,
    )]
    checks.append(await expect_error("model has schema history",
        business.entities.delete_model(model.id), 409,
    ))
    return {"protected_records": checks}


if __name__ == "__main__":
    run(main, write=False)
