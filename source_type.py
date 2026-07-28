from enum import StrEnum


class SourceType(StrEnum):
    PROJECT_HOME = "project_home"
    NEWS = "news"
    ANNOUNCEMENTS = "announcements"
    CALLS = "calls"
    SCHEDULE = "schedule"
    DOCUMENTS = "documents"
    REGULATIONS = "regulations"
    RESULTS = "results"
    ARCHIVE = "archive"
    CONTACT = "contact"
    OTHER = "other"
