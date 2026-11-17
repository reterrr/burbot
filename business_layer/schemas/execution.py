"""Results shared by the business coordinator and its definition/data owners."""

from pydantic import BaseModel, ConfigDict, Field


class SeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objects: dict[str, int] = Field(default_factory=dict)
    created: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)


class ExecutionResult(SeedResult):
    code_version: int | None = None
    revision_id: int | None
    schema_changed: bool
