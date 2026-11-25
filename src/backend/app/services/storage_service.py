from __future__ import annotations

# pyright: reportUnknownVariableType=false
import asyncio
from collections.abc import Mapping
from typing import Final, Protocol, cast, runtime_checkable
from urllib.parse import urlparse
from uuid import UUID, uuid4

import boto3  # type: ignore[import-untyped]
import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable
from starlette.datastructures import UploadFile

from app.core.config import settings

MAX_IMAGES_PER_PRODUCT: Final[int] = 10
MAX_FILE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset({"image/jpeg", "image/png"})


@runtime_checkable
class ScalarResultProtocol(Protocol):
    def scalar_one(self) -> object: ...


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> ScalarResultProtocol: ...


@runtime_checkable
class S3ClientProtocol(Protocol):
    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> object: ...

    def delete_object(self, *, Bucket: str, Key: str) -> object: ...

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
    ) -> str: ...


@beartype
def _content_type_to_extension(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    raise ValueError("Only JPEG and PNG images are allowed.")


class StorageService:
    @beartype
    def __init__(
        self,
        *,
        db_session: DatabaseSessionProtocol,
        s3_client: S3ClientProtocol | None = None,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        self._db_session = db_session
        self._bucket_name = bucket_name or settings.s3_bucket_name
        self._endpoint_url = endpoint_url or settings.s3_endpoint_url
        self._public_base_url = (
            public_base_url or settings.s3_public_base_url or settings.s3_endpoint_url
        )
        resolved_s3_client: S3ClientProtocol
        if s3_client is not None:
            resolved_s3_client = s3_client
        else:
            raw_client: object = boto3.client(  # pyright: ignore[reportUnknownMemberType]
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region_name,
            )
            resolved_s3_client = cast(
                S3ClientProtocol,
                raw_client,
            )

        self._s3_client: S3ClientProtocol = resolved_s3_client

    @beartype
    async def upload(self, file: UploadFile, product_id: UUID, sort_order: int) -> str:
        if sort_order < 0 or sort_order >= MAX_IMAGES_PER_PRODUCT:
            raise ValueError("sort_order must be between 0 and 9.")

        content_type = file.content_type or ""
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("Only JPEG and PNG images are allowed.")

        await self._ensure_images_limit(product_id=product_id)

        file_bytes = await file.read(MAX_FILE_SIZE_BYTES + 1)
        if len(file_bytes) == 0:
            raise ValueError("File is empty.")
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError("File size must not exceed 5MB.")

        extension = _content_type_to_extension(content_type)
        object_key = f"products/{product_id}/{sort_order:02d}-{uuid4().hex}{extension}"

        await asyncio.to_thread(
            self._s3_client.put_object,
            Bucket=self._bucket_name,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return self._build_public_url(object_key)

    @beartype
    async def delete(self, url_or_key: str) -> None:
        object_key = self._extract_object_key(url_or_key)
        await asyncio.to_thread(
            self._s3_client.delete_object,
            Bucket=self._bucket_name,
            Key=object_key,
        )

    @beartype
    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        if expires_in <= 0:
            raise ValueError("expires_in must be positive.")
        if not key.strip():
            raise ValueError("Object key must not be empty.")

        return self._s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": self._bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )

    @beartype
    async def _ensure_images_limit(self, *, product_id: UUID) -> None:
        result = await self._db_session.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM product_images
                WHERE product_id = :product_id
                """
            ),
            {"product_id": product_id},
        )
        count_result = result.scalar_one()
        if not isinstance(count_result, int):
            raise RuntimeError("Image count query returned non-integer value.")
        if count_result >= MAX_IMAGES_PER_PRODUCT:
            raise ValueError("A product cannot have more than 10 images.")

    @beartype
    def _build_public_url(self, object_key: str) -> str:
        base_url = self._public_base_url.rstrip("/")
        return f"{base_url}/{self._bucket_name}/{object_key}"

    @beartype
    def _extract_object_key(self, url_or_key: str) -> str:
        candidate = url_or_key.strip()
        if not candidate:
            raise ValueError("Object URL or key must not be empty.")

        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            path = parsed.path.lstrip("/")
            bucket_prefix = f"{self._bucket_name}/"
            if path.startswith(bucket_prefix):
                key = path[len(bucket_prefix) :]
            else:
                key = path
        else:
            key = candidate.lstrip("/")

        if not key:
            raise ValueError("Could not extract object key.")
        return key
