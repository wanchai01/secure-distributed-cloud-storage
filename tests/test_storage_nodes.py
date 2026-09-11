"""
Distributed storage / round-robin node selection tests (Phase 5
behavior). These talk to the real DB (storage_nodes table), since
node_service.select_node() is keyed off live DB state.
"""

from tests.conftest import auth_headers, make_upload, set_node_status


def _upload(client, token, filename, content=b"data"):
    return client.post(
        "/files/upload",
        headers=auth_headers(token),
        files=make_upload(filename, content),
    )


def test_round_robin_visits_three_distinct_nodes(client, register_user):
    for node in ("node1", "node2", "node3"):
        set_node_status(node, "online")

    u = register_user()
    uploaded_ids = []
    nodes_seen = []
    try:
        for i in range(3):
            r = _upload(client, u["token"], f"rr_{i}.txt", f"content-{i}".encode())
            assert r.status_code == 201, r.text
            nodes_seen.append(r.json()["storage_node"])
            uploaded_ids.append(r.json()["id"])

        assert len(set(nodes_seen)) == 3, (
            f"Expected 3 distinct nodes across 3 uploads, got {nodes_seen}"
        )
    finally:
        for file_id in uploaded_ids:
            client.delete(f"/files/{file_id}", headers=auth_headers(u["token"]))


def test_offline_node_is_never_selected(client, register_user):
    set_node_status("node2", "offline")
    u = register_user()
    file_id = None
    try:
        r = _upload(client, u["token"], "offline_test.txt")
        assert r.status_code == 201, r.text
        assert r.json()["storage_node"] != "node2"
        file_id = r.json()["id"]
    finally:
        set_node_status("node2", "online")
        if file_id:
            client.delete(f"/files/{file_id}", headers=auth_headers(u["token"]))


def test_all_nodes_offline_returns_503(client, register_user):
    for node in ("node1", "node2", "node3"):
        set_node_status(node, "offline")

    u = register_user()
    try:
        r = _upload(client, u["token"], "outage_test.txt")
        assert r.status_code == 503
    finally:
        for node in ("node1", "node2", "node3"):
            set_node_status(node, "online")
