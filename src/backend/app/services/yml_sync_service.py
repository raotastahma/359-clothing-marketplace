# YML (Yandex Market Language) feed synchronisation service: downloads a brand's
# product feed XML from its stored feed_url, parses offers, and updates product
# prices/stock. Feed URLs are brand-supplied, so downloads go through an SSRF
# guard that restricts schemes and blocks non-public network targets.
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast, runtime_checkable
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.models.catalog import FeedSyncStatus

MAX_FEED_BYTES = 20 * 1024 * 1024
MAX_FEED_REDIRECTS = 5
_EVERY_N_HOURS_RE = re.compile(r"^\s*(\d{1,2})\s+\*/(\d{1,2})\s+\*\s+\*\s+\*\s*$")
_EVERY_N_MINUTES_RE = re.compile(r"^\s*\*/(\d{1,2})\s+\*\s+\*\s+\*\s+\*\s*$")


@dataclass(frozen=True, slots=True)
class ParsedOffer:
    vendor_code: str
    price_rub: Decimal
    compare_at_price_rub: Decimal | None
    stock_quantity: int


@beartype
def _to_uuid(value: object) -> UUID:
    return UUID(str(value))


@beartype
def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("Expected integer-compatible value.")


@beartype
def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


class ConcurrentSyncError(ValueError):
    pass


@beartype
async def _resolve_host_ips(host: str) -> list[str]:
    """Resolve a hostname to all of its IP addresses without blocking the event loop."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None)
    return [str(info[4][0]) for info in infos]


@beartype
async def _ensure_safe_feed_url(url: str) -> list[str]:
    """SSRF guard for brand-supplied feed URLs.

    Rejects non-http(s) schemes and any URL whose host resolves to a non-public
    address (loopback, private, link-local, reserved), so a malicious feed_url
    cannot be used to probe internal services or cloud metadata endpoints.
    Returns the validated IPs so the caller can connect to the exact address
    that passed validation. Raises RuntimeError, which the sync flow already
    records as a feed error.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise RuntimeError("Feed URL must use http or https.")
    host = parts.hostname
    if not host:
        raise RuntimeError("Feed URL must include a hostname.")
    try:
        resolved_ips = await _resolve_host_ips(host)
    except OSError as exc:
        raise RuntimeError(f"Feed URL hostname could not be resolved: {host}") from exc
    if not resolved_ips:
        raise RuntimeError(f"Feed URL hostname could not be resolved: {host}")
    validated_ips: list[str] = []
    for raw_ip in resolved_ips:
        # IPv6 link-local results may carry a "%scope" suffix that ip_address() rejects.
        normalized_ip = raw_ip.split("%", 1)[0]
        ip = ipaddress.ip_address(normalized_ip)
        if not ip.is_global:
            raise RuntimeError("Feed URL resolves to a non-public network address.")
        validated_ips.append(normalized_ip)
    return validated_ips


@beartype
def _pinned_feed_request_parts(
    *,
    original_url: httpx.URL,
    validated_ip: str,
) -> tuple[httpx.URL, dict[str, str], dict[str, str]]:
    pinned_url = original_url.copy_with(host=validated_ip)
    headers = {"Host": original_url.netloc.decode("ascii")}
    extensions: dict[str, str] = {}
    if original_url.scheme == "https":
        extensions["sni_hostname"] = original_url.host
    return pinned_url, headers, extensions


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...

    def all(self) -> list[Mapping[str, object]]: ...


@runtime_checkable
class ExecuteResultProtocol(Protocol):
    def mappings(self) -> MappingResultProtocol: ...

    def scalar_one_or_none(self) -> object: ...


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> ExecuteResultProtocol: ...

    async def commit(self) -> None: ...


