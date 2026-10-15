import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import Paper, User, Workspace


def test_create_user_and_workspace_and_paper(db_session):
    # 1. Create User
    user = User(
        email="researcher@university.edu",
        password_hash="test_hash_xyz",
        display_name="Dr. Jane Doe",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "researcher@university.edu"

    # 2. Create Workspace
    ws = Workspace(
        user_id=user.id,
        name="Quantum Computing",
        description="Literature review on quantum error correction.",
    )
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)

    assert ws.id is not None
    assert ws.user_id == user.id

    # 3. Create Paper
    paper = Paper(
        workspace_id=ws.id,
        original_filename="surface_codes_2024.pdf",
        storage_path="data/pdfs/sample_uuid.pdf",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        size_bytes=1048576,
        page_count=12,
        title="Fault-Tolerant Surface Codes",
        status="uploaded",
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    assert paper.id is not None
    assert paper.status == "uploaded"
    assert paper.size_bytes == 1048576


def test_unique_user_email(db_session):
    u1 = User(email="unique@test.org", password_hash="h1")
    db_session.add(u1)
    db_session.commit()

    u2 = User(email="unique@test.org", password_hash="h2")
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_workspace_name_per_user(db_session):
    u1 = User(email="user1@test.org", password_hash="h1")
    u2 = User(email="user2@test.org", password_hash="h2")
    db_session.add_all([u1, u2])
    db_session.commit()

    # User 1 creates workspace 'AI'
    ws1 = Workspace(user_id=u1.id, name="AI")
    db_session.add(ws1)
    db_session.commit()

    # User 2 can also create workspace 'AI' (different user)
    ws2_user2 = Workspace(user_id=u2.id, name="AI")
    db_session.add(ws2_user2)
    db_session.commit()

    # User 1 cannot duplicate workspace 'AI'
    ws1_dup = Workspace(user_id=u1.id, name="AI")
    db_session.add(ws1_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_paper_sha256_per_workspace(db_session):
    u = User(email="paper_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()

    ws1 = Workspace(user_id=u.id, name="WS1")
    ws2 = Workspace(user_id=u.id, name="WS2")
    db_session.add_all([ws1, ws2])
    db_session.commit()

    sha = "abc123def456" * 5

    p1 = Paper(
        workspace_id=ws1.id,
        original_filename="doc1.pdf",
        storage_path="path1.pdf",
        sha256=sha,
        size_bytes=5000,
    )
    db_session.add(p1)
    db_session.commit()

    # Same paper in different workspace is allowed
    p_other_ws = Paper(
        workspace_id=ws2.id,
        original_filename="doc1_copy.pdf",
        storage_path="path2.pdf",
        sha256=sha,
        size_bytes=5000,
    )
    db_session.add(p_other_ws)
    db_session.commit()

    # Duplicate upload in WS1 is rejected
    p_dup = Paper(
        workspace_id=ws1.id,
        original_filename="doc1_duplicate.pdf",
        storage_path="path3.pdf",
        sha256=sha,
        size_bytes=5000,
    )
    db_session.add(p_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete(db_session):
    u = User(email="cascade@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()

    ws = Workspace(user_id=u.id, name="Cascade WS")
    db_session.add(ws)
    db_session.commit()

    p = Paper(
        workspace_id=ws.id,
        original_filename="test.pdf",
        storage_path="path.pdf",
        sha256="sha_cascade_123",
        size_bytes=1000,
    )
    db_session.add(p)
    db_session.commit()

    # Verify entities exist
    assert db_session.query(Paper).filter(Paper.id == p.id).count() == 1

    # Deleting user must cascade-delete workspace and paper
    db_session.delete(u)
    db_session.commit()

    assert db_session.query(Workspace).filter(Workspace.id == ws.id).count() == 0
    assert db_session.query(Paper).filter(Paper.id == p.id).count() == 0


def test_foreign_key_enforcement(db_session):
    # Attempt to insert a workspace with a non-existent user_id
    invalid_ws = Workspace(user_id="non-existent-user-uuid", name="Orphaned")
    db_session.add(invalid_ws)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
