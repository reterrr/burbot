"""Strategies available when fetching an imported sources."""

# enums/fetch_strategy.py

from enum import StrEnum


class FetchStrategy(StrEnum):
    """Enumerate the supported fetch strategy values."""
    AUTO = "auto"
    HTTP = "http"
    BROWSER = "browser"
    API = "api"
    MANUAL = "manual"
