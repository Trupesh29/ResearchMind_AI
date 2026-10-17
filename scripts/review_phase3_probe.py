import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import fitz
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import Paper, ProcessingJob, User, Workspace
from backend.app.services import extraction_service, processing_service
from worker.engine import WorkerEngine

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    engine = create_engine("sqlite:///" + str(Path(tmp) / "probe.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id="u", email="probe@example.test", display_name="Probe", password_hash="unused"))
        db.flush()
        db.add(Workspace(id="w", user_id="u", name="Probe"))
        db.flush()
        db.add(
            Paper(
                id="p",
                workspace_id="w",
                original_filename="probe.pdf",
                storage_path=str(Path(tmp) / "missing.pdf"),
                sha256="a" * 64,
                size_bytes=10,
                status="uploaded",
            )
        )
        db.flush()
        processing_service.enqueue_validation_job(db, "p")
        db.commit()
    barrier = threading.Barrier(2)

    def sync_claim(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE processing_jobs SET"):
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", sync_claim)

    def claim(name):
        with factory() as db:
            return WorkerEngine(worker_id=name)._claim_next_job(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["one", "two"]))
    event.remove(engine, "before_cursor_execute", sync_claim)
    print(
        "CLAIM_WINNERS",
        len([r for r in results if r]),
        "DISTINCT_TOKENS",
        len({r["claim_token"] for r in results if r}),
    )
    with factory() as db:
        db.query(ProcessingJob).delete()
        db.commit()
    barrier = threading.Barrier(2)

    def sync_reprocess(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE papers SET"):
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", sync_reprocess)

    def reprocess(_):
        with factory() as db:
            return processing_service.request_reprocess(db, "u", "p").status

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(reprocess, [1, 2]))
    event.remove(engine, "before_cursor_execute", sync_reprocess)
    with factory() as db:
        print("REPROCESS_ACCEPTED", result, "ACTIVE_RUNS", db.query(ProcessingJob).count())
        db.query(ProcessingJob).delete()
        processing_service.enqueue_validation_job(db, "p")
        db.commit()
        info = WorkerEngine()._claim_next_job(db)
    with patch("worker.engine.get_session_factory", return_value=factory):
        WorkerEngine()._handle_validating_stage(info)
    with factory() as db:
        result = processing_service.get_paper_status_details(db, "u", "p")
        print("PUBLIC_ERROR", result.error)
    pdf = Path(tmp) / "rotated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 700), "Body near lower edge, outside rotated height")
    page.set_rotation(90)
    doc.save(pdf)
    doc.close()
    result = extraction_service.extract_pdf(str(pdf))
    page = result.pages[0]
    print("ROTATION", page.rotation, "SIZE", page.width, page.height, "BBOX", page.blocks[0].bbox)
    engine.dispose()
