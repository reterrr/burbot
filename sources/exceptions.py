"""Domain errors translated to HTTP errors at the API boundary."""


class SourceError(Exception):
    pass


class SourceNotFound(SourceError):
    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source {source_id} not found")


class SourceConflict(SourceError):
    pass


class InvalidSourceFile(SourceError):
    pass
