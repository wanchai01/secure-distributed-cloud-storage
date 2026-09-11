"""JWT unit tests - no DB required, tests utils/jwt.py directly."""

import pytest
from jose import JWTError

from backend.utils.jwt import create_access_token, decode_access_token


def test_create_and_decode_roundtrip():
    token = create_access_token({"user_id": 1, "username": "alice", "role": "user"})
    payload = decode_access_token(token)

    assert payload["user_id"] == 1
    assert payload["username"] == "alice"
    assert payload["role"] == "user"
    assert "exp" in payload


def test_decode_malformed_token_raises():
    with pytest.raises(JWTError):
        decode_access_token("this.is.not.a.valid.jwt")


def test_decode_expired_token_raises():
    # -1 minute expiry => already expired the moment it's created
    token = create_access_token(
        {"user_id": 1, "username": "alice", "role": "user"}, expires_minutes=-1
    )
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_tokens_for_different_payloads_are_different():
    t1 = create_access_token({"user_id": 1, "username": "alice", "role": "user"})
    t2 = create_access_token({"user_id": 2, "username": "bob", "role": "user"})
    assert t1 != t2
