import pytest

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import User


def test_bootstrap_idempotency(db_session):
    # First execution creates the default user
    u1 = bootstrap_default_user(db_session)
    assert u1 is not None
    assert u1.email == settings.DEFAULT_USER_EMAIL.lower()
    user_id = u1.id

    # Second execution returns the exact same user
    u2 = bootstrap_default_user(db_session)
    assert u2.id == user_id

    # Verify database has exactly 1 user
    total_users = db_session.query(User).count()
    assert total_users == 1


def test_bootstrap_preserves_existing_user_data(db_session):
    u = bootstrap_default_user(db_session)
    # Manually update display name
    u.display_name = "Custom Research Lead"
    db_session.commit()

    # Re-run bootstrap
    u_after = bootstrap_default_user(db_session)
    assert u_after.display_name == "Custom Research Lead"


def test_get_current_user_local_mode(db_session):
    # In local mode (AUTH_ENABLED=False), get_current_user returns default local user
    settings.AUTH_ENABLED = False
    current_user = get_current_user(db=db_session)
    assert current_user.email == settings.DEFAULT_USER_EMAIL.lower()


def test_get_current_user_auth_enabled_fails_explicitly(db_session):
    # When AUTH_ENABLED=True without JWT implemented, must fail with 501
    settings.AUTH_ENABLED = True
    try:
        with pytest.raises(AppException) as exc_info:
            get_current_user(db=db_session)
        assert exc_info.value.code == ErrorCode.NOT_IMPLEMENTED
        assert exc_info.value.status_code == 501
    finally:
        # Reset to default
        settings.AUTH_ENABLED = False
