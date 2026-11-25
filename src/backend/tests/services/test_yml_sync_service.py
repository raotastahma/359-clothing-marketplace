# Tests for YmlSyncService: feed parsing, mocked-HTTP download, and the SSRF
# guard that restricts feed URLs to public http(s) targets.
from __future__ import annotations

# pyright: reportPrivateUsage=false
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import cast

import httpx
import pytest

import app.services.yml_sync_service as yml_sync_module
from app.services.yml_sync_service import (
    DatabaseSessionProtocol,
    YmlSyncService,
    _ensure_safe_feed_url,
)

# Documentation/example public IP; keeps SSRF-guard tests independent of real DNS.
PUBLIC_IP = "93.184.216.34"


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, *, ips: list[str]) -> None:
    async def _fake_resolve(host: str) -> list[str]:
        _ = host
        return ips

    monkeypatch.setattr(yml_sync_module, "_resolve_host_ips", _fake_resolve)


class _FakeResult:
    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return None

    def all(self) -> list[Mapping[str, object]]:
        return []

    def scalar_one_or_none(self) -> object:
        return None


class _FakeDb:
    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        _ = statement
        _ = params
        return _FakeResult()

    async def commit(self) -> None:
        return


def _fixture_path(name: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return str(root / "fixtures" / name)


def test_parse_offers_from_sample_fixture() -> None:
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, _FakeDb()))
    offers = service._parse_offers(file_path=_fixture_path("sample_yml_feed.xml"))

    assert len(offers) == 2
    assert offers[0].vendor_code == "MSL-JKT-001-S"
    assert str(offers[0].price_rub) == "15000.00"
    assert offers[0].stock_quantity == 5
    # vendorCode fallback to offer id
    assert offers[1].vendor_code == "MSL-JKT-001-M"
    assert offers[1].stock_quantity == 0


class _RecordedStreamRequest:
    def __init__(
        self,
        *,
        client_number: int,
        method: str,
        url: httpx.URL,
        headers: Mapping[str, str],
        extensions: Mapping[str, str],
    ) -> None:
        self.client_number = client_number
        self.method = method
        self.url = url
        self.headers = headers
        self.extensions = extensions


