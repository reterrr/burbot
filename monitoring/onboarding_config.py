"""Explicit network and enrollment policy for scheduler-driven onboarding."""

import os
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, ValidationError, field_validator

from extraction.schemas.selector_tree import PortableModel
from monitoring.security import MonitoringError, approve_origins

PolicyName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,47}$")]
MonitoringMode = Literal["strict", "trusted"]


def configured_origins(values):
    try:
        return tuple(approve_origins(values[0], values)) if values else ()
    except MonitoringError:
        raise ValueError("Use exact public HTTPS origins without paths or query strings") from None


class ApprovalPolicy(PortableModel):
    origins: tuple[str, ...] = Field(min_length=1, max_length=1000)
    additional_origins: tuple[str, ...] = Field(default=(), max_length=20)
    continuous: bool = False
    auto_enroll: bool = False
    agent_ids: tuple[UUID, ...] = Field(default=(), max_length=20)

    @field_validator("origins", "additional_origins")
    @classmethod
    def normalize_origins(cls, values):
        return configured_origins(values)


class ScheduleDefaults(PortableModel):
    enabled: bool = True
    interval_seconds: int = Field(default=86400, ge=1, le=2147483647)
    initial_spread_seconds: int = Field(default=86400, ge=0, le=2592000)


class OnboardingConfig(PortableModel):
    mode: MonitoringMode = "strict"
    trusted_allow_http: bool = False
    policies: dict[PolicyName, ApprovalPolicy] = Field(default_factory=dict, max_length=32)
    default_schedule: ScheduleDefaults = Field(default_factory=ScheduleDefaults)
    monitoring_enabled: bool = True
    max_active_jobs: int = Field(default=200, ge=1, le=100000)
    max_active_jobs_per_origin: int | None = Field(default=None, ge=1, le=100000)
    job_batch_size: int = Field(default=50, ge=1, le=250)
    agent_unavailable_grace_seconds: int = Field(default=600, ge=180, le=86400)
    batch_size: int = Field(default=20, ge=1, le=100)
    probe_concurrency: int = Field(default=4, ge=1, le=8)
    probe_timeout_seconds: int = Field(default=8, ge=1, le=20)
    discovery_attempts: int = Field(default=3, ge=1, le=8)
    retry_base_seconds: int = Field(default=30, ge=1, le=900)
    per_origin_interval_seconds: int = Field(default=1, ge=0, le=3600)

    def policy(self, name):
        policy = self.policies.get(name)
        if policy is None:
            raise MonitoringError(422, "ONBOARDING_POLICY_NOT_FOUND")
        return policy


@lru_cache(maxsize=4)
def parse_config(raw):
    try:
        return OnboardingConfig.model_validate_json(raw)
    except ValidationError:
        raise MonitoringError(503, "ONBOARDING_CONFIG_INVALID") from None


def onboarding_config():
    return parse_config(os.getenv("MONITORING_ONBOARDING_CONFIG") or "{}")
