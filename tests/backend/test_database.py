import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import Paper, User, Workspace, utcnow_iso


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


def test_paper_status_check_constraint_valid(db_session):
    u = User(email="paper_status_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(user_id=u.id, name="Status WS")
    db_session.add(ws)
    db_session.commit()

    valid_statuses = ["uploaded", "processing", "ready", "failed"]
    for idx, st in enumerate(valid_statuses):
        p = Paper(
            workspace_id=ws.id,
            original_filename=f"doc_{idx}.pdf",
            storage_path=f"path_{idx}.pdf",
            sha256=f"sha_valid_{idx}_{st}" * 3,
            size_bytes=1024,
            status=st,
        )
        db_session.add(p)
    db_session.commit()


def test_paper_status_check_constraint_invalid(db_session):
    u = User(email="invalid_status_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(user_id=u.id, name="Invalid Status WS")
    db_session.add(ws)
    db_session.commit()

    p = Paper(
        workspace_id=ws.id,
        original_filename="bad_status.pdf",
        storage_path="bad_path.pdf",
        sha256="sha_bad_status_1234567890",
        size_bytes=1024,
        status="non_existent_status",
    )
    db_session.add(p)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_paper_size_bytes_check_constraint(db_session):
    u = User(email="bad_size_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(user_id=u.id, name="Bad Size WS")
    db_session.add(ws)
    db_session.commit()

    p = Paper(
        workspace_id=ws.id,
        original_filename="zero_size.pdf",
        storage_path="zero_path.pdf",
        sha256="sha_zero_size_1234567890",
        size_bytes=0,
        status="uploaded",
    )
    db_session.add(p)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_paper_page_count_check_constraint(db_session):
    u = User(email="page_count_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(user_id=u.id, name="Page Count WS")
    db_session.add(ws)
    db_session.commit()

    # Valid with None
    p_none = Paper(
        workspace_id=ws.id,
        original_filename="none_pages.pdf",
        storage_path="p1.pdf",
        sha256="sha_page_none_12345",
        size_bytes=1024,
        page_count=None,
        status="uploaded",
    )
    db_session.add(p_none)
    db_session.commit()

    # Valid with positive int
    p_pos = Paper(
        workspace_id=ws.id,
        original_filename="pos_pages.pdf",
        storage_path="p2.pdf",
        sha256="sha_page_pos_12345",
        size_bytes=1024,
        page_count=15,
        status="uploaded",
    )
    db_session.add(p_pos)
    db_session.commit()

    # Invalid with 0
    p_zero = Paper(
        workspace_id=ws.id,
        original_filename="zero_pages.pdf",
        storage_path="p3.pdf",
        sha256="sha_page_zero_12345",
        size_bytes=1024,
        page_count=0,
        status="uploaded",
    )
    db_session.add(p_zero)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_paper_publication_year_check_constraint(db_session):
    u = User(email="year_user@test.org", password_hash="h1")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(user_id=u.id, name="Year WS")
    db_session.add(ws)
    db_session.commit()

    # Valid: None
    p_none = Paper(
        workspace_id=ws.id,
        original_filename="none_year.pdf",
        storage_path="py1.pdf",
        sha256="sha_year_none_12345",
        size_bytes=1024,
        publication_year=None,
        status="uploaded",
    )
    db_session.add(p_none)
    db_session.commit()

    # Valid: 2024
    p_valid = Paper(
        workspace_id=ws.id,
        original_filename="valid_year.pdf",
        storage_path="py2.pdf",
        sha256="sha_year_valid_12345",
        size_bytes=1024,
        publication_year=2024,
        status="uploaded",
    )
    db_session.add(p_valid)
    db_session.commit()

    # Invalid: < 1900
    p_too_early = Paper(
        workspace_id=ws.id,
        original_filename="early_year.pdf",
        storage_path="py3.pdf",
        sha256="sha_year_early_12345",
        size_bytes=1024,
        publication_year=1850,
        status="uploaded",
    )
    db_session.add(p_too_early)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid: > 2100
    p_too_late = Paper(
        workspace_id=ws.id,
        original_filename="late_year.pdf",
        storage_path="py4.pdf",
        sha256="sha_year_late_12345",
        size_bytes=1024,
        publication_year=2150,
        status="uploaded",
    )
    db_session.add(p_too_late)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_alembic_schema_drift_regression(isolated_env):
    """
    Compares the migrated database schema with declared ORM metadata.
    Enables compare_type=True and compare_server_default=True to verify
    zero schema differences across tables, columns, types, and server defaults.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from backend.app.db.base import Base

    engine = isolated_env["engine"]
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
            },
        )
        diff = compare_metadata(context, Base.metadata)
        assert len(diff) == 0, f"Detected schema differences against Base.metadata: {diff}"


def test_upgrade_populated_database_preserves_records(temp_test_dir):
    """
    Verifies upgrade of a database populated at 0001_initial_core_schema
    to head (0002_add_paper_check_constraints) preserves all existing records
    and enforces check constraints on subsequent inserts.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    db_file = temp_test_dir / "migration_upgrade_populated_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Migrate only to 0001_initial_core_schema
    command.upgrade(alembic_cfg, "0001_initial_core_schema")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    # 2. Insert records into 0001 schema
    with SessionCls() as session:
        user = User(
            email="historical@test.org",
            password_hash="h1",
            display_name="Historical Researcher",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        ws = Workspace(user_id=user.id, name="Historical WS")
        session.add(ws)
        session.commit()
        session.refresh(ws)

        paper_id = str(uuid.uuid4())
        now = utcnow_iso()
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, publication_year, status, created_at, updated_at) "
                "VALUES (:id, :workspace_id, :original_filename, :storage_path, :sha256, :size_bytes, :publication_year, :status, :created_at, :updated_at)"
            ),
            {
                "id": paper_id,
                "workspace_id": ws.id,
                "original_filename": "historical_paper.pdf",
                "storage_path": "path/to/historical.pdf",
                "sha256": "sha_hist_1234567890",
                "size_bytes": 2048,
                "publication_year": 2021,
                "status": "uploaded",
                "created_at": now,
                "updated_at": now,
            },
        )
        session.commit()

    # 3. Upgrade to head (0002_add_paper_check_constraints)
    command.upgrade(alembic_cfg, "head")

    # 4. Verify existing records are preserved intact after batch recreation
    with SessionCls() as session:
        u = session.query(User).filter_by(email="historical@test.org").first()
        assert u is not None
        assert u.display_name == "Historical Researcher"

        w = session.query(Workspace).filter_by(user_id=u.id).first()
        assert w is not None
        assert w.name == "Historical WS"

        p = session.query(Paper).filter_by(workspace_id=w.id).first()
        assert p is not None
        assert p.original_filename == "historical_paper.pdf"
        assert p.status == "uploaded"
        assert p.size_bytes == 2048

        # 5. Verify check constraints from 0002 are now enforced on new inserts
        invalid_paper = Paper(
            workspace_id=w.id,
            original_filename="invalid_negative.pdf",
            storage_path="path/to/inv.pdf",
            sha256="sha_inv_999",
            size_bytes=-100,
            status="uploaded",
        )
        session.add(invalid_paper)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    engine.dispose()


def test_migration_0003_to_0004_data_preservation_and_reconciliation(temp_test_dir):
    """
    Verifies upgrade of a database at historical 0003_add_processing_jobs_and_pages
    (from 2ef4ec2) to head (0004_add_generation_and_fencing_controls):
    - papers.current_run_id and published_run_id are backfilled consistently
    - pages.run_id is backfilled
    - duplicate active jobs are reconciled to exactly 1 active job before partial unique index
    - unique constraints and indexes are enforced
    - downgrade to 0003 functions cleanly
    """
    import shutil
    import subprocess
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    db_file = temp_test_dir / "migration_0003_0004_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # Setup isolated migrations directory containing historical 0003
    hist_migrations = temp_test_dir / "test_migrations"
    shutil.copytree(PROJECT_ROOT / "backend" / "migrations", hist_migrations)
    rev_0003 = "0003_add_processing_jobs_and_pages.py"
    original_0003 = subprocess.check_output(
        ["git", "show", f"2ef4ec2:backend/migrations/versions/{rev_0003}"],
        cwd=PROJECT_ROOT,
    )
    (hist_migrations / "versions" / rev_0003).write_bytes(original_0003)

    # 1. Migrate to historical 0003 (before 0004 existed)
    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(hist_migrations))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "0003_add_processing_jobs_and_pages")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    # 2. Insert pre-existing records: paper with duplicate active jobs and page without run_id
    paper_id = str(uuid.uuid4())
    run_1 = str(uuid.uuid4())
    now = utcnow_iso()
    with SessionCls() as session:
        user = User(email="hist_p3@test.org", password_hash="h1", display_name="Hist P3")
        session.add(user)
        session.commit()
        session.refresh(user)

        ws = Workspace(user_id=user.id, name="Hist P3 WS")
        session.add(ws)
        session.commit()
        session.refresh(ws)

        # Paper in historical 0003 schema (no current_run_id column yet)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :ws_id, 'hist.pdf', 'hist.pdf', 'hist_sha_123', 500, 'processing', :now, :now)"
            ),
            {"id": paper_id, "ws_id": ws.id, "now": now},
        )
        # Duplicate active jobs for the same paper (allowed in 0003)
        job1_id = str(uuid.uuid4())
        job2_id = str(uuid.uuid4())
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES (:id, :paper_id, :run_id, 'validating', 'queued', 1, '2026-10-18T10:00:00+00:00')"
            ),
            {"id": job1_id, "paper_id": paper_id, "run_id": run_1},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES (:id, :paper_id, :run_id, 'validating', 'running', 2, '2026-10-18T10:05:00+00:00')"
            ),
            {"id": job2_id, "paper_id": paper_id, "run_id": run_1},
        )
        # Page in historical 0003 schema (had paper_id, page_number, but NO run_id)
        page1_id = str(uuid.uuid4())
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, page_number, char_count, extraction_status, flags_json, created_at) "
                "VALUES (:id, :paper_id, 1, 100, 'ok', '[]', :now)"
            ),
            {"id": page1_id, "paper_id": paper_id, "now": now},
        )
        session.commit()

    engine.dispose()

    # 3. Upgrade to head (0004 forward migration)
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    command.upgrade(cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    # 4. Verify data preservation and backfilling
    with SessionCls() as session:
        # Check papers columns
        cols = {c["name"] for c in inspect(engine).get_columns("papers")}
        assert "current_run_id" in cols
        assert "published_run_id" in cols

        paper_row = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"),
            {"id": paper_id},
        ).fetchone()
        assert paper_row[0] == run_1  # Backfilled from jobs
        assert paper_row[1] == run_1  # Backfilled from pages

        # Check pages run_id
        page_cols = {c["name"] for c in inspect(engine).get_columns("pages")}
        assert "run_id" in page_cols
        page_row = session.execute(
            text("SELECT run_id FROM pages WHERE id = :id"),
            {"id": page1_id},
        ).fetchone()
        assert page_row[0] == run_1

        # Check duplicate active jobs reconciliation:
        # job1 (older) marked failed, job2 (newer) remained running
        j1 = session.execute(text("SELECT status FROM processing_jobs WHERE id = :id"), {"id": job1_id}).fetchone()
        j2 = session.execute(text("SELECT status FROM processing_jobs WHERE id = :id"), {"id": job2_id}).fetchone()
        assert j1[0] == "failed"
        assert j2[0] == "running"

        # Check partial unique index: cannot insert another active job for this paper
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                    "VALUES (:id, :paper_id, 'run_dup', 'validating', 'queued', 1, :now)"
                ),
                {"id": str(uuid.uuid4()), "paper_id": paper_id, "now": now},
            )
            session.commit()
        session.rollback()

    # 5. Verify downgrade to 0003 works cleanly
    command.downgrade(cfg, "0003_add_processing_jobs_and_pages")
    with engine.connect() as c:
        rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0003_add_processing_jobs_and_pages"

    engine.dispose()