class _MockStreamResponse:
    def __init__(
        self,
        *,
        status_code: int,
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    async def __aenter__(self) -> _MockStreamResponse:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type
        _ = exc
        _ = tb
        return

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        yield self._body


class _MockAsyncClient:
    def __init__(
        self,
        *,
        responses: list[_MockStreamResponse],
        requests: list[_RecordedStreamRequest],
        client_number: int,
        **kwargs: object,
    ) -> None:
        _ = kwargs
        self._responses = responses
        self._requests = requests
        self._client_number = client_number

    async def __aenter__(self) -> _MockAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type
        _ = exc
        _ = tb
        return

    def stream(
        self,
        method: str,
        url: httpx.URL | str,
        *,
        headers: Mapping[str, str] | None = None,
        extensions: Mapping[str, str] | None = None,
    ) -> _MockStreamResponse:
        self._requests.append(
            _RecordedStreamRequest(
                client_number=self._client_number,
                method=method,
                url=httpx.URL(url),
                headers=headers or {},
                extensions=extensions or {},
            )
        )
        return self._responses.pop(0)


def _patch_http_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[_MockStreamResponse],
    requests: list[_RecordedStreamRequest],
    client_numbers: list[int] | None = None,
) -> None:
    def _client_factory(*args: object, **kwargs: object) -> _MockAsyncClient:
        _ = args
        client_number = len(client_numbers or []) + 1
        if client_numbers is not None:
            client_numbers.append(client_number)
        return _MockAsyncClient(
            responses=responses,
            requests=requests,
            client_number=client_number,
            **kwargs,
        )

    monkeypatch.setattr(yml_sync_module.httpx, "AsyncClient", _client_factory)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_download_feed_to_tempfile_with_mocked_http(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_bytes = Path(_fixture_path("sample_yml_feed.xml")).read_bytes()
    requests: list[_RecordedStreamRequest] = []
    _patch_http_client(
        monkeypatch,
        responses=[_MockStreamResponse(status_code=200, body=fixture_bytes)],
        requests=requests,
    )
    # example.test does not resolve in real DNS; stub the resolver to a public IP
    # so the SSRF guard passes and the test stays offline-deterministic.
    _patch_resolver(monkeypatch, ips=[PUBLIC_IP])
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, _FakeDb()))
    temp_path = await service._download_feed_to_tempfile(feed_url="https://example.test/feed.xml")
    try:
        downloaded = Path(temp_path).read_bytes()
        assert downloaded == fixture_bytes
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert str(requests[0].url) == f"https://{PUBLIC_IP}/feed.xml"
        assert requests[0].headers["Host"] == "example.test"
        assert requests[0].extensions["sni_hostname"] == "example.test"
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_download_feed_to_tempfile_isolates_same_ip_cross_host_https_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_bytes = Path(_fixture_path("sample_yml_feed.xml")).read_bytes()
    requests: list[_RecordedStreamRequest] = []
    client_numbers: list[int] = []
    _patch_http_client(
        monkeypatch,
        responses=[
            _MockStreamResponse(
                status_code=302,
                headers={"location": "https://cdn.example.test/feed.xml"},
            ),
            _MockStreamResponse(status_code=200, body=fixture_bytes),
        ],
        requests=requests,
        client_numbers=client_numbers,
    )

    async def _fake_resolve(host: str) -> list[str]:
        if host in {"feeds.example.test", "cdn.example.test"}:
            return [PUBLIC_IP]
        raise AssertionError(f"Unexpected host: {host}")

    monkeypatch.setattr(yml_sync_module, "_resolve_host_ips", _fake_resolve)
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, _FakeDb()))
    temp_path = await service._download_feed_to_tempfile(
        feed_url="https://feeds.example.test/feed.xml"
    )
    try:
        downloaded = Path(temp_path).read_bytes()
        assert downloaded == fixture_bytes
        assert client_numbers == [1, 2]
        assert [request.client_number for request in requests] == [1, 2]
        assert [request.url.host for request in requests] == [PUBLIC_IP, PUBLIC_IP]
        assert [request.headers["Host"] for request in requests] == [
            "feeds.example.test",
            "cdn.example.test",
        ]
        assert [request.extensions["sni_hostname"] for request in requests] == [
            "feeds.example.test",
            "cdn.example.test",
        ]
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_download_feed_to_tempfile_rejects_private_redirect_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[_RecordedStreamRequest] = []
    _patch_http_client(
        monkeypatch,
        responses=[
            _MockStreamResponse(
                status_code=302,
                headers={"location": "https://internal.example.test/feed.xml"},
            )
        ],
        requests=requests,
    )

    async def _fake_resolve(host: str) -> list[str]:
        if host == "feeds.example.test":
            return [PUBLIC_IP]
        if host == "internal.example.test":
            return ["10.0.0.5"]
        raise AssertionError(f"Unexpected host: {host}")

    monkeypatch.setattr(yml_sync_module, "_resolve_host_ips", _fake_resolve)
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, _FakeDb()))

    with pytest.raises(RuntimeError, match="non-public"):
        await service._download_feed_to_tempfile(feed_url="https://feeds.example.test/feed.xml")

    assert len(requests) == 1
    assert requests[0].url.host == PUBLIC_IP
    assert requests[0].headers["Host"] == "feeds.example.test"


@pytest.mark.asyncio
async def test_download_feed_to_tempfile_rejects_more_than_five_redirect_hops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[_RecordedStreamRequest] = []
    _patch_http_client(
        monkeypatch,
        responses=[
            _MockStreamResponse(status_code=302, headers={"location": f"/hop-{index}.xml"})
            for index in range(6)
        ],
        requests=requests,
    )
    _patch_resolver(monkeypatch, ips=[PUBLIC_IP])
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, _FakeDb()))

    with pytest.raises(RuntimeError, match="redirected too many times"):
        await service._download_feed_to_tempfile(feed_url="https://feeds.example.test/feed.xml")

    assert len(requests) == 6
    assert {request.url.host for request in requests} == {PUBLIC_IP}
    assert {request.headers["Host"] for request in requests} == {"feeds.example.test"}


@pytest.mark.asyncio
async def test_ensure_safe_feed_url_allows_public_https_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolver(monkeypatch, ips=[PUBLIC_IP])

    # Must not raise for a public https target.
    await _ensure_safe_feed_url("https://feeds.example.com/feed.xml")


@pytest.mark.asyncio
async def test_ensure_safe_feed_url_rejects_non_http_scheme() -> None:
    with pytest.raises(RuntimeError, match="http or https"):
        await _ensure_safe_feed_url("ftp://feeds.example.com/feed.xml")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "feed_url",
    [
        # Loopback and metadata-endpoint IP literals resolve locally (no network needed).
        "http://127.0.0.1/feed.xml",
        "http://169.254.169.254/latest/meta-data",
    ],
)
async def test_ensure_safe_feed_url_rejects_non_public_ip_literal(feed_url: str) -> None:
    with pytest.raises(RuntimeError, match="non-public"):
        await _ensure_safe_feed_url(feed_url)


@pytest.mark.asyncio
async def test_ensure_safe_feed_url_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resolver(monkeypatch, ips=["10.0.0.5"])

    with pytest.raises(RuntimeError, match="non-public"):
        await _ensure_safe_feed_url("https://internal.example.com/feed.xml")
