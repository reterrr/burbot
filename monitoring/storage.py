"""Presigned S3 PUTs and verified, backend-owned snapshots."""

import asyncio
import hashlib
import os
from contextlib import closing
from functools import lru_cache
from urllib.parse import urlsplit

from monitoring.contracts import MAX_BYTES, MIME_TYPE
from monitoring.security import MonitoringError


class SnapshotStorage:
    def __init__(self, internal, public, bucket, access_key, secret_key):
        import boto3
        from botocore.config import Config

        external = urlsplit(public)
        if (
            external.username is not None
            or external.path not in ("", "/")
            or external.query
            or external.fragment
            or (
                external.scheme != "https"
                and (
                    external.scheme != "http"
                    or external.hostname not in {"localhost", "127.0.0.1", "::1"}
                )
            )
        ):
            raise ValueError("The browser storage endpoint must be HTTPS or loopback HTTP")
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=10,
            retries={"total_max_attempts": 1},
        )
        credentials = dict(
            region_name="us-east-1",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=config,
        )
        self.reader = boto3.client("s3", endpoint_url=internal, **credentials)
        self.signer = boto3.client("s3", endpoint_url=public, **credentials)
        self.bucket = bucket

    def ensure_bucket(self):
        """Initialize the private bucket for the local Compose setup."""
        from botocore.exceptions import ClientError

        try:
            self.reader.head_bucket(Bucket=self.bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
                raise
            self.reader.create_bucket(Bucket=self.bucket)

    def presign(self, key, seconds, size):
        return self.signer.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": MIME_TYPE,
                "ContentLength": size,
            },
            ExpiresIn=seconds,
        )

    def _seal(self, temp_key, final_key, size, digest, max_bytes):
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self.reader.get_object(Bucket=self.bucket, Key=temp_key)
            with closing(response["Body"]) as stream:
                if response["ContentLength"] != size or not 0 < size <= max_bytes:
                    raise MonitoringError(422, "UPLOAD_SIZE_MISMATCH")
                if response.get("ContentType") != MIME_TYPE:
                    raise MonitoringError(422, "UPLOAD_MEDIA_TYPE_MISMATCH")
                body = stream.read(size + 1)
            if len(body) != size:
                raise MonitoringError(422, "UPLOAD_SIZE_MISMATCH")
            if hashlib.sha256(body).hexdigest() != digest:
                raise MonitoringError(422, "UPLOAD_HASH_MISMATCH")
            # Seal the exact bytes we verified under a different, server-only key.
            # A replayed presigned PUT cannot alter the evidence.
            self.reader.put_object(
                Bucket=self.bucket,
                Key=final_key,
                Body=body,
                ContentType=MIME_TYPE,
                ContentDisposition="attachment",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] in {"NoSuchKey", "NotFound", "404"}:
                raise MonitoringError(409, "UPLOAD_NOT_FOUND") from error
            raise MonitoringError(503, "STORAGE_UNAVAILABLE") from error
        except BotoCoreError as error:
            raise MonitoringError(503, "STORAGE_UNAVAILABLE") from error

    async def seal(self, temp_key, final_key, size, digest, *, max_bytes=MAX_BYTES):
        await asyncio.to_thread(self._seal, temp_key, final_key, size, digest, max_bytes)

    def _read_snapshot(self, file, max_bytes):
        from botocore.exceptions import BotoCoreError, ClientError, IncompleteReadError

        if file.size_bytes is not None and file.size_bytes > max_bytes:
            raise MonitoringError(413, "SNAPSHOT_TOO_LARGE")
        try:
            response = self.reader.get_object(Bucket=self.bucket, Key=file.storage_key)
            with closing(response["Body"]) as stream:
                size = response.get("ContentLength")
                if type(size) is not int or size < 0:
                    raise MonitoringError(422, "SNAPSHOT_INTEGRITY_MISMATCH")
                if size > max_bytes:
                    raise MonitoringError(413, "SNAPSHOT_TOO_LARGE")
                if file.size_bytes is not None and file.size_bytes != size:
                    raise MonitoringError(422, "SNAPSHOT_INTEGRITY_MISMATCH")
                body = stream.read(size + 1)
            if len(body) > max_bytes:
                raise MonitoringError(413, "SNAPSHOT_TOO_LARGE")
            if len(body) != size or (
                file.sha256 is not None and hashlib.sha256(body).hexdigest() != file.sha256.lower()
            ):
                raise MonitoringError(422, "SNAPSHOT_INTEGRITY_MISMATCH")
            return body
        except IncompleteReadError as error:
            raise MonitoringError(422, "SNAPSHOT_INTEGRITY_MISMATCH") from error
        except ClientError as error:
            if error.response["Error"]["Code"] in {"NoSuchKey", "NotFound", "404"}:
                raise MonitoringError(404, "SNAPSHOT_ARTIFACT_NOT_FOUND") from error
            raise MonitoringError(503, "STORAGE_UNAVAILABLE") from error
        except BotoCoreError as error:
            raise MonitoringError(503, "STORAGE_UNAVAILABLE") from error

    async def read_snapshot(self, file, *, max_bytes=MAX_BYTES):
        return await asyncio.to_thread(self._read_snapshot, file, max_bytes)

    async def delete(self, key):
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            await asyncio.to_thread(self.reader.delete_object, Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as error:
            raise MonitoringError(503, "STORAGE_UNAVAILABLE") from error


@lru_cache
def storage_from_env():
    values = [
        os.environ.get(f"MONITORING_S3_{item}")
        for item in ("INTERNAL_URL", "PUBLIC_URL", "BUCKET", "ACCESS_KEY", "SECRET_KEY")
    ]
    if not all(values):
        raise MonitoringError(503, "STORAGE_NOT_CONFIGURED")
    return SnapshotStorage(*values)
