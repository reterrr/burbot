"""Allowed domain transitions; workers and orchestration choose when to request them."""

from sources.schemas.enums import SourceState as State

TRANSITIONS: dict[State, frozenset[State]] = {
    State.ADDING: frozenset({State.UNDISCOVERED, State.FAILED}),
    State.UNDISCOVERED: frozenset({State.DISCOVERING}),
    State.DISCOVERING: frozenset({State.VALIDATING, State.NEEDS_REVIEW, State.FAILED}),
    State.VALIDATING: frozenset({State.ACTIVE, State.NEEDS_REVIEW, State.FAILED}),
    State.ACTIVE: frozenset({State.DEGRADED, State.REDISCOVERING, State.NEEDS_REVIEW}),
    State.DEGRADED: frozenset(
        {
            State.ACTIVE,
            State.REDISCOVERING,
            State.NEEDS_REVIEW,
            State.FAILED,
        }
    ),
    State.REDISCOVERING: frozenset({State.VALIDATING, State.NEEDS_REVIEW, State.FAILED}),
    State.NEEDS_REVIEW: frozenset(
        {
            State.DISCOVERING,
            State.REDISCOVERING,
            State.VALIDATING,
            State.FAILED,
        }
    ),
    State.FAILED: frozenset({State.UNDISCOVERED, State.DISCOVERING}),
    State.SUSPENDED: frozenset({State.UNDISCOVERED}),
    State.BLOCKED_BY_POLICY: frozenset({State.UNDISCOVERED}),
    State.ARCHIVED: frozenset(),
}


def can_transition(current: State, target: State) -> bool:
    if current == target:
        return True
    if current == State.ARCHIVED:
        return False
    if target in {State.SUSPENDED, State.ARCHIVED, State.BLOCKED_BY_POLICY}:
        return True
    return target in TRANSITIONS[current]
