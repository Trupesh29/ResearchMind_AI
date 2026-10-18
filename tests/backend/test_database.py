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
        # Earlier extraction job that produced the page:
        job0_id = str(uuid.uuid4())
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES (:id, :paper_id, :run_id, 'extracting', 'succeeded', 1, '2026-10-18T09:00:00+00:00')"
            ),
            {"id": job0_id, "paper_id": paper_id, "run_id": run_1},
        )
        # Duplicate active jobs for the same paper in a subsequent reprocess attempt
        run_2 = str(uuid.uuid4())
        job1_id = str(uuid.uuid4())
        job2_id = str(uuid.uuid4())
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES (:id, :paper_id, :run_id, 'validating', 'queued', 1, '2026-10-18T10:00:00+00:00')"
            ),
            {"id": job1_id, "paper_id": paper_id, "run_id": run_2},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES (:id, :paper_id, :run_id, 'validating', 'running', 2, '2026-10-18T10:05:00+00:00')"
            ),
            {"id": job2_id, "paper_id": paper_id, "run_id": run_2},
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

    # 3. Upgrade to head (0004 forward migration and 0005 repair)
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
        assert paper_row[0] == run_2  # Backfilled from active reprocess job
        assert paper_row[1] == run_1  # Backfilled from successful extraction job

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


