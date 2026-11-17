from ._common import demo_model, remember, run, seed_ids
from ._programs import EVOLVED_SCHEMA


async def main(business, key):
    """Rename data/reference fields while keeping their client-controlled keys and data."""
    model = await demo_model(business, key)
    project_id = seed_ids(model)["project"]
    entity = await business.entities.resolve_entity(model.id, "Project")
    budget = await business.entities.resolve_field_by_persistent_key(entity.entity_id, "budget")
    provider = await business.entities.resolve_field_by_persistent_key(
        entity.entity_id, "operator",
    )
    obj = await business.data.get_object(project_id)
    before = next(
        field for field in obj.fields if field.business_entity_field_id == budget.field_id
    )
    relations = await business.entities.list_relations(entity.entity_id)
    old_relation = next(row for row in relations if row.from_field_id == provider.field_id)
    code = EVOLVED_SCHEMA.replace(
        '    budget: Decimal(persistent_key="budget",',
        '    funding_budget: Decimal(persistent_key="budget",',
    ).replace(
        '    operator: Operator(persistent_key="operator",',
        '    provider: Operator(persistent_key="operator",',
    )
    program = await business.entities.compile(model.id, code)
    registered = await business.entities.register_program(
        model.id, program, reason="Walkthrough: rename fields using persistent keys",
    )
    renamed = await business.entities.resolve_field_by_persistent_key(entity.entity_id, "budget")
    obj = await business.data.get_object(project_id)
    after = next(
        field for field in obj.fields if field.business_entity_field_id == renamed.field_id
    )
    relations = await business.entities.list_relations(entity.entity_id)
    new_relation = next(row for row in relations if row.from_field_id == provider.field_id)
    if (renamed.field_id != budget.field_id or after.object_field_id != before.object_field_id
            or after.value_id != before.value_id
            or new_relation.relation_id != old_relation.relation_id):
        raise RuntimeError("Field rename must preserve identities, values, and reference relations")
    await remember(business, model.id, renamed_fields=True)
    return {
        "result": registered, "persistent_key": renamed.persistent_key,
        "old_name": budget.key, "new_name": renamed.key,
        "field_id_before": budget.field_id, "field_id_after": renamed.field_id,
        "slot_before": before.object_field_id, "slot_after": after.object_field_id,
        "value_before": before.value, "value_after": after.value,
        "value_version_before": before.value_id, "value_version_after": after.value_id,
        "relation_before": old_relation.relation_id, "relation_after": new_relation.relation_id,
    }


if __name__ == "__main__":
    run(main)
