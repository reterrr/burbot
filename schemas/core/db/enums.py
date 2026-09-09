"""Database enums. Values intentionally match the DBML contract."""

from enum import StrEnum

from sources.schemas.enums import (
    SourceState as SourceState,
)
from sources.schemas.enums import (
    SourceStateTrigger as SourceStateTrigger,
)
from sources.schemas.enums import (
    SourceType as SourceType,
)


class DatabaseEnum(StrEnum):
    """Provide the common base for enums persisted by their string values."""


class ProjectType(DatabaseEnum):
    """Enumerate the supported project type values."""
    B2B = "B2B"
    B2C = "B2C"


class ProjectStatus(DatabaseEnum):
    """Enumerate the supported project status values."""
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"
    PLANNED = "PLANNED"


class OperatorType(DatabaseEnum):
    """Enumerate the supported operator type values."""
    LEAD = "LEAD"
    PARTNER = "PARTNER"


class GeographyType(DatabaseEnum):
    """Enumerate the supported geography type values."""
    VOIVODSHIP = "VOIVODSHIP"
    SUBREGION = "SUBREGION"
    COUNTY = "COUNTY"
    COMMUNE = "COMMUNE"


class RelationType(DatabaseEnum):
    """Enumerate the supported relation type values."""
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class RecruitmentStatus(DatabaseEnum):
    """Enumerate the supported recruitment status values."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ANNOUNCED = "ANNOUNCED"
    CLOSED = "CLOSED"


class ClosedStatus(DatabaseEnum):
    """Enumerate the supported closed status values."""
    END_DATE_EXCEEDED = "END_DATE_EXCEEDED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCELLED = "CANCELLED"
    OTHER = "OTHER"


class BusinessEntityType(DatabaseEnum):
    """Enumerate the supported business entity type values."""
    FUNDING_RULE = "FUNDING_RULE"
    GEOGRAPHY = "GEOGRAPHY"
    PROJECT = "PROJECT"
    OPERATOR = "OPERATOR"
    RECRUITMENT = "RECRUITMENT"


class WarningSeverity(DatabaseEnum):
    """Enumerate the supported warning severity values."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class WarningStatus(DatabaseEnum):
    """Enumerate the supported warning status values."""
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class ExtractionRunStatus(DatabaseEnum):
    """Enumerate the supported extraction run status values."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ElementFrom(DatabaseEnum):
    """Enumerate the supported element from values."""
    HTML = "HTML"
    PDF = "PDF"


class DiscoveryMethod(DatabaseEnum):
    """Enumerate the supported discovery method values."""
    MANUAL = "MANUAL"
    REGEX = "REGEX"
    SEQ_PATTERN = "SEQ_PATTERN"
    ASSOC_RULE = "ASSOC_RULE"
    EMBEDDING = "EMBEDDING"
    LOCAL_LLM = "LOCAL_LLM"
    CLOUD_LLM = "CLOUD_LLM"


class SelectorType(DatabaseEnum):
    """Enumerate the supported selector type values."""
    CSS = "CSS"
    XPATH = "XPATH"
    ANCHOR_RELATIVE = "ANCHOR_RELATIVE"
    TEXT_PATTERN = "TEXT_PATTERN"
    INDEX_ABSOLUTE = "INDEX_ABSOLUTE"
    PDF_REGION = "PDF_REGION"


class AnchorRelationKind(DatabaseEnum):
    """Enumerate the supported anchor relation kind values."""
    NEXT_SIBLING = "NEXT_SIBLING"
    PREVIOUS_SIBLING = "PREVIOUS_SIBLING"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    SAME_ROW = "SAME_ROW"
    SAME_COLUMN = "SAME_COLUMN"
    NEAREST_AFTER = "NEAREST_AFTER"
    NEAREST_BEFORE = "NEAREST_BEFORE"


class PatternType(DatabaseEnum):
    """Enumerate the supported pattern type values."""
    SEQUENTIAL = "SEQUENTIAL"
    ASSOCIATIVE = "ASSOCIATIVE"


class ItemKind(DatabaseEnum):
    """Enumerate the supported item kind values."""
    TOKEN_CLASS = "TOKEN_CLASS"
    PHRASE = "PHRASE"
    SEMANTIC_CLASS = "SEMANTIC_CLASS"
    TARGET_FIELD = "TARGET_FIELD"


class ItemsetRole(DatabaseEnum):
    """Enumerate the supported itemset role values."""
    ANTECEDENT = "ANTECEDENT"
    CONSEQUENT = "CONSEQUENT"
    NONE = "NONE"


class ObservationStatus(DatabaseEnum):
    """Enumerate the supported observation status values."""
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    BOUND = "BOUND"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ConfirmedBy(DatabaseEnum):
    """Enumerate the supported confirmed by values."""
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class GeographyCodeSystem(DatabaseEnum):
    TERC = "TERC"
    NUTS = "NUTS"
