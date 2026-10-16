import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.router import api_router
from backend.app.core.config import ensure_data_directories, settings
from backend.app.core.errors import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from backend.app.core.logging import setup_logging
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.session import SessionLocal

# Setup structured logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("researchmind.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager:
    - Runs on server startup and shutdown.
    - Ensures storage directories exist.
    - Idempotently bootstraps the default local user.
    """
    effective_settings = getattr(app.state, "settings", None) or settings
    ensure_data_directories(effective_settings.DATA_DIR)

    logger.info(
        f"Starting {effective_settings.PROJECT_NAME} v{effective_settings.VERSION} [{effective_settings.APP_ENV}]"
    )
    logger.info(f"Storage directory: {effective_settings.DATA_DIR.resolve()}")
    logger.info(f"Database URL: {effective_settings.DATABASE_URL}")

    # Bootstrap local default user
    session_factory = getattr(app.state, "session_factory", None) or SessionLocal
    try:
        with session_factory() as db:
            user = bootstrap_default_user(db)
            logger.info(f"Active local user ready: {user.email}")
            app.state.bootstrap_error = None
    except Exception as exc:
        app.state.bootstrap_error = str(exc)
        logger.error(f"Error during local user bootstrap: {exc}")

    yield

    logger.info(f"Shutting down {effective_settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Evidence-first universal research document analyzer API",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# 1. Request ID and Timing Middleware
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    # Retrieve or generate standard request ID
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:10]}"
    request.state.request_id = request_id

    start_time = time.perf_counter()
    logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={"request_id": request_id},
    )

    response: Response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    logger.info(
        f"Completed {request.method} {request.url.path} with status {response.status_code} in {duration_ms:.2f}ms",
        extra={"request_id": request_id},
    )
    return response


# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
)

# 3. Centralized Exception Handlers (API_SPEC.md envelope format)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 4. API Routes
app.include_router(api_router, prefix=settings.API_V1_STR)


# Direct root health endpoint convenience alias
@app.get("/health", include_in_schema=False)
def root_health():
    return {"status": "ok"}
