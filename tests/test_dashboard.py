"""Dashboard tests (Phase 3 behavior)."""

from tests.conftest import auth_headers


def test_dashboard_requires_auth(client):
    r = client.get("/dashboard")
    assert r.status_code == 401


def test_dashboard_returns_expected_shape(client, register_user):
    u = register_user()
    r = client.get("/dashboard", headers=auth_headers(u["token"]))
    assert r.status_code == 200

    body = r.json()
    for key in (
        "users",
        "files",
        "storage_used",
        "nodes",
        "online_nodes",
        "login_count",
        "node_status",
    ):
        assert key in body, f"dashboard response missing '{key}'"

    assert body["nodes"] == 3
    assert isinstance(body["node_status"], list)
    assert len(body["node_status"]) == 3
    assert body["users"] >= 1  # at least the user we just registered
