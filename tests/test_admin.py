"""
Admin endpoint content tests (Phase 7 behavior). Access-control tests
(401/403) for these same endpoints live in test_authorization.py -
this file checks the actual data returned to an admin.
"""

from tests.conftest import auth_headers, make_upload


def test_admin_users_lists_registered_users(client, register_admin, register_user):
    admin = register_admin()
    other = register_user()

    r = client.get("/admin/users", headers=auth_headers(admin["token"]))
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()}
    assert admin["username"] in usernames
    assert other["username"] in usernames


def test_admin_files_shows_files_from_any_user(client, register_admin, register_user):
    admin = register_admin()
    owner = register_user()

    r = client.post(
        "/files/upload",
        headers=auth_headers(owner["token"]),
        files=make_upload("admin_visible.txt", b"content"),
    )
    file_id = r.json()["id"]

    try:
        r = client.get("/admin/files", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        matching = [f for f in r.json() if f["id"] == file_id]
        assert len(matching) == 1
        assert matching[0]["username"] == owner["username"]
    finally:
        client.delete(f"/files/{file_id}", headers=auth_headers(owner["token"]))


def test_admin_nodes_returns_three_nodes(client, register_admin):
    admin = register_admin()
    r = client.get("/admin/nodes", headers=auth_headers(admin["token"]))
    assert r.status_code == 200
    node_names = {n["node_name"] for n in r.json()}
    assert node_names == {"node1", "node2", "node3"}


def test_admin_audit_logs_contains_recent_actions(client, register_admin):
    admin = register_admin()  # this alone generates REGISTER + LOGIN audit rows
    r = client.get("/admin/audit-logs", headers=auth_headers(admin["token"]))
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_admin_logins_contains_recent_login(client, register_admin):
    admin = register_admin()
    r = client.get("/admin/logins", headers=auth_headers(admin["token"]))
    assert r.status_code == 200
    assert any(
        entry["username"] == admin["username"] and entry["status"] == "success"
        for entry in r.json()
    )
