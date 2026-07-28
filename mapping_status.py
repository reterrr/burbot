from enum import StrEnum


class MappingStatus(StrEnum):
    REQUIRES_ANALYSIS = "requires_analysis"
    MAPPED = "mapped"
    REQUIRES_VERIFICATION = "requires_verification"
    VERIFIED = "verified"
    MANUAL_ONLY = "manual_only"
    INVALID = "invalid"