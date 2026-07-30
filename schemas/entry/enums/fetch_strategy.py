# enums/fetch_strategy.py

from enum import StrEnum


class FetchStrategy(StrEnum):
    AUTO = "auto"
    HTTP = "http"
    BROWSER = "browser"
    API = "api"
    MANUAL = "manual"