from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from uuid import uuid4

import pytest
from beartype import beartype
from starlette.datastructures import Headers, UploadFile

from app.services.storage_service import StorageService


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value


class _FakeSession:
    def __init__(self, image_count: int) -> None:
        self._image_count = image_count

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _ScalarResult:
        _ = statement
        _ = params
        return _ScalarResult(self._image_count)


class _FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> object:
        self.put_calls.append(
            {
                "Bucket": Bucket,
                "Key": Key,
                "Body": Body,
                "ContentType": ContentType,
            }
        )
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def delete_object(self, *, Bucket: str, Key: str) -> object:
        self.delete_calls.append({"Bucket": Bucket, "Key": Key})
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
    ) -> str:
        return (
            f"https://signed.example/{ClientMethod}"
            f"?bucket={Params['Bucket']}&key={Params['Key']}&expires={ExpiresIn}"
        )


@beartype
def _make_upload_file(*, content: bytes, content_type: str, filename: str) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@beartype
def _build_service(*, image_count: int) -> tuple[StorageService, _FakeS3Client]:
    s3_client = _FakeS3Client()
    service = StorageService(
        db_session=_FakeSession(image_count),
        s3_client=s3_client,
        bucket_name="threefivenine-media",
        endpoint_url="https://s3.twcstorage.ru",
        public_base_url="https://s3.twcstorage.ru",
    )
    return service, s3_client


@pytest.mark.asyncio
async def test_upload_accepts_starlette_upload_file() -> None:
    service, s3_client = _build_service(image_count=2)
    upload_file = _make_upload_file(
        content=b"fake-jpeg-content",
        content_type="image/jpeg",
        filename="photo.jpg",
    )
    product_id = uuid4()

    assert type(upload_file) is UploadFile

    uploaded_url = await service.upload(file=upload_file, product_id=product_id, sort_order=1)

    assert uploaded_url.startswith("https://s3.twcstorage.ru/threefivenine-media/products/")
    assert len(s3_client.put_calls) == 1
    assert s3_client.put_calls[0]["Bucket"] == "threefivenine-media"
    assert s3_client.put_calls[0]["ContentType"] == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_rejects_more_than_ten_images_per_product() -> None:
    service, _ = _build_service(image_count=10)
    upload_file = _make_upload_file(
        content=b"fake-jpeg-content",
        content_type="image/jpeg",
        filename="photo.jpg",
    )

    with pytest.raises(ValueError, match="cannot have more than 10 images"):
        await service.upload(file=upload_file, product_id=uuid4(), sort_order=0)


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_content_type() -> None:
    service, _ = _build_service(image_count=0)
    upload_file = _make_upload_file(
        content=b"fake-gif-content",
        content_type="image/gif",
        filename="photo.gif",
    )

    with pytest.raises(ValueError, match="Only JPEG and PNG images are allowed"):
        await service.upload(file=upload_file, product_id=uuid4(), sort_order=0)


@pytest.mark.asyncio
async def test_upload_rejects_file_larger_than_five_mb() -> None:
    service, _ = _build_service(image_count=0)
    upload_file = _make_upload_file(
        content=b"x" * (5 * 1024 * 1024 + 1),
        content_type="image/png",
        filename="large.png",
    )

    with pytest.raises(ValueError, match="must not exceed 5MB"):
        await service.upload(file=upload_file, product_id=uuid4(), sort_order=0)


@pytest.mark.asyncio
async def test_delete_accepts_full_url_and_uses_extracted_key() -> None:
    service, s3_client = _build_service(image_count=0)
    await service.delete("https://s3.twcstorage.ru/threefivenine-media/products/abc/file.jpg")

    assert s3_client.delete_calls == [
        {
            "Bucket": "threefivenine-media",
            "Key": "products/abc/file.jpg",
        }
    ]


def test_generate_presigned_url_returns_signed_url() -> None:
    service, _ = _build_service(image_count=0)
    presigned = service.generate_presigned_url("products/test/upload.jpg", expires_in=600)

    assert "signed.example/put_object" in presigned
    assert "expires=600" in presigned
