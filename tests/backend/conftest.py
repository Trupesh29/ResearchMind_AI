import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import Settings
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.session import get_session_factory, set_session_factory
from backend.app.main import app


@pytest.fixture(scope="session", autouse=True)
def guard_real_project_storage():
    """
    Ensures tests do not modify or create files in the real project database or storage directory.
    Recursively snapshots all files, sizes, and mtimes before and after the test run.
    """
    real_data_dir = PROJECT_ROOT / "data"
    before_snapshot: dict[Path, tuple[int, float]] = {}
    if real_data_dir.exists():
        for path in real_data_dir.rglob("*"):
            if path.is_file():
                before_snapshot[path] = (path.stat().st_size, path.stat().st_mtime)

    yield

    after_snapshot: dict[Path, tuple[int, float]] = {}
    if real_data_dir.exists():
        for path in real_data_dir.rglob("*"):
            if path.is_file():
                after_snapshot[path] = (path.stat().st_size, path.stat().st_mtime)

    # 1. Verify no existing files were modified or deleted
    for path, before_info in before_snapshot.items():
        assert path in after_snapshot, f"Real project file {path} was removed by tests!"
        after_info = after_snapshot[path]
        assert after_info == before_info, (
            f"Real project file {path} was modified by tests! Before: {before_info}, After: {after_info}"
        )

    # 2. Verify no new files were created in real project storage (WAL, SHM, probe files, etc.)
    new_files = set(after_snapshot.keys()) - set(before_snapshot.keys())
    assert not new_files, f"Test suite created unexpected files in real project storage: {new_files}"


@pytest.fixture(scope="session")
def temp_test_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        yield Path(tmp)


@pytest.fixture(scope="function")
def isolated_env(temp_test_dir: Path) -> Generator[dict, None, None]:
    """
    Creates an isolated test environment with fresh SQLite DB and temporary DATA_DIR.
    Runs real Alembic migrations on the database.
    Restores all app state, settings, and session factory overrides in teardown.
    """
    from sqlalchemy.pool import NullPool

    test_run_id = os.urandom(6).hex()
    test_data_dir = temp_test_dir / f"data_{test_run_id}"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["pdfs", "indexes", "models", "reports"]:
        (test_data_dir / sub).mkdir(parents=True, exist_ok=True)

    db_file = test_data_dir / "test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # Run real Alembic migrations on the disposable test database
    alembic_cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    test_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        future=True,
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if hasattr(dbapi_connection, "cursor"):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    test_settings = Settings(
        DATA_DIR=test_data_dir,
        DATABASE_URL=db_url,
    )

    # Bootstrap default user in test database using test_settings
    with TestSessionLocal() as session:
        bootstrap_default_user(session, settings=test_settings)

    # Inject into app state and session factory with full try...finally restoration
    old_session_factory = getattr(app.state, "session_factory", None)
    old_settings = getattr(app.state, "settings", None)
    old_global_factory = get_session_factory()

    app.state.session_factory = TestSessionLocal
    app.state.settings = test_settings
    set_session_factory(TestSessionLocal)

    try:
        yield {
            "engine": test_engine,
            "session_factory": TestSessionLocal,
            "settings": test_settings,
            "data_dir": test_data_dir,
            "db_url": db_url,
            "alembic_cfg": alembic_cfg,
        }
    finally:
        test_engine.dispose()
        app.state.session_factory = old_session_factory
        app.state.settings = old_settings
        set_session_factory(old_global_factory)


@pytest.fixture(scope="function")
def db_session(isolated_env: dict) -> Generator[Session, None, None]:
    session = isolated_env["session_factory"]()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(isolated_env: dict) -> Generator[TestClient, None, None]:
    """
    TestClient executing against the REAL get_db and get_settings dependencies,
    which read from app.state.session_factory and app.state.settings.
    """
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
