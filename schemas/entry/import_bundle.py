# schemas/entry/import_bundle.py

from pydantic import Field, model_validator

from common import BurInputModel
from import_metadata import BurImportMetadataIn
from operator import BurOperatorIn
from project import BurProjectIn
from project_geography import BurProjectGeographyIn
from project_operator import BurProjectOperatorIn
from project_source import BurProjectSourceIn
from source import BurSourceIn
from source_expectation import BurSourceExpectationIn
from source_section import BurSourceSectionIn
from source_selector import BurSourceSelectorIn


class BurImportBundleIn(BurInputModel):
    metadata: BurImportMetadataIn

    operators: list[BurOperatorIn] = Field(default_factory=list)
    projects: list[BurProjectIn] = Field(default_factory=list)

    project_operators: list[BurProjectOperatorIn] = Field(
        default_factory=list
    )
    project_geographies: list[BurProjectGeographyIn] = Field(
        default_factory=list
    )

    sources: list[BurSourceIn] = Field(default_factory=list)
    project_sources: list[BurProjectSourceIn] = Field(
        default_factory=list
    )

    source_sections: list[BurSourceSectionIn] = Field(
        default_factory=list
    )
    source_selectors: list[BurSourceSelectorIn] = Field(
        default_factory=list
    )
    source_expectations: list[BurSourceExpectationIn] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_references(self) -> "BurImportBundleIn":
        operator_refs = {
            operator.operator_ref
            for operator in self.operators
        }
        project_refs = {
            project.project_ref
            for project in self.projects
        }
        source_refs = {
            source.source_ref
            for source in self.sources
        }
        project_source_refs = {
            relation.project_source_ref
            for relation in self.project_sources
        }
        section_refs = {
            section.section_ref
            for section in self.source_sections
        }

        self._ensure_unique(
            [operator.operator_ref for operator in self.operators],
            "operator_ref",
        )
        self._ensure_unique(
            [project.project_ref for project in self.projects],
            "project_ref",
        )
        self._ensure_unique(
            [source.source_ref for source in self.sources],
            "source_ref",
        )
        self._ensure_unique(
            [
                relation.project_source_ref
                for relation in self.project_sources
            ],
            "project_source_ref",
        )
        self._ensure_unique(
            [
                section.section_ref
                for section in self.source_sections
            ],
            "section_ref",
        )

        for relation in self.project_operators:
            if relation.project_ref not in project_refs:
                raise ValueError(
                    f"Nieznany project_ref: {relation.project_ref}"
                )

            if relation.operator_ref not in operator_refs:
                raise ValueError(
                    f"Nieznany operator_ref: {relation.operator_ref}"
                )

        for geography in self.project_geographies:
            if geography.project_ref not in project_refs:
                raise ValueError(
                    f"Nieznany project_ref geografii: "
                    f"{geography.project_ref}"
                )

        for relation in self.project_sources:
            if relation.project_ref not in project_refs:
                raise ValueError(
                    f"Nieznany project_ref źródła: "
                    f"{relation.project_ref}"
                )

            if relation.source_ref not in source_refs:
                raise ValueError(
                    f"Nieznany source_ref: {relation.source_ref}"
                )

        for section in self.source_sections:
            if section.project_source_ref not in project_source_refs:
                raise ValueError(
                    f"Nieznany project_source_ref sekcji: "
                    f"{section.project_source_ref}"
                )

        for selector in self.source_selectors:
            if selector.section_ref not in section_refs:
                raise ValueError(
                    f"Nieznany section_ref selektora: "
                    f"{selector.section_ref}"
                )

        for expectation in self.source_expectations:
            if (
                    expectation.project_source_ref
                    not in project_source_refs
            ):
                raise ValueError(
                    f"Nieznany project_source_ref oczekiwania: "
                    f"{expectation.project_source_ref}"
                )

            if (
                    expectation.section_ref is not None
                    and expectation.section_ref not in section_refs
            ):
                raise ValueError(
                    f"Nieznany section_ref oczekiwania: "
                    f"{expectation.section_ref}"
                )

        self._validate_primary_operators()

        return self

    @staticmethod
    def _ensure_unique(
            values: list[str],
            field_name: str,
    ) -> None:
        duplicates = {
            value
            for value in values
            if values.count(value) > 1
        }

        if duplicates:
            raise ValueError(
                f"Powtórzone wartości {field_name}: "
                f"{sorted(duplicates)}"
            )

    def _validate_primary_operators(self) -> None:
        from project_operator import ProjectOperatorRole

        primary_by_project: dict[str, int] = {}

        for relation in self.project_operators:
            if relation.role == ProjectOperatorRole.PRIMARY_OPERATOR:
                primary_by_project[relation.project_ref] = (
                        primary_by_project.get(relation.project_ref, 0) + 1
                )

        invalid_projects = {
            project_ref: count
            for project_ref, count in primary_by_project.items()
            if count > 1
        }

        if invalid_projects:
            raise ValueError(
                "Projekt nie może mieć więcej niż jednego "
                f"głównego operatora: {invalid_projects}"
            )
