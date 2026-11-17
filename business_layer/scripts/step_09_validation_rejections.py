from ._common import demo_model, expect_error, object_fields, run, seed_ids


async def main(business, key):
    """Show rejected invalid, duplicate, read-only, and stale writes."""
    model = await demo_model(business, key)
    ids = seed_ids(model)
    fields = await object_fields(business, ids["project"])
    update = (model.metadata_json or {}).get("last_update")
    if not update:
        raise RuntimeError("Run step_07_update_values first")
    checks = []
    for label, field, value in [
        ("negative budget", "budget", "-1.00"),
        ("invalid enum", "status", "UNKNOWN"),
        ("required value is null", "name", None),
        ("wrong reference entity", "operator", ids["recruitment"]),
        ("generated ID is read-only", "id", 999999),
        ("boolean type", "enabled", 1),
        ("integer type", "quantity", True),
        ("float bound", "rating", 6),
        ("UUID format", "external_id", "invalid"),
        ("datetime offset missing", "starts_at", "2026-11-01T09:00:00"),
    ]:
        checks.append(await expect_error(label,
            business.data.assign_object_fields_values(ids["project"], {
                fields[field].object_field_id: value,
            }), 422,
        ))
    operator = await business.entities.resolve_entity(model.id, "Operator")
    name = next(field.field_id for field in operator.fields if field.key == "name")
    old_name = (await object_fields(business, ids["operator"]))["name"].value
    checks.append(await expect_error("duplicate unique name",
        business.data.create_object(operator.entity_id, {name: old_name}), 409,
    ))
    checks.append(await expect_error("stale value ID",
        business.data.assign_object_fields_values(ids["project"], {
            update["slot_id"]: "999.00",
        }, expected_value_ids={update["slot_id"]: update["old_value_id"]}), 409,
    ))
    return {"rejected_operations": checks,
            "unchanged_object": await business.data.get_object(ids["project"])}


if __name__ == "__main__":
    run(main, write=False)
