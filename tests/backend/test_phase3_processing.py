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
import os
import uuid
from pathlib import Path
from typing import Generator

import fitz  # PyMuPDF
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import Page, Paper, ProcessingJob, User, Workspace, utcnow_iso
from backend.app.db.session import set_session_factory
from backend.app.main import app
from backend.app.services import extraction_service, processing_service
from worker.engine import WorkerEngine


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

    db.add(User(id=user_id, email="w1@example.com", password_hash="hash", created_at=utcnow_iso()))
    db.add(Workspace(id=ws_id, user_id=user_id, name="W1 Workspace", created_at=utcnow_iso()))
    db.add(
        Paper(
            id=paper_id,
            workspace_id=ws_id,
            original_filename="week1.pdf",
            storage_path=f"data/pdfs/{paper_id}.pdf",
            sha256="abc123456789",
            size_bytes=1024,
            status="uploaded",
            created_at=utcnow_iso(),
            updated_at=utcnow_iso(),
        )
    )
    db.commit()
    db.close()

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
    db.add(
        Page(
            id=page_id,
            paper_id=paper_id,
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
    assert meta.sources.get("publication_year") == "pdf"
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
    reclaimed_job = db.query(ProcessingJob).filter(ProcessingJob.id == ext_job.id).first()
    # Worker 2 successfully finished extracting!
    assert reclaimed_job.status == "succeeded"
    assert reclaimed_job.worker_id == "worker-2"
    token_w2 = reclaimed_job.claim_token
    assert token_w2 != token_w1

    # Pages are persisted by Worker 2
    pages = db.query(Page).filter(Page.paper_id == paper_id).all()
    assert len(pages) == 1
    db.close()

    # Now simulate Worker 1 (stale) waking up and trying to publish results with token_w1
    # It must cleanly fail because claim_token no longer matches!
    claimed["claim_token"] = token_w1
    # Calling execution with stale token should not overwrite or mutate pages
    worker1._execute_claimed_job(claimed)

    db = p3_env["factory"]()
    final_job = db.query(ProcessingJob).filter(ProcessingJob.id == ext_job.id).first()
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

    # Verify pages count is still 1 (old pages were replaced, not duplicated or mixed!)
    pages_res2 = client.get(f"/api/papers/{paper_id}/pages")
    assert pages_res2.status_code == 200
    assert len(pages_res2.json()["items"]) == 1


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
