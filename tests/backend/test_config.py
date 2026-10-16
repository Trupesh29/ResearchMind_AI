import os
from pathlib import Path

from backend.app.core.config import Settings


def test_settings_defaults(monkeypatch):
    # Isolate from caller's environment and .env file
    for env_key in [
        "DATABASE_URL",
        "DATA_DIR",
        "BASE_DIR",
        "ALLOWED_ORIGINS",
        "AUTH_ENABLED",
        "GENERATOR_PROVIDER",
    ]:
        monkeypatch.delenv(env_key, raising=False)

    s = Settings(_env_file=None)
    assert s.PROJECT_NAME == "ResearchMind AI"
    assert s.API_V1_STR == "/api"
    assert s.MAX_UPLOAD_MB == 25
    assert s.AUTH_ENABLED is False
    assert s.DEFAULT_USER_EMAIL == "local@researchmind.ai"
    assert s.GENERATOR_PROVIDER in ["mock", "openai", "anthropic", "gemini"]
    assert isinstance(s.ALLOWED_ORIGINS, list)
    assert len(s.ALLOWED_ORIGINS) >= 1
    # DATABASE_URL derives from DATA_DIR
    assert s.DATABASE_URL == f"sqlite:///{(s.DATA_DIR / 'researchmind.db').as_posix()}"


def test_explicit_database_url_override_isolated(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom_guard.db")
    s = Settings(_env_file=None)
    assert s.DATABASE_URL == f"sqlite:///{(s.BASE_DIR / 'custom_guard.db').as_posix()}"


def test_cors_origins_parsing():
    s = Settings(ALLOWED_ORIGINS="http://example.com, https://app.example.com", _env_file=None)
    assert "http://example.com" in s.ALLOWED_ORIGINS
    assert "https://app.example.com" in s.ALLOWED_ORIGINS


def test_custom_absolute_data_dir(tmp_path: Path):
    custom_dir = tmp_path / "custom_abs_data"
    s = Settings(DATA_DIR=custom_dir, DATABASE_URL="")
    assert s.DATA_DIR == custom_dir.resolve()
    assert s.DATABASE_URL == f"sqlite:///{(custom_dir / 'researchmind.db').as_posix()}"


def test_custom_relative_data_dir():
    s = Settings(DATA_DIR=Path("custom_rel_data"), DATABASE_URL="")
    assert s.DATA_DIR.is_absolute()
    assert s.DATA_DIR == (s.BASE_DIR / "custom_rel_data").resolve()
    assert s.DATABASE_URL == f"sqlite:///{(s.DATA_DIR / 'researchmind.db').as_posix()}"


def test_explicit_sqlite_url():
    s = Settings(DATABASE_URL="sqlite:///custom_db.sqlite")
    assert s.DATABASE_URL == f"sqlite:///{(s.BASE_DIR / 'custom_db.sqlite').as_posix()}"


def test_settings_from_another_working_directory(tmp_path: Path):
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        s = Settings()
        assert s.BASE_DIR.exists()
        assert s.DATA_DIR.is_absolute()
        assert s.DATABASE_URL.startswith("sqlite:///")
    finally:
        os.chdir(cwd)