class YmlSyncService:
    @beartype
    def __init__(self, *, db: DatabaseSessionProtocol) -> None:
        self._db = db

    @beartype
    async def sync_all_due_feeds(self) -> int:
        brands = await self._get_due_brands()
        synced = 0
        for brand in brands:
            try:
                await self.sync_brand_feed(brand_id=_to_uuid(brand["id"]))
            except ConcurrentSyncError:
                continue
            synced += 1
        return synced

    @beartype
    async def sync_brand_feed(self, *, brand_id: UUID) -> dict[str, object]:
        brand = await self._get_brand(brand_id=brand_id)
        if await self._is_sync_running(brand_id=brand_id):
            raise ConcurrentSyncError("Feed sync is already running for this brand.")

        log_id = await self._create_running_log(brand_id=brand_id)
        temp_path: str | None = None
        try:
            feed_url = cast(str | None, brand["yml_feed_url"])
            if feed_url is None or not feed_url.strip():
                raise ValueError("Brand has no yml_feed_url configured.")

            temp_path = await self._download_feed_to_tempfile(feed_url=feed_url)
            offers = self._parse_offers(file_path=temp_path)
            updated_count, unmatched_codes = await self._apply_offers(
                brand_id=brand_id,
                offers=offers,
            )
            await self._finish_log_success(
                log_id=log_id,
                updated_count=updated_count,
                unmatched_codes=unmatched_codes,
            )
            await self._db.commit()
            return {
                "log_id": log_id,
                "status": FeedSyncStatus.SUCCESS.value,
                "updated_count": updated_count,
                "unmatched_codes": unmatched_codes,
            }
        except Exception as exc:
            await self._finish_log_error(log_id=log_id, error_message=str(exc))
            await self._db.commit()
            raise
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                os.unlink(temp_path)

    @beartype
    async def list_logs(
        self,
        *,
        brand_id: UUID,
        page: int,
        per_page: int,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (page - 1) * per_page
        rows_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    id,
                    brand_id,
                    started_at,
                    completed_at,
                    status,
                    updated_count,
                    unmatched_codes,
                    error_message,
                    created_at
                FROM feed_sync_logs
                WHERE brand_id = :brand_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"brand_id": brand_id, "limit": per_page, "offset": offset},
        )
        rows = [self._log_row_to_payload(row=row) for row in rows_result.mappings().all()]

        total_result = await self._db.execute(
            sa.text(
                """
                SELECT COUNT(*) AS total
                FROM feed_sync_logs
                WHERE brand_id = :brand_id
                """
            ),
            {"brand_id": brand_id},
        )
        total_row = total_result.mappings().first()
        total = _to_int(total_row["total"]) if total_row is not None else 0
        return rows, total

    @beartype
    async def get_log(self, *, brand_id: UUID, log_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    id,
                    brand_id,
                    started_at,
                    completed_at,
                    status,
                    updated_count,
                    unmatched_codes,
                    error_message,
                    created_at
                FROM feed_sync_logs
                WHERE brand_id = :brand_id
                  AND id = :log_id
                LIMIT 1
                """
            ),
            {"brand_id": brand_id, "log_id": log_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Sync log not found.")
        return self._log_row_to_payload(row=row)

    @beartype
    async def _get_brand(self, *, brand_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, yml_feed_url, yml_sync_schedule, is_active
                FROM brands
                WHERE id = :brand_id
                LIMIT 1
                """
            ),
            {"brand_id": brand_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Brand not found.")
        return row

    @beartype
    async def _get_due_brands(self) -> list[Mapping[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    b.id,
                    b.yml_feed_url,
                    b.yml_sync_schedule,
                    (
                        SELECT MAX(l.completed_at)
                        FROM feed_sync_logs l
                        WHERE l.brand_id = b.id
                          AND l.status = 'success'
                    ) AS last_completed_at
                FROM brands b
                WHERE b.is_active = TRUE
                  AND b.yml_feed_url IS NOT NULL
                ORDER BY b.created_at ASC
                """
            )
        )
        now_utc = datetime.now(UTC)
        due: list[Mapping[str, object]] = []
        for row in result.mappings().all():
            schedule = str(row["yml_sync_schedule"] or "0 */4 * * *")
            last_completed_at = cast(datetime | None, row["last_completed_at"])
            if self._is_due(
                now_utc=now_utc,
                schedule=schedule,
                last_completed_at=last_completed_at,
            ):
                due.append(row)
        return due

    @beartype
    def _is_due(
        self,
        *,
        now_utc: datetime,
        schedule: str,
        last_completed_at: datetime | None,
    ) -> bool:
        if last_completed_at is None:
            return True
        interval = self._schedule_interval(schedule=schedule)
        return last_completed_at + timedelta(minutes=interval) <= now_utc

    @beartype
    def _schedule_interval(self, *, schedule: str) -> int:
        every_hours_match = _EVERY_N_HOURS_RE.match(schedule)
        if every_hours_match is not None:
            every_hours = int(every_hours_match.group(2))
            return max(every_hours, 1) * 60
        every_minutes_match = _EVERY_N_MINUTES_RE.match(schedule)
        if every_minutes_match is not None:
            every_minutes = int(every_minutes_match.group(1))
            return max(every_minutes, 1)
        # Fallback for unsupported cron shapes.
        return 240

    @beartype
    async def _is_sync_running(self, *, brand_id: UUID) -> bool:
        result = await self._db.execute(
            sa.text(
                """
                SELECT 1
                FROM feed_sync_logs
                WHERE brand_id = :brand_id
                  AND status = 'running'
                  AND completed_at IS NULL
                LIMIT 1
                """
            ),
            {"brand_id": brand_id},
        )
        return result.scalar_one_or_none() is not None

    @beartype
    async def _create_running_log(self, *, brand_id: UUID) -> UUID:
        result = await self._db.execute(
            sa.text(
                """
                INSERT INTO feed_sync_logs (brand_id, status, started_at, updated_count, unmatched_codes)
                VALUES (:brand_id, 'running', now(), 0, '[]'::jsonb)
                RETURNING id
                """
            ),
            {"brand_id": brand_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RuntimeError("Failed to create feed sync log.")
        return _to_uuid(row["id"])

    @beartype
    async def _finish_log_success(
        self,
        *,
        log_id: UUID,
        updated_count: int,
        unmatched_codes: list[str],
    ) -> None:
        await self._db.execute(
            sa.text(
                """
                UPDATE feed_sync_logs
                SET
                    status = 'success',
                    completed_at = now(),
                    updated_count = :updated_count,
                    unmatched_codes = CAST(:unmatched_codes AS jsonb),
                    error_message = NULL
                WHERE id = :log_id
                """
            ),
            {
                "log_id": log_id,
                "updated_count": updated_count,
                "unmatched_codes": self._json_dumps(unmatched_codes),
            },
        )

    @beartype
    async def _finish_log_error(self, *, log_id: UUID, error_message: str) -> None:
        await self._db.execute(
            sa.text(
                """
                UPDATE feed_sync_logs
                SET
                    status = 'error',
                    completed_at = now(),
                    error_message = :error_message
                WHERE id = :log_id
                """
            ),
            {"log_id": log_id, "error_message": error_message[:2000]},
        )

    @beartype
    async def _download_feed_to_tempfile(self, *, feed_url: str) -> str:
        with tempfile.NamedTemporaryFile(prefix="yml_feed_", suffix=".xml", delete=False) as tmp:
            temp_path = tmp.name
            current_url = httpx.URL(feed_url)
            redirects_followed = 0
            while True:
                # Resolve and validate each hop immediately before building
                # the request, then connect to that validated address only.
                validated_ips = await _ensure_safe_feed_url(str(current_url))
                pinned_url, headers, extensions = _pinned_feed_request_parts(
                    original_url=current_url,
                    validated_ip=validated_ips[0],
                )
                # Use a fresh pool per hop so cross-host HTTPS redirects that
                # pin to the same IP cannot reuse a connection with stale SNI.
                async with httpx.AsyncClient(
                    timeout=30.0,
                ) as client:
                    async with client.stream(
                        "GET",
                        pinned_url,
                        headers=headers,
                        extensions=extensions,
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            redirect_url = response.headers.get("location")
                            if redirect_url is None:
                                raise RuntimeError(f"Feed URL returned HTTP {response.status_code}")
                            if redirects_followed >= MAX_FEED_REDIRECTS:
                                raise RuntimeError("Feed URL redirected too many times.")
                            redirects_followed += 1
                            # Keep redirect semantics tied to the hostname URL;
                            # the pinned URL exists only for the socket target.
                            current_url = current_url.join(redirect_url)
                            continue

                        if response.status_code != 200:
                            raise RuntimeError(f"Feed URL returned HTTP {response.status_code}")
                        downloaded = 0
                        async for chunk in response.aiter_bytes():
                            downloaded += len(chunk)
                            if downloaded > MAX_FEED_BYTES:
                                raise RuntimeError("Feed file is too large (>20MB).")
                            tmp.write(chunk)
                        break
        return temp_path

    @beartype
    def _parse_offers(self, *, file_path: str) -> list[ParsedOffer]:
        offers: list[ParsedOffer] = []
        context = ET.iterparse(file_path, events=("end",))
        for _, elem in context:
            if _strip_ns(elem.tag) != "offer":
                continue
            parsed = self._parse_offer_element(offer=elem)
            if parsed is not None:
                offers.append(parsed)
            elem.clear()
        return offers

    @beartype
    def _parse_offer_element(self, *, offer: ET.Element) -> ParsedOffer | None:
        vendor_code = self._find_text(offer=offer, key="vendorCode")
        if vendor_code is None:
            vendor_code = offer.attrib.get("id")
        if vendor_code is None or not vendor_code.strip():
            return None

        price_text = self._find_text(offer=offer, key="price")
        if price_text is None:
            return None
        try:
            price_rub = Decimal(price_text).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None

        oldprice_text = self._find_text(offer=offer, key="oldprice")
        compare_at_price_rub: Decimal | None = None
        if oldprice_text is not None:
            try:
                compare_at_price_rub = Decimal(oldprice_text).quantize(Decimal("0.01"))
            except InvalidOperation:
                compare_at_price_rub = None

        stock_quantity = self._extract_stock(offer=offer)
        return ParsedOffer(
            vendor_code=vendor_code.strip(),
            price_rub=price_rub,
            compare_at_price_rub=compare_at_price_rub,
            stock_quantity=max(stock_quantity, 0),
        )

    @beartype
    def _extract_stock(self, *, offer: ET.Element) -> int:
        for node in offer.iter():
            if _strip_ns(node.tag) == "outlet":
                stock = node.attrib.get("instock")
                if stock is not None:
                    try:
                        return max(int(stock), 0)
                    except ValueError:
                        return 0
        count_text = self._find_text(offer=offer, key="count")
        if count_text is None:
            return 0
        try:
            return max(int(count_text), 0)
        except ValueError:
            return 0

    @beartype
    def _find_text(self, *, offer: ET.Element, key: str) -> str | None:
        for node in offer.iter():
            if _strip_ns(node.tag) != key:
                continue
            if node.text is None:
                return None
            value = node.text.strip()
            return value or None
        return None

    @beartype
    async def _apply_offers(
        self,
        *,
        brand_id: UUID,
        offers: list[ParsedOffer],
    ) -> tuple[int, list[str]]:
        updated_count = 0
        unmatched_codes: list[str] = []
        for offer in offers:
            result = await self._db.execute(
                sa.text(
                    """
                    UPDATE product_variants pv
                    SET
                        stock_quantity = :stock_quantity,
                        price_rub = :price_rub,
                        compare_at_price_rub = CASE
                            WHEN :compare_at_price_rub IS NULL THEN pv.compare_at_price_rub
                            ELSE :compare_at_price_rub
                        END,
                        is_active = :is_active
                    FROM products p
                    WHERE pv.product_id = p.id
                      AND p.brand_id = :brand_id
                      AND pv.vendor_code = :vendor_code
                    RETURNING pv.id
                    """
                ),
                {
                    "stock_quantity": offer.stock_quantity,
                    "price_rub": offer.price_rub,
                    "compare_at_price_rub": offer.compare_at_price_rub,
                    "is_active": offer.stock_quantity > 0,
                    "brand_id": brand_id,
                    "vendor_code": offer.vendor_code,
                },
            )
            if result.mappings().first() is None:
                unmatched_codes.append(offer.vendor_code)
            else:
                updated_count += 1
        return updated_count, unmatched_codes

    @beartype
    def _log_row_to_payload(self, *, row: Mapping[str, object]) -> dict[str, object]:
        unmatched_codes_raw = row["unmatched_codes"]
        unmatched_codes: list[str]
        if isinstance(unmatched_codes_raw, list):
            typed_items = cast(list[object], unmatched_codes_raw)
            unmatched_codes = [str(item) for item in typed_items]
        else:
            unmatched_codes = []
        return {
            "id": _to_uuid(row["id"]),
            "brand_id": _to_uuid(row["brand_id"]),
            "started_at": cast(datetime, row["started_at"]),
            "completed_at": cast(datetime | None, row["completed_at"]),
            "status": str(row["status"]),
            "updated_count": _to_int(row["updated_count"]),
            "unmatched_codes": unmatched_codes,
            "error_message": cast(str | None, row["error_message"]),
            "created_at": cast(datetime, row["created_at"]),
        }

    @beartype
    def _json_dumps(self, value: object) -> str:
        import json

        return json.dumps(value, ensure_ascii=False)