def test_historical_generation_attribution_matrix(temp_test_dir):
    """
    Exhaustively verifies G1 generation attribution across the historical matrix:
    1. Successful A followed by failed B:
       - current_run_id = B, published_run_id = A, pages.run_id = A
       - get_paper_pages() returns is_stale=True and displays retained pages from A.
    2. Successful A followed by active B (queued/running):
       - current_run_id = B, published_run_id = A, pages.run_id = A.
    3. Ambiguous / missing extraction history:
       - pages exist, but no successful extracting jobs exist.
       - published_run_id is assigned a dedicated legacy run id, pages.run_id = legacy ID.
       - pages and records are preserved, not falsely claimed by a failed run.
    4. Competing runs (duplicate active jobs):
       - reconciled to exactly 1 active job, with current_run_id matching that active job.
    5. Forward-repair from already-applied 0004:
       - simulates a database where 0004 misattributed published_run_id to run-new.
       - 0005 upgrade repairs published_run_id and pages.run_id back to run-old.
    6. Clean install / empty database upgrade to head.
    """
    import subprocess
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from backend.app.services.processing_service import get_paper_pages

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    db_file = temp_test_dir / "migration_g1_matrix.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # Setup isolated migrations directory containing historical 0003
    hist_migrations = temp_test_dir / "test_migrations_g1"
    import shutil

    shutil.copytree(PROJECT_ROOT / "backend" / "migrations", hist_migrations)
    rev_0003 = "0003_add_processing_jobs_and_pages.py"
    original_0003 = subprocess.check_output(
        ["git", "show", f"2ef4ec2:backend/migrations/versions/{rev_0003}"],
        cwd=PROJECT_ROOT,
    )
    (hist_migrations / "versions" / rev_0003).write_bytes(original_0003)

    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(hist_migrations))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "0003_add_processing_jobs_and_pages")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    user_id = "user_g1"
    ws_id = "ws_g1"
    p1_id = "paper_succ_then_failed"
    p2_id = "paper_succ_then_active"
    p3_id = "paper_ambiguous"
    p4_id = "paper_competing"

    now = "2026-10-18T10:00:00+00:00"
    later = "2026-10-18T11:00:00+00:00"

    with SessionCls() as session:
        session.execute(
            text("INSERT INTO users (id, email, password_hash, created_at) VALUES (:u, 'g1@test.org', 'h', :now)"),
            {"u": user_id, "now": now},
        )
        session.execute(
            text("INSERT INTO workspaces (id, user_id, name, created_at) VALUES (:w, :u, 'G1 WS', :now)"),
            {"w": ws_id, "u": user_id, "now": now},
        )

        # 1. Paper 1: Successful A followed by failed B
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :w, 'p1.pdf', 'p1.pdf', 'sha1', 100, 'failed', :now, :later)"
            ),
            {"id": p1_id, "w": ws_id, "now": now, "later": later},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j1_old', :pid, 'run-A1', 'extracting', 'succeeded', 1, :now)"
            ),
            {"pid": p1_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j1_new', :pid, 'run-B1', 'extracting', 'failed', 1, :later)"
            ),
            {"pid": p1_id, "later": later},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('pg1', :pid, 1, 20, 'ok', '[]', 'Page text from run A1', :now)"
            ),
            {"pid": p1_id, "now": now},
        )

        # 2. Paper 2: Successful A followed by active B (running)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :w, 'p2.pdf', 'p2.pdf', 'sha2', 100, 'processing', :now, :later)"
            ),
            {"id": p2_id, "w": ws_id, "now": now, "later": later},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j2_old', :pid, 'run-A2', 'extracting', 'succeeded', 1, :now)"
            ),
            {"pid": p2_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j2_active', :pid, 'run-B2', 'validating', 'running', 1, :later)"
            ),
            {"pid": p2_id, "later": later},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('pg2', :pid, 1, 20, 'ok', '[]', 'Page text from run A2', :now)"
            ),
            {"pid": p2_id, "now": now},
        )

        # 3. Paper 3: Ambiguous / missing extraction history (pages exist, but only failed job recorded)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :w, 'p3.pdf', 'p3.pdf', 'sha3', 100, 'failed', :now, :now)"
            ),
            {"id": p3_id, "w": ws_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j3_fail', :pid, 'run-fail3', 'extracting', 'failed', 1, :now)"
            ),
            {"pid": p3_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('pg3', :pid, 1, 20, 'ok', '[]', 'Orphan page text', :now)"
            ),
            {"pid": p3_id, "now": now},
        )

        # 4. Paper 4: Competing runs (duplicate active jobs)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :w, 'p4.pdf', 'p4.pdf', 'sha4', 100, 'processing', :now, :now)"
            ),
            {"id": p4_id, "w": ws_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j4_1', :pid, 'run-comp1', 'validating', 'queued', 1, :now)"
            ),
            {"pid": p4_id, "now": now},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('j4_2', :pid, 'run-comp2', 'validating', 'running', 2, :later)"
            ),
            {"pid": p4_id, "later": later},
        )

        session.commit()

    engine.dispose()

    # Upgrade to head through 0004 and 0005
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    command.upgrade(cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    with SessionCls() as session:
        # 1. Paper 1 Verification:
        # current_run_id = run-B1 (failed attempt), published_run_id = run-A1, pages.run_id = run-A1
        p1_row = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"), {"id": p1_id}
        ).fetchone()
        assert p1_row[0] == "run-B1"
        assert p1_row[1] == "run-A1"
        pg1_row = session.execute(text("SELECT run_id FROM pages WHERE id = 'pg1'")).fetchone()
        assert pg1_row[0] == "run-A1"

        pages_result1 = get_paper_pages(session, user_id, p1_id)
        assert pages_result1.is_stale is True
        assert pages_result1.run_id == "run-A1"
        assert len(pages_result1.items) == 1
        pg1_text = session.execute(text("SELECT raw_text FROM pages WHERE id = 'pg1'")).scalar()
        assert pg1_text == "Page text from run A1"

        # 2. Paper 2 Verification:
        # current_run_id = run-B2 (active reprocess), published_run_id = run-A2, pages.run_id = run-A2
        p2_row = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"), {"id": p2_id}
        ).fetchone()
        assert p2_row[0] == "run-B2"
        assert p2_row[1] == "run-A2"
        pg2_row = session.execute(text("SELECT run_id FROM pages WHERE id = 'pg2'")).fetchone()
        assert pg2_row[0] == "run-A2"

        pages_result2 = get_paper_pages(session, user_id, p2_id)
        assert pages_result2.is_stale is True

        # 3. Paper 3 Verification:
        # Ambiguous history: pages preserved with isolated legacy run ID, not falsely tied to run-fail3
        p3_row = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"), {"id": p3_id}
        ).fetchone()
        assert p3_row[0] == "run-fail3"
        assert p3_row[1].startswith("legacy-")
        pg3_row = session.execute(text("SELECT run_id FROM pages WHERE id = 'pg3'")).fetchone()
        assert pg3_row[0] == p3_row[1]

        # 4. Paper 4 Verification:
        # Duplicate active jobs reconciled: j4_1 marked failed, j4_2 preserved as running
        j4_1_st = session.execute(text("SELECT status FROM processing_jobs WHERE id = 'j4_1'")).scalar()
        j4_2_st = session.execute(text("SELECT status FROM processing_jobs WHERE id = 'j4_2'")).scalar()
        assert j4_1_st == "failed"
        assert j4_2_st == "running"
        p4_row = session.execute(text("SELECT current_run_id FROM papers WHERE id = :id"), {"id": p4_id}).fetchone()
        assert p4_row[0] == "run-comp2"

    # 5. Forward-repair verification:
    # Downgrade to 0004, simulate misattributed published_run_id (as produced by buggy 0004),
    # then upgrade to 0005 to prove the forward repair corrects it:
    command.downgrade(cfg, "0004_add_generation_and_fencing_controls")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE papers SET published_run_id = 'run-B1' WHERE id = :id"),
            {"id": p1_id},
        )
        conn.execute(
            text("UPDATE pages SET run_id = 'run-B1' WHERE id = 'pg1'"),
        )
    command.upgrade(cfg, "0005_repair_historical_generation_attribution")

    with SessionCls() as session:
        repaired_p1 = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"), {"id": p1_id}
        ).fetchone()
        assert repaired_p1[0] == "run-B1"
        assert repaired_p1[1] == "run-A1"  # Repaired to successful run A1!
        repaired_pg1 = session.execute(text("SELECT run_id FROM pages WHERE id = 'pg1'")).fetchone()
        assert repaired_pg1[0] == "run-A1"  # Pages repaired to run A1!

    # 6. Advance to head (0006) and verify stability
    command.upgrade(cfg, "head")
    with SessionCls() as session:
        head_rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert head_rev == "0006_preserve_multirun_page_generations"
        final_p1 = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :id"), {"id": p1_id}
        ).fetchone()
        assert final_p1[0] == "run-B1"
        assert final_p1[1] == "run-A1"
        final_pg1 = session.execute(text("SELECT run_id FROM pages WHERE id = 'pg1'")).fetchone()
        assert final_pg1[0] == "run-A1"

    engine.dispose()


