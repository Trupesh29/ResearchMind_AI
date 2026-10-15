from pathlib import Path

from pydantic import Field, field_validator
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
    ALLOWED_ORIGINS: list[str] | str = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Base Paths (handles spaces and absolute resolution)
    BASE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent
    )
    DATA_DIR: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parent.parent.parent.parent / "data"
        )
    )
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
        env_file=".env",
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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str, info) -> str:
        if v and v.strip():
            return v.strip()
        # Fallback to local data/researchmind.db relative to project base
        base = Path(__file__).resolve().parent.parent.parent.parent
        db_path = base / "data" / "researchmind.db"
        # Standardize SQLite URL with forward slashes
        return f"sqlite:///{db_path.as_posix()}"


settings = Settings()
# Ensure data directories exist
for sub in ["pdfs", "indexes", "models", "reports"]:
    (settings.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
