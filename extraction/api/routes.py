from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/extractions",
)


class CreateExtractionConcreteValueRequest(BaseModel):
    concrete_value: str
    char_start: int
    char_end: int

    token_class_id: str

    object_field_id: int


class SetExtractionFieldEvidenceRequest(BaseModel):
    snapshot_id: int

    values: list[CreateExtractionConcreteValueRequest]


class CreateFieldObservationRequest(BaseModel):
    object_id: int

    concrete_values: list[SetExtractionFieldEvidenceRequest]


class CreateExtractionRunRequest(BaseModel):
    workflow_id: int

    field_observations: list[CreateFieldObservationRequest]


@router.get(
    "/"
)
async def get_extraction_runs():


@router.post(
    "/"
)
async def create_extraction_run():
