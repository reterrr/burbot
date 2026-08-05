"""Projects, operators, recruitments and hierarchical geography."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlmodel import Field, SQLModel

from ..enums import (
    ClosedStatus,
    GeographyType,
    OperatorType,
    ProjectStatus,
    ProjectType,
    RecruitmentStatus,
    RelationType,
)
from ..mixins import SoftDeleteMixin, pg_enum


class Project(SoftDeleteMixin, table=True):
    """Represent a monitored funding project.

    :ivar id: Database primary key.
    :ivar type: Type.
    :ivar name: Human-readable name.
    :ivar number: Number.
    :ivar status: Status.
    :ivar start_date: Start date.
    :ivar end_date: End date.
    """
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_status", "status"),)

    id: int | None = Field(default=None, primary_key=True)
    type: ProjectType = Field(
        sa_column=Column(pg_enum(ProjectType, "project_type"), nullable=False)
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    number: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, unique=True),
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.PLANNED,
        sa_column=Column(
            pg_enum(ProjectStatus, "project_status"),
            nullable=False,
            server_default=text("'PLANNED'"),
        ),
    )
    start_date: date | None = None
    end_date: date | None = None


class Operator(SoftDeleteMixin, table=True):
    """Represent an organization operating or partnering on a project.

    :ivar id: Database primary key.
    :ivar name: Human-readable name.
    :ivar nip: Normalized ten-digit Polish tax identifier.
    """
    __tablename__ = "operators"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, nullable=False))
    nip: str | None = Field(
        default=None,
        sa_column=Column(String(10), nullable=True, unique=True),
    )


class ProjectOperator(SoftDeleteMixin, table=True):
    """Associate an operator with a project and record its role.

    :ivar project_id: Identifier of the related project.
    :ivar operator_id: Identifier of the related operator.
    :ivar operator_type: Operator type.
    """
    __tablename__ = "project_operators"
    __table_args__ = (
        Index("ix_project_operators_operator_project", "operator_id", "project_id"),
    )

    project_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    operator_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("operators.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    operator_type: OperatorType = Field(
        sa_column=Column(pg_enum(OperatorType, "operator_type"), nullable=False)
    )


class Recruitment(SoftDeleteMixin, table=True):
    """Represent a recruitment round belonging to a project.

    :ivar id: Database primary key.
    :ivar project_id: Identifier of the related project.
    :ivar external_number: External number.
    :ivar sequence_number: Sequence number.
    :ivar year: Year.
    :ivar status: Status.
    :ivar start_date: Start date.
    :ivar end_date: End date.
    :ivar announced_year: Announced year.
    :ivar announced_quarter: Announced quarter.
    :ivar closed_status: Closed status.
    :ivar status_reason: Status reason.
    """
    __tablename__ = "recruitments"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "external_number",
            name="uq_recruitments_project_external_number",
        ),
        UniqueConstraint(
            "project_id",
            "year",
            "sequence_number",
            name="uq_recruitments_project_year_sequence",
        ),
        CheckConstraint(
            "announced_quarter IS NULL OR announced_quarter BETWEEN 1 AND 4",
            name="announced_quarter_range",
        ),
        Index("ix_recruitments_project_status", "project_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    external_number: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    sequence_number: int | None = None
    year: int | None = None
    status: RecruitmentStatus = Field(
        default=RecruitmentStatus.ANNOUNCED,
        sa_column=Column(
            pg_enum(RecruitmentStatus, "recruitment_status"),
            nullable=False,
            server_default=text("'ANNOUNCED'"),
        ),
    )
    start_date: date | None = None
    end_date: date | None = None
    announced_year: int | None = None
    announced_quarter: int | None = None
    closed_status: ClosedStatus | None = Field(
        default=None,
        sa_column=Column(pg_enum(ClosedStatus, "closed_status"), nullable=True),
    )
    status_reason: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class RecruitmentStatusHistory(SQLModel, table=True):
    """Record an immutable recruitment status transition.

    :ivar id: Database primary key.
    :ivar recruitment_id: Identifier of the related recruitment.
    :ivar from_status: From status.
    :ivar to_status: To status.
    :ivar closed_status: Closed status.
    :ivar reason: Reason.
    :ivar changed_at: Timestamp for changed.
    """
    __tablename__ = "recruitment_status_history"
    __table_args__ = (
        Index(
            "ix_recruitment_status_history_recruitment_changed",
            "recruitment_id",
            "changed_at",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    recruitment_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("recruitments.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    from_status: RecruitmentStatus | None = Field(
        default=None,
        sa_column=Column(
            pg_enum(RecruitmentStatus, "recruitment_status"),
            nullable=True,
        ),
    )
    to_status: RecruitmentStatus = Field(
        sa_column=Column(
            pg_enum(RecruitmentStatus, "recruitment_status"),
            nullable=False,
        )
    )
    closed_status: ClosedStatus | None = Field(
        default=None,
        sa_column=Column(pg_enum(ClosedStatus, "closed_status"), nullable=True),
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    changed_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )


class Geography(SoftDeleteMixin, table=True):
    """Represent one node in the hierarchical geography registry.

    :ivar id: Database primary key.
    :ivar type: Type.
    :ivar name: Human-readable name.
    :ivar parent_id: Identifier of the related parent.
    :ivar teryt_code: Teryt code.
    """
    __tablename__ = "geographies"
    __table_args__ = (
        Index(
            "uq_geographies_type_name_parent",
            "type",
            "name",
            "parent_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_geographies_parent_id", "parent_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    type: GeographyType = Field(
        sa_column=Column(pg_enum(GeographyType, "geography_type"), nullable=False)
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    parent_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("geographies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    teryt_code: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, unique=True),
    )


class ProjectGeography(SoftDeleteMixin, table=True):
    """Associate a project with an included or excluded geographic unit.

    :ivar project_id: Identifier of the related project.
    :ivar geography_id: Identifier of the related geography.
    :ivar relation_type: Relation type.
    """
    __tablename__ = "project_geographies"
    __table_args__ = (Index("ix_project_geographies_geography_id", "geography_id"),)

    project_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    geography_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("geographies.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    relation_type: RelationType = Field(
        default=RelationType.INCLUDE,
        sa_column=Column(
            pg_enum(RelationType, "relation_type"),
            primary_key=True,
            nullable=False,
            server_default=text("'INCLUDE'"),
        ),
    )
