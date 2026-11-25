from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import create_access_token, create_refresh_token, decode_token


def test_create_and_decode_access_token() -> None:
    user_id = uuid4()
    token = create_access_token(user_id=user_id, scopes=["customer"])

    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["scope"] == "customer"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token() -> None:
    user_id = uuid4()
    token = create_refresh_token(user_id=user_id, scopes=["customer", "brand"])

    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["scope"] == "customer brand"
    assert payload["type"] == "refresh"


def test_decode_invalid_token_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_token("not.a.valid.jwt")


def test_access_and_refresh_tokens_are_different() -> None:
    user_id = uuid4()
    access = create_access_token(user_id=user_id, scopes=["customer"])
    refresh = create_refresh_token(user_id=user_id, scopes=["customer"])

    assert access != refresh
