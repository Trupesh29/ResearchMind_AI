from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import User
from backend.app.main import app


def test_create_workspace_success(client: TestClient):
    res = client.post(
        "/api/workspaces", json={"name": " Quantum Computing ", "description": "Quantum physics and algorithms"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Quantum Computing"
    assert data["description"] == "Quantum physics and algorithms"
    assert data["paper_count"] == 0
    assert "id" in data
    assert "created_at" in data


def test_create_workspace_duplicate_name_conflict(client: TestClient):
    res1 = client.post("/api/workspaces", json={"name": "Machine Learning"})
    assert res1.status_code == 201

    res2 = client.post("/api/workspaces", json={"name": "Machine Learning"})
    assert res2.status_code == 409
    err = res2.json()
    assert err["error"]["code"] == "NAME_CONFLICT"
    assert "already exists" in err["error"]["message"].lower()


def test_create_workspace_validation_empty_name(client: TestClient):
    res = client.post("/api/workspaces", json={"name": "   "})
    assert res.status_code == 400
    err = res.json()
    assert err["error"]["code"] == "INVALID_REQUEST"


def test_list_workspaces_pagination_and_sorting(client: TestClient):
    for i in range(5):
        client.post("/api/workspaces", json={"name": f"Workspace {i:02d}"})

    res = client.get("/api/workspaces?limit=3")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 3
    assert data["total_count"] == 5
    assert data["next_cursor"] is not None

    next_cursor = data["next_cursor"]
    res2 = client.get(f"/api/workspaces?cursor={next_cursor}&limit=3")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 2
    assert data2["next_cursor"] is None


def test_get_workspace_by_id(client: TestClient):
    create_res = client.post("/api/workspaces", json={"name": "Neuroscience", "description": "Brain studies"})
    ws_id = create_res.json()["id"]

    res = client.get(f"/api/workspaces/{ws_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == ws_id
    assert data["name"] == "Neuroscience"
    assert data["description"] == "Brain studies"
    assert data["paper_count"] == 0


def test_get_workspace_not_found(client: TestClient):
    res = client.get("/api/workspaces/nonexistent-id")
    assert res.status_code == 404
    err = res.json()
    assert err["error"]["code"] == "NOT_FOUND"


def test_update_workspace(client: TestClient):
    create_res = client.post("/api/workspaces", json={"name": "Old Title", "description": "Old desc"})
    ws_id = create_res.json()["id"]

    res = client.patch(f"/api/workspaces/{ws_id}", json={"name": "New Title", "description": "Updated desc"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "New Title"
    assert data["description"] == "Updated desc"


def test_update_workspace_name_conflict(client: TestClient):
    client.post("/api/workspaces", json={"name": "Alpha"})
    res2 = client.post("/api/workspaces", json={"name": "Beta"})
    beta_id = res2.json()["id"]

    res = client.patch(f"/api/workspaces/{beta_id}", json={"name": "Alpha"})
    assert res.status_code == 409
    err = res.json()
    assert err["error"]["code"] == "NAME_CONFLICT"


def test_delete_workspace_cascades(client: TestClient):
    create_res = client.post("/api/workspaces", json={"name": "To Delete"})
    ws_id = create_res.json()["id"]

    del_res = client.delete(f"/api/workspaces/{ws_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/workspaces/{ws_id}")
    assert get_res.status_code == 404


def test_foreign_user_workspace_isolation(client: TestClient, db_session: Session):
    # Create foreign user in DB
    foreign_user = User(
        id="foreign-user-uuid",
        email="other@researchmind.local",
        password_hash="mock_hash_value",
        display_name="Other User",
    )
    db_session.add(foreign_user)
    db_session.commit()

    # User 1 creates a workspace
    create_res = client.post("/api/workspaces", json={"name": "Private WS"})
    ws_id = create_res.json()["id"]

    # Now override get_current_user to simulate foreign user
    app.dependency_overrides[get_current_user] = lambda: foreign_user
    try:
        # Foreign user tries to get ws_id -> 404 (not 403, for privacy)
        res = client.get(f"/api/workspaces/{ws_id}")
        assert res.status_code == 404

        # Foreign user tries to update ws_id -> 404
        res = client.patch(f"/api/workspaces/{ws_id}", json={"name": "Hacked"})
        assert res.status_code == 404

        # Foreign user tries to delete ws_id -> 404
        res = client.delete(f"/api/workspaces/{ws_id}")
        assert res.status_code == 404

        # Foreign user listing workspaces does not see User 1's workspace
        list_res = client.get("/api/workspaces")
        assert list_res.status_code == 200
        assert all(item["id"] != ws_id for item in list_res.json()["items"])
    finally:
        app.dependency_overrides.pop(get_current_user, None)
