"""Compile/validate programs without writes, or explicitly apply schema and seeds."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import Field

from business_layer.api.dependencies import BusinessServiceDep
from business_layer.api.dependencies import get_business_service as get_language_service
from business_layer.schemas.execution import ExecutionResult
from business_layer.services.schema_language import LanguageModel, Sema
from business_layer.services.schema_parser import Program, compile_source

router = APIRouter(prefix="/business", tags=["business language"])


class CompileRequest(LanguageModel):
    code: str = Field(max_length=100_000)
    namespace: str = ""
    table_names: dict[str, str] = Field(default_factory=dict)


class ExecuteRequest(LanguageModel):
    code: str | None = Field(default=None, max_length=100_000)
    program: Program | None = None
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None


# Compatibility names for callers overriding the old language dependency.
LanguageServiceDep = BusinessServiceDep


def language_error(error):
    if isinstance(error, Sema.SemaException):
        return HTTPException(422, error.diagnostic())
    if isinstance(error, LookupError):
        return HTTPException(404, str(error))
    return HTTPException(422, str(error))


@router.post("/language/compile", response_model=Program)
async def compile_program(request: CompileRequest):
    try:
        return compile_source(
            request.code, namespace=request.namespace, table_names=request.table_names
        )
    except (ValueError, LookupError) as error:
        raise language_error(error) from error


@router.post("/models/{model_id}/compile", response_model=Program)
@router.post("/models/{model_id}/language/compile", response_model=Program, include_in_schema=False)
async def compile_model_program(
    model_id: int, request: CompileRequest, service: BusinessServiceDep
):
    try:
        return await service.compile(model_id, request.code)
    except (ValueError, LookupError) as error:
        raise language_error(error) from error


@router.post("/models/{model_id}/execute", response_model=ExecutionResult)
@router.post(
    "/models/{model_id}/language/execute", response_model=ExecutionResult, include_in_schema=False
)
async def execute_program(model_id: int, request: ExecuteRequest, service: BusinessServiceDep):
    try:
        return await service.execute(
            model_id,
            code=request.code,
            program=request.program,
            reason=request.reason,
            metadata_json=request.metadata_json,
        )
    except (ValueError, LookupError) as error:
        raise language_error(error) from error


__all__ = ["router", "get_language_service", "LanguageServiceDep"]
