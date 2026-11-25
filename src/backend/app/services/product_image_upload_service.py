from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from beartype import beartype
from starlette.datastructures import UploadFile

from app.services.storage_service import MAX_IMAGES_PER_PRODUCT

logger = logging.getLogger(__name__)


@runtime_checkable
class ProductImageTransactionProtocol(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@runtime_checkable
class ProductImageWriterProtocol(Protocol):
    async def lock_product_for_image_upload(self, *, product_id: UUID) -> None: ...

    async def count_images(self, *, product_id: UUID) -> int: ...

    async def add_image(
        self,
        *,
        product_id: UUID,
        url: str,
        sort_order: int,
        alt_text: str | None,
        commit: bool = True,
    ) -> dict[str, object]: ...


@runtime_checkable
class ProductImageStorageProtocol(Protocol):
    async def upload(self, file: UploadFile, product_id: UUID, sort_order: int) -> str: ...

    async def delete(self, url_or_key: str) -> None: ...


@beartype
async def upload_product_images_atomically(
    *,
    db: ProductImageTransactionProtocol,
    product_service: ProductImageWriterProtocol,
    storage: ProductImageStorageProtocol,
    product_id: UUID,
    files: Sequence[UploadFile],
    sort_orders: Sequence[int],
    alt_texts: Sequence[str | None],
) -> list[dict[str, object]]:
    uploaded_urls: list[str] = []
    uploaded_images: list[dict[str, object]] = []
    try:
        await product_service.lock_product_for_image_upload(product_id=product_id)
        existing_images_count = await product_service.count_images(product_id=product_id)
        if existing_images_count + len(files) > MAX_IMAGES_PER_PRODUCT:
            raise ValueError("A product cannot have more than 10 images.")

        for index, file in enumerate(files):
            sort_order = sort_orders[index] if sort_orders else index
            url = await storage.upload(file=file, product_id=product_id, sort_order=sort_order)
            uploaded_urls.append(url)
            image = await product_service.add_image(
                product_id=product_id,
                url=url,
                sort_order=sort_order,
                alt_text=alt_texts[index],
                commit=False,
            )
            uploaded_images.append(image)
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            logger.exception("Failed to roll back product image batch.")
        for url in reversed(uploaded_urls):
            try:
                await storage.delete(url)
            except Exception:
                logger.exception("Failed to clean uploaded product image %s.", url)
        raise

    return uploaded_images
