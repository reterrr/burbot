from ._common import demo_model, run
from ._programs import EVOLVED_SCHEMA


async def main(business, key):
    """Reapply definitions without creating additional objects."""
    model = await demo_model(business, key)
    metadata = model.metadata_json or {}
    combined_id = metadata.get("execute_model_id")
    if not combined_id:
        raise RuntimeError("Run step_20_execute_program first")
    result = await business.execute(combined_id, code=EVOLVED_SCHEMA)
    if result.objects or result.created or result.schema_changed:
        raise RuntimeError("Definition execution unexpectedly created objects or changed schema")
    return {"combined_model_id": combined_id, "result": result,
            "note": "Definitions are unchanged; no constructors were executed."}


if __name__ == "__main__":
    run(main)
