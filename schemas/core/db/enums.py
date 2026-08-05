"""Database enums. Values intentionally match the DBML contract."""

from enum import StrEnum


class DatabaseEnum(StrEnum):
    """String enum persisted by value in named PostgreSQL enum types."""


class ProjectType(DatabaseEnum):
    B2B = "B2B"
    B2C = "B2C"


class ProjectStatus(DatabaseEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"
    PLANNED = "PLANNED"


class OperatorType(DatabaseEnum):
    LEAD = "LEAD"
    PARTNER = "PARTNER"


class GeographyType(DatabaseEnum):
    VOIVODSHIP = "VOIVODSHIP"
    SUBREGION = "SUBREGION"
    COUNTY = "COUNTY"
    COMMUNE = "COMMUNE"


class RelationType(DatabaseEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class RecruitmentStatus(DatabaseEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ANNOUNCED = "ANNOUNCED"
    CLOSED = "CLOSED"


class ClosedStatus(DatabaseEnum):
    END_DATE_EXCEEDED = "END_DATE_EXCEEDED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCELLED = "CANCELLED"
    OTHER = "OTHER"


class BusinessEntityType(DatabaseEnum):
    PROJECT = "PROJECT"
    OPERATOR = "OPERATOR"
    RECRUITMENT = "RECRUITMENT"


class SourceState(DatabaseEnum):
    ADDING = "ADDING"
    UNDISCOVERED = "UNDISCOVERED"
    DISCOVERING = "DISCOVERING"
    VALIDATING = "VALIDATING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    REDISCOVERING = "REDISCOVERING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"


class SourceType(DatabaseEnum):
    HTML = "HTML"
    PDF = "PDF"


class SourceStateTrigger(DatabaseEnum):
    USER = "USER"
    SCHEDULER = "SCHEDULER"
    CRAWLER = "CRAWLER"
    PARSER = "PARSER"
    VALIDATOR = "VALIDATOR"
    DISCOVERY_ENGINE = "DISCOVERY_ENGINE"
    POLICY_CHECK = "POLICY_CHECK"
    SYSTEM = "SYSTEM"


class WarningSeverity(DatabaseEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class WarningStatus(DatabaseEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class ExtractionRunStatus(DatabaseEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ElementFrom(DatabaseEnum):
    HTML = "HTML"
    PDF = "PDF"


class DiscoveryMethod(DatabaseEnum):
    MANUAL = "MANUAL"
    REGEX = "REGEX"
    SEQ_PATTERN = "SEQ_PATTERN"
    ASSOC_RULE = "ASSOC_RULE"
    EMBEDDING = "EMBEDDING"
    LOCAL_LLM = "LOCAL_LLM"
    CLOUD_LLM = "CLOUD_LLM"


class SelectorType(DatabaseEnum):
    CSS = "CSS"
    XPATH = "XPATH"
    ANCHOR_RELATIVE = "ANCHOR_RELATIVE"
    TEXT_PATTERN = "TEXT_PATTERN"
    INDEX_ABSOLUTE = "INDEX_ABSOLUTE"
    PDF_REGION = "PDF_REGION"


class AnchorRelationKind(DatabaseEnum):
    NEXT_SIBLING = "NEXT_SIBLING"
    PREVIOUS_SIBLING = "PREVIOUS_SIBLING"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    SAME_ROW = "SAME_ROW"
    SAME_COLUMN = "SAME_COLUMN"
    NEAREST_AFTER = "NEAREST_AFTER"
    NEAREST_BEFORE = "NEAREST_BEFORE"


class PatternType(DatabaseEnum):
    SEQUENTIAL = "SEQUENTIAL"
    ASSOCIATIVE = "ASSOCIATIVE"


class ItemKind(DatabaseEnum):
    TOKEN_CLASS = "TOKEN_CLASS"
    PHRASE = "PHRASE"
    SEMANTIC_CLASS = "SEMANTIC_CLASS"
    TARGET_FIELD = "TARGET_FIELD"


class ItemsetRole(DatabaseEnum):
    ANTECEDENT = "ANTECEDENT"
    CONSEQUENT = "CONSEQUENT"
    NONE = "NONE"


class ObservationStatus(DatabaseEnum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    BOUND = "BOUND"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ConfirmedBy(DatabaseEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
