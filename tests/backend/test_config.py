from backend.app.core.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.PROJECT_NAME == "ResearchMind AI"
    assert s.API_V1_STR == "/api"
    assert s.MAX_UPLOAD_MB == 25
    assert s.AUTH_ENABLED is False
    assert s.DEFAULT_USER_EMAIL == "local@researchmind.ai"
    assert s.GENERATOR_PROVIDER in ["mock", "openai", "anthropic", "gemini"]
    assert isinstance(s.ALLOWED_ORIGINS, list)
    assert len(s.ALLOWED_ORIGINS) >= 1


def test_cors_origins_parsing():
    s = Settings(ALLOWED_ORIGINS="http://example.com, https://app.example.com")
    assert "http://example.com" in s.ALLOWED_ORIGINS
    assert "https://app.example.com" in s.ALLOWED_ORIGINS


def test_data_dir_resolution():
    s = Settings()
    assert s.DATA_DIR.exists()
    assert (s.DATA_DIR / "pdfs").exists()
    assert (s.DATA_DIR / "indexes").exists()
