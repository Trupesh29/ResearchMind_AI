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


def test_ready_endpoint_healthy(client: TestClient):
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "checks" in data
    db_check = data["checks"]["database"]
    assert db_check["status"] == "healthy"
    assert db_check["message"] == "Connected and schema verified"
    assert (
        "0006_preserve_multirun_page_generations" in db_check["current_revisions"]
        or "0005_repair_historical_generation_attribution" in db_check["current_revisions"]
        or "0004_add_generation_and_fencing_controls" in db_check["current_revisions"]
        or "0003_add_processing_jobs_and_pages" in db_check["current_revisions"]
    )
    assert data["checks"]["storage"]["message"] == "Storage directory writable"
    assert data["checks"]["generator"]["configured"] is True
    assert data["checks"]["generator"]["connectivity"] == "unverified"
    assert data["checks"]["ml_environment"]["model_loaded"] is False
    assert data["checks"]["ml_environment"]["runtime_status"] == "unverified"


def test_ready_endpoint_outdated_migration_returns_503(client: TestClient, db_session):
    from sqlalchemy import text

    # Set version to 0001 while 0002 is pending
    db_session.execute(text("UPDATE alembic_version SET version_num = '0001_initial_core_schema'"))
    db_session.commit()

    res = client.get("/api/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    db_check = data["checks"]["database"]
    assert db_check["status"] == "unhealthy"
    assert db_check["migration_state"] == "outdated"
    assert "pending" in db_check["message"]


def test_ready_endpoint_empty_alembic_version_returns_503(client: TestClient, db_session):
    from sqlalchemy import text

    db_session.execute(text("DELETE FROM alembic_version"))
    db_session.commit()

    res = client.get("/api/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    db_check = data["checks"]["database"]
    assert db_check["status"] == "unhealthy"
    assert db_check["migration_state"] == "empty"


def test_ready_endpoint_absent_alembic_version_returns_503(client: TestClient, db_session):
    from sqlalchemy import text

    db_session.execute(text("DROP TABLE alembic_version"))
    db_session.commit()

    res = client.get("/api/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    db_check = data["checks"]["database"]
    assert db_check["status"] == "unhealthy"
    assert db_check["migration_state"] == "absent"


def test_ready_endpoint_unknown_revision_returns_503(client: TestClient, db_session):
    from sqlalchemy import text

    db_session.execute(text("UPDATE alembic_version SET version_num = '9999_unknown_future_rev'"))
    db_session.commit()

    res = client.get("/api/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    db_check = data["checks"]["database"]
    assert db_check["status"] == "unhealthy"
    assert db_check["migration_state"] == "unknown"
    assert "unknown migration revision" in db_check["message"]


def test_ready_endpoint_missing_table_returns_503(client: TestClient, db_session):
    from sqlalchemy import text

    # Drop papers table to simulate incomplete schema
    db_session.execute(text("DROP TABLE papers"))
    db_session.commit()

    res = client.get("/api/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    assert data["checks"]["database"]["status"] == "unhealthy"
    assert "not initialized" in data["checks"]["database"]["message"]


def test_ready_endpoint_unwritable_storage_returns_503(client: TestClient, isolated_env):
    # Point injected DATA_DIR to an unwritable location without mutating global settings
    old_data_dir = isolated_env["settings"].DATA_DIR
    try:
        blocking_file = isolated_env["data_dir"] / "blocking_file.txt"
        blocking_file.write_text("blocker")
        invalid_path = blocking_file / "sub_data"
        isolated_env["settings"].DATA_DIR = invalid_path

        res = client.get("/api/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert data["checks"]["storage"]["status"] == "unhealthy"
        assert data["checks"]["storage"]["message"] == "Storage directory unwritable"
        # Ensure no raw tracebacks or paths leaked
        assert "blocking_file.txt" not in data["checks"]["storage"]["message"]
    finally:
        isolated_env["settings"].DATA_DIR = old_data_dir


def test_ready_endpoint_unconfigured_generator(client: TestClient, isolated_env):
    old_prov = isolated_env["settings"].GENERATOR_PROVIDER
    old_key = isolated_env["settings"].GENERATOR_API_KEY
    try:
        isolated_env["settings"].GENERATOR_PROVIDER = "openai"
        isolated_env["settings"].GENERATOR_API_KEY = ""
        res = client.get("/api/ready")
        data = res.json()
        gen = data["checks"]["generator"]
        assert gen["configured"] is False
        assert gen["connectivity"] == "unconfigured"
        assert gen["status"] == "api_key_missing"
    finally:
        isolated_env["settings"].GENERATOR_PROVIDER = old_prov
        isolated_env["settings"].GENERATOR_API_KEY = old_key


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
