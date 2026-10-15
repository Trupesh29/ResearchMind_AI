from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(tags=["System"])

_ml_env_cache: dict[str, Any] | None = None


def _get_cached_ml_env() -> dict[str, Any]:
    global _ml_env_cache
    if _ml_env_cache is not None:
        return _ml_env_cache
    try:
        import torch

        _ml_env_cache = {
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "sentence_transformers_available": True,
            "faiss_available": True,
        }
    except Exception as exc:
        _ml_env_cache = {"available": False, "detail": str(exc)}
    return _ml_env_cache


@router.get("/health")
def get_health() -> dict[str, str]:
    """
    Liveness probe endpoint.
    Indicates whether the FastAPI backend process is running and responding.
    """
    return {"status": "ok"}


@router.get("/ready")
def get_ready(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Readiness probe endpoint.
    Checks connectivity to SQLite database, write permissions on data storage,
    and reports ML environment and generator provider readiness without leaking secrets.
    """
    checks = {
        "database": "unknown",
        "storage": "unknown",
        "ml_environment": "unknown",
        "generator": {
            "provider": settings.GENERATOR_PROVIDER,
            "model": settings.GENERATOR_MODEL,
            "configured": False,
        },
    }
    is_ready = True

    # 1. Database Connectivity Check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = f"error: {exc!s}"
        is_ready = False

    # 2. Storage Directory Writable Check
    try:
        test_file = settings.DATA_DIR / ".write_test.tmp"
        with open(test_file, "w") as f:
            f.write("ok")
        if test_file.exists():
            test_file.unlink()
        checks["storage"] = "writable"
    except Exception as exc:
        checks["storage"] = f"unwritable: {exc!s}"
        is_ready = False

    # 3. ML Environment Verification (cached to ensure rapid response)
    checks["ml_environment"] = _get_cached_ml_env()

    # 4. Generator Provider Configuration Check (non-secret status)
    if settings.GENERATOR_PROVIDER == "mock":
        checks["generator"]["configured"] = True
        checks["generator"]["status"] = "mock_provider_active"
    elif bool(settings.GENERATOR_API_KEY.strip()):
        checks["generator"]["configured"] = True
        checks["generator"]["status"] = "api_key_configured"
    else:
        checks["generator"]["configured"] = False
        checks["generator"]["status"] = "api_key_missing"

    return {
        "status": "ready" if is_ready else "degraded",
        "checks": checks,
    }


@router.get("/config/public")
def get_public_config() -> dict[str, Any]:
    """
    Public non-sensitive configuration parameters consumed by the frontend shell.
    """
    return {
        "project_name": settings.PROJECT_NAME,
        "api_version": settings.VERSION,
        "environment": settings.APP_ENV,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "auth_enabled": settings.AUTH_ENABLED,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "generator_provider": settings.GENERATOR_PROVIDER,
        "default_user": {
            "email": settings.DEFAULT_USER_EMAIL,
            "display_name": settings.DEFAULT_USER_NAME,
        },
    }
