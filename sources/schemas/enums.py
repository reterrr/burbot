"""Enums belonging to Layer 2: Sources / Acquisition."""

from enum import StrEnum


class SourceState(StrEnum):
    """Enumerate the supported sources state values."""

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


class SourceType(StrEnum):
    """Enumerate the supported sources type values."""

    HTML = "HTML"
    PDF = "PDF"
    XLSX = "XLSX"


class SourceStateTrigger(StrEnum):
    """Enumerate the supported sources state trigger values."""

    USER = "USER"
    SCHEDULER = "SCHEDULER"
    CRAWLER = "CRAWLER"
    PARSER = "PARSER"
    VALIDATOR = "VALIDATOR"
    DISCOVERY_ENGINE = "DISCOVERY_ENGINE"
    POLICY_CHECK = "POLICY_CHECK"
    SYSTEM = "SYSTEM"


class WarningSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class WarningStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"
