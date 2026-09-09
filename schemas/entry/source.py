"""Input schema describing a monitored BUR sources."""

# schemas/entry/sources.py

from datetime import datetime

from pydantic import AnyHttpUrl

from enums.fetch_strategy import FetchStrategy
from source_content_type import SourceContentType
from common import BurInputModel, ExternalRef


class BurSourceIn(BurInputModel):
    """Validate a monitored sources supplied by a BUR import.

    :ivar source_ref: Stable external reference to the sources.
    :ivar name: Human-readable name.
    :ivar url: Canonical URL of the sources.
    :ivar content_type: Content type.
    :ivar fetch_strategy: Fetch strategy.
    :ivar enabled: Enabled.
    :ivar canonical_url: URL providing canonical information.
    :ivar last_verified_at: Timestamp for last verified.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    source_ref: ExternalRef

    name: str
    url: AnyHttpUrl

    content_type: SourceContentType
    fetch_strategy: FetchStrategy = FetchStrategy.AUTO

    enabled: bool = True

    canonical_url: AnyHttpUrl | None = None
    last_verified_at: datetime | None = None

    notes: str | None = None
