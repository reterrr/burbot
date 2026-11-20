"""Shared canonical bitemporal decisions, called while holding the owner's lock."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import null, select

from business_layer.schemas.models.data import BusinessObjectFieldValue
from business_layer.schemas.models.entities import BusinessEntityFieldVersion


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effective_at must include a timezone offset")
    return value.astimezone(UTC)


def equal_json(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def temporal_predicates(model, at, known_at):
    return (
        model.valid_from <= at,
        model.valid_to.is_(None) | (model.valid_to > at),
        model.transaction_from <= known_at,
        model.transaction_to.is_(None) | (model.transaction_to > known_at),
    )


def history_temporal_predicates(model, *, at=None, known_at=None):
    predicates = []
    if at is not None:
        at = aware(at)
        predicates.extend(
            [model.valid_from <= at, model.valid_to.is_(None) | (model.valid_to > at)]
        )
    if at is not None or known_at is not None:
        known_at = aware(known_at) if known_at is not None else datetime.now(UTC)
        predicates.extend(
            [
                model.transaction_from <= known_at,
                model.transaction_to.is_(None) | (model.transaction_to > known_at),
            ]
        )
    return predicates


def history_predicates(field_id: int, *, at=None, known_at=None):
    return [
        BusinessObjectFieldValue.business_object_field_id == field_id,
        *history_temporal_predicates(BusinessObjectFieldValue, at=at, known_at=known_at),
    ]


def _stored_payload(model, payload):
    # JSON null represents an explicit scalar null; SQL NULL represents an unused
    # value channel. Keep that distinction when copying older transaction views.
    if model is BusinessObjectFieldValue and payload.get("collection_id") is not None:
        return {**payload, "value_json": null()}
    return payload


async def accept_timeline(session, model, identity, segments, *, effective_at, recorded_at):
    """Replace a suffix of one identity's valid timeline, preserving earlier beliefs.

    Segments are (start, end, payload) triples; gaps remain unset. Adjacent equal
    segments are coalesced. All closures precede inserts for immediate exclusions.
    The same engine serves scalar values, collection pointers, and item versions.
    """
    effective_at, recorded_at = aware(effective_at), aware(recorded_at)
    if effective_at > recorded_at:
        raise ValueError("effective_at cannot be in the future")
    merged = []
    for start, end, payload in segments:
        if end is not None and end <= start:
            continue
        if merged and merged[-1][1] == start and equal_json(merged[-1][2], payload):
            merged[-1] = (merged[-1][0], end, payload)
        else:
            merged.append((start, end, payload))
    keys = set().union(*(payload.keys() for _, _, payload in merged))
    rows = list(
        (
            await session.scalars(
                select(model)
                .where(
                    *(getattr(model, key) == value for key, value in identity.items()),
                    model.transaction_to.is_(None),
                )
                .order_by(model.valid_from)
            )
        ).all()
    )
    suffix = [
        (max(row.valid_from, effective_at), row.valid_to, {key: getattr(row, key) for key in keys})
        for row in rows
        if row.valid_to is None or row.valid_to > effective_at
    ]
    if equal_json(
        [(a.isoformat(), b.isoformat() if b else None, c) for a, b, c in suffix],
        [(a.isoformat(), b.isoformat() if b else None, c) for a, b, c in merged],
    ):
        return False
    prefixes = []
    for row in rows:
        if row.valid_to is not None and row.valid_to <= effective_at:
            continue
        if recorded_at <= row.transaction_from:
            raise ValueError("Recorded time must advance beyond the preceding decision")
        row.transaction_to = recorded_at
        if row.valid_from < effective_at:
            prefixes.append(
                (row.valid_from, effective_at, {key: getattr(row, key) for key in keys})
            )
    await session.flush()
    for start, end, payload in [*prefixes, *merged]:
        session.add(
            model(
                **identity,
                **_stored_payload(model, payload),
                valid_from=start,
                valid_to=end,
                transaction_from=recorded_at,
            )
        )
    await session.flush()
    return True


async def accept_value(
    session,
    field_id,
    value,
    *,
    field_version: BusinessEntityFieldVersion,
    effective_at,
    recorded_at,
    collection_id=None,
):
    """Accept a value together with the definition that actually validated it.

    The definition is part of the decision payload: revalidating the same value
    against a new schema creates history, while copied prefixes retain their
    original validation version.
    """
    await accept_timeline(
        session,
        BusinessObjectFieldValue,
        {
            "business_object_field_id": field_id,
            "business_entity_field_id": field_version.business_entity_field_id,
        },
        [
            (
                effective_at,
                None,
                {
                    "value_json": value,
                    "collection_id": collection_id,
                    "validated_against_field_version_id": field_version.id,
                },
            )
        ],
        effective_at=effective_at,
        recorded_at=recorded_at,
    )
    return await session.scalar(
        select(BusinessObjectFieldValue).where(
            BusinessObjectFieldValue.business_object_field_id == field_id,
            BusinessObjectFieldValue.transaction_to.is_(None),
            BusinessObjectFieldValue.valid_to.is_(None),
        )
    )
