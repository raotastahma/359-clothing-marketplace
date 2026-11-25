from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_handlers import register_exception_handlers


async def _not_found() -> dict[str, str]:
    raise HTTPException(status_code=404, detail="Object not found")


async def _validation(age: int) -> dict[str, int]:
    return {"age": age}


async def _boom() -> dict[str, str]:
    raise RuntimeError("Unexpected failure")


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_api_route("/not-found", _not_found, methods=["GET"])
    app.add_api_route("/validation", _validation, methods=["GET"])
    app.add_api_route("/boom", _boom, methods=["GET"])

    return app


def test_http_exception_is_wrapped_in_error_envelope() -> None:
    client = TestClient(_build_app())

    response = client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Object not found"}}


def test_validation_error_is_wrapped_in_error_envelope() -> None:
    client = TestClient(_build_app())

    response = client.get("/validation", params={"age": "not-an-int"})

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Validation error"
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["details"]


def test_unexpected_exception_returns_internal_error() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error."}
    }
