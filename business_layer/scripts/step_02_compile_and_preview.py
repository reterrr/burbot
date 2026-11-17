from ._common import demo_model, run
from ._programs import SCHEMA


async def main(business, key):
    """Compile and preview a schema without registering it."""
    model = await demo_model(business, key)
    program = await business.compile(model.id, SCHEMA)
    changes = await business.entities.find_changes(model.id, program.schema)
    return {"model_id": model.id, "program": program, "proposed_changes": changes}


if __name__ == "__main__":
    run(main, write=False)
