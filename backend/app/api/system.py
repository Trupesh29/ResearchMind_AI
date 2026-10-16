import importlib.util
import logging
import uuid
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db

logger = logging.getLogger("researchmind.system")
router = APIRouter(tags=["System"])


def get_migration_revisions(
    db: Session,
    migrations_dir: Path | None = None,
) -> tuple[str, str, list[str], list[str]]:
    """
    Inspects alembic_version and compares against migration script directory.
    Returns: (migration_state, message, current_revisions, expected_heads)
    States:
      - 'up_to_date': Current revisions match expected heads
      - 'outdated': Migrations pending (revisions are known but not head)
      - 'empty': alembic_version table exists but has no rows
      - 'absent': alembic_version table does not exist
      - 'unknown': Database has revisions not found in migration scripts
      - 'error': Exception encountered during inspection
    """
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())
    if "alembic_version" not in table_names:
        return (
            "absent",
            "Database schema version table 'alembic_version' is absent",
            [],
            [],
        )

    try:
        rows = db.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        current_revisions = [row[0] for row in rows]
    except Exception as exc:
        return ("error", f"Failed to query alembic_version: {exc}", [], [])

    if not current_revisions:
        return (
            "empty",
            "Database schema version table 'alembic_version' is empty",
            [],
            [],
        )

    try:
        if migrations_dir is None:
            migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        expected_heads = set(script_dir.get_heads())
        known_revisions = {rev.revision for rev in script_dir.walk_revisions()}
    except Exception as exc:
        logger.error(f"Failed to inspect Alembic migration directory: {exc}")
        return ("error", "Failed to inspect migration directory", current_revisions, [])

    current_set = set(current_revisions)
    unknown = current_set - known_revisions
    if unknown:
        return (
            "unknown",
            f"Database contains unknown migration revision(s): {sorted(unknown)}",
            sorted(current_revisions),
            sorted(expected_heads),
        )

    if current_set != expected_heads:
        return (
            "outdated",
            f"Database migrations are pending. Current: {sorted(current_revisions)}, expected head: {sorted(expected_heads)}",
            sorted(current_revisions),
            sorted(expected_heads),
        )

    return (
        "up_to_date",
        "Database schema migrations up to date",
        sorted(current_revisions),
        sorted(expected_heads),
    )


def _check_ml_dependencies() -> dict[str, Any]:
    """
    Check if ML dependencies are installed without importing heavy runtime modules.
    Keeps shell readiness probe lightweight and instant.
    """
    torch_spec = importlib.util.find_spec("torch") is not None
    st_spec = importlib.util.find_spec("sentence_transformers") is not None
    faiss_spec = importlib.util.find_spec("faiss") is not None

    return {
        "torch_installed": torch_spec,
        "sentence_transformers_installed": st_spec,
        "faiss_installed": faiss_spec,
        "runtime_status": "unverified",
        "model_loaded": False,
    }


@router.get("/health")
def get_health() -> dict[str, str]:
    """
    Liveness probe endpoint.
    Indicates whether the FastAPI backend process is running and responding.
    """
    return {"status": "ok"}


