"""Effective archive settings, copied onto each claimed attempt."""

import os
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from extraction.schemas.selector_tree import PortableModel
from monitoring.security import MonitoringError

MIB = 1024 * 1024
FULL_ARCHIVE_VERSION = "full-resource-1"
MAX_ARCHIVE_BYTES = 512 * MIB
MAX_ARCHIVE_RESOURCE_BYTES = 64 * MIB
MAX_ARCHIVE_DOCUMENT_BYTES = 16 * MIB
MAX_ARCHIVE_ENTRIES = 512
MAX_MANIFEST_BYTES = 3 * MIB
SnapshotMode = Literal["minimal", "full"]


class ArchiveLimits(PortableModel):
    version: Literal["full-resource-1"] = FULL_ARCHIVE_VERSION
    max_bytes: Annotated[int, Field(ge=MIB, le=MAX_ARCHIVE_BYTES)]
    max_resource_bytes: Annotated[int, Field(ge=MIB, le=MAX_ARCHIVE_RESOURCE_BYTES)]


@lru_cache(maxsize=8)
def parse_policy(mode, total_mb, resource_mb):
    try:
        if mode not in {"minimal", "full"}:
            raise ValueError("Invalid snapshot mode")
        archive = ArchiveLimits(
            version=FULL_ARCHIVE_VERSION,
            max_bytes=int(total_mb) * MIB,
            max_resource_bytes=int(resource_mb) * MIB,
        )
        if archive.max_resource_bytes > archive.max_bytes:
            raise ValueError("Resource limit exceeds archive limit")
    except (ValueError, ValidationError):
        raise MonitoringError(503, "SNAPSHOT_CONFIG_INVALID") from None
    return mode, archive if mode == "full" else None


def snapshot_policy():
    return parse_policy(
        os.getenv("BURBOT_MONITORING_SNAPSHOT_MODE", "minimal").strip(),
        os.getenv("BURBOT_MONITORING_FULL_SNAPSHOT_MAX_MB", "256"),
        os.getenv("BURBOT_MONITORING_FULL_RESOURCE_MAX_MB", "32"),
    )
