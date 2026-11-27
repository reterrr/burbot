"""Full archive upload receipts and metadata for a single monitoring attempt."""

import json
import math
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import func, or_, select

from extraction.schemas.common import utc_now
from monitoring.contracts import ArchiveObjectTarget, ArchiveSummary
from monitoring.models import READY, STRICT_NAVIGATION, TERMINAL, TRUSTED_HTTP, MonitoringJob
from monitoring.models import MonitoringArchiveUpload as Upload
from monitoring.security import MonitoringError, check_origin, trusted_origin
from monitoring.snapshot_config import (
    FULL_ARCHIVE_VERSION,
    MAX_ARCHIVE_DOCUMENT_BYTES,
    MAX_ARCHIVE_ENTRIES,
    MAX_MANIFEST_BYTES,
    ArchiveLimits,
)
from monitoring.storage import ARCHIVE_MEDIA_TYPE

UPLOAD_SECONDS = 60


def blob_key(digest):
    return f"monitoring/archive-resources/sha256/{digest}"


def manifest_key(job):
    return f"monitoring/archives/{job.id}/{job.lease_id}/manifest.json"


def pending_key(upload):
    return f"monitoring/archive-pending/{upload.job_id}/{upload.lease_id}/{upload.sha256}"


def failed_archive(reason):
    return {"status": "failed", "version": FULL_ARCHIVE_VERSION, "failure": reason}


def archive_summary(job):
    return summarize_archive(job.snapshot_policy, job.archive_result)


def summarize_archive(policy, result):
    mode = (policy or {}).get("mode")
    if mode == "minimal":
        return ArchiveSummary(mode=mode, status="minimal").portable()
    if mode == "full" and result:
        return ArchiveSummary(
            mode=mode,
            **{
                key: result[key]
                for key in (
                    "status",
                    "version",
                    "captured",
                    "missing",
                    "truncated",
                    "sizeBytes",
                    "failure",
                )
                if key in result
            },
        ).portable()
    return None


def bind_archive(job, completion):
    """Match the manifest to the capture boundary without making evidence depend on it."""
    if (job.snapshot_policy or {}).get("mode") != "full":
        return
    result = job.archive_result
    if result is None:
        job.archive_result = failed_archive("agent_incomplete")
    elif result["status"] != "failed" and (
        result["pageUrl"] != completion.page_url
        or datetime.fromisoformat(result["capturedAt"]) != completion.captured_at
    ):
        job.archive_result = failed_archive("capture_mismatch")


