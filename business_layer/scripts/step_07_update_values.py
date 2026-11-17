from datetime import UTC, datetime
from decimal import Decimal

from ._common import demo_model, object_fields, remember, run, seed_ids


async def main(business, key):
    """Change values and persist their history plus timestamps for the next step."""
    model = await demo_model(business, key)
    object_id = seed_ids(model)["project"]
    fields = await object_fields(business, object_id)
    budget = fields["budget"]
    amount = format(Decimal(str(budget.value)) + Decimal("1250.50"), ".2f")
    before = datetime.now(UTC)
    obj = await business.data.assign_object_fields_values(object_id, {
        budget.object_field_id: amount,
        fields["status"].object_field_id: "ACTIVE",
        fields["rating"].object_field_id: 4.5,
        fields["quantity"].object_field_id: 2147483648,
        fields["settings"].object_field_id: {"regions": ["PL", "EU"], "remote": False},
    }, effective_at=before, expected_value_ids={budget.object_field_id: budget.value_id})
    after = datetime.now(UTC)
    await remember(business, model.id, last_update={
        "object_id": object_id, "slot_id": budget.object_field_id,
        "old_value_id": budget.value_id, "old_value": budget.value,
        "effective_at": before.isoformat(), "known_before": before.isoformat(),
        "known_after": after.isoformat(),
    })
    return {"object": obj, "previous_budget": budget.value, "new_budget": amount}


if __name__ == "__main__":
    run(main)
