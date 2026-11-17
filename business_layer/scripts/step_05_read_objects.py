from ._common import demo_model, run, seed_ids


async def main(business, key):
    """Read definitions, resolve names, and list current objects and relations."""
    model = await demo_model(business, key)
    ids = seed_ids(model)
    project = await business.entities.resolve_entity(model.id, "Project")
    field = await business.entities.resolve_field(project.entity_id, "budget")
    entities = await business.entities.list_entities(model.id)
    objects = {}
    for entity in entities:
        objects[entity.key] = await business.data.list_objects(
            entity.entity_id, include_archived=True,
        )
    return {"model": await business.entities.get_model(model.id),
            "schema": await business.entities.get_schema(model.id),
            "resolved_budget_field": field, "objects": objects,
            "project": await business.data.get_object(ids["project"]),
            "relations": await business.entities.list_relations(project.entity_id)}


if __name__ == "__main__":
    run(main, write=False)
