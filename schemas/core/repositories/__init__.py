"""Public storage-agnostic repository interfaces."""

from .base import (
    AppendOnlyRepository,
    CurrentStateRepository,
    ReadRepository,
    SoftDeleteRepository,
)
from .business import (
    GeographyRepository,
    OperatorRepository,
    ProjectRepository,
    RecruitmentRepository,
)
from .extraction import (
    ElementRepository,
    FieldObservationRepository,
    GroundTruthRepository,
    PatternRepository,
    PhraseClassificationRepository,
    PhraseRepository,
    ScopeInstanceRepository,
    ScopeRepository,
    SemanticClassRepository,
    TargetFieldRepository,
    TokenClassRepository,
)
from .system import (
    ExtractionRunRepository,
    SourceRepository,
    SourceSnapshotRepository,
    StoredFileRepository,
)

__all__ = [
    "AppendOnlyRepository",
    "CurrentStateRepository",
    "ElementRepository",
    "ExtractionRunRepository",
    "FieldObservationRepository",
    "GeographyRepository",
    "GroundTruthRepository",
    "OperatorRepository",
    "PatternRepository",
    "PhraseClassificationRepository",
    "PhraseRepository",
    "ProjectRepository",
    "ReadRepository",
    "RecruitmentRepository",
    "ScopeInstanceRepository",
    "ScopeRepository",
    "SemanticClassRepository",
    "SoftDeleteRepository",
    "SourceRepository",
    "SourceSnapshotRepository",
    "StoredFileRepository",
    "TargetFieldRepository",
    "TokenClassRepository",
]
