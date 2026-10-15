from fastapi import Depends, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import User
from backend.app.db.session import get_db


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Dependency that resolves the active user.
    In local single-user mode (AUTH_ENABLED=false), returns the bootstrapped local user.
    If AUTH_ENABLED=true, fails explicitly with 501 Not Implemented to prevent
    inadvertent security downgrade or assumption of unverified auth.
    """
    if settings.AUTH_ENABLED:
        raise AppException(
            code=ErrorCode.NOT_IMPLEMENTED,
            message=(
                "Authentication is enabled in configuration, but JWT/multi-user provider "
                "is not implemented in this local release. Set AUTH_ENABLED=false for local mode."
            ),
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"auth_enabled": True},
        )

    return bootstrap_default_user(db)
