# schemas/entry/source.py

from datetime import datetime

from pydantic import AnyHttpUrl

from enums.fetch_strategy import FetchStrategy
from source_content_type import SourceContentType
from common import BurInputModel, ExternalRef


class BurSourceIn(BurInputModel):
    source_ref: ExternalRef

    name: str
    url: AnyHttpUrl

    content_type: SourceContentType
    fetch_strategy: FetchStrategy = FetchStrategy.AUTO

    enabled: bool = True

    canonical_url: AnyHttpUrl | None = None
    last_verified_at: datetime | None = None

    notes: str | None = None