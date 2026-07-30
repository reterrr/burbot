# enums/expected_information.py

from enum import StrEnum


class ExpectedInformationType(StrEnum):
    NEW_CALL = "new_call"
    CALL_OPENED = "call_opened"
    CALL_CLOSED = "call_closed"
    CALL_SUSPENDED = "call_suspended"
    CALL_RESUMED = "call_resumed"

    CALL_START_DATE = "call_start_date"
    CALL_END_DATE = "call_end_date"
    DEADLINE_CHANGED = "deadline_changed"

    BUDGET_EXHAUSTED = "budget_exhausted"
    FUNDING_CHANGED = "funding_changed"

    SCHEDULE_PUBLISHED = "schedule_published"
    SCHEDULE_CHANGED = "schedule_changed"

    DOCUMENT_PUBLISHED = "document_published"
    DOCUMENT_CHANGED = "document_changed"
    REGULATION_CHANGED = "regulation_changed"

    GEOGRAPHY_CHANGED = "geography_changed"
    TARGET_GROUP_CHANGED = "target_group_changed"

    RESULTS_PUBLISHED = "results_published"