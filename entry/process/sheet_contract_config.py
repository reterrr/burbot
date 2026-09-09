from typing import Final

from entry.adapters.common import WorkbookSheet
from entry.process.sheet_contract import SheetIntakeContract

PROJECTS_INTAKE_CONTRACT = SheetIntakeContract(
    required_headers=frozenset({
        "main_url",
    }),
    optional_headers=frozenset({
        "project_ref",
        "project_number",
        "name",
        "onboarding_status",
        "lifecycle_status",
        "monitoring_enabled",
        "starts_at",
        "ends_at",
        "last_verified_at",
        "notes",
    }),
    required_values=frozenset({
        "main_url",
    }),
    header_aliases={
        "strona_projektu": "main_url",
        "adres_projektu": "main_url",
        "url_projektu": "main_url",
        "link_do_projektu": "main_url",
        "strona_www_projektu": "main_url",

        "nazwa_projektu": "name",
        "numer_projektu": "project_number",
        "data_rozpoczecia": "starts_at",
        "data_zakonczenia": "ends_at",
        "uwagi": "notes",
    },
)

WORKBOOK_INTAKE_CONTRACT: Final[
    dict[WorkbookSheet, SheetIntakeContract]
] = {
    WorkbookSheet.PROJECTS: PROJECTS_INTAKE_CONTRACT,

    WorkbookSheet.OPERATORS: SheetIntakeContract(
        required_headers=frozenset(),
        optional_headers=frozenset({
            "operator_ref",
            "name",
            "nip",
            "website_url",
            "active",
            "notes",
        }),
        header_aliases={
            "nazwa_operatora": "name",
            "nip_operatora": "nip",
            "strona_operatora": "website_url",
            "adres_operatora": "website_url",
        },
    ),

    WorkbookSheet.SOURCES: SheetIntakeContract(
        required_headers=frozenset({
            "url",
        }),
        optional_headers=frozenset({
            "source_ref",
            "name",
            "content_type",
            "fetch_strategy",
            "enabled",
            "canonical_url",
            "last_verified_at",
            "notes",
        }),
        required_values=frozenset({
            "url",
        }),
        header_aliases={
            "adres_zrodla": "url",
            "link_zrodla": "url",
            "nazwa_zrodla": "name",
        },
    ),
}
