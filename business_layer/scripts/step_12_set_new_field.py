from ._common import demo_model, object_fields, run, seed_ids


async def main(business, key):
    """Assign a value to the newly synchronized Project.score field."""
    model = await demo_model(business, key)
    project_id = seed_ids(model)["project"]
    fields = await object_fields(business, project_id)
    if "score" not in fields:
        raise RuntimeError("Run steps 10 and 11 first")
    result = await business.data.assign_object_fields_values(project_id, {
        fields["score"].object_field_id: 5,
    })
    return {"object": result}


if __name__ == "__main__":
    run(main)