class ArchiveUploads:
    def __init__(self, queue):
        self.queue = queue
        self.session = queue.session

    async def limits(self, job, lease):
        await self.queue._lease(job, lease)
        policy = job.snapshot_policy or {}
        if policy.get("mode") != "full":
            raise MonitoringError(409, "FULL_ARCHIVE_NOT_REQUESTED")
        return ArchiveLimits.model_validate(policy["limits"])

    def receipts(self, job):
        return select(Upload).where(Upload.job_id == job.id, Upload.lease_id == job.lease_id)

    async def grant(self, job, request):
        limits = await self.limits(job, request.lease_id)
        maximum = (
            MAX_ARCHIVE_DOCUMENT_BYTES if request.kind == "document" else limits.max_resource_bytes
        )
        if request.size_bytes > maximum:
            raise MonitoringError(413, "ARCHIVE_OBJECT_TOO_LARGE")
        now = utc_now()
        ttl = min(UPLOAD_SECONDS, math.floor((job.lease_expires_at - now).total_seconds()))
        if ttl <= 0:
            raise MonitoringError(409, "LEASE_LOST")
        upload = await self.session.get(Upload, (job.id, job.lease_id, request.sha256))
        if upload is None:
            if job.archive_result is not None:
                raise MonitoringError(409, "ARCHIVE_ALREADY_REPORTED")
            total, count = (
                await self.session.execute(
                    select(func.coalesce(func.sum(Upload.size_bytes), 0), func.count()).where(
                        Upload.job_id == job.id, Upload.lease_id == job.lease_id
                    )
                )
            ).one()
            if total + request.size_bytes > limits.max_bytes or count >= MAX_ARCHIVE_ENTRIES + 1:
                raise MonitoringError(413, "ARCHIVE_BUDGET_EXCEEDED")
            upload = Upload(
                job_id=job.id,
                lease_id=job.lease_id,
                sha256=request.sha256,
                size_bytes=request.size_bytes,
                expires_at=now + timedelta(seconds=ttl + 1),
            )
            self.session.add(upload)
        if upload.size_bytes != request.size_bytes:
            raise MonitoringError(409, "UPLOAD_INTENT_CONFLICT")
        if not upload.sealed:
            upload.sealed = await self.queue.store.archive_exists(
                blob_key(upload.sha256), upload.size_bytes, upload.sha256
            )
        if upload.sealed:
            return ArchiveObjectTarget(stored=True)
        upload.expires_at = max(upload.expires_at, now + timedelta(seconds=ttl + 1))
        return ArchiveObjectTarget(
            stored=False,
            url=self.queue.store.presign(
                pending_key(upload), ttl, upload.size_bytes, mime_type=ARCHIVE_MEDIA_TYPE
            ),
        )

    async def seal(self, job, request):
        await self.limits(job, request.lease_id)
        upload = await self.session.get(Upload, (job.id, job.lease_id, request.sha256))
        if upload is None or upload.cleaned_at is not None:
            raise MonitoringError(404, "UPLOAD_INTENT_NOT_FOUND")
        if upload.size_bytes != request.size_bytes:
            raise MonitoringError(409, "UPLOAD_INTENT_CONFLICT")
        if not upload.sealed:
            await self.queue.store.seal_archive(
                pending_key(upload), blob_key(upload.sha256), upload.size_bytes, upload.sha256
            )
            upload.sealed = True
        return ArchiveObjectTarget(stored=True)

    async def report(self, job, request):
        limits = await self.limits(job, request.lease_id)
        if job.archive_result is not None:
            # A lost acknowledgement must keep the first committed manifest.
            return archive_summary(job)
        if request.failure is not None:
            job.archive_result = failed_archive(request.failure)
            return archive_summary(job)

        manifest = request.manifest
        allow_http = job.navigation_policy == TRUSTED_HTTP
        if job.navigation_policy == STRICT_NAVIGATION:
            check_origin(manifest.page_url, job.origins)
        else:
            trusted_origin(manifest.page_url, allow_http=allow_http)
        trusted_origin(manifest.base_url, allow_http=allow_http)
        if (
            not job.claimed_at - timedelta(minutes=5)
            <= manifest.captured_at
            <= (utc_now() + timedelta(minutes=5))
        ):
            raise MonitoringError(422, "CAPTURE_TIME_OUTSIDE_ATTEMPT")

        uploads = {
            row.sha256: row for row in (await self.session.scalars(self.receipts(job))).all()
        }

        def include(part):
            upload = uploads.get(part.sha256)
            if upload is None or not upload.sealed or upload.size_bytes != part.size_bytes:
                raise MonitoringError(422, "UNVERIFIED_ARCHIVE_OBJECT")
            upload.included = True

        include(manifest.document)
        counts = Counter()
        for resource in manifest.resources:
            counts[resource.status] += 1
            urls = [url for url in (resource.original_url, resource.response_url) if url]
            for url in urls:
                if resource.status == "captured" and job.navigation_policy == STRICT_NAVIGATION:
                    check_origin(url, job.origins)
                else:
                    trusted_origin(url, allow_http=allow_http)
            if resource.status == "captured":
                if resource.size_bytes > limits.max_resource_bytes:
                    raise MonitoringError(413, "ARCHIVE_OBJECT_TOO_LARGE")
                include(resource)

        data = manifest.portable()
        data["completeness"] = {key: counts[key] for key in ("captured", "missing", "truncated")}
        data["jobId"] = str(job.id)
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        if len(body) > MAX_MANIFEST_BYTES:
            raise MonitoringError(413, "ARCHIVE_MANIFEST_TOO_LARGE")
        digest = sha256(body).hexdigest()
        await self.queue.store.write_archive_manifest(manifest_key(job), body, digest)
        job.archive_result = {
            "status": "partial"
            if manifest.issues or counts["missing"] or counts["truncated"]
            else "stored",
            "version": FULL_ARCHIVE_VERSION,
            **data["completeness"],
            "sizeBytes": sum(row.size_bytes for row in uploads.values() if row.included),
            "manifestSha256": digest,
            "manifestSizeBytes": len(body),
            "pageUrl": manifest.page_url,
            "capturedAt": manifest.captured_at.isoformat(),
        }
        return archive_summary(job)

    async def cleanup(self, limit):
        rows = (
            await self.session.scalars(
                select(Upload)
                .join(MonitoringJob, MonitoringJob.id == Upload.job_id)
                .where(
                    Upload.cleaned_at.is_(None),
                    Upload.expires_at < utc_now(),
                    or_(
                        MonitoringJob.status.in_((*TERMINAL, *READY)),
                        MonitoringJob.lease_id != Upload.lease_id,
                    ),
                )
                .order_by(Upload.expires_at)
                .limit(limit)
                .with_for_update(of=Upload, skip_locked=True)
            )
        ).all()
        for upload in rows:
            await self.queue.store.delete(pending_key(upload))
            upload.cleaned_at = utc_now()
        return len(rows)
