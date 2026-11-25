from __future__ import annotations

# pyright: reportUnusedFunction=false
from collections.abc import Sequence
from typing import cast

from beartype import beartype
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_core import ErrorDetails

STATUS_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
}


def _code_for_status(http_status: int) -> str:
    return STATUS_TO_ERROR_CODE.get(http_status, "API_ERROR")


def _coerce_message(detail: object) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict):
        typed_detail = cast(dict[str, object], detail)
        message = typed_detail.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return "Request failed."


def _coerce_details(detail: object) -> list[object] | None:
    if isinstance(detail, list):
        return list(cast(list[object], detail))
    if isinstance(detail, dict):
        typed_detail = cast(dict[str, object], detail)
        details = typed_detail.get("details")
        if isinstance(details, list):
            return list(cast(list[object], details))
    return None


@beartype
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        error_code = _code_for_status(exc.status_code)
        message = _coerce_message(exc.detail)
        details = _coerce_details(exc.detail)
        payload: dict[str, object] = {"code": error_code, "message": message}
        if details:
            payload["details"] = details
        return JSONResponse(status_code=exc.status_code, content={"error": payload})

    @app.exception_handler(RequestValidationError)
    async def _request_validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        details: list[dict[str, str]] = []
        validation_errors: Sequence[ErrorDetails] = exc.errors()
        for error in validation_errors:
            location_parts = [str(part) for part in error.get("loc", ()) if part != "body"]
            location = ".".join(location_parts)
            details.append({"field": location, "message": str(error.get("msg", "Invalid value"))})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation error",
                    "details": details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected_exception_handler(_: Request, __: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                }
            },
        )
