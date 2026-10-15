from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    # Root alias and API prefix
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "X-Request-ID" in res.headers

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json() == {"status": "ok"}


def test_ready_endpoint(client: TestClient):
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "checks" in data
    assert data["checks"]["database"] == "connected"
    assert data["checks"]["storage"] == "writable"
    assert "generator" in data["checks"]
    assert "ml_environment" in data["checks"]


def test_public_config_endpoint(client: TestClient):
    res = client.get("/api/config/public")
    assert res.status_code == 200
    data = res.json()
    assert data["project_name"] == "ResearchMind AI"
    assert data["max_upload_mb"] == 25
    assert data["auth_enabled"] is False
    assert data["default_user"]["email"] == "local@researchmind.ai"


def test_request_id_header_propagated(client: TestClient):
    custom_req_id = "req_custom_test_999"
    res = client.get("/api/health", headers={"X-Request-ID": custom_req_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_req_id


def test_error_envelope_on_404(client: TestClient):
    res = client.get("/api/unmapped_route_for_testing")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "request_id" in error
    assert error["request_id"] != ""
