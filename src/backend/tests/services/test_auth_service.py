from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from app.core.security import create_refresh_token, decode_token
from app.integrations.sms.base import SmsResult
from app.services.auth_service import AuthService


class _FakeMappingRow:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows: list[Mapping[str, object]] = rows if rows is not None else []

    def mappings(self) -> _FakeMappingRow:
        return _FakeMappingRow(self._rows)

    def scalar_one_or_none(self) -> object:
        if not self._rows:
            return None
        first_row = self._rows[0]
        first_value = next(iter(first_row.values()), None)
        return first_value


class _FakeDbSession:
    """Returns pre-configured results for sequential execute() calls."""

    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)
        self._call_index = 0
        self.committed = False

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        _ = statement
        _ = params
        if self._call_index >= len(self._results):
            return _FakeResult()
        result = self._results[self._call_index]
        self._call_index += 1
        return result

    async def commit(self) -> None:
        self.committed = True


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self._store.get(name)

    async def setex(self, name: str, time: int, value: str) -> object:
        _ = time
        self._store[name] = value
        return True

    async def delete(self, *names: str) -> object:
        for name in names:
            self._store.pop(name, None)
        return 1


class _FakeSmsProvider:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_sms(self, *, phone: str, message: str) -> SmsResult:
        self.sent.append({"phone": phone, "message": message})
        return SmsResult(success=True, provider="fake")


def _build_service(
    *,
    db_results: list[_FakeResult],
) -> tuple[AuthService, _FakeDbSession, _FakeRedis, _FakeSmsProvider]:
    db = _FakeDbSession(db_results)
    redis = _FakeRedis()
    sms = _FakeSmsProvider()
    service = AuthService(db=db, redis=redis, sms_provider=sms)
    return service, db, redis, sms


@pytest.mark.asyncio
async def test_send_code_stores_otp_in_redis_and_sends_sms() -> None:
    service, _, redis, sms = _build_service(db_results=[])

    result = await service.send_code(phone="+79001234567")

    assert result["message"] == "Code sent"
    assert isinstance(result["expires_in"], int)
    assert len(sms.sent) == 1
    assert sms.sent[0]["phone"] == "+79001234567"

    stored = await redis.get("otp:+79001234567")
    assert stored is not None
    assert len(stored) == 4


@pytest.mark.asyncio
async def test_verify_code_creates_user_and_returns_tokens() -> None:
    user_id = uuid4()

    service, db, redis, _ = _build_service(
        db_results=[
            _FakeResult(),
            _FakeResult(
                [
                    {
                        "id": user_id,
                        "phone": "+79001234567",
                        "email": None,
                        "name": None,
                        "is_verified": True,
                    }
                ]
            ),
            _FakeResult(),
            _FakeResult(),
        ],
    )

    await redis.setex("otp:+79001234567", 300, "9999")

    result = await service.verify_code(phone="+79001234567", code="9999")

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert db.committed

    access_payload = decode_token(str(result["access_token"]))
    assert access_payload["sub"] == str(user_id)
    assert "customer" in str(access_payload["scope"])


@pytest.mark.asyncio
async def test_verify_code_rejects_wrong_otp() -> None:
    service, _, redis, _ = _build_service(db_results=[])

    await redis.setex("otp:+79001234567", 300, "1234")

    with pytest.raises(ValueError, match="Invalid verification code"):
        await service.verify_code(phone="+79001234567", code="0000")


@pytest.mark.asyncio
async def test_verify_code_rejects_expired_otp() -> None:
    service, _, _, _ = _build_service(db_results=[])

    with pytest.raises(ValueError, match="OTP expired or not found"):
        await service.verify_code(phone="+79001234567", code="1234")


@pytest.mark.asyncio
async def test_refresh_tokens_returns_new_pair() -> None:
    user_id = uuid4()

    service, _, _, _ = _build_service(
        db_results=[
            _FakeResult([{"id": user_id}]),
            _FakeResult(),
            _FakeResult(),
        ],
    )

    old_refresh = create_refresh_token(user_id=user_id, scopes=["customer"])
    result = await service.refresh_tokens(refresh_token=old_refresh)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["access_token"] != result["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_access_token() -> None:
    from app.core.security import create_access_token

    user_id = uuid4()
    access = create_access_token(user_id=user_id, scopes=["customer"])

    service, _, _, _ = _build_service(db_results=[])

    with pytest.raises(ValueError, match="not a refresh token"):
        await service.refresh_tokens(refresh_token=access)


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_nonexistent_user() -> None:
    user_id = uuid4()
    refresh = create_refresh_token(user_id=user_id, scopes=["customer"])

    service, _, _, _ = _build_service(
        db_results=[_FakeResult()],
    )

    with pytest.raises(ValueError, match="User not found"):
        await service.refresh_tokens(refresh_token=refresh)


@pytest.mark.asyncio
async def test_refresh_tokens_adds_admin_scope_for_admin_user() -> None:
    user_id = uuid4()
    refresh = create_refresh_token(user_id=user_id, scopes=["customer"])

    service, _, _, _ = _build_service(
        db_results=[
            _FakeResult([{"id": user_id}]),
            _FakeResult(),
            _FakeResult([{"is_admin": True}]),
        ],
    )

    result = await service.refresh_tokens(refresh_token=refresh)
    access_payload = decode_token(str(result["access_token"]))

    scope_claim = str(access_payload["scope"])
    assert "admin" in scope_claim


@pytest.mark.asyncio
async def test_verify_code_adds_brand_claims_to_tokens() -> None:
    user_id = uuid4()
    brand_id = uuid4()
    service, _, redis, _ = _build_service(
        db_results=[
            _FakeResult(),
            _FakeResult(
                [
                    {
                        "id": user_id,
                        "phone": "+79001234567",
                        "email": None,
                        "name": None,
                        "is_verified": True,
                    }
                ]
            ),
            _FakeResult([{"exists": 1}]),
            _FakeResult([{"is_admin": False}]),
            _FakeResult([{"brand_id": brand_id, "role": "manager"}]),
        ],
    )

    await redis.setex("otp:+79001234567", 300, "7777")
    result = await service.verify_code(phone="+79001234567", code="7777")

    payload = decode_token(str(result["access_token"]))
    assert "brand" in str(payload["scope"])
    assert UUID(str(payload["brand_id"])) == brand_id
    assert payload["role"] == "manager"
