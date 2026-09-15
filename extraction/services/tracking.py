"""Source-specific baseline policy. Canonical business values are never consulted."""

from extraction.exceptions import ExtractionValidationError
from extraction.schemas.enums import ObservationStatus
from extraction.schemas.models import FieldObservation
from extraction.services.repositories import ExtractionRepository
from sources.services.tracking import append_tracking_version, as_utc


def comparable_value(value):
    if value.is_semantic_null:
        return (value.token_class_id, True, None)
    return (
        value.token_class_id,
        False,
        value.normalized_value if value.normalized_value is not None else value.raw_value,
    )


async def update_tracking_from_observation(repo: ExtractionRepository, tracking, observation):
    """Return (new tracking version, changed).

    DETECTED updates last/check only. VALIDATED/BOUND/ACCEPTED may advance the
    baseline. Late evidence is retained without rewinding either pointer.
    """
    observed_tracking = await repo.get(type(tracking), observation.source_object_field_tracking_id)
    if (
        observed_tracking.tracking_id != tracking.tracking_id
        or observation.source_field_tracking_id != tracking.source_field_tracking_id
        or observation.business_object_field_id != tracking.business_object_field_id
    ):
        raise ExtractionValidationError("Observation belongs to a different tracking binding")
    if observation.status in {ObservationStatus.REJECTED, ObservationStatus.SUPERSEDED}:
        return tracking, False
    if tracking.last_observation_id is not None:
        latest = await repo.get(FieldObservation, tracking.last_observation_id)
        if (as_utc(observation.observed_at), observation.id) <= (
            as_utc(latest.observed_at),
            latest.id,
        ):
            return tracking, False
    changes = {"last_observation_id": observation.id, "last_checked_at": observation.observed_at}
    changed = False
    if observation.status in {
        ObservationStatus.VALIDATED,
        ObservationStatus.BOUND,
        ObservationStatus.ACCEPTED,
    }:
        value = await repo.observation_value(observation)
        if value is None:
            raise ExtractionValidationError(
                "Observation has no normalized literal for baseline comparison"
            )
        baseline = None
        replaced = False
        if tracking.baseline_observation_id is not None:
            previous = await repo.get(FieldObservation, tracking.baseline_observation_id)
            baseline = await repo.observation_value(previous)
            replaced = previous.status == ObservationStatus.SUPERSEDED
        differs = baseline is not None and comparable_value(value) != comparable_value(baseline)
        if baseline is None or replaced or differs:
            changes["baseline_observation_id"] = observation.id
            if differs:
                changes["last_changed_at"] = observation.observed_at
                changed = True
    successor = await append_tracking_version(
        repo.session, tracking, changes, "Extraction observation"
    )
    return successor, changed
