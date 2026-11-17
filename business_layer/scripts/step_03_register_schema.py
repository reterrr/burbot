from ._common import demo_model, run
from ._programs import SCHEMA


async def main(business, key):
    """Register entity, field, enum, and relation definitions; create no objects."""
    model = await demo_model(business, key)
    program = await business.entities.compile(model.id, SCHEMA)
    result = await business.entities.register_program(
        model.id, program, reason="Walkthrough: initial schema",
        metadata_json={"step": "03_register_schema"},
    )
    return {"model_id": model.id, "result": result,
            "entities": await business.entities.list_entities(model.id)}


if __name__ == "__main__":
    run(main)
