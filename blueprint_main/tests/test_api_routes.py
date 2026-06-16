import json
import os

from fastapi.testclient import TestClient

from blueprint_main.app import app


def _sample_snapshot():
    return {
        "meta": {"file_key": "api-demo", "node_id": "10:1", "name": "demo"},
        "nodes": [
            {
                "id": "node-a",
                "name": "Start",
                "sections": [
                    {"title": "MAIN", "pins": [{"id": "pin-a1", "name": "Go", "side": "right"}]}
                ],
            },
            {
                "id": "node-b",
                "name": "Decision",
                "sections": [
                    {"title": "MAIN", "pins": [{"id": "pin-b1", "name": "是否继续?", "side": "left"}]}
                ],
            },
        ],
        "edges": [{"from": "pin-a1", "to": "pin-b1"}],
    }


def test_snapshot_graph_and_tree_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_MAIN_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("BLUEPRINT_MAIN_LEGACY_SNAPSHOT_DIR", str(tmp_path / "legacy_empty"))
    monkeypatch.setenv("BLUEPRINT_MAIN_FLOW_DIR", str(tmp_path / "flow"))
    client = TestClient(app)

    save_response = client.post("/api/blueprint-main/snapshots", json=_sample_snapshot())
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["ok"] is True
    assert os.path.exists(saved["path"])

    list_response = client.get("/api/blueprint-main/snapshots")
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    latest_response = client.get("/api/blueprint-main/snapshots/latest")
    assert latest_response.status_code == 200
    snapshot_name = latest_response.json()["name"]

    graph_response = client.post(
        "/api/blueprint-main/graphs/build",
        json={"name": snapshot_name, "folder": "api-demo", "scope": "pin", "save_output": True},
    )
    assert graph_response.status_code == 200
    assert graph_response.json()["graph"]["stats"]["node_count"] == 2
    assert os.path.exists(graph_response.json()["path"])

    tree_response = client.post(
        "/api/blueprint-main/trees/build",
        json={"name": snapshot_name, "folder": "api-demo", "scope": "pin", "cycle_aware": True, "save_output": True},
    )
    assert tree_response.status_code == 200
    assert tree_response.json()["tree"]["stats"]["node_count"] == 2
    assert tree_response.json()["structured_tree"]["root"]["type"] == "sequence"
    assert os.path.exists(tree_response.json()["path"])


def test_snapshot_routes_include_legacy_snapshot_folders(tmp_path, monkeypatch):
    snapshot_dir = tmp_path / "snapshots"
    legacy_dir = tmp_path / "legacy_snapshots"
    legacy_folder = legacy_dir / "default"
    legacy_folder.mkdir(parents=True)
    legacy_name = "legacy-demo_10-1_demo_123.json"
    legacy_path = legacy_folder / legacy_name
    legacy_path.write_text(json.dumps(_sample_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setenv("BLUEPRINT_MAIN_SNAPSHOT_DIR", str(snapshot_dir))
    monkeypatch.setenv("BLUEPRINT_MAIN_LEGACY_SNAPSHOT_DIR", str(legacy_dir))
    client = TestClient(app)

    folders_response = client.get("/api/blueprint-main/snapshots/folders")
    assert folders_response.status_code == 200
    assert "default" in folders_response.json()["folders"]

    list_response = client.get("/api/blueprint-main/snapshots", params={"folder": "default"})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == legacy_name
    assert items[0]["folder"] == "default"

    load_response = client.get(f"/api/blueprint-main/snapshots/{legacy_name}", params={"folder": "default"})
    assert load_response.status_code == 200
    assert load_response.json()["meta"]["file_key"] == "api-demo"
