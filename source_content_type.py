from enum import StrEnum


class SourceContentType(StrEnum):
    HTML = "html"
    DYNAMIC_HTML = "dynamic_html"
    PDF = "pdf"
    PDF_LIST = "pdf_list"
    FILE_LIST = "file_list"
    API = "api"
    MANUAL = "manual"
    UNKNOWN = "unknown"