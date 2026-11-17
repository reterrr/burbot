from datetime import datetime

from ._common import demo_model, run


async def main(business, key):
    """Read model revisions and entity, field, and relation histories."""
    model = await demo_model(business, key)
    metadata = model.metadata_json or {}
    previous = metadata.get("previous_revision")
    if not previous:
        raise RuntimeError("Run step_10_evolve_schema first")
    project = await business.entities.resolve_entity(model.id, "Project")
    budget = await business.entities.resolve_field(project.entity_id, "budget")
    relations = await business.entities.list_relations(project.entity_id)
    revisions, total = await business.entities.get_revisions(model_id=model.id)
    relation_histories = {}
    for relation in relations:
        history = await business.entities.get_relation_history(relation.relation_id)
        relation_histories[str(relation.relation_id)] = history
    return {
        "revision_count": await business.entities.get_revisions_count(model.id),
        "revisions": revisions, "total": total,
        "previous_revision": await business.entities.get_revision(previous),
        "previous_schema": await business.entities.get_schema(model.id, revision_id=previous),
        "entity_before_change": await business.entities.get_entity(
            project.entity_id, at=datetime.fromisoformat(metadata["before_schema_change"]),
        ),
        "entity_history": await business.entities.get_entity_history(project.entity_id),
        "budget_field_history": await business.entities.get_field_history(budget.field_id),
        "relation_histories": relation_histories,
    }


if __name__ == "__main__":
    run(main, write=False)
