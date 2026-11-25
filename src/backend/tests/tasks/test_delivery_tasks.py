from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol, cast
from uuid import uuid4

import pytest

from app.core.config import settings
from app.tasks import delivery_tasks


class _FakeMappings:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def __iter__(self) -> Iterator[Mapping[str, object]]:
        return iter(self._rows)

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeConnection:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        statement_text = str(statement)
        self.statements.append(statement_text)
        self.params.append(params)
        if "SELECT id, order_id, tracking_number" in statement_text:
            return _FakeResult(self._rows)
        if "UPDATE sub_orders" in statement_text:
            assert params is not None
            sub_order_id = params["sub_order_id"]
            order_id = next(row["order_id"] for row in self._rows if row["id"] == sub_order_id)
            return _FakeResult([{"order_id": order_id}])
        return _FakeResult([])


class _FakeBegin:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        _ = exc_type
        _ = exc
        _ = traceback


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection
        self.disposed = False

    def begin(self) -> _FakeBegin:
        return _FakeBegin(self._connection)

    async def dispose(self) -> None:
        self.disposed = True


class _FakeDeliveryProvider:
    def __init__(self, remote_status: str) -> None:
        self._remote_status = remote_status
        self.tracking_numbers: list[str] = []

    async def get_tracking_status(self, *, tracking_number: str) -> str:
        self.tracking_numbers.append(tracking_number)
        return self._remote_status


class _TaskWithRun(Protocol):
    def run(self, *, limit: int = 100) -> int: ...


def test_refresh_tracking_statuses_updates_shipped_sub_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()
    sub_order_id = uuid4()
    connection = _FakeConnection(
        [
            {
                "id": sub_order_id,
                "order_id": order_id,
                "tracking_number": "YD-123",
            }
        ]
    )
    engine = _FakeEngine(connection=connection)
    provider = _FakeDeliveryProvider(remote_status="delivered")

    def _create_async_engine(url: str) -> _FakeEngine:
        assert url == settings.database_url
        return engine

    monkeypatch.setattr(delivery_tasks, "get_delivery_provider", lambda: provider)
    monkeypatch.setattr(delivery_tasks, "create_async_engine", _create_async_engine)

    updated_count = cast(_TaskWithRun, delivery_tasks.refresh_tracking_statuses_task).run(limit=10)

    assert updated_count == 1
    assert provider.tracking_numbers == ["YD-123"]
    assert engine.disposed is True
    assert "FROM sub_orders" in connection.statements[0]
    assert "UPDATE sub_orders" in connection.statements[1]
    assert "UPDATE orders o" in connection.statements[2]
    assert connection.params[1] == {"sub_order_id": sub_order_id}
    assert connection.params[2] == {"order_id": order_id}


def test_refresh_tracking_statuses_skips_non_delivered_remote_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeConnection(
        [
            {
                "id": uuid4(),
                "order_id": uuid4(),
                "tracking_number": "YD-123",
            }
        ]
    )
    engine = _FakeEngine(connection=connection)
    provider = _FakeDeliveryProvider(remote_status="shipped")

    def _create_async_engine(url: str) -> _FakeEngine:
        assert url == settings.database_url
        return engine

    monkeypatch.setattr(delivery_tasks, "get_delivery_provider", lambda: provider)
    monkeypatch.setattr(delivery_tasks, "create_async_engine", _create_async_engine)

    updated_count = cast(_TaskWithRun, delivery_tasks.refresh_tracking_statuses_task).run(limit=10)

    assert updated_count == 0
    assert len(connection.statements) == 1