def test_multirun_page_generation_preservation_matrix(temp_test_dir):
    """
    Exhaustively verifies H1 multi-generation page preservation:
    1. Overlapping multi-generation pages:
       - Run A (succeeded) has page 1 with raw_text='Run A page 1'
       - Run B (succeeded) has page 1 with raw_text='Run B page 1'
       - Both rows survive unchanged with their respective run_ids and raw_texts.
       - published_run_id = 'run-B'. get_paper_pages() serves Run B page 1.
    2. Non-overlapping historical pages:
       - Run A has page 1, Run B has page 2.
       - Neither is relabeled. Run A retains page 1, Run B retains page 2.
       - get_paper_pages() serves Run B page 2.
    3. Active replacement run (successful A + running C):
       - current_run_id = 'run-C', published_run_id = 'run-A'.
       - get_paper_pages() serves Run A page 1 with is_stale=True.
    4. Failed replacement run (successful A + failed F):
       - current_run_id = 'run-F', published_run_id = 'run-A'.
       - get_paper_pages() serves Run A page 1 with is_stale=True.
    5. Ambiguous history (no successful extracting jobs):
       - Pages preserved under dedicated legacy ID without false claim by failed job.
    6. Unique constraint enforcement:
       - Attempting to insert duplicate (paper_id, run_id, page_number) raises IntegrityError.
    7. Forward compatibility:
       - Upgrading from 0004 directly to head (0006) succeeds cleanly.
       - Upgrading from already-applied 0005 to head (0006) succeeds cleanly.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    from backend.app.services.processing_service import get_paper_pages

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    db_file = temp_test_dir / "multirun_preservation.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Start at 0004 to create the exact multi-generation state
    command.upgrade(cfg, "0004_add_generation_and_fencing_controls")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    user_id = "user_multirun"
    ws_id = "ws_multirun"
    p_overlap_id = "p_overlap"
    p_nonov_id = "p_nonov"
    p_active_id = "p_active"
    p_failed_id = "p_failed"
    p_ambig_id = "p_ambig"

    t1 = "2026-10-18T10:00:00+00:00"
    t2 = "2026-10-18T11:00:00+00:00"
    t3 = "2026-10-18T12:00:00+00:00"

    with SessionCls() as session:
        session.execute(
            text("INSERT INTO users (id, email, password_hash, created_at) VALUES (:u, 'mr@test.org', 'h', :now)"),
            {"u": user_id, "now": t1},
        )
        session.execute(
            text("INSERT INTO workspaces (id, user_id, name, created_at) VALUES (:w, :u, 'MR WS', :now)"),
            {"w": ws_id, "u": user_id, "now": t1},
        )

        # Paper 1: Overlapping multi-generation (Run A page 1, Run B page 1)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, "
                "current_run_id, published_run_id, created_at, updated_at) "
                "VALUES (:id, :w, 'overlap.pdf', 'overlap.pdf', 'sha_ov', 100, 'processing', 'run-B', 'run-B', :t1, :t2)"
            ),
            {"id": p_overlap_id, "w": ws_id, "t1": t1, "t2": t2},
        )
        for r_id, r_time, p_text in [("run-A", t1, "Run A page 1 text"), ("run-B", t2, "Run B page 1 text")]:
            session.execute(
                text(
                    "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                    "VALUES (:jid, :pid, :rid, 'extracting', 'succeeded', 1, :tm)"
                ),
                {"jid": f"job-{r_id}", "pid": p_overlap_id, "rid": r_id, "tm": r_time},
            )
            session.execute(
                text(
                    "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                    "VALUES (:pgid, :pid, :rid, 1, 20, 'ok', '[]', :txt, :tm)"
                ),
                {"pgid": f"page-{r_id}", "pid": p_overlap_id, "rid": r_id, "txt": p_text, "tm": r_time},
            )

        # Paper 2: Non-overlapping multi-generation (Run A page 1, Run B page 2)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, "
                "current_run_id, published_run_id, created_at, updated_at) "
                "VALUES (:id, :w, 'nonov.pdf', 'nonov.pdf', 'sha_no', 100, 'processing', 'run-B-no', 'run-B-no', :t1, :t2)"
            ),
            {"id": p_nonov_id, "w": ws_id, "t1": t1, "t2": t2},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-A-no', :pid, 'run-A-no', 'extracting', 'succeeded', 1, :t1)"
            ),
            {"pid": p_nonov_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-B-no', :pid, 'run-B-no', 'extracting', 'succeeded', 1, :t2)"
            ),
            {"pid": p_nonov_id, "t2": t2},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('page-A-no', :pid, 'run-A-no', 1, 15, 'ok', '[]', 'Non-ov page 1', :t1)"
            ),
            {"pid": p_nonov_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('page-B-no', :pid, 'run-B-no', 2, 15, 'ok', '[]', 'Non-ov page 2', :t2)"
            ),
            {"pid": p_nonov_id, "t2": t2},
        )

        # Paper 3: Successful A + Active replacement run C (running)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, "
                "current_run_id, published_run_id, created_at, updated_at) "
                "VALUES (:id, :w, 'act.pdf', 'act.pdf', 'sha_act', 100, 'processing', 'run-C-act', 'run-A-act', :t1, :t3)"
            ),
            {"id": p_active_id, "w": ws_id, "t1": t1, "t3": t3},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-A-act', :pid, 'run-A-act', 'extracting', 'succeeded', 1, :t1)"
            ),
            {"pid": p_active_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-C-act', :pid, 'run-C-act', 'validating', 'running', 1, :t3)"
            ),
            {"pid": p_active_id, "t3": t3},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('page-A-act', :pid, 'run-A-act', 1, 15, 'ok', '[]', 'Active doc page 1', :t1)"
            ),
            {"pid": p_active_id, "t1": t1},
        )

        # Paper 4: Successful A + Failed replacement run F
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, "
                "current_run_id, published_run_id, created_at, updated_at) "
                "VALUES (:id, :w, 'fail.pdf', 'fail.pdf', 'sha_fail', 100, 'failed', 'run-F-fail', 'run-A-fail', :t1, :t3)"
            ),
            {"id": p_failed_id, "w": ws_id, "t1": t1, "t3": t3},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-A-fail', :pid, 'run-A-fail', 'extracting', 'succeeded', 1, :t1)"
            ),
            {"pid": p_failed_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-F-fail', :pid, 'run-F-fail', 'extracting', 'failed', 1, :t3)"
            ),
            {"pid": p_failed_id, "t3": t3},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('page-A-fail', :pid, 'run-A-fail', 1, 15, 'ok', '[]', 'Failed doc page 1', :t1)"
            ),
            {"pid": p_failed_id, "t1": t1},
        )

        # Paper 5: Ambiguous (no successful extracting jobs, pages exist)
        session.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, "
                "current_run_id, published_run_id, created_at, updated_at) "
                "VALUES (:id, :w, 'ambig.pdf', 'ambig.pdf', 'sha_amb', 100, 'failed', 'run-bad', 'run-bad', :t1, :t1)"
            ),
            {"id": p_ambig_id, "w": ws_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                "VALUES ('job-amb-bad', :pid, 'run-bad', 'extracting', 'failed', 1, :t1)"
            ),
            {"pid": p_ambig_id, "t1": t1},
        )
        session.execute(
            text(
                "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                "VALUES ('page-amb', :pid, 'run-bad', 1, 15, 'ok', '[]', 'Ambiguous page 1', :t1)"
            ),
            {"pid": p_ambig_id, "t1": t1},
        )

        session.commit()

    engine.dispose()

    # 2. Upgrade to head (0004 -> 0005 -> 0006)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionCls = sessionmaker(bind=engine)

    with SessionCls() as session:
        # Check revision advanced to 0006
        rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0006_preserve_multirun_page_generations"

        # Verification 1: Overlapping multi-generation pages survive!
        ov_pages = session.execute(
            text("SELECT id, run_id, page_number, raw_text FROM pages WHERE paper_id = :pid ORDER BY id"),
            {"pid": p_overlap_id},
        ).fetchall()
        assert len(ov_pages) == 2
        assert ov_pages[0] == ("page-run-A", "run-A", 1, "Run A page 1 text")
        assert ov_pages[1] == ("page-run-B", "run-B", 1, "Run B page 1 text")

        ov_paper = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :pid"),
            {"pid": p_overlap_id},
        ).fetchone()
        assert ov_paper[0] == "run-B"
        assert ov_paper[1] == "run-B"

        ov_view = get_paper_pages(session, user_id, p_overlap_id)
        assert ov_view.run_id == "run-B"
        assert ov_view.is_stale is False
        assert len(ov_view.items) == 1
        assert ov_view.items[0].page_number == 1

        # Verification 2: Non-overlapping historical pages survive without silent relabeling!
        no_pages = session.execute(
            text("SELECT id, run_id, page_number, raw_text FROM pages WHERE paper_id = :pid ORDER BY id"),
            {"pid": p_nonov_id},
        ).fetchall()
        assert len(no_pages) == 2
        assert no_pages[0] == ("page-A-no", "run-A-no", 1, "Non-ov page 1")
        assert no_pages[1] == ("page-B-no", "run-B-no", 2, "Non-ov page 2")

        no_view = get_paper_pages(session, user_id, p_nonov_id)
        assert no_view.run_id == "run-B-no"
        assert len(no_view.items) == 1
        assert no_view.items[0].page_number == 2

        # Verification 3: Active replacement run
        act_paper = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :pid"),
            {"pid": p_active_id},
        ).fetchone()
        assert act_paper[0] == "run-C-act"
        assert act_paper[1] == "run-A-act"
        act_view = get_paper_pages(session, user_id, p_active_id)
        assert act_view.is_stale is True
        assert act_view.run_id == "run-A-act"

        # Verification 4: Failed replacement run
        fail_paper = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :pid"),
            {"pid": p_failed_id},
        ).fetchone()
        assert fail_paper[0] == "run-F-fail"
        assert fail_paper[1] == "run-A-fail"
        fail_view = get_paper_pages(session, user_id, p_failed_id)
        assert fail_view.is_stale is True
        assert fail_view.run_id == "run-A-fail"

        # Verification 5: Ambiguous history preserved under legacy run ID
        amb_paper = session.execute(
            text("SELECT current_run_id, published_run_id FROM papers WHERE id = :pid"),
            {"pid": p_ambig_id},
        ).fetchone()
        assert amb_paper[0] == "run-bad"
        assert amb_paper[1].startswith("legacy-")
        amb_pg = session.execute(text("SELECT run_id FROM pages WHERE id = 'page-amb'")).scalar()
        assert amb_pg == amb_paper[1]

        # Verification 6: Unique constraint (paper_id, run_id, page_number) is actively enforced
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO pages (id, paper_id, run_id, page_number, char_count, extraction_status, flags_json, raw_text, created_at) "
                    "VALUES ('dup-pg', :pid, 'run-B', 1, 10, 'ok', '[]', 'Dup', :t2)"
                ),
                {"pid": p_overlap_id, "t2": t2},
            )
            session.commit()
        session.rollback()

    # 3. Test downgrade to 0005, then upgrade to 0006 (simulates database already applied 0005)
    command.downgrade(cfg, "0005_repair_historical_generation_attribution")
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0005_repair_historical_generation_attribution"
        )
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0006_preserve_multirun_page_generations"
        )

    engine.dispose()


def test_clean_install_and_already_0005_upgrade(temp_test_dir):
    """Verifies clean install directly to head and idempotence of 0006 on already-0005 databases."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    db_file = temp_test_dir / "clean_install.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Clean install to head
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.connect() as c:
        rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0006_preserve_multirun_page_generations"

    # 2. Downgrade to 0005 and upgrade back to head
    command.downgrade(cfg, "0005_repair_historical_generation_attribution")
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0005_repair_historical_generation_attribution"
        )
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0006_preserve_multirun_page_generations"
        )

    engine.dispose()
