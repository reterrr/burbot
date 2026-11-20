from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from extraction.schemas.selector_tree import PortableModel, SelectorEvaluationResult, SelectorTree

MAX_ID = 2**63 - 1


def valid_id(value):
    if int(value) > MAX_ID:
        raise ValueError("Identifier exceeds PostgreSQL BIGINT")
    return value


Id = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,18}$"), AfterValidator(valid_id)]
LocalId = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"^[^\x00]+$")]
FieldKey = Annotated[str, StringConstraints(min_length=1, max_length=150, pattern=r"^[^\x00]+$")]


class NestedTarget(PortableModel):
    kind: FieldKey
    id: LocalId


class Identity(PortableModel):
    local_object_id: LocalId
    local_type: FieldKey
    target: NestedTarget | None = None


class Resolve(PortableModel):
    workspace_uuid: UUID
    identity: Identity
    action: Literal["preview", "resolve", "bind", "create"] = "preview"
    existing_business_object_id: Id | None = None

    @model_validator(mode="after")
    def explicit_target(self):
        if (self.action == "bind") != (self.existing_business_object_id is not None):
            raise ValueError("Binding requires exactly one confirmed server object ID")
        return self


class FieldChange(PortableModel):
    persistent_key: FieldKey
    business_object_field_id: Id
    field_version_id: Id
    expected_value_id: Id | None
    expected_collection_revision: Annotated[int, Field(strict=True, ge=0, le=MAX_ID)] | None = None
    value: Any


class ObjectChange(PortableModel):
    identity: Identity
    business_object_id: Id
    fields: list[FieldChange] = Field(min_length=1, max_length=200)


class Commit(PortableModel):
    workspace_uuid: UUID
    operation_id: UUID
    schema_revision_id: Id
    changes: list[ObjectChange] = Field(min_length=1, max_length=200)


class SelectorSync(PortableModel):
    workspace_uuid: UUID
    identity: Identity
    source_id: Id
    tree: SelectorTree
    # Send this only from the explicit selector synchronization action.
    publish_reviewed: bool = False


class ReportCapture(PortableModel):
    workspace_uuid: UUID
    operation_id: UUID
    identity: Identity
    selector_uuid: UUID
    source_snapshot_id: Id
    page_url: Annotated[str, StringConstraints(max_length=2048)]
    result: SelectorEvaluationResult
