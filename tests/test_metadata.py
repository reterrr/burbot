"""Fast metadata checks that do not require a running PostgreSQL server."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from schemas.core.db import metadata

EXPECTED_TABLES = {
    "anchor_element_references",
    "check_schedules",
    "concrete_values",
    "elements",
    "elements_html",
    "elements_pdf",
    "extraction_runs",
    "field_observations",
    "field_selectors",
    "generalized_patterns",
    "geographies",
    "ground_truth",
    "operator_sources",
    "operators",
    "pattern_instance_matches",
    "pattern_instances",
    "pattern_items",
    "phrase_classifications",
    "phrases",
    "project_geographies",
    "project_operators",
    "project_sources",
    "projects",
    "recruitment_sources",
    "recruitment_status_history",
    "recruitments",
    "scope_instances",
    "semantic_classes",
    "source_metadata",
    "source_scopes",
    "source_snapshots",
    "source_state_history",
    "source_warnings",
    "sources",
    "stored_files",
    "target_fields",
    "token_classes",
}


def test_all_tables_are_registered() -> None:
    assert set(metadata.tables) == EXPECTED_TABLES


def test_every_table_compiles_for_postgresql() -> None:
    dialect = postgresql.dialect()
    for table in metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl


def test_soft_delete_policy() -> None:
    soft_deletable = {
        "generalized_patterns",
        "geographies",
        "ground_truth",
        "operator_sources",
        "operators",
        "pattern_items",
        "phrase_classifications",
        "phrases",
        "project_geographies",
        "project_operators",
        "project_sources",
        "projects",
        "recruitment_sources",
        "recruitments",
        "semantic_classes",
        "target_fields",
        "token_classes",
    }

    actual = {
        table.name
        for table in metadata.tables.values()
        if "deleted_at" in table.columns
    }
    assert actual == soft_deletable


def test_runtime_tables_are_not_soft_deletable() -> None:
    runtime_tables = {
        "concrete_values",
        "elements",
        "extraction_runs",
        "field_observations",
        "pattern_instances",
        "scope_instances",
        "source_snapshots",
        "source_state_history",
    }

    for table_name in runtime_tables:
        assert "deleted_at" not in metadata.tables[table_name].columns
