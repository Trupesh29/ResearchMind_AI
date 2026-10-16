from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import (
    get_db,
    get_session_factory,
    set_session_factory,
)
from backend.app.main import app


def test_openapi_has_no_request_parameters():
    """
    Ensure FastAPI dependency injection does not expose internal 'request'
    as an OpenAPI query parameter on any endpoint.
    """
    openapi_schema = app.openapi()
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, op_def in methods.items():
            parameters = op_def.get("parameters", [])
            for param in parameters:
                assert param.get("name") != "request", (
                    f"Route {method.upper()} {path} accidentally exposes 'request' query parameter in OpenAPI: {param}"
                )


def test_app_state_settings_reaches_public_config(isolated_env, client: TestClient):
    """
    Ensure app.state.settings override reaches /api/config/public via the real
    get_settings dependency (without app.dependency_overrides).
    """
    sentinel_name = "Sentinel ResearchMind Override 42"
    custom_settings = Settings(
        PROJECT_NAME=sentinel_name,
        DATA_DIR=isolated_env["data_dir"],
        DATABASE_URL=isolated_env["db_url"],
    )
    old_state_settings = getattr(app.state, "settings", None)
    app.state.settings = custom_settings
    try:
        # Clear any dependency overrides to test the REAL get_settings
        app.dependency_overrides.pop(get_settings, None)
        res = client.get("/api/config/public")
        assert res.status_code == 200
        assert res.json()["project_name"] == sentinel_name
    finally:
        app.state.settings = old_state_settings


def test_app_state_session_factory_used_over_global_factory(isolated_env, client: TestClient):
    """
    Ensure app.state.session_factory supplies the actual request database session
    and the global session factory is bypassed when app.state.session_factory is set.
    """

    # Create a poisoned global factory that raises if called
    def poison_factory():
        raise RuntimeError("POISON: global session factory was called instead of app.state.session_factory")

    old_global_factory = get_session_factory()
    set_session_factory(poison_factory)

    # Ensure app.state has the valid test session factory
    app.state.session_factory = isolated_env["session_factory"]
    app.state.settings = isolated_env["settings"]

    try:
        # Clear dependency overrides so real get_db and get_settings execute
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)

        res = client.get("/api/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"
    finally:
        set_session_factory(old_global_factory)


def test_app_state_settings_controls_readiness_storage(isolated_env, client: TestClient):
    """
    Ensure app.state.settings controls the probe path for readiness storage checks
    through the real get_settings dependency.
    """
    # Create an unwritable DATA_DIR on app.state.settings
    blocking_file = isolated_env["data_dir"] / "blocker_override.txt"
    blocking_file.write_text("blocked")
    unwritable_dir = blocking_file / "invalid_sub"

    override_settings = Settings(
        DATA_DIR=unwritable_dir,
        DATABASE_URL=isolated_env["db_url"],
    )
    old_state_settings = getattr(app.state, "settings", None)
    app.state.settings = override_settings

    try:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)

        res = client.get("/api/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["checks"]["storage"]["status"] == "unhealthy"
        assert data["checks"]["storage"]["message"] == "Storage directory unwritable"
    finally:
        app.state.settings = old_state_settings


def test_app_state_settings_controls_readiness_identity_checks(isolated_env, client: TestClient):
    """
    Ensure app.state.settings controls the expected default user email in readiness
    checks, failing if the configured identity is missing from the database.
    """
    override_settings = Settings(
        DEFAULT_USER_EMAIL="unknown_user@example.com",
        DATA_DIR=isolated_env["data_dir"],
        DATABASE_URL=isolated_env["db_url"],
    )
    old_state_settings = getattr(app.state, "settings", None)
    app.state.settings = override_settings

    try:
        res = client.get("/api/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["checks"]["database"]["status"] == "unhealthy"
        assert "Default local user not found" in data["checks"]["database"]["message"]
    finally:
        app.state.settings = old_state_settings


def test_normal_defaults_work_when_no_state_override(isolated_env):
    """
    Ensure that when app.state has no overrides, get_settings and get_db fall back
    cleanly to their normal default instances.
    """
    from backend.app.core.config import settings as global_settings

    # 1. Direct Python call without arguments
    s = get_settings()
    assert s is global_settings

    # 2. Direct Python call to get_db without arguments uses global/injected factory
    db_gen = get_db()
    assert isinstance(db_gen, Generator)
    db = next(db_gen)
    try:
        assert isinstance(db, Session)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_state_and_dependency_overrides_restored_after_tests(isolated_env, client: TestClient):
    """
    Verify that tests modifying app.state or dependency overrides leave no
    residual overrides that leak into subsequent test executions.
    """
    # Verify no persistent overrides in app.dependency_overrides
    assert get_db not in app.dependency_overrides
    assert get_settings not in app.dependency_overrides

    # Baseline readiness call succeeds with isolated test environment
    res = client.get("/api/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
