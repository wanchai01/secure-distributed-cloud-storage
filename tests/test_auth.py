"""Authentication tests (Phase 2 behavior)."""

from tests.conftest import auth_headers


def test_register_success(register_user):
    u = register_user()
    assert u["user"]["role"] == "user"
    assert "password" not in u["user"]
    assert "password_hash" not in u["user"]


def test_register_duplicate_username_returns_409(client, register_user):
    u = register_user()
    r = client.post(
        "/auth/register",
        json={
            "username": u["username"],
            "email": f"different_{u['username']}@example.com",
            "password": "anotherpass",
        },
    )
    assert r.status_code == 409


def test_register_duplicate_email_returns_409(client, register_user):
    u = register_user()
    r = client.post(
        "/auth/register",
        json={
            "username": f"different_{u['username']}",
            "email": u["user"]["email"],
            "password": "anotherpass",
        },
    )
    assert r.status_code == 409


def test_register_short_password_returns_422(client):
    r = client.post(
        "/auth/register",
        json={"username": "shortpwuser", "email": "shortpw@example.com", "password": "123"},
    )
    assert r.status_code == 422


def test_login_success(register_user):
    u = register_user()
    assert u["token"]


def test_login_wrong_password_returns_401(client, register_user):
    u = register_user()
    r = client.post(
        "/auth/login", data={"username": u["username"], "password": "wrong-password"}
    )
    assert r.status_code == 401


def test_login_nonexistent_user_returns_401(client):
    r = client.post(
        "/auth/login", data={"username": "no_such_user_ever", "password": "whatever"}
    )
    assert r.status_code == 401


def test_me_without_token_returns_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    r = client.get("/auth/me", headers=auth_headers("not.a.valid.jwt"))
    assert r.status_code == 401


def test_me_with_valid_token_returns_profile(client, register_user):
    u = register_user()
    r = client.get("/auth/me", headers=auth_headers(u["token"]))
    assert r.status_code == 200
    assert r.json()["username"] == u["username"]
