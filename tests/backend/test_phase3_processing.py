"""ResearchMind AI — Phase 3 Persistent Processing & Extraction Test Suite.

Verifies:
- Alembic migration 0003 integrity, Week 1 data preservation, FK cascades
- PyMuPDF extraction: dimensions, rotation, coordinates, multi-column, metadata provenance
- Quality heuristics: scan-like, table-heavy, equation-heavy, all-image failure
- Worker concurrency: atomic claims, lease expiry recovery, fencing token protection
- Reprocess lifecycle: 409 conflict on active jobs, 202 on accepted reprocess
- Deletion safety: in-flight worker publication drops results cleanly without resurrecting records
- Security & ownership: foreign caller rejection, no path or secret leaks
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import unittest.mock
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generator

import fitz  # PyMuPDF
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.core.errors import AppException
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import Page, Paper, ProcessingJob, User, Workspace, utcnow_iso
from backend.app.db.session import set_session_factory
from backend.app.main import app
from backend.app.services import extraction_service, processing_service
from worker.engine import WorkerEngine, WorkerFencingViolation


@pytest.fixture
def p3_env(temp_test_dir: Path) -> Generator[dict, None, None]:
    """Provides isolated storage and database migrated to head (0003)."""
    run_id = os.urandom(6).hex()
    test_dir = temp_test_dir / f"p3_{run_id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["pdfs", "indexes", "models", "reports", ".trash"]:
        (test_dir / sub).mkdir(parents=True, exist_ok=True)

    db_path = test_dir / "test_p3.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "backend" / "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent.parent.parent / "backend" / "migrations"),
    )
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
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

    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    set_session_factory(factory)

    test_settings = Settings(
        DATA_DIR=test_dir,
        DATABASE_URL=db_url,
        AUTH_ENABLED=False,
        DISPOSABLE_TEST_ENV=True,
    )

    db: Session = factory()
    try:
        user = bootstrap_default_user(db, test_settings)
        ws = Workspace(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Phase 3 Test Workspace",
            description="Testing persistent processing slice",
        )
        db.add(ws)
        db.commit()
        db.refresh(user)
        db.refresh(ws)
        user_id = user.id
        workspace_id = ws.id
    finally:
        db.close()

    app.state.settings = test_settings
    app.state.session_factory = factory

    client = TestClient(app)

    yield {
        "data_dir": test_dir,
        "db_url": db_url,
        "factory": factory,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "client": client,
        "settings": test_settings,
        "alembic_cfg": alembic_cfg,
    }

    set_session_factory(None)
    if hasattr(app.state, "settings"):
        delattr(app.state, "settings")
    if hasattr(app.state, "session_factory"):
        delattr(app.state, "session_factory")


def _create_synthetic_pdf(
    file_path: Path,
    pages_spec: list[dict],
    metadata: dict | None = None,
) -> str:
    """Helper creating a synthetic multi-page PDF with specific layouts and text."""
    doc = fitz.open()
    for spec in pages_spec:
        page = doc.new_page(width=spec.get("width", 612), height=spec.get("height", 792))
        if spec.get("rotation"):
            page.set_rotation(spec["rotation"])

        # Insert text blocks
        for block in spec.get("blocks", []):
            rect = fitz.Rect(block["rect"])
            page.insert_textbox(rect, block["text"], fontsize=block.get("fontsize", 11))

        # Insert images if requested
        if spec.get("draw_image"):
            # Create a 50x50 dummy pixmap
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), 0)
            pix.clear_with(200)
            img_rect = fitz.Rect(100, 100, 200, 200)
            page.insert_image(img_rect, pixmap=pix)

    if metadata:
        doc.set_metadata(metadata)

    doc.save(str(file_path))
    doc.close()

    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ==============================================================================
# 1. Migration Tests
# ==============================================================================


def test_phase3_migrations_preserve_data_and_schema(temp_test_dir: Path):
    """Verify upgrading from 0002 to 0003 preserves Week 1 papers and cascades cleanly."""
    db_file = temp_test_dir / "migration_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "backend" / "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent.parent.parent / "backend" / "migrations"),
    )
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Step A: Upgrade to 0002 (Week 1 schema)
    command.upgrade(alembic_cfg, "0002_add_paper_check_constraints")

    engine = create_engine(db_url, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def pragma(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    session_maker = sessionmaker(bind=engine)
    db = session_maker()

    # Insert Week 1 user, workspace, and paper
    user_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    paper_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES (:id, :email, :password_hash, :created_at)"
            ),
            {"id": user_id, "email": "w1@example.com", "password_hash": "hash", "created_at": utcnow_iso()},
        )
        conn.execute(
            text("INSERT INTO workspaces (id, user_id, name, created_at) VALUES (:id, :user_id, :name, :created_at)"),
            {"id": ws_id, "user_id": user_id, "name": "W1 Workspace", "created_at": utcnow_iso()},
        )
        conn.execute(
            text(
                "INSERT INTO papers (id, workspace_id, original_filename, storage_path, sha256, size_bytes, status, created_at, updated_at) "
                "VALUES (:id, :workspace_id, :original_filename, :storage_path, :sha256, :size_bytes, :status, :created_at, :updated_at)"
            ),
            {
                "id": paper_id,
                "workspace_id": ws_id,
                "original_filename": "week1.pdf",
                "storage_path": f"data/pdfs/{paper_id}.pdf",
                "sha256": "abc123456789",
                "size_bytes": 1024,
                "status": "uploaded",
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )

    # Step B: Upgrade to 0003 (Phase 3 schema)
    command.upgrade(alembic_cfg, "head")

    db = session_maker()
    preserved_paper = db.query(Paper).filter(Paper.id == paper_id).first()
    assert preserved_paper is not None
    assert preserved_paper.original_filename == "week1.pdf"

    # Insert Phase 3 records for this paper
    job_id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    db.add(
        ProcessingJob(
            id=job_id,
            paper_id=paper_id,
            run_id=str(uuid.uuid4()),
            stage="validating",
            status="queued",
            attempt=1,
            created_at=utcnow_iso(),
        )
    )
    page_run_id = str(uuid.uuid4())
    db.add(
        Page(
            id=page_id,
            paper_id=paper_id,
            run_id=page_run_id,
            page_number=1,
            char_count=100,
            extraction_status="ok",
            flags_json="[]",
            created_at=utcnow_iso(),
        )
    )
    db.commit()

    # Verify FK CASCADE deletes both jobs and pages
    db.delete(preserved_paper)
    db.commit()

    assert db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first() is None
    assert db.query(Page).filter(Page.id == page_id).first() is None
    db.close()


# ==============================================================================
# 2. PyMuPDF Extraction & Quality Heuristics Tests
# ==============================================================================


def test_extraction_engine_and_quality_heuristics(p3_env: dict):
    """Test PyMuPDF extraction on multi-column, rotated, table, equation, and scan-like pages."""
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "rich_document.pdf"

    pages_spec = [
        # Page 1: Normal paper with title, authors, abstract, and year pattern
        {
            "width": 612,
            "height": 792,
            "rotation": 0,
            "blocks": [
                {
                    "rect": [72, 72, 540, 120],
                    "text": "Attention Is All You Need for Deep Transformers",
                    "fontsize": 16,
                },
                {
                    "rect": [72, 130, 540, 160],
                    "text": "Ashish Vaswani, Noam Shazeer, Niki Parmar",
                    "fontsize": 11,
                },
                {
                    "rect": [72, 170, 540, 220],
                    "text": "Published in Advances in Neural Information Processing Systems, 2017.",
                    "fontsize": 10,
                },
                {
                    "rect": [72, 230, 540, 300],
                    "text": "Keywords: Deep Learning, Self-Attention, Natural Language Processing",
                    "fontsize": 10,
                },
                {
                    "rect": [72, 310, 540, 500],
                    "text": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer.",
                    "fontsize": 10,
                },
            ],
        },
        # Page 2: Rotated 90 degrees with an irregular table
        {
            "width": 792,
            "height": 612,
            "rotation": 90,
            "blocks": [
                {
                    "rect": [72, 72, 600, 250],
                    "text": "Table 1: Benchmark Results Comparison\nModel\tBLEU\tTraining Cost\nTransformer\t28.4\t3.3 days",
                    "fontsize": 10,
                }
            ],
        },
        # Page 3: Contains mathematical formulas / LaTeX / Greek symbols
        {
            "width": 612,
            "height": 792,
            "rotation": 0,
            "blocks": [
                {
                    "rect": [72, 72, 540, 200],
                    "text": "We define Attention(Q, K, V) = softmax(QK^T / \\sqrt{d_k}) V where \\sum_{i=1}^n \\alpha_i = 1 and \\sigma > 0.",
                    "fontsize": 10,
                }
            ],
        },
        # Page 4: Mixed scan-like image page (minimal text + image)
        {
            "width": 612,
            "height": 792,
            "rotation": 0,
            "draw_image": True,
            "blocks": [{"rect": [72, 72, 200, 90], "text": "Fig 1", "fontsize": 8}],
        },
    ]

    metadata = {
        "title": "Attention Is All You Need",
        "author": "Ashish Vaswani, Noam Shazeer",
        "creationDate": "D:20171206180000",
        "keywords": "Transformer, Attention",
    }

    _create_synthetic_pdf(pdf_file, pages_spec, metadata)

    result = extraction_service.extract_pdf(pdf_file)

    # 1. Page count and dimensions
    assert result.page_count == 4
    assert len(result.pages) == 4

    p1 = result.pages[0]
    assert p1.page_number == 1
    assert p1.rotation == 0
    assert p1.width == 612.0
    assert p1.height == 792.0
    assert len(p1.blocks) >= 4
    assert p1.char_count > 100

    # Stable block IDs and bounding box coordinate conventions
    b0 = p1.blocks[0]
    assert b0.id == "p1_b0"
    assert len(b0.bbox) == 4
    assert b0.bbox[0] < b0.bbox[2]  # x0 < x1
    assert b0.bbox[1] < b0.bbox[3]  # y0 < y1
    assert len(b0.text_hash) == 16

    # 2. Page 2: Rotated & Table flag
    p2 = result.pages[1]
    assert p2.page_number == 2
    assert p2.rotation == 90
    assert "table_unreliable" in p2.flags
    assert p2.extraction_status == "partial"

    # 3. Page 3: Equations flag
    p3 = result.pages[2]
    assert "equations_may_be_missing" in p3.flags

    # 4. Page 4: Scan-like flag (image with < 50 chars)
    p4 = result.pages[3]
    assert "possible_scan" in p4.flags

    # 5. Document Quality Summary
    quality = result.quality
    assert quality.readable_pages == 4
    assert quality.flagged_pages >= 3
    assert 2 in quality.table_unreliable_pages
    assert 3 in quality.equations_missing_pages
    assert 4 in quality.possible_scan_pages
    assert quality.total_chars > 200
    assert not quality.all_image_document

    # 6. Metadata provenance
    meta = result.metadata
    assert meta.title == "Attention Is All You Need"
    assert meta.sources.get("title") == "pdf"
    assert "Ashish Vaswani" in meta.authors
    assert meta.publication_year == 2017
    assert meta.sources.get("publication_year") == "inferred"
    assert meta.sources.get("publication_year")["evidence"] == "2017"
    assert "Transformer" in meta.keywords


def test_all_image_document_fails_with_explicit_unsupported_error(p3_env: dict):
    """An image-only PDF with zero selectable text must fail with an explicit unsupported error."""
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "all_image.pdf"

    # 2 pages with only images, 0 text
    pages_spec = [
        {"width": 612, "height": 792, "draw_image": True, "blocks": []},
        {"width": 612, "height": 792, "draw_image": True, "blocks": []},
    ]

    _create_synthetic_pdf(pdf_file, pages_spec)

    with pytest.raises(extraction_service.UnsupportedTextError) as exc_info:
        extraction_service.extract_pdf(pdf_file)

    assert "UNSUPPORTED_TEXT_NO_SELECTABLE_TEXT" in str(exc_info.value)


# ==============================================================================
# 3. Worker Concurrency, Claims & Lease Fencing Tests
# ==============================================================================


def test_worker_atomic_claim_and_fencing(p3_env: dict):
    """Verify atomic claims, lease expiration recovery, and stale token fencing."""
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "concurrency_test.pdf"

    _create_synthetic_pdf(
        pdf_file,
        [
            {
                "width": 612,
                "height": 792,
                "blocks": [{"rect": [72, 72, 500, 150], "text": "Concurrency Test Document Body"}],
            }
        ],
    )

    db: Session = p3_env["factory"]()
    paper_id = str(uuid.uuid4())
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="concurrency_test.pdf",
        storage_path=str(pdf_file),
        sha256=hashlib.sha256(pdf_file.read_bytes()).hexdigest(),
        size_bytes=pdf_file.stat().st_size,
        status="uploaded",
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
    )
    db.add(paper)
    job = processing_service.enqueue_validation_job(db, paper_id=paper_id)
    job_id = job.id
    db.commit()
    db.close()

    # Worker 1 runs once and processes validating -> creates extracting job
    worker1 = WorkerEngine(worker_id="worker-1", lease_timeout_seconds=5)
    worked = worker1.run_once()
    assert worked is True

    db = p3_env["factory"]()
    v_job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    assert v_job.status == "succeeded"

    # An extracting job is now queued
    ext_job = (
        db.query(ProcessingJob).filter(ProcessingJob.paper_id == paper_id, ProcessingJob.stage == "extracting").first()
    )
    assert ext_job is not None
    assert ext_job.status == "queued"

    # Worker 1 claims the extracting job
    claimed = worker1._claim_next_job(db)
    assert claimed is not None
    token_w1 = claimed["claim_token"]
    assert claimed["job_id"] == ext_job.id
    db.close()

    # Worker 2 attempts to claim: queue is empty!
    worker2 = WorkerEngine(worker_id="worker-2", lease_timeout_seconds=5)
    db = p3_env["factory"]()
    claimed_w2 = worker2._claim_next_job(db)
    assert claimed_w2 is None
    db.close()

    # Simulate Worker 1 hanging: artificially age heartbeat beyond lease_timeout (10 seconds ago)
    db = p3_env["factory"]()
    stale_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)).isoformat()
    db.query(ProcessingJob).filter(ProcessingJob.id == ext_job.id).update(
        {"heartbeat_at": stale_time, "claimed_at": stale_time}
    )
    db.commit()
    db.close()

    # Worker 2 runs: recovers expired job, increments attempt, and claims it
    worked_w2 = worker2.run_once()
    assert worked_w2 is True

    db = p3_env["factory"]()
    # Attempt 1 is preserved in historical records as failed due to expired lease
    retired_job = db.query(ProcessingJob).filter(ProcessingJob.id == ext_job.id).first()
    assert retired_job.status == "failed"
    assert retired_job.attempt == 1
    assert "lease expired" in (retired_job.error_message or "").lower()

    # Attempt 2 is a separate record and successfully finished extracting!
    succeeded_job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.paper_id == paper_id,
            ProcessingJob.stage == "extracting",
            ProcessingJob.attempt == 2,
        )
        .first()
    )
    assert succeeded_job is not None
    assert succeeded_job.status == "succeeded"
    assert succeeded_job.worker_id == "worker-2"
    token_w2 = succeeded_job.claim_token
    assert token_w2 != token_w1

    # Pages are persisted by Worker 2
    pages = db.query(Page).filter(Page.paper_id == paper_id).all()
    assert len(pages) == 1
    db.close()

    # Now simulate Worker 1 (stale) waking up and trying to publish results with token_w1
    # It must cleanly fail with WorkerFencingViolation because claim_token no longer matches!
    claimed["claim_token"] = token_w1
    with pytest.raises(WorkerFencingViolation):
        worker1._execute_claimed_job(claimed)

    db = p3_env["factory"]()
    final_job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.paper_id == paper_id,
            ProcessingJob.stage == "extracting",
            ProcessingJob.attempt == 2,
        )
        .first()
    )
    assert final_job.worker_id == "worker-2"  # Preserved Worker 2's publication
    db.close()


# ==============================================================================
# 4. Reprocess Conflict and Generation Consistency Tests
# ==============================================================================


def test_reprocess_conflict_and_generation_consistency(p3_env: dict):
    """Test 409 conflict when running, 202 on accepted reprocess, and clean page replacement."""
    client: TestClient = p3_env["client"]
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "reprocess_paper.pdf"

    _create_synthetic_pdf(
        pdf_file,
        [
            {
                "width": 612,
                "height": 792,
                "blocks": [{"rect": [72, 72, 400, 120], "text": "Initial Generation Content"}],
            }
        ],
    )

    # 1. Upload paper via API
    with open(pdf_file, "rb") as f:
        res = client.post(
            "/api/papers",
            data={"workspace_id": p3_env["workspace_id"]},
            files={"files": ("reprocess_paper.pdf", f, "application/pdf")},
        )
    assert res.status_code == 202
    data = res.json()
    paper_id = data["papers"][0]["id"]

    # 2. Attempting reprocess while job is queued/running must return 409 Conflict
    rep_res = client.post(f"/api/papers/{paper_id}/reprocess")
    assert rep_res.status_code == 409
    assert "active processing job" in rep_res.json()["error"]["message"]

    # 3. Process to completion using WorkerEngine
    worker = WorkerEngine(worker_id="test-worker", lease_timeout_seconds=30)
    # Pass 1: processes validating -> enqueues extracting
    worker.run_once()
    # Pass 2: processes extracting -> completes extraction
    worker.run_once()

    # Check status
    stat_res = client.get(f"/api/papers/{paper_id}/status")
    assert stat_res.status_code == 200
    stat_data = stat_res.json()
    assert stat_data["status"] == "processing"
    assert stat_data["stage"] == "extracting"
    assert stat_data["progress"] == 0.5

    # Check pages
    pages_res = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_res.status_code == 200
    assert len(pages_res.json()["items"]) == 1

    # 4. Now that the job is no longer queued/running, request reprocess
    rep_res2 = client.post(f"/api/papers/{paper_id}/reprocess")
    assert rep_res2.status_code == 202
    assert rep_res2.json()["status"] == "processing"
    assert rep_res2.json()["stage"] == "validating"

    # Worker runs new generation
    worker.run_once()  # validating
    worker.run_once()  # extracting

    # Verify pages count in API is still 1 (latest published generation served, not mixed!)
    pages_res2 = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_res2.status_code == 200
    assert len(pages_res2.json()["items"]) == 1

    # Verify database retains pages from BOTH generations with distinct run_ids
    db: Session = p3_env["factory"]()
    all_pages = db.query(Page).filter(Page.paper_id == paper_id).all()
    assert len(all_pages) == 2
    distinct_runs = {p.run_id for p in all_pages}
    assert len(distinct_runs) == 2
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    assert paper.published_run_id in distinct_runs
    db.close()


def test_worker_multirun_migration_preservation(p3_env: dict):
    """Verifies that an actual worker-produced reprocess database upgrades/downgrades cleanly without losing generations."""
    client: TestClient = p3_env["client"]
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "worker_multirun.pdf"

    _create_synthetic_pdf(
        pdf_file,
        [
            {
                "width": 612,
                "height": 792,
                "blocks": [{"rect": [72, 72, 400, 120], "text": "Worker Gen 1 Text"}],
            }
        ],
    )

    with open(pdf_file, "rb") as f:
        res = client.post(
            "/api/papers",
            data={"workspace_id": p3_env["workspace_id"]},
            files={"files": ("worker_multirun.pdf", f, "application/pdf")},
        )
    assert res.status_code == 202
    paper_id = res.json()["papers"][0]["id"]

    worker = WorkerEngine(worker_id="test-worker-mr", lease_timeout_seconds=30)
    worker.run_once()  # validating
    worker.run_once()  # extracting gen 1

    # Reprocess to create gen 2
    rep_res = client.post(f"/api/papers/{paper_id}/reprocess")
    assert rep_res.status_code == 202
    worker.run_once()  # validating
    worker.run_once()  # extracting gen 2

    # Database has 2 worker-produced page records
    db: Session = p3_env["factory"]()
    pages_before = db.query(Page).filter(Page.paper_id == paper_id).order_by(Page.created_at.asc()).all()
    assert len(pages_before) == 2
    page_ids_before = [p.id for p in pages_before]
    page_runs_before = [p.run_id for p in pages_before]
    assert len(set(page_runs_before)) == 2
    db.close()

    # Perform migration test on this live worker DB:
    cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "backend" / "alembic.ini"))
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parent.parent.parent / "backend" / "migrations"),
    )
    cfg.set_main_option("sqlalchemy.url", p3_env["db_url"])

    # Downgrade to 0004
    command.downgrade(cfg, "0004_add_generation_and_fencing_controls")
    # Upgrade to head (0006)
    command.upgrade(cfg, "head")

    # Verify both worker generations survive with identical IDs and run_ids
    db = p3_env["factory"]()
    pages_after = db.query(Page).filter(Page.paper_id == paper_id).order_by(Page.created_at.asc()).all()
    assert len(pages_after) == 2
    assert [p.id for p in pages_after] == page_ids_before
    assert [p.run_id for p in pages_after] == page_runs_before

    paper_after = db.query(Paper).filter(Paper.id == paper_id).first()
    assert paper_after.published_run_id == page_runs_before[1]
    db.close()

    # API still serves the latest published generation
    pages_res = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_res.status_code == 200
    assert len(pages_res.json()["items"]) == 1
    assert pages_res.json()["run_id"] == page_runs_before[1]


# ==============================================================================
# 5. Deletion During Processing Safety Test
# ==============================================================================


def test_deletion_during_processing_drops_results_cleanly(p3_env: dict):
    """Deleting a paper while worker holds a claim must safely drop results without orphan publication."""
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "delete_race.pdf"

    _create_synthetic_pdf(
        pdf_file,
        [
            {
                "width": 612,
                "height": 792,
                "blocks": [{"rect": [72, 72, 400, 120], "text": "Delete Race Content"}],
            }
        ],
    )

    db: Session = p3_env["factory"]()
    paper_id = str(uuid.uuid4())
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="delete_race.pdf",
        storage_path=str(pdf_file),
        sha256=hashlib.sha256(pdf_file.read_bytes()).hexdigest(),
        size_bytes=pdf_file.stat().st_size,
        status="uploaded",
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
    )
    db.add(paper)
    processing_service.enqueue_validation_job(db, paper_id=paper_id)
    db.commit()
    db.close()

    worker = WorkerEngine(worker_id="test-worker")
    worker.run_once()  # validates and enqueues extracting

    db = p3_env["factory"]()
    claimed = worker._claim_next_job(db)
    assert claimed is not None
    db.close()

    # User deletes the paper while worker has claimed the extracting job
    client: TestClient = p3_env["client"]
    del_res = client.delete(f"/api/papers/{paper_id}")
    assert del_res.status_code == 204

    # Worker executes and publishes: must not resurrect paper or fail with unhandled exception
    worker._execute_claimed_job(claimed)

    db = p3_env["factory"]()
    assert db.query(Paper).filter(Paper.id == paper_id).first() is None
    assert db.query(Page).filter(Page.paper_id == paper_id).all() == []
    assert db.query(ProcessingJob).filter(ProcessingJob.paper_id == paper_id).all() == []
    db.close()


# ==============================================================================
# 6. API Inspection & Security Tests
# ==============================================================================


def test_api_inspection_and_foreign_ownership_security(p3_env: dict):
    """Verify inspection endpoints, 404 for nonexistent pages, and foreign ownership isolation."""
    client: TestClient = p3_env["client"]
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "inspect_paper.pdf"

    _create_synthetic_pdf(
        pdf_file,
        [
            {
                "width": 612,
                "height": 792,
                "blocks": [{"rect": [72, 72, 400, 120], "text": "Page One Inspection Target"}],
            }
        ],
    )

    with open(pdf_file, "rb") as f:
        res = client.post(
            "/api/papers",
            data={"workspace_id": p3_env["workspace_id"]},
            files={"files": ("inspect_paper.pdf", f, "application/pdf")},
        )
    paper_id = res.json()["papers"][0]["id"]

    worker = WorkerEngine()
    worker.run_once()  # validate
    worker.run_once()  # extract

    # 1. Blocks endpoint
    blocks_res = client.get(f"/api/papers/{paper_id}/pages/1/blocks")
    assert blocks_res.status_code == 200
    b_data = blocks_res.json()
    assert b_data["page_number"] == 1
    assert len(b_data["blocks"]) >= 1
    assert "Page One Inspection Target" in b_data["blocks"][0]["text"]

    # 2. Nonexistent page returns 404
    p404_res = client.get(f"/api/papers/{paper_id}/pages/99/blocks")
    assert p404_res.status_code == 404

    # 3. Foreign user cannot access status, pages, blocks, or reprocess
    db: Session = p3_env["factory"]()
    foreign_user = User(
        id=str(uuid.uuid4()),
        email="foreign@example.com",
        password_hash="hash",
        created_at=utcnow_iso(),
    )
    db.add(foreign_user)
    db.commit()
    foreign_id = foreign_user.id
    db.close()

    from backend.app.api import deps

    app.dependency_overrides[deps.get_current_user] = lambda: User(
        id=foreign_id, email="foreign@example.com", password_hash="hash", created_at=utcnow_iso()
    )

    try:
        assert client.get(f"/api/papers/{paper_id}/status").status_code == 404
        assert client.get(f"/api/papers/{paper_id}/pages").status_code == 404
        assert client.get(f"/api/papers/{paper_id}/pages/1/blocks").status_code == 404
        assert client.post(f"/api/papers/{paper_id}/reprocess").status_code == 404
    finally:
        app.dependency_overrides.pop(deps.get_current_user, None)


# ==============================================================================
# 5. Phase 3 Independent Review Regression Gate (R1–R7)
# ==============================================================================


def test_r1_concurrent_job_claim_race(p3_env: dict):
    """R1: Two workers racing to claim the same queued job; exactly 1 wins, 1 None."""
    paper_id = str(uuid.uuid4())
    db: Session = p3_env["factory"]()
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="r1_test.pdf",
        storage_path="r1_test.pdf",
        sha256="a" * 64,
        size_bytes=100,
        status="uploaded",
    )
    db.add(paper)
    processing_service.enqueue_validation_job(db, paper_id)
    db.commit()
    engine = db.get_bind()
    db.close()

    barrier = threading.Barrier(2)

    def sync_claim(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE processing_jobs SET"):
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", sync_claim)

    def claim(worker_id: str):
        with p3_env["factory"]() as s:
            return WorkerEngine(worker_id=worker_id)._claim_next_job(s)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["w1", "w2"]))

    event.remove(engine, "before_cursor_execute", sync_claim)

    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert winners[0]["claim_token"] is not None


def test_r2_lease_liveness_and_worker_kill_recovery(p3_env: dict):
    """R2: Lease liveness renewed during slow extraction; killed worker lease recovered."""
    test_dir = p3_env["data_dir"]
    pdf_file = test_dir / "r2_liveness.pdf"
    _create_synthetic_pdf(
        pdf_file,
        [{"width": 612, "height": 792, "blocks": [{"rect": [72, 72, 300, 100], "text": "Heartbeat Test"}]}],
    )

    db: Session = p3_env["factory"]()
    paper_id = str(uuid.uuid4())
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="r2_liveness.pdf",
        storage_path=str(pdf_file),
        sha256=hashlib.sha256(pdf_file.read_bytes()).hexdigest(),
        size_bytes=pdf_file.stat().st_size,
        status="uploaded",
    )
    db.add(paper)
    job = processing_service.enqueue_validation_job(db, paper_id)
    paper.current_run_id = job.run_id
    db.commit()
    db.close()

    w1 = WorkerEngine(worker_id="slow-worker", lease_timeout_seconds=2)
    w1.run_once()  # completes validation -> extracting queued

    # Patch extract_pdf to take 3.0s (longer than lease_timeout_seconds=2)
    real_extract = extraction_service.extract_pdf

    def slow_extract(*args, **kwargs):
        time.sleep(3.0)
        return real_extract(*args, **kwargs)

    w2 = WorkerEngine(worker_id="polling-worker", lease_timeout_seconds=2)

    def run_slow():
        with unittest.mock.patch("backend.app.services.extraction_service.extract_pdf", side_effect=slow_extract):
            w1.run_once()

    t = threading.Thread(target=run_slow)
    t.start()
    # Wait 2.2s: the original 2.0s lease duration has expired, but heartbeat actively renewed
    time.sleep(2.2)
    # While slow-worker is running past the original lease window, polling-worker checks for expired leases
    w2_worked = w2.run_once()
    t.join()

    # Polling worker could NOT steal the job because heartbeat was actively refreshed past the 2s mark
    assert w2_worked is False

    with p3_env["factory"]() as s:
        ext_job = (
            s.query(ProcessingJob)
            .filter(ProcessingJob.paper_id == paper_id, ProcessingJob.stage == "extracting")
            .first()
        )
        assert ext_job.status == "succeeded"
        assert ext_job.worker_id == "slow-worker"

    # Part 2: Real worker subprocess kill and recovery with independent worker
    proc_paper_id = str(uuid.uuid4())
    proc_pdf = p3_env["data_dir"] / "subprocess_kill.pdf"
    _create_synthetic_pdf(
        proc_pdf,
        [{"width": 612, "height": 792, "blocks": [{"rect": [72, 72, 200, 100], "text": "Subprocess Test"}]}],
    )
    with p3_env["factory"]() as s:
        p2 = Paper(
            id=proc_paper_id,
            workspace_id=p3_env["workspace_id"],
            original_filename="subprocess_kill.pdf",
            storage_path=str(proc_pdf),
            sha256=hashlib.sha256(proc_pdf.read_bytes()).hexdigest(),
            size_bytes=proc_pdf.stat().st_size,
            status="uploaded",
        )
        s.add(p2)
        job2 = processing_service.enqueue_validation_job(s, proc_paper_id)
        p2.current_run_id = job2.run_id
        s.commit()

    root_dir = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["DATABASE_URL"] = p3_env["db_url"]
    env["PYTHONPATH"] = str(root_dir)

    subproc_cmd = (
        "import sys, time; "
        "import backend.app.services.extraction_service as es; "
        "orig = es.extract_pdf; "
        "es.extract_pdf = lambda *a, **k: (time.sleep(3.0), orig(*a, **k))[1]; "
        "from worker.main import main; "
        "sys.argv = ['worker', '--db-url', sys.argv[1], '--poll-interval', '0.1', '--lease-timeout', '2', '--worker-id', 'subprocess-victim']; "
        "sys.exit(main())"
    )

    subproc_log = p3_env["data_dir"] / "subprocess_victim.log"
    log_fp = open(subproc_log, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            subproc_cmd,
            p3_env["db_url"],
        ],
        env=env,
        cwd=str(root_dir),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        # Wait until worker subprocess claims the extracting job and is running
        claimed = False
        for _ in range(60):
            time.sleep(0.2)
            with p3_env["factory"]() as s:
                running_job = (
                    s.query(ProcessingJob)
                    .filter(
                        ProcessingJob.paper_id == proc_paper_id,
                        ProcessingJob.stage == "extracting",
                        ProcessingJob.status == "running",
                    )
                    .first()
                )
                if running_job:
                    claimed = True
                    break
        if not claimed:
            proc.kill()
            proc.wait(timeout=3)
            log_fp.close()
            log_content = subproc_log.read_text(encoding="utf-8", errors="replace")
            with p3_env["factory"]() as s:
                jobs_dump = [(j.stage, j.status, j.attempt) for j in s.query(ProcessingJob).all()]
            raise AssertionError(
                f"Worker subprocess did not enter running state for extracting stage. "
                f"Poll={proc.poll()}, Jobs={jobs_dump}, Output={log_content}"
            )

        # Terminate the worker abruptly while it is actively processing
        proc.kill()
        proc.wait(timeout=5)

        # Wait for the lease to expire (2.0s + buffer)
        time.sleep(2.5)

        # Independent recovery worker recovers expired lease, retrying it
        recovery_worker = WorkerEngine(worker_id="recovery-worker", lease_timeout_seconds=2)
        recovery_worker.run_once()  # recovers expired attempt 1 -> queued attempt 2
        recovery_worker.run_once()  # processes attempt 2

        with p3_env["factory"]() as s:
            ext_jobs = (
                s.query(ProcessingJob)
                .filter(ProcessingJob.paper_id == proc_paper_id, ProcessingJob.stage == "extracting")
                .order_by(ProcessingJob.attempt.asc())
                .all()
            )
            assert len(ext_jobs) >= 2
            assert ext_jobs[0].status == "failed"
            assert ext_jobs[0].attempt == 1
            assert "Worker lease expired" in (ext_jobs[0].error_message or "")
            assert ext_jobs[-1].attempt >= 2
            assert ext_jobs[-1].status in ("running", "succeeded")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if not log_fp.closed:
            log_fp.close()


def test_r3_concurrent_reprocess_conflict_and_generation_isolation(p3_env: dict):
    """R3: Concurrent reprocess yields exactly one 202 and one 409; generation isolation."""
    paper_id = str(uuid.uuid4())
    db: Session = p3_env["factory"]()
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="r3_test.pdf",
        storage_path="r3_test.pdf",
        sha256="b" * 64,
        size_bytes=200,
        status="uploaded",
    )
    db.add(paper)
    db.commit()
    engine = db.get_bind()
    db.close()

    barrier = threading.Barrier(2)

    def sync_reprocess(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE papers SET"):
            barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", sync_reprocess)

    def do_reprocess(user_id):
        with p3_env["factory"]() as s:
            try:
                res = processing_service.request_reprocess(s, p3_env["user_id"], paper_id)
                return ("ok", res.status)
            except AppException as exc:
                return ("err", exc.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(do_reprocess, [1, 2]))

    event.remove(engine, "before_cursor_execute", sync_reprocess)

    codes = [o[1] for o in outcomes]
    assert 409 in codes
    assert "processing" in codes or "ok" in [o[0] for o in outcomes]

    with p3_env["factory"]() as s:
        active_runs = (
            s.query(ProcessingJob)
            .filter(
                ProcessingJob.paper_id == paper_id,
                ProcessingJob.status.in_(["queued", "running"]),
            )
            .count()
        )
        assert active_runs == 1


def test_r4_public_error_sanitization_no_paths_exposed(p3_env: dict):
    """R4: Missing file and unexpected errors do not leak internal filesystem paths, UNC paths, or tokens."""
    client = p3_env["client"]
    db: Session = p3_env["factory"]()
    paper_id = str(uuid.uuid4())
    fake_path = "F:\\dev\\private\\storage\\secrets\\nonexistent.pdf"
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="secret_leak.pdf",
        storage_path=fake_path,
        sha256="c" * 64,
        size_bytes=300,
        status="uploaded",
    )
    db.add(paper)
    job = processing_service.enqueue_validation_job(db, paper_id)
    paper.current_run_id = job.run_id
    db.commit()
    db.close()

    worker = WorkerEngine()
    worker.run_once()  # validation fails on missing file

    res = client.get(f"/api/papers/{paper_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "failed"
    top_err = data["error"] or ""
    assert "F:" not in top_err
    assert "private" not in top_err
    assert "secrets" not in top_err
    assert "\\" not in top_err
    assert "/" not in top_err

    for st in data["stages"]:
        st_err = st["error"] or ""
        assert "F:" not in st_err
        assert "private" not in st_err
        assert "\\" not in st_err

    # Also test unexpected exceptions containing forward-slash paths, UNC paths, and secret tokens
    with p3_env["factory"]() as s:
        j = s.query(ProcessingJob).filter(ProcessingJob.paper_id == paper_id).first()
        j.error_message = "parser crashed at F:/secret/private.pdf; unc=\\\\storage\\share; token=secret-bearer-999; unix=/var/log/private.log"
        s.commit()

    res2 = client.get(f"/api/papers/{paper_id}/status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["error"] == "An error occurred during document processing."
    assert "secret" not in data2["error"]
    assert "F:" not in data2["error"]
    assert "/" not in data2["error"]
    assert "\\" not in data2["error"]
    for st in data2["stages"]:
        st_e = st["error"] or ""
        assert "secret" not in st_e
        assert "F:" not in st_e
        assert "/" not in st_e
        assert "\\" not in st_e


def test_r5_rotated_and_cropped_geometry_consistency(p3_env: dict):
    """R5: 0/90/180/270 rotated and cropped pages have block coords strictly within page bounds and valid overlays."""
    test_dir = p3_env["data_dir"]

    # 1. Test 0, 90, 180, 270 rotations with visual overlay inspection
    for rot in [0, 90, 180, 270]:
        pdf_path = test_dir / f"rot_{rot}.pdf"
        doc = fitz.open()
        p = doc.new_page(width=612, height=792)
        p.insert_text((72, 700), f"Rotated page test {rot}")
        p.set_rotation(rot)
        doc.save(pdf_path)
        doc.close()

        result = extraction_service.extract_pdf(str(pdf_path))
        extracted_p = result.pages[0]
        assert extracted_p.rotation == rot
        assert len(extracted_p.blocks) > 0

        # Visual overlay inspection: draw extracted bounding boxes onto page pixmap
        # Derotate visual coordinates back through page.derotation_matrix for PDF shape drawing
        render_doc = fitz.open(pdf_path)
        render_page = render_doc[0]
        shape = render_page.new_shape()
        for b in extracted_p.blocks:
            x0, y0, x1, y1 = b.bbox
            assert 0.0 <= x0 <= x1 <= extracted_p.width + 0.1
            assert 0.0 <= y0 <= y1 <= extracted_p.height + 0.1
            unrot_rect = fitz.Rect(x0, y0, x1, y1) * render_page.derotation_matrix
            shape.draw_rect(unrot_rect)
        shape.finish(color=(1, 0, 0), width=1.5)
        shape.commit()

        pix = render_page.get_pixmap()
        overlay_path = test_dir / f"overlay_rot_{rot}.png"
        pix.save(overlay_path)
        render_doc.close()

        assert overlay_path.exists()
        assert pix.width > 0 and pix.height > 0
        assert len(pix.samples) > 0

        # Validate that red overlay pixels precisely enclose black text glyphs
        red_pts = [
            (x, y)
            for y in range(pix.height)
            for x in range(pix.width)
            if pix.pixel(x, y)[0] > 200 and pix.pixel(x, y)[1] < 50 and pix.pixel(x, y)[2] < 50
        ]
        black_pts = [
            (x, y)
            for y in range(pix.height)
            for x in range(pix.width)
            if pix.pixel(x, y)[0] < 50 and pix.pixel(x, y)[1] < 50 and pix.pixel(x, y)[2] < 50
        ]
        assert len(red_pts) > 0, f"No red overlay pixels found for rot {rot}"
        assert len(black_pts) > 0, f"No black text pixels found for rot {rot}"

        min_rx, max_rx = min(p[0] for p in red_pts), max(p[0] for p in red_pts)
        min_ry, max_ry = min(p[1] for p in red_pts), max(p[1] for p in red_pts)
        min_bx, max_bx = min(p[0] for p in black_pts), max(p[0] for p in black_pts)
        min_by, max_by = min(p[1] for p in black_pts), max(p[1] for p in black_pts)

        # Enclosure check with 2px stroke tolerance
        assert min_rx <= min_bx + 2, f"Red box left {min_rx} does not enclose text left {min_bx} for rot {rot}"
        assert max_rx >= max_bx - 2, f"Red box right {max_rx} does not enclose text right {max_bx} for rot {rot}"
        assert min_ry <= min_by + 2, f"Red box top {min_ry} does not enclose text top {min_by} for rot {rot}"
        assert max_ry >= max_by - 2, f"Red box bottom {max_ry} does not enclose text bottom {max_by} for rot {rot}"

        # Negative control: intentionally omitting derotation on rotated pages (rot != 0)
        # proves that raw visual coordinates without derotation fail the enclosure assertion
        if rot in (90, 270):
            neg_doc = fitz.open(pdf_path)
            neg_page = neg_doc[0]
            neg_shape = neg_page.new_shape()
            for b in extracted_p.blocks:
                neg_shape.draw_rect(fitz.Rect(b.bbox))
            neg_shape.finish(color=(1, 0, 0), width=1.5)
            neg_shape.commit()
            neg_pix = neg_page.get_pixmap()
            neg_doc.close()

            neg_red_pts = [
                (x, y)
                for y in range(neg_pix.height)
                for x in range(neg_pix.width)
                if neg_pix.pixel(x, y)[0] > 200 and neg_pix.pixel(x, y)[1] < 50 and neg_pix.pixel(x, y)[2] < 50
            ]
            if len(neg_red_pts) == 0:
                # Shape was drawn outside unrotated page bounds and clipped entirely
                misaligned = True
            else:
                neg_min_rx, neg_max_rx = min(p[0] for p in neg_red_pts), max(p[0] for p in neg_red_pts)
                neg_min_ry, neg_max_ry = min(p[1] for p in neg_red_pts), max(p[1] for p in neg_red_pts)

                misaligned = neg_min_rx > min_bx or neg_max_rx < max_bx or neg_min_ry > min_by or neg_max_ry < max_by
            assert misaligned is True, f"Negative control failed to detect misalignment for rot {rot}"

    # 2. Test cropped page
    crop_pdf = test_dir / "cropped_page.pdf"
    crop_doc = fitz.open()
    cp = crop_doc.new_page(width=612, height=792)
    cp.insert_text((100, 150), "Cropped content text")
    cp.set_cropbox(fitz.Rect(50, 50, 500, 600))
    crop_doc.save(crop_pdf)
    crop_doc.close()

    crop_result = extraction_service.extract_pdf(str(crop_pdf))
    crop_p = crop_result.pages[0]
    assert len(crop_p.blocks) > 0
    for b in crop_p.blocks:
        x0, y0, x1, y1 = b.bbox
        assert 0.0 <= x0 <= x1 <= crop_p.width + 0.1
        assert 0.0 <= y0 <= y1 <= crop_p.height + 0.1

    render_crop_doc = fitz.open(crop_pdf)
    rc_page = render_crop_doc[0]
    crop_shape = rc_page.new_shape()
    for b in crop_p.blocks:
        crop_shape.draw_rect(fitz.Rect(b.bbox))
    crop_shape.finish(color=(0, 0, 1), width=1.5)
    crop_shape.commit()
    crop_pix = rc_page.get_pixmap()
    crop_overlay_path = test_dir / "overlay_crop.png"
    crop_pix.save(crop_overlay_path)
    render_crop_doc.close()

    assert crop_overlay_path.exists()
    assert crop_pix.width > 0 and crop_pix.height > 0

    # Verify blue box encloses text on cropped page
    blue_pts = [
        (x, y)
        for y in range(crop_pix.height)
        for x in range(crop_pix.width)
        if crop_pix.pixel(x, y)[2] > 200 and crop_pix.pixel(x, y)[0] < 50 and crop_pix.pixel(x, y)[1] < 50
    ]
    crop_black_pts = [
        (x, y)
        for y in range(crop_pix.height)
        for x in range(crop_pix.width)
        if crop_pix.pixel(x, y)[0] < 50 and crop_pix.pixel(x, y)[1] < 50 and crop_pix.pixel(x, y)[2] < 50
    ]
    assert len(blue_pts) > 0
    assert len(crop_black_pts) > 0
    assert min(p[0] for p in blue_pts) <= min(p[0] for p in crop_black_pts) + 2
    assert max(p[0] for p in blue_pts) >= max(p[0] for p in crop_black_pts) - 2
    assert min(p[1] for p in blue_pts) <= min(p[1] for p in crop_black_pts) + 2
    assert max(p[1] for p in blue_pts) >= max(p[1] for p in crop_black_pts) - 2

    # Negative control for cropped page: shifted box (+100px) must fail enclosure
    neg_crop_doc = fitz.open(crop_pdf)
    neg_cpage = neg_crop_doc[0]
    neg_cshape = neg_cpage.new_shape()
    for b in crop_p.blocks:
        neg_cshape.draw_rect(fitz.Rect(b.bbox[0] + 100, b.bbox[1] + 100, b.bbox[2] + 100, b.bbox[3] + 100))
    neg_cshape.finish(color=(0, 0, 1), width=1.5)
    neg_cshape.commit()
    neg_cpix = neg_cpage.get_pixmap()
    neg_crop_doc.close()

    neg_blue_pts = [
        (x, y)
        for y in range(neg_cpix.height)
        for x in range(neg_cpix.width)
        if neg_cpix.pixel(x, y)[2] > 200 and neg_cpix.pixel(x, y)[0] < 50 and neg_cpix.pixel(x, y)[1] < 50
    ]
    neg_crop_misaligned = min(p[0] for p in neg_blue_pts) > min(p[0] for p in crop_black_pts) or min(
        p[1] for p in neg_blue_pts
    ) > min(p[1] for p in crop_black_pts)
    assert neg_crop_misaligned is True


def test_r6_metadata_provenance_and_clean_heuristics(p3_env: dict):
    """R6: CreationDate not promoted to year; uncertain heuristics marked inferred or omitted."""
    test_dir = p3_env["data_dir"]
    pdf_path = test_dir / "r6_heuristics.pdf"
    doc = fitz.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 100), "A Systematic Study of Document Ingestion")
    p.insert_text((72, 150), "Random Header Without Author Format")
    p.insert_text((72, 200), "No publication year mentioned here.")
    doc.set_metadata({"creationDate": "D:20240101120000Z", "title": "A Systematic Study of Document Ingestion"})
    doc.save(pdf_path)
    doc.close()

    result = extraction_service.extract_pdf(str(pdf_path))
    meta = result.metadata
    assert meta.publication_year is None
    assert meta.sources.get("publication_year") is None
    assert meta.authors == []


def test_r7_attempt_history_preservation(p3_env: dict):
    """R7: Retrying expired or failed attempts creates distinct attempt records."""
    paper_id = str(uuid.uuid4())
    db: Session = p3_env["factory"]()
    paper = Paper(
        id=paper_id,
        workspace_id=p3_env["workspace_id"],
        original_filename="r7_test.pdf",
        storage_path="r7_test.pdf",
        sha256="e" * 64,
        size_bytes=500,
        status="uploaded",
    )
    db.add(paper)
    job = processing_service.enqueue_validation_job(db, paper_id)
    paper.current_run_id = job.run_id
    db.commit()

    worker = WorkerEngine(worker_id="test-w", lease_timeout_seconds=1)
    claimed = worker._claim_next_job(db)
    assert claimed is not None

    # Artificially age the job to simulate lease expiration
    past_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
    db.query(ProcessingJob).filter(ProcessingJob.id == job.id).update(
        {"heartbeat_at": past_iso, "claimed_at": past_iso}
    )
    db.commit()

    # Recover expired lease
    worker._recover_expired_leases(db)

    # Verify attempt 1 is retained as failed
    job_att1 = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    assert job_att1.status == "failed"
    assert job_att1.attempt == 1

    # Verify attempt 2 is created
    job_att2 = db.query(ProcessingJob).filter(ProcessingJob.paper_id == paper_id, ProcessingJob.attempt == 2).first()
    assert job_att2 is not None
    assert job_att2.status == "queued"
    assert job_att2.id != job.id
    db.close()


def test_f1_structured_provenance_and_http_contracts(p3_env: dict):
    """F1: Uploaded & processed PDF with structured provenance returns 200 on detail and library listing."""
    client = p3_env["client"]
    test_dir = p3_env["data_dir"]
    pdf_path = test_dir / "provenance_paper.pdf"
    doc = fitz.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 100), "Deep Learning Architectures for Document Reasoning")
    p.insert_text((72, 140), "Alice Smith and Bob Jones")
    p.insert_text((72, 180), "Published in 2023. Keywords: deep learning, transformer, pdf")
    doc.set_metadata(
        {
            "title": "Deep Learning Architectures for Document Reasoning",
            "author": "Alice Smith, Bob Jones",
            "keywords": "deep learning, transformer",
        }
    )
    doc.save(pdf_path)
    doc.close()

    # Upload via HTTP endpoint
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/papers",
            data={"workspace_id": p3_env["workspace_id"]},
            files={"files": ("provenance_paper.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 202
    paper_id = resp.json()["papers"][0]["id"]

    # Run worker to process validating and extracting
    worker = WorkerEngine()
    worker.run_once()  # validating
    worker.run_once()  # extracting

    # 1. Detail endpoint returns 200 with structured provenance intact
    detail_res = client.get(f"/api/papers/{paper_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["title"] == "Deep Learning Architectures for Document Reasoning"
    assert "Alice Smith" in detail["authors"]
    assert detail["metadata_source"] is not None
    assert isinstance(detail["metadata_source"], dict)
    title_src = detail["metadata_source"].get("title")
    assert title_src is not None
    assert isinstance(title_src, dict)
    assert title_src["source"] in ("pdf", "text")
    assert title_src.get("evidence") is not None

    # 2. Library list endpoint returns 200 with structured provenance intact
    list_res = client.get(f"/api/papers?workspace_id={p3_env['workspace_id']}")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    found = next((item for item in items if item["id"] == paper_id), None)
    assert found is not None
    assert found["metadata_source"]["title"]["source"] in ("pdf", "text")

    # 3. Backward compatibility: legacy paper with string sources returns 200
    with p3_env["factory"]() as s:
        legacy_p = Paper(
            id=str(uuid.uuid4()),
            workspace_id=p3_env["workspace_id"],
            original_filename="legacy.pdf",
            storage_path=str(pdf_path),
            sha256="f" * 64,
            size_bytes=100,
            status="ready",
            metadata_source_json=json.dumps({"title": "pdf", "authors": "text"}),
        )
        s.add(legacy_p)
        s.commit()
        legacy_id = legacy_p.id

    legacy_detail = client.get(f"/api/papers/{legacy_id}")
    assert legacy_detail.status_code == 200
    assert legacy_detail.json()["metadata_source"] == {"title": "pdf", "authors": "text"}


def test_f3_retry_history_and_generation_staleness(p3_env: dict):
    """F3: Status reflects latest attempt; retries do not permanently fail; pages report staleness."""
    client = p3_env["client"]
    paper_id = str(uuid.uuid4())
    run_1 = str(uuid.uuid4())
    with p3_env["factory"]() as s:
        paper = Paper(
            id=paper_id,
            workspace_id=p3_env["workspace_id"],
            original_filename="staleness_test.pdf",
            storage_path="staleness_test.pdf",
            sha256="1" * 64,
            size_bytes=100,
            status="processing",
            current_run_id=run_1,
            published_run_id=None,
        )
        s.add(paper)
        s.flush()
        # Stage validating succeeded
        s.add(
            ProcessingJob(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                run_id=run_1,
                stage="validating",
                status="succeeded",
                attempt=1,
            )
        )
        # Stage extracting attempt 1 expired / failed
        s.add(
            ProcessingJob(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                run_id=run_1,
                stage="extracting",
                status="failed",
                attempt=1,
                error_message="Worker lease expired after 30s.",
            )
        )
        # Stage extracting attempt 2 queued
        s.add(
            ProcessingJob(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                run_id=run_1,
                stage="extracting",
                status="queued",
                attempt=2,
            )
        )
        s.commit()

    # While attempt 2 is queued, status is processing attempt 2, error is None
    res = client.get(f"/api/papers/{paper_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processing"
    assert data["stage"] == "extracting"
    assert data["attempt"] == 2
    assert data["error"] is None

    # When attempt 2 succeeds, status is processing awaiting sectioning (Phase 3 boundary)
    with p3_env["factory"]() as s:
        job2 = (
            s.query(ProcessingJob)
            .filter(
                ProcessingJob.paper_id == paper_id,
                ProcessingJob.stage == "extracting",
                ProcessingJob.attempt == 2,
            )
            .first()
        )
        job2.status = "succeeded"
        paper_db = s.query(Paper).filter(Paper.id == paper_id).first()
        paper_db.published_run_id = run_1
        # Add published page
        s.add(
            Page(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                run_id=run_1,
                page_number=1,
                char_count=50,
                extraction_status="ok",
                blocks_json=json.dumps([{"id": "b1", "bbox": [10, 10, 50, 50], "text": "Hello", "text_hash": "h"}]),
            )
        )
        s.commit()

    res2 = client.get(f"/api/papers/{paper_id}/status")
    assert res2.status_code == 200
    assert res2.json()["status"] == "processing"
    assert res2.json()["progress"] == 0.5
    assert res2.json()["attempt"] == 2

    # Verify pages: published run, not stale
    pages_res = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_res.status_code == 200
    assert pages_res.json()["is_stale"] is False
    assert pages_res.json()["run_id"] == run_1

    # Now simulate a reprocess request starting run_2
    run_2 = str(uuid.uuid4())
    with p3_env["factory"]() as s:
        paper_db = s.query(Paper).filter(Paper.id == paper_id).first()
        paper_db.current_run_id = run_2
        s.commit()

    # Now pages should report is_stale=True because current_run_id != published_run_id
    pages_stale_res = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_stale_res.status_code == 200
    assert pages_stale_res.json()["is_stale"] is True
    assert pages_stale_res.json()["run_id"] == run_1

    blocks_stale_res = client.get(f"/api/papers/{paper_id}/pages/1/blocks")
    assert blocks_stale_res.status_code == 200
    assert blocks_stale_res.json()["is_stale"] is True
    assert blocks_stale_res.json()["run_id"] == run_1
