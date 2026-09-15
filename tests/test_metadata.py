"""Validate the active backend registry instead of the retired fixed-entity schema."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlmodel import SQLModel

from migrations.load_models import load_models


def test_active_evidence_registry_and_foreign_keys():
    load_models()
    expected = {
        "extraction_runs",
        "field_observations",
        "extraction_concrete_values",
        "elements",
        "elements_html",
        "elements_pdf",
        "elements_xlsx",
        "anchor_element_references",
        "source_scopes",
        "scope_instances",
        "field_selectors",
        "ground_truth",
        "source_snapshots",
        "extraction_captures",
    }
    assert expected <= SQLModel.metadata.tables.keys()
    assert "target_fields" not in SQLModel.metadata.tables
    tracking = SQLModel.metadata.tables["source_object_field_trackings"]
    for column in ("last_observation_id", "baseline_observation_id"):
        assert (
            next(iter(tracking.c[column].foreign_keys)).target_fullname == "field_observations.id"
        )
    for name in expected:
        table = SQLModel.metadata.tables[name]
        assert "deleted_at" not in table.c
        for foreign_key in table.foreign_keys:
            assert foreign_key.column is not None
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=postgresql.dialect()))
