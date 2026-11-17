from ._common import demo_model, remember, run, seed_ids


async def main(business, key):
    """Create an additional object directly, without a language seed binding."""
    model = await demo_model(business, key)
    ids = seed_ids(model)
    entity = await business.entities.resolve_entity(model.id, "Recruitment")
    fields = {field.key: field.field_id for field in entity.fields}
    created = await business.data.create_object(entity.entity_id, {
        fields["project"]: ids["project"], fields["closes_on"]: "2027-01-31",
    })
    manual = list((model.metadata_json or {}).get("manual_objects", []))
    await remember(business, model.id, manual_objects=[*manual, created.object_id])
    return {"created": created, "object": await business.data.get_object(created.object_id)}


if __name__ == "__main__":
    run(main)
