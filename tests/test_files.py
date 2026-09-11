"""File upload/list/get/download/delete tests (Phase 4 behavior)."""

from tests.conftest import auth_headers, make_upload


def test_upload_requires_auth(client):
    r = client.post("/files/upload", files=make_upload())
    assert r.status_code == 401


def test_upload_list_get_download_delete_roundtrip(client, register_user):
    u = register_user()
    headers = auth_headers(u["token"])
    content = b"hello world test file content"

    r = client.post(
        "/files/upload", headers=headers, files=make_upload("hello.txt", content)
    )
    assert r.status_code == 201, r.text
    meta = r.json()
    assert meta["original_filename"] == "hello.txt"
    assert meta["file_size"] == len(content)
    assert meta["storage_node"] in ("node1", "node2", "node3")
    file_id = meta["id"]

    r = client.get("/files", headers=headers)
    assert r.status_code == 200
    assert any(f["id"] == file_id for f in r.json())

    r = client.get(f"/files/{file_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == file_id

    r = client.get(f"/files/{file_id}/download", headers=headers)
    assert r.status_code == 200
    assert r.content == content

    r = client.delete(f"/files/{file_id}", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/files/{file_id}", headers=headers)
    assert r.status_code == 404


def test_upload_empty_file_returns_400(client, register_user):
    u = register_user()
    r = client.post(
        "/files/upload",
        headers=auth_headers(u["token"]),
        files=make_upload("empty.txt", b""),
    )
    assert r.status_code == 400


def test_get_nonexistent_file_returns_404(client, register_user):
    u = register_user()
    r = client.get("/files/999999999", headers=auth_headers(u["token"]))
    assert r.status_code == 404


def test_file_ownership_is_enforced(client, register_user):
    owner = register_user()
    other = register_user()

    r = client.post(
        "/files/upload",
        headers=auth_headers(owner["token"]),
        files=make_upload("secret.txt", b"top secret"),
    )
    assert r.status_code == 201
    file_id = r.json()["id"]

    try:
        r = client.get(f"/files/{file_id}", headers=auth_headers(other["token"]))
        assert r.status_code == 403

        r = client.get(
            f"/files/{file_id}/download", headers=auth_headers(other["token"])
        )
        assert r.status_code == 403

        r = client.delete(f"/files/{file_id}", headers=auth_headers(other["token"]))
        assert r.status_code == 403
    finally:
        # cleanup as the actual owner regardless of assertion outcome
        client.delete(f"/files/{file_id}", headers=auth_headers(owner["token"]))


def test_list_files_only_shows_own_files(client, register_user):
    a = register_user()
    b = register_user()

    r = client.post(
        "/files/upload",
        headers=auth_headers(a["token"]),
        files=make_upload("a_file.txt", b"a's file"),
    )
    a_file_id = r.json()["id"]

    try:
        r = client.get("/files", headers=auth_headers(b["token"]))
        assert r.status_code == 200
        assert all(f["id"] != a_file_id for f in r.json())
    finally:
        client.delete(f"/files/{a_file_id}", headers=auth_headers(a["token"]))
