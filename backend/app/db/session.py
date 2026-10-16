from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

# Engine configuration
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG and False,  # Keep logs clean unless debugging queries
    future=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Ensure SQLite enables foreign key enforcement, WAL mode, and busy timeout.
    """
    if hasattr(dbapi_connection, "cursor"):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_session_factory = SessionLocal


def set_session_factory(factory) -> None:
    """
    Allows injecting an isolated session factory (e.g. for testing).
    """
    global _session_factory
    _session_factory = factory


def get_session_factory():
    """
    Returns the current active session factory.
    """
    return _session_factory


def get_db(request: Request = None) -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a transactional database session.
    Prioritizes session factory configured on app.state, then injected factory,
    then global SessionLocal.
    """
    factory = None
    if request is not None and hasattr(request, "app"):
        factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        factory = get_session_factory()

    db = factory()
    try:
        yield db
    finally:
        db.close()
