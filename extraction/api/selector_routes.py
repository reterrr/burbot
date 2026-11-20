"""Portable SelectorTree lifecycle and run-bound snapshot evaluation."""

import re
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from extraction.api.dependencies import ExtractionServiceDep
from extraction.exceptions import ExtractionValidationError
from extraction.schemas.api import Identifier, Page
from extraction.schemas.selector_api import (
    ClientEvaluation,
    SelectorExecution,
    SelectorExecutionResult,
    SelectorImport,
    SelectorReview,
    StoredEvaluation,
)
from extraction.schemas.selector_tree import (
    PortableUUID,
    SelectorDefinition,
    SelectorTree,
    SelectorVersionDefinition,
)

router = APIRouter(prefix="/selectors", tags=["selectors"])
IfMatch = Annotated[str | None, Header(alias="If-Match")]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def revision(if_match):
    if if_match is None:
        return None
    match = re.fullmatch(r'"([0-9]{1,19})"', if_match)
    if match is None:
        raise ExtractionValidationError("If-Match must be the selector's quoted ETag")
    return int(match[1])


def tagged(response, result):
    tree, token = result
    response.headers["ETag"] = f'"{token}"'
    return tree


@router.post("", response_model=SelectorTree, response_model_exclude_unset=True, status_code=201)
async def create_selector(body: SelectorImport, response: Response, service: ExtractionServiceDep):
    return tagged(
        response,
        await service.selectors.import_tree(
            body.tree, body.binding, body.snapshot_bindings, create=True
        ),
    )


@router.post("/import", response_model=SelectorTree, response_model_exclude_unset=True)
async def import_selector(
    body: SelectorImport,
    response: Response,
    service: ExtractionServiceDep,
    if_match: IfMatch = None,
):
    return tagged(
        response,
        await service.selectors.import_tree(
            body.tree, body.binding, body.snapshot_bindings, revision(if_match)
        ),
    )


@router.get("", response_model=Page[SelectorDefinition], response_model_exclude_unset=True)
async def list_selectors(
    service: ExtractionServiceDep,
    offset: Offset = 0,
    limit: Limit = 100,
    source_id: Identifier | None = None,
):
    definitions, total = await service.selectors.page(offset, limit, source_id)
    return Page(items=definitions, total=total, offset=offset, limit=limit)


@router.get("/{uuid}", response_model=SelectorTree, response_model_exclude_unset=True)
@router.get("/{uuid}/export", response_model=SelectorTree, response_model_exclude_unset=True)
async def get_tree(uuid: PortableUUID, response: Response, service: ExtractionServiceDep):
    row = await service.selectors.selector(uuid)
    tree, _ = await service.selectors.tree(row)
    return tagged(response, (tree, row.revision))


@router.get(
    "/{uuid}/versions",
    response_model=list[SelectorVersionDefinition],
    response_model_exclude_unset=True,
)
async def list_versions(uuid: PortableUUID, response: Response, service: ExtractionServiceDep):
    tree = await get_tree(uuid, response, service)
    return tree.versions


@router.get(
    "/{uuid}/versions/{version_uuid}",
    response_model=SelectorVersionDefinition,
    response_model_exclude_unset=True,
)
async def get_version(
    uuid: PortableUUID,
    version_uuid: PortableUUID,
    response: Response,
    service: ExtractionServiceDep,
):
    row = await service.selectors.selector(uuid)
    version = await service.selectors.version(row.id, version_uuid)
    response.headers["ETag"] = f'"{row.revision}"'
    return await service.selectors.definition(version, uuid)


@router.post("/{uuid}/drafts", response_model=SelectorTree, response_model_exclude_unset=True)
async def create_draft(
    uuid: PortableUUID, response: Response, service: ExtractionServiceDep, if_match: IfMatch = None
):
    return tagged(response, await service.selectors.draft(uuid, revision(if_match)))


@router.put(
    "/{uuid}/drafts/{version_uuid}", response_model=SelectorTree, response_model_exclude_unset=True
)
async def save_draft(
    uuid: PortableUUID,
    version_uuid: PortableUUID,
    body: SelectorVersionDefinition,
    response: Response,
    service: ExtractionServiceDep,
    if_match: IfMatch = None,
):
    return tagged(
        response, await service.selectors.save_draft(uuid, version_uuid, body, revision(if_match))
    )


@router.post(
    "/{uuid}/drafts/{version_uuid}/approve",
    response_model=SelectorTree,
    response_model_exclude_unset=True,
)
async def approve_draft(
    uuid: PortableUUID,
    version_uuid: PortableUUID,
    response: Response,
    service: ExtractionServiceDep,
    body: SelectorReview | None = None,
    if_match: IfMatch = None,
):
    return tagged(
        response,
        await service.selectors.review(
            uuid, version_uuid, True, body.reviewed_by if body else None, revision(if_match)
        ),
    )


@router.post(
    "/{uuid}/drafts/{version_uuid}/reject",
    response_model=SelectorTree,
    response_model_exclude_unset=True,
)
async def reject_draft(
    uuid: PortableUUID,
    version_uuid: PortableUUID,
    response: Response,
    service: ExtractionServiceDep,
    body: SelectorReview | None = None,
    if_match: IfMatch = None,
):
    return tagged(
        response,
        await service.selectors.review(
            uuid, version_uuid, False, body.reviewed_by if body else None, revision(if_match)
        ),
    )


@router.post(
    "/{uuid}/evaluate", response_model=SelectorExecutionResult, response_model_exclude_unset=True
)
async def evaluate(uuid: PortableUUID, body: SelectorExecution, service: ExtractionServiceDep):
    return await service.selector_execution.execute(uuid, body)


@router.post(
    "/{uuid}/evaluations",
    response_model=StoredEvaluation,
    response_model_exclude_unset=True,
    status_code=201,
)
async def record_evaluation(
    uuid: PortableUUID, body: ClientEvaluation, service: ExtractionServiceDep
):
    return await service.selector_execution.record_client(uuid, body)


@router.get(
    "/{uuid}/evaluations", response_model=Page[StoredEvaluation], response_model_exclude_unset=True
)
async def list_evaluations(
    uuid: PortableUUID,
    service: ExtractionServiceDep,
    offset: Offset = 0,
    limit: Limit = 100,
):
    items, total = await service.selector_execution.page(uuid, offset, limit)
    return Page(items=items, total=total, offset=offset, limit=limit)
