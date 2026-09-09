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
    """Define persistence operations for project records."""

    async def get_by_number(
        self,
        number: str,
        *,
        include_deleted: bool = False,
    ) -> Project | None:
        """Retrieve a record by number.

        :param number: Number value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_by_status(
        self,
        status: ProjectStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Project]:
        """List records filtered by status.

        :param status: Status value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_operators(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectOperator]:
        """List operators.

        :param project_id: Identifier of the project.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def put_operator(
        self,
        project_id: int,
        operator_id: int,
        operator_type: OperatorType,
    ) -> ProjectOperator:
        """Create or update operator.

        :param project_id: Identifier of the project.
        :param operator_id: Identifier of the operator.
        :param operator_type: Operator type value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def remove_operator(
        self,
        project_id: int,
        operator_id: int,
    ) -> bool:
        """Remove operator.

        :param project_id: Identifier of the project.
        :param operator_id: Identifier of the operator.
        :return: ``True`` when the requested state change was applied.
        """
        ...

    async def list_geographies(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectGeography]:
        """List geographies.

        :param project_id: Identifier of the project.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def put_geography(
        self,
        project_id: int,
        geography_id: int,
        relation_type: RelationType,
    ) -> ProjectGeography:
        """Create or update geography.

        :param project_id: Identifier of the project.
        :param geography_id: Identifier of the geography.
        :param relation_type: Relation type value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def remove_geography(
        self,
        project_id: int,
        geography_id: int,
        relation_type: RelationType,
    ) -> bool:
        """Remove geography.

        :param project_id: Identifier of the project.
        :param geography_id: Identifier of the geography.
        :param relation_type: Relation type value.
        :return: ``True`` when the requested state change was applied.
        """
        ...

    async def list_sources(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[ProjectSource]:
        """List sources.

        :param project_id: Identifier of the project.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def put_source(
        self,
        project_id: int,
        source_id: int,
    ) -> ProjectSource:
        """Create or update sources.

        :param project_id: Identifier of the project.
        :param source_id: Identifier of the sources.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def remove_source(
        self,
        project_id: int,
        source_id: int,
    ) -> bool:
        """Remove sources.

        :param project_id: Identifier of the project.
        :param source_id: Identifier of the sources.
        :return: ``True`` when the requested state change was applied.
        """
        ...


class OperatorRepository(SoftDeleteRepository[Operator, int], Protocol):
    """Define persistence operations for operator records."""

    async def get_by_nip(
        self,
        nip: str,
        *,
        include_deleted: bool = False,
    ) -> Operator | None:
        """Retrieve a record by nip.

        :param nip: Nip value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_sources(
        self,
        operator_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[OperatorSource]:
        """List sources.

        :param operator_id: Identifier of the operator.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def get_main_source(self, operator_id: int) -> Source | None:
        """Retrieve main sources.

        :param operator_id: Identifier of the operator.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def put_source(
        self,
        operator_id: int,
        source_id: int,
        *,
        is_main: bool = False,
    ) -> OperatorSource:
        """Create or update sources.

        :param operator_id: Identifier of the operator.
        :param source_id: Identifier of the sources.
        :param is_main: Whether the associated sources is the operator's primary sources.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def remove_source(
        self,
        operator_id: int,
        source_id: int,
    ) -> bool:
        """Remove sources.

        :param operator_id: Identifier of the operator.
        :param source_id: Identifier of the sources.
        :return: ``True`` when the requested state change was applied.
        """
        ...


class RecruitmentRepository(SoftDeleteRepository[Recruitment, int], Protocol):
    """Define persistence operations for recruitment records."""

    async def get_by_external_number(
        self,
        project_id: int,
        external_number: str,
        *,
        include_deleted: bool = False,
    ) -> Recruitment | None:
        """Retrieve a record by external number.

        :param project_id: Identifier of the project.
        :param external_number: External number value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def get_by_sequence(
        self,
        project_id: int,
        year: int,
        sequence_number: int,
        *,
        include_deleted: bool = False,
    ) -> Recruitment | None:
        """Retrieve a record by sequence.

        :param project_id: Identifier of the project.
        :param year: Year value.
        :param sequence_number: Sequence number value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_for_project(
        self,
        project_id: int,
        *,
        status: RecruitmentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Recruitment]:
        """List records belonging to project.

        :param project_id: Identifier of the project.
        :param status: Status value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def append_status(
        self,
        transition: RecruitmentStatusHistory,
    ) -> RecruitmentStatusHistory:
        """Append status.

        :param transition: Transition value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def list_status_history(
        self,
        recruitment_id: int,
    ) -> Sequence[RecruitmentStatusHistory]:
        """List status history.

        :param recruitment_id: Identifier of the recruitment.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_sources(
        self,
        recruitment_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[RecruitmentSource]:
        """List sources.

        :param recruitment_id: Identifier of the recruitment.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def put_source(
        self,
        recruitment_id: int,
        source_id: int,
    ) -> RecruitmentSource:
        """Create or update sources.

        :param recruitment_id: Identifier of the recruitment.
        :param source_id: Identifier of the sources.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def remove_source(
        self,
        recruitment_id: int,
        source_id: int,
    ) -> bool:
        """Remove sources.

        :param recruitment_id: Identifier of the recruitment.
        :param source_id: Identifier of the sources.
        :return: ``True`` when the requested state change was applied.
        """
        ...


class GeographyRepository(SoftDeleteRepository[Geography, int], Protocol):
    """Define persistence operations for geography records."""

    async def get_by_teryt(
        self,
        teryt_code: str,
        *,
        include_deleted: bool = False,
    ) -> Geography | None:
        """Retrieve a record by teryt.

        :param teryt_code: Teryt code value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def find(
        self,
        geography_type: GeographyType,
        name: str,
        parent_id: int | None,
        *,
        include_deleted: bool = False,
    ) -> Geography | None:
        """Find a record matching the supplied attributes.

        :param geography_type: Geography type value.
        :param name: Human-readable or database type name, depending on context.
        :param parent_id: Identifier of the parent record, or ``None`` for root records.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_children(
        self,
        parent_id: int | None,
        *,
        geography_type: GeographyType | None = None,
        include_deleted: bool = False,
    ) -> Sequence[Geography]:
        """List children.

        :param parent_id: Identifier of the parent record, or ``None`` for root records.
        :param geography_type: Geography type value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...
