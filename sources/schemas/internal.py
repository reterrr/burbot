"""Acquisition-worker contracts. These are not mounted on the public API."""

from pydantic import AwareDatetime

from sources.schemas.api import Identifier, TrackingVersionUpdate


class TrackingObservationUpdate(TrackingVersionUpdate):
    last_observation_id: Identifier | None = None
    baseline_observation_id: Identifier | None = None
    last_checked_at: AwareDatetime | None = None
    last_changed_at: AwareDatetime | None = None
