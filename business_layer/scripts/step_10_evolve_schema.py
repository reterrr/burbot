from datetime import UTC, datetime

from ._common import demo_model, remember, run
from ._programs import EVOLVED_SCHEMA


async def main(business, key):
    """Add Project.score to the schema, without creating object slots yet."""
    model = await demo_model(business, key)
    previous_revision = model.current_revision_id
    before = datetime.now(UTC)
    program = await business.entities.compile(model.id, EVOLVED_SCHEMA)
    changes = await business.entities.find_changes(model.id, program.schema)
    registered = await business.entities.register_program(
        model.id, program, reason="Walkthrough: add Project.score",
    )
    await remember(business, model.id, previous_revision=previous_revision,
                   before_schema_change=before.isoformat())
    return {"changes": changes, "result": registered,
            "project": await business.entities.resolve_entity(model.id, "Project")}


if __name__ == "__main__":
    run(main)