@router.get("/ready")
def get_ready(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Readiness probe endpoint.
    Checks:
    1. Database schema: required tables present, migrations at expected head, default user verified.
    2. Private storage: directory writable using safe unique probe file.
    3. ML dependencies: package installation status without heavy runtime loading.
    4. Generator: honest unconfigured / configured / unverified connectivity status.
    Returns HTTP 200 when ready, HTTP 503 when degraded / unready.
    """
    checks: dict[str, Any] = {
        "database": {"status": "unknown"},
        "storage": {"status": "unknown"},
        "ml_environment": _check_ml_dependencies(),
        "generator": {
            "provider": settings.GENERATOR_PROVIDER,
            "model": settings.GENERATOR_MODEL,
            "configured": False,
            "connectivity": "unconfigured",
            "message": "",
        },
    }
    is_ready = True

    # 1. Database Schema & Connectivity Verification
    try:
        # Check basic connectivity
        db.execute(text("SELECT 1"))

        # Inspect required schema tables
        inspector = inspect(db.bind)
        table_names = set(inspector.get_table_names())
        required_tables = {"users", "workspaces", "papers", "alembic_version"}
        missing_tables = required_tables - table_names

        if missing_tables:
            logger.error(f"Readiness database schema incomplete. Missing tables: {missing_tables}")
            mig_state = "absent" if "alembic_version" in missing_tables else "unhealthy"
            checks["database"] = {
                "status": "unhealthy",
                "message": "Database schema not initialized or migration pending",
                "missing_tables": sorted(missing_tables),
                "migration_state": mig_state,
            }
            is_ready = False
        else:
            # Check migration revision against expected heads
            mig_state, mig_msg, cur_revs, exp_heads = get_migration_revisions(db)
            if mig_state != "up_to_date":
                logger.error(f"Readiness database migration check failed: {mig_msg} ({mig_state})")
                checks["database"] = {
                    "status": "unhealthy",
                    "message": mig_msg,
                    "migration_state": mig_state,
                    "current_revisions": cur_revs,
                    "expected_heads": exp_heads,
                }
                is_ready = False
            else:
                # Check bootstrap user status if auth is disabled
                bootstrap_error = getattr(request.app.state, "bootstrap_error", None)
                if bootstrap_error:
                    logger.error(f"Readiness bootstrap error noted: {bootstrap_error}")
                    checks["database"] = {
                        "status": "unhealthy",
                        "message": "Default user bootstrap failed",
                        "migration_state": mig_state,
                        "current_revisions": cur_revs,
                        "expected_heads": exp_heads,
                    }
                    is_ready = False
                elif not settings.AUTH_ENABLED:
                    user = db.query(User).filter_by(email=settings.DEFAULT_USER_EMAIL.lower()).first()
                    if not user:
                        checks["database"] = {
                            "status": "unhealthy",
                            "message": "Default local user not found",
                            "migration_state": mig_state,
                            "current_revisions": cur_revs,
                            "expected_heads": exp_heads,
                        }
                        is_ready = False
                    else:
                        checks["database"] = {
                            "status": "healthy",
                            "message": "Connected and schema verified",
                            "migration_state": mig_state,
                            "current_revisions": cur_revs,
                            "expected_heads": exp_heads,
                        }
                else:
                    checks["database"] = {
                        "status": "healthy",
                        "message": "Connected and schema verified",
                        "migration_state": mig_state,
                        "current_revisions": cur_revs,
                        "expected_heads": exp_heads,
                    }
    except Exception as exc:
        logger.error(f"Readiness database check failed: {exc}", exc_info=True)
        checks["database"] = {
            "status": "unhealthy",
            "message": "Database connectivity or query failure",
        }
        is_ready = False

    # 2. Private Storage Directory Writable Verification (safe unique probe in injected settings.DATA_DIR)
    probe_file = settings.DATA_DIR / f".probe_{uuid.uuid4().hex[:8]}.tmp"
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(probe_file, "w", encoding="utf-8") as f:
            f.write("ok")
        checks["storage"] = {
            "status": "healthy",
            "message": "Storage directory writable",
        }
    except Exception as exc:
        logger.error(f"Readiness storage check failed: {exc}", exc_info=True)
        checks["storage"] = {
            "status": "unhealthy",
            "message": "Storage directory unwritable",
        }
        is_ready = False
    finally:
        if probe_file.exists():
            try:
                probe_file.unlink()
            except OSError:
                pass

    # 3. Generator Provider Configuration Check (truthful, unverified connectivity)
    if settings.GENERATOR_PROVIDER == "mock":
        checks["generator"]["configured"] = True
        checks["generator"]["connectivity"] = "unverified"
        checks["generator"]["status"] = "mock_configured_unverified"
        checks["generator"]["message"] = "Mock generator provider configured; live connectivity unverified"
    elif bool(settings.GENERATOR_API_KEY.strip()):
        checks["generator"]["configured"] = True
        checks["generator"]["connectivity"] = "unverified"
        checks["generator"]["status"] = "api_key_configured_unverified"
        checks["generator"]["message"] = "Provider API key configured; live connectivity unverified"
    else:
        checks["generator"]["configured"] = False
        checks["generator"]["connectivity"] = "unconfigured"
        checks["generator"]["status"] = "api_key_missing"
        checks["generator"]["message"] = "Provider API key not configured"

    # Set HTTP status: 200 if ready, 503 if degraded
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "degraded",
        "checks": checks,
    }


@router.get("/config/public")
def get_public_config(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
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
