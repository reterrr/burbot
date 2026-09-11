"""Domain errors translated to HTTP errors at the API boundary."""

from uuid import UUID


class SourceError(Exception):
    pass


class SourceNotFound(SourceError):
    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source {source_id} not found")


class SourceConflict(SourceError):
    pass


class SourceResourceNotFound(SourceError):
    def __init__(self, resource: str, identifier: int | UUID) -> None:
        super().__init__(f"{resource} {identifier} not found")


class SourceValidationError(SourceError):
    pass


class InvalidSourceFile(SourceValidationError):
    pass
