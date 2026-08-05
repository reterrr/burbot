"""Repository interfaces for business aggregates."""

from collections.abc import Sequence
from typing import Protocol

from ..db import (
    Geography,
    Operator,
    OperatorSource,
    Project,
    ProjectGeography,
    ProjectOperator,
    ProjectSource,
    Recruitment,
    RecruitmentSource,
    RecruitmentStatusHistory,
    Source,
)
from ..db.enums import (
    GeographyType,
    OperatorType,
    ProjectStatus,
    RecruitmentStatus,
    RelationType,
)
from .base import SoftDeleteRepository


class ProjectRepository(SoftDeleteRepository[Project, int], Protocol):
    """Project aggregate, including operators, geographies and source links."""

    async def get_by_number(
        self,
        number: str,
        *,
        include_deleted: bool = False,
    ) -> Project | None: ...

    async def list_by_status(
        self,
        status: ProjectStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Project]: ...

    async def list_operators(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectOperator]: ...

    async def put_operator(
        self,
        project_id: int,
        operator_id: int,
        operator_type: OperatorType,
    ) -> ProjectOperator: ...

    async def remove_operator(
        self,
        project_id: int,
        operator_id: int,
    ) -> bool: ...

    async def list_geographies(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectGeography]: ...

    async def put_geography(
        self,
        project_id: int,
        geography_id: int,
        relation_type: RelationType,
    ) -> ProjectGeography: ...

    async def remove_geography(
        self,
        project_id: int,
        geography_id: int,
        relation_type: RelationType,
    ) -> bool: ...

    async def list_sources(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectSource]: ...

    async def put_source(
        self,
        project_id: int,
        source_id: int,
    ) -> ProjectSource: ...

    async def remove_source(
        self,
        project_id: int,
        source_id: int,
    ) -> bool: ...


class OperatorRepository(SoftDeleteRepository[Operator, int], Protocol):
    """Operator aggregate, including its source links."""

    async def get_by_nip(
        self,
        nip: str,
        *,
        include_deleted: bool = False,
    ) -> Operator | None: ...

    async def list_sources(
        self,
        operator_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[OperatorSource]: ...

    async def get_main_source(self, operator_id: int) -> Source | None: ...

    async def put_source(
        self,
        operator_id: int,
        source_id: int,
        *,
        is_main: bool = False,
    ) -> OperatorSource: ...

    async def remove_source(
        self,
        operator_id: int,
        source_id: int,
    ) -> bool: ...


class RecruitmentRepository(SoftDeleteRepository[Recruitment, int], Protocol):
    """Recruitment aggregate, including status history and source links."""

    async def get_by_external_number(
        self,
        project_id: int,
        external_number: str,
        *,
        include_deleted: bool = False,
    ) -> Recruitment | None: ...

    async def get_by_sequence(
        self,
        project_id: int,
        year: int,
        sequence_number: int,
        *,
        include_deleted: bool = False,
    ) -> Recruitment | None: ...

    async def list_for_project(
        self,
        project_id: int,
        *,
        status: RecruitmentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Recruitment]: ...

    async def append_status(
        self,
        transition: RecruitmentStatusHistory,
    ) -> RecruitmentStatusHistory: ...

    async def list_status_history(
        self,
        recruitment_id: int,
    ) -> Sequence[RecruitmentStatusHistory]: ...

    async def list_sources(
        self,
        recruitment_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[RecruitmentSource]: ...

    async def put_source(
        self,
        recruitment_id: int,
        source_id: int,
    ) -> RecruitmentSource: ...

    async def remove_source(
        self,
        recruitment_id: int,
        source_id: int,
    ) -> bool: ...


class GeographyRepository(SoftDeleteRepository[Geography, int], Protocol):
    """Hierarchical geography registry."""

    async def get_by_teryt(
        self,
        teryt_code: str,
        *,
        include_deleted: bool = False,
    ) -> Geography | None: ...

    async def find(
        self,
        geography_type: GeographyType,
        name: str,
        parent_id: int | None,
        *,
        include_deleted: bool = False,
    ) -> Geography | None: ...

    async def list_children(
        self,
        parent_id: int | None,
        *,
        geography_type: GeographyType | None = None,
        include_deleted: bool = False,
    ) -> Sequence[Geography]: ...
