"""API tests for admin finance routes and payout query validation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.admin import finance as admin_finance
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.schemas.payout import PayoutStatusLiteral


class _MappingResult:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def first(self) -> Mapping[str, object] | None:
        return self._row


class _ExecuteResult:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> _MappingResult:
        return _MappingResult(self._row)


class _FakeAuthDb:
    def __init__(self, user_id: UUID) -> None:
        self._user_id = user_id

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _ExecuteResult:
        _ = statement, params
        return _ExecuteResult(
            {
                "id": self._user_id,
                "phone": "+79001234567",
                "email": "admin@example.com",
                "name": "Admin",
                "is_verified": True,
            }
        )


class _FakePayoutService:
    captured_statuses: ClassVar[list[str | None]] = []

    def __init__(self, *, db: object) -> None:
        _ = db

    async def list_payouts(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        brand_id: UUID | None = None,
        status_filter: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        _ = page, per_page, brand_id
        self.captured_statuses.append(status_filter)
        return [], 0


async def _override_db() -> AsyncIterator[object]:
    yield _FakeAuthDb(_ADMIN_USER_ID)


_ADMIN_USER_ID = uuid4()


@pytest.fixture(autouse=True)
def _patch_admin_finance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    _FakePayoutService.captured_statuses = []
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(admin_finance, "PayoutService", _FakePayoutService)
    yield
    app.dependency_overrides.pop(get_db, None)


def _admin_headers() -> dict[str, str]:
    token = create_access_token(user_id=_ADMIN_USER_ID, scopes=["admin"])
    return {"Authorization": f"Bearer {token}"}


def test_list_payouts_rejects_unknown_status_before_service() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/payouts?status=unknown",
            headers=_admin_headers(),
        )

    assert response.status_code == 422
    assert _FakePayoutService.captured_statuses == []


@pytest.mark.parametrize(
    "payout_status",
    ["pending", "scheduled", "processing", "paid", "failed"],
)
def test_list_payouts_passes_supported_public_status_to_service(
    payout_status: PayoutStatusLiteral,
) -> None:
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/admin/payouts?status={payout_status}",
            headers=_admin_headers(),
        )

    assert response.status_code == 200
    assert _FakePayoutService.captured_statuses == [payout_status]
