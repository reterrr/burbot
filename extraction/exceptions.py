class ExtractionError(Exception):
    """Base class for extraction-layer application errors."""


class ExtractionNotFound(ExtractionError):
    """Requested extraction resource does not exist."""


class ExtractionConflict(ExtractionError):
    """Requested operation conflicts with the current workflow/source state."""


class ExtractionValidationError(ExtractionError):
    """Submitted extraction evidence is inconsistent with the domain model."""


class ExtractionNotConfigured(ExtractionError):
    """Snapshot execution adapter is not configured in this application."""
