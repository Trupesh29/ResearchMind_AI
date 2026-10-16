from pathlib import Path

from fastapi import Request
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application & Environment
    PROJECT_NAME: str = "ResearchMind AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")

    # Server Binding
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)

    # Allowed CORS Origins
    ALLOWED_ORIGINS: list[str] | str = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])

    # Base Paths (handles spaces and absolute resolution)
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent / "data")
    DATABASE_URL: str = Field(default="")

    # Authentication & Local User Mode
    AUTH_ENABLED: bool = Field(default=False)
    DEFAULT_USER_EMAIL: str = Field(default="local@researchmind.ai")
    DEFAULT_USER_NAME: str = Field(default="Local Researcher")

    # Document & Upload limits
    MAX_UPLOAD_MB: int = Field(default=25)

    # Embedding / Retrieval Baseline (Week 3)
    EMBEDDING_MODEL_NAME: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DEVICE: str = Field(default="auto")

    # Generator Configuration (Week 4)
    GENERATOR_PROVIDER: str = Field(default="mock")
    GENERATOR_MODEL: str = Field(default="gpt-4o-mini")
    GENERATOR_API_KEY: str = Field(default="")
    GENERATOR_TIMEOUT_SECONDS: int = Field(default=30)
    GENERATOR_MAX_RETRIES: int = Field(default=2)
    GENERATOR_BUDGET_USD: float = Field(default=5.00)

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def assemble_paths_and_db_url(self) -> "Settings":
        # Resolve BASE_DIR
        if not self.BASE_DIR.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self.BASE_DIR = (project_root / self.BASE_DIR).resolve()
        else:
            self.BASE_DIR = self.BASE_DIR.resolve()

        # Resolve DATA_DIR relative to BASE_DIR if not absolute
        if not self.DATA_DIR.is_absolute():
            self.DATA_DIR = (self.BASE_DIR / self.DATA_DIR).resolve()
        else:
            self.DATA_DIR = self.DATA_DIR.resolve()

        # Derive or resolve DATABASE_URL from DATA_DIR if empty
        if not self.DATABASE_URL or not self.DATABASE_URL.strip():
            db_path = self.DATA_DIR / "researchmind.db"
            self.DATABASE_URL = f"sqlite:///{db_path.as_posix()}"
        elif self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:////"):
            sub_path = self.DATABASE_URL.removeprefix("sqlite:///")
            if not Path(sub_path).is_absolute() and not sub_path.startswith(":memory:"):
                resolved_sub = (self.BASE_DIR / sub_path).resolve()
                self.DATABASE_URL = f"sqlite:///{resolved_sub.as_posix()}"
        return self


def ensure_data_directories(data_dir: Path | None = None) -> None:
    """
    Ensure all required storage subdirectories exist.
    Called explicitly at startup / lifespan rather than on module import.
    """
    target = data_dir or settings.DATA_DIR
    for sub in ["pdfs", "indexes", "models", "reports"]:
        (target / sub).mkdir(parents=True, exist_ok=True)


settings = Settings()


def get_settings(request: Request = None) -> Settings:
    """
    FastAPI dependency that returns the effective application settings.
    Prioritizes request.app.state.settings for test/context overrides,
    falling back to the global singleton settings.
    """
    if request is not None and hasattr(request, "app"):
        app_settings = getattr(request.app.state, "settings", None)
        if app_settings is not None:
            return app_settings
    return settings
