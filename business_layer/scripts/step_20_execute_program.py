from ._common import demo_model, find_model, remember, run
from ._programs import EVOLVED_SCHEMA, SEEDS


async def main(business, key):
    """Apply a compiled schema and seed plan together in a separate demo model."""
    model = await demo_model(business, key)
    combined_key = key + "_execute"
    combined = await find_model(business, combined_key)
    if combined is None:
        combined = await business.entities.create_model(
            combined_key, "Combined schema + seed execution", metadata_json={"script_demo": True},
        )
    elif not (combined.metadata_json or {}).get("script_demo"):
        raise RuntimeError("The combined-model key belongs to a non-demo model")
    program = await business.compile(combined.id, EVOLVED_SCHEMA + SEEDS)
    result = await business.execute(
        combined.id, program=program, reason="Walkthrough: compile then execute",
        metadata_json={"step": "20_execute_program"},
    )
    await remember(business, model.id, execute_model_id=combined.id,
                   execute_objects=result.objects)
    return {"combined_model_id": combined.id, "result": result}


if __name__ == "__main__":
    run(main)
