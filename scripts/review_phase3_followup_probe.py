"""Disposable diagnostics for bd78083; printed observations are not acceptance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import shutil
import subprocess
import tempfile

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text, update
from sqlalchemy.orm import sessionmaker

from backend.app.api.deps import get_current_user
from backend.app.db.base import Base
from backend.app.db.models import Paper, ProcessingJob, User, Workspace, utcnow_iso
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.schemas.paper import PaperResponse
from backend.app.services import processing_service
from worker.engine import WorkerEngine, sanitize_error_message

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    tmp = Path(tmp)
    historical = tmp / "migrations"
    shutil.copytree(root / "backend/migrations", historical)
    revision_file = "0003_add_processing_jobs_and_pages.py"
    original = subprocess.check_output(
        ["git", "show", f"2ef4ec2:backend/migrations/versions/{revision_file}"], cwd=root
    )
    (historical / "versions" / revision_file).write_bytes(original)
    url = "sqlite:///" + (tmp / "upgrade.db").as_posix()
    cfg = Config(str(root / "backend/alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(historical))
    command.upgrade(cfg, "head")
    cfg.set_main_option("script_location", str(root / "backend/migrations"))
    command.upgrade(cfg, "head")
    old_engine = create_engine(url)
    print("UPGRADE_HAS_CURRENT_RUN", "current_run_id" in {c["name"] for c in inspect(old_engine).get_columns("papers")})
    with old_engine.connect() as c:
        print("UPGRADE_REVISION", c.execute(text("select version_num from alembic_version")).scalar())
    old_engine.dispose()

    engine = create_engine("sqlite:///" + (tmp / "probe.db").as_posix())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id="u", email="probe@example.test", password_hash="unused"))
        db.flush()
        db.add(Workspace(id="w", user_id="u", name="Probe"))
        db.flush()
        p = Paper(
            id="p",
            workspace_id="w",
            original_filename="probe.pdf",
            storage_path="probe.pdf",
            sha256="a" * 64,
            size_bytes=10,
            status="processing",
            current_run_id="run",
        )
        p.metadata_source_json = json.dumps({"title": {"source": "pdf", "evidence": "A title"}})
        db.add(p)
        db.flush()
        db.add(
            ProcessingJob(
                id="job",
                paper_id="p",
                run_id="run",
                stage="extracting",
                status="running",
                attempt=1,
                claim_token="token",
                heartbeat_at="2000-01-01T00:00:00+00:00",
            )
        )
        db.commit()
        try:
            PaperResponse.model_validate(p)
            print("STRUCTURED_PROVENANCE_SERIALIZES", True)
        except Exception as exc:
            print("STRUCTURED_PROVENANCE_SERIALIZES", False, type(exc).__name__)

    def probe_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = probe_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u", email="probe@example.test", password_hash="unused"
    )
    try:
        client = TestClient(app, raise_server_exceptions=False)
        print("PAPER_HTTP_STATUS", client.get("/api/papers/p").status_code)
        print("LIBRARY_HTTP_STATUS", client.get("/api/papers?workspace_id=w").status_code)
        client.close()
    finally:
        app.dependency_overrides.clear()

    refreshed = False

    def refresh_after_selection(conn, cursor, statement, parameters, context, executemany):
        global refreshed
        if statement.startswith("UPDATE processing_jobs SET") and not refreshed:
            refreshed = True
            with factory() as live:
                live.execute(update(ProcessingJob).where(ProcessingJob.id == "job").values(heartbeat_at=utcnow_iso()))
                live.commit()

    event.listen(engine, "before_cursor_execute", refresh_after_selection)
    with factory() as db:
        WorkerEngine()._recover_expired_leases(db)
    event.remove(engine, "before_cursor_execute", refresh_after_selection)
    with factory() as db:
        jobs = db.query(ProcessingJob).order_by(ProcessingJob.attempt).all()
        print("REFRESHED_LEASE_RECOVERY", [(j.attempt, j.status) for j in jobs])
        jobs[-1].status = "succeeded"
        db.commit()
        status = processing_service.get_paper_status_details(db, "u", "p")
        print("SUCCESS_AFTER_RETRY_PUBLIC_STATUS", status.status, status.attempt, status.error)
    print(
        "UNKNOWN_ERROR_SANITIZED", sanitize_error_message("parser failed at F:/private/paper.pdf; token=example-secret")
    )
    engine.dispose()
