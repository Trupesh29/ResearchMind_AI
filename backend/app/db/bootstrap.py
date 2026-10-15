import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import User

logger = logging.getLogger("researchmind.bootstrap")


def bootstrap_default_user(db: Session) -> User:
    """
    Idempotent local user bootstrap:
    - Finds or creates the default local user configured in settings.
    - Repeated execution creates no duplicates and mutates no existing user data.
    - Uses a non-reversible dummy hash placeholder for the single-user local MVP.
    """
    stmt = select(User).where(User.email == settings.DEFAULT_USER_EMAIL.lower())
    existing_user = db.execute(stmt).scalar_one_or_none()

    if existing_user is not None:
        logger.debug(
            f"Default user '{existing_user.email}' already exists (id={existing_user.id})."
        )
        return existing_user

    # Generate a local dummy hash placeholder (never a plain shared password)
    dummy_hash = (
        "local_hash_"
        + hashlib.sha256(
            f"researchmind_local_{settings.DEFAULT_USER_EMAIL}".encode()
        ).hexdigest()
    )

    new_user = User(
        email=settings.DEFAULT_USER_EMAIL.lower(),
        password_hash=dummy_hash,
        display_name=settings.DEFAULT_USER_NAME,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(
        f"Bootstrapped default local user: '{new_user.email}' (id={new_user.id})."
    )
    return new_user
