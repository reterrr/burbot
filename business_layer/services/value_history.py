"""Canonical value decisions. Call within a transaction holding the object lock."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from business_layer.schemas.models.data import (
    BusinessObjectFieldValue,
)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effective_at must include a timezone offset")
    return value.astimezone(UTC)


def equal_json(left: Any, right: Any) -> bool:
    # Python considers True == 1, but they are different business values.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def history_predicates(
    field_id: int, *, at: datetime | None = None, known_at: datetime | None = None,
):
    """Half-open valid/transaction intervals; no times means complete audit history."""
    value = BusinessObjectFieldValue
    predicates = [value.business_object_field_id == field_id]
    if at is not None:
        at = aware(at)
        predicates.extend([
            value.valid_from <= at,
            value.valid_to.is_(None) | (value.valid_to > at),
        ])
    if at is not None or known_at is not None:
        known_at = aware(known_at) if known_at is not None else datetime.now(UTC)
        predicates.extend([
            value.transaction_from <= known_at,
            value.transaction_to.is_(None) | (value.transaction_to > known_at),
        ])
    return predicates


async def accept_value(
    session,
    field_id: int,
    value: Any,
    *,
    effective_at: datetime,
    recorded_at: datetime,
) -> BusinessObjectFieldValue:
    """Replace the accepted timeline from effective_at onward, retaining prior beliefs.

    Earlier valid-time segments are copied into the new transaction-time view.
    Equal open-ended values reuse their version.
    """
    effective_at, recorded_at = aware(effective_at), aware(recorded_at)
    if effective_at > recorded_at:
        raise ValueError("effective_at cannot be in the future")
    equal_json(value, value)  # Reject non-JSON/NaN input before mutating anything.
    rows = list((await session.scalars(
        select(BusinessObjectFieldValue).where(
            BusinessObjectFieldValue.business_object_field_id == field_id,
            BusinessObjectFieldValue.transaction_to.is_(None),
        ).order_by(BusinessObjectFieldValue.valid_from)
    )).all())
    target = next((row for row in rows if row.valid_to is None
                   and row.valid_from <= effective_at and equal_json(row.value_json, value)), None)
    if target is None:
        for row in rows:
            if row.valid_to is not None and row.valid_to <= effective_at:
                continue
            if recorded_at <= row.transaction_from:
                raise ValueError("Recorded time must advance beyond the preceding decision")
            # Only close transaction time. Never rewrite an earlier belief's valid period.
            row.transaction_to = recorded_at
            if row.valid_from < effective_at:
                prefix = BusinessObjectFieldValue(
                    business_object_field_id=field_id, value_json=row.value_json,
                    valid_from=row.valid_from, valid_to=effective_at,
                    transaction_from=recorded_at,
                )
                session.add(prefix)
                await session.flush()
        # Flush closures before insertion to satisfy the immediate exclusion constraint.
        await session.flush()
        target = BusinessObjectFieldValue(
            business_object_field_id=field_id, value_json=value,
            valid_from=effective_at, transaction_from=recorded_at,
        )
        session.add(target)
        await session.flush()

    return target
