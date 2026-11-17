from ._common import demo_model, remember, run
from ._programs import SCHEMA, SEEDS


async def main(business, key):
    """Create or reuse the named operator, project, and recruitment objects."""
    model = await demo_model(business, key)
    program = await business.entities.compile(model.id, SCHEMA + SEEDS)
    result = await business.data.seed_objects(model.id, program)
    await remember(business, model.id, seed_objects=result.objects)
    return {"model_id": model.id, "result": result}


if __name__ == "__main__":
    run(main)
