from enum import StrEnum


class ExtractionRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    COMPLETED = "completed"  # Read compatibility for historical workflow runs.


class ElementFrom(StrEnum):
    HTML = "HTML"
    PDF = "PDF"
    XLSX = "XLSX"


class SelectorType(StrEnum):
    CSS = "CSS"
    XPATH = "XPATH"
    ANCHOR_RELATIVE = "ANCHOR_RELATIVE"
    TEXT_PATTERN = "TEXT_PATTERN"
    INDEX_ABSOLUTE = "INDEX_ABSOLUTE"
    PDF_REGION = "PDF_REGION"
    XLSX_RANGE = "XLSX_RANGE"


class DiscoveryMethod(StrEnum):
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"
    PATTERN = "PATTERN"


class ObservationStatus(StrEnum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    BOUND = "BOUND"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AnchorRelationKind(StrEnum):
    SAME_ROW = "SAME_ROW"
    SAME_COLUMN = "SAME_COLUMN"
    NEXT_SIBLING = "NEXT_SIBLING"
    PREVIOUS_SIBLING = "PREVIOUS_SIBLING"
    PARENT = "PARENT"
    CHILD = "CHILD"


class ExtractionIssueCode(StrEnum):
    VALUE_NOT_FOUND = "VALUE_NOT_FOUND"
    SELECTOR_BROKEN = "SELECTOR_BROKEN"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
