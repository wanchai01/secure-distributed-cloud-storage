"""
Cross-cutting authorization tests: unauthenticated access is blocked
(401), and role-restricted routes reject non-admin users (403).
Ownership-specific checks live in test_files.py.
"""

from tests.conftest import auth_headers

PROTECTED_GET_ENDPOINTS = [
    "/dashboard",
    "/files",
    "/auth/me",
]

ADMIN_ONLY_ENDPOINTS = [
    "/admin/users",
    "/admin/files",
    "/admin/logins",
    "/admin/audit-logs",
    "/admin/nodes",
]


def test_protected_endpoints_reject_missing_token(client):
    for path in PROTECTED_GET_ENDPOINTS:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


def test_protected_endpoints_reject_garbage_token(client):
    for path in PROTECTED_GET_ENDPOINTS:
        r = client.get(path, headers=auth_headers("garbage.token.value"))
        assert r.status_code == 401, f"{path} should reject an invalid token"


def test_admin_endpoints_reject_missing_token(client):
    for path in ADMIN_ONLY_ENDPOINTS:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


def test_admin_endpoints_reject_regular_user(client, register_user):
    u = register_user()
    headers = auth_headers(u["token"])
    for path in ADMIN_ONLY_ENDPOINTS:
        r = client.get(path, headers=headers)
        assert r.status_code == 403, f"{path} should reject a non-admin user"


def test_admin_endpoints_accept_admin_user(client, register_admin):
    admin = register_admin()
    headers = auth_headers(admin["token"])
    for path in ADMIN_ONLY_ENDPOINTS:
        r = client.get(path, headers=headers)
        assert r.status_code == 200, f"{path} should allow an admin user"
