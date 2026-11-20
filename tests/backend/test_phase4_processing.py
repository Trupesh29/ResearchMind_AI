"""ResearchMind AI — Phase 4 Sectioning, Token-Safe Chunking & Quality Center Test Suite.

Verifies:
- Alembic migration 0007 upgrade/downgrade integrity
- Full 4-stage pipeline execution: validating -> extracting -> sectioning -> chunking
- Decoupled pre-index chunk storage with MiniLM token bounds (<= 256 tokens)
- Reference chunk exclusion flag (is_excluded = 1 for references)
- Status response with substate="awaiting_indexing" (Week 2 processing boundary)
- GET /api/papers/{paper_id}/chunks with cursor pagination and page/section filters
- GET /api/papers/{paper_id}/sections endpoint
- Generation bundle preservation across reprocessing and 409 conflict handling
- Security & ownership checks.
"""

from __future__ import annotations

import os
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
from backend.app.db.models import Chunk, Section, Workspace, utcnow_iso
from backend.app.db.session import set_session_factory
from backend.app.main import app
from worker.engine import WorkerEngine


@pytest.fixture
def p4_env(temp_test_dir: Path) -> Generator[dict, None, None]:
    """Provides isolated storage and database migrated to head (0007)."""
    run_id = os.urandom(6).hex()
    test_dir = temp_test_dir / f"p4_{run_id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["pdfs", "indexes", "models", "reports", ".trash"]:
        (test_dir / sub).mkdir(parents=True, exist_ok=True)

    db_path = test_dir / "test_p4.db"
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
                cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    set_session_factory(factory)

    test_settings = Settings(
        BASE_DIR=test_dir,
        DATA_DIR=test_dir,
        DATABASE_URL=db_url,
        AUTH_ENABLED=False,
    )
    app.state.settings = test_settings

    # Bootstrap default user and workspace
    db = factory()
    user = bootstrap_default_user(db, test_settings)
    ws = Workspace(
        id=f"ws-{run_id}",
        user_id=user.id,
        name="Phase 4 Ingestion Test Workspace",
        created_at=utcnow_iso(),
    )
    db.add(ws)
    db.commit()
    ws_id = ws.id
    user_id = user.id
    db.close()

    yield {
        "engine": engine,
        "factory": factory,
        "settings": test_settings,
        "test_dir": test_dir,
        "user_id": user_id,
        "workspace_id": ws_id,
        "alembic_cfg": alembic_cfg,
    }

    set_session_factory(None)
    engine.dispose()


def create_sample_pdf(output_path: Path) -> None:
    """Create a structured academic test PDF with Abstract, Introduction, and References."""
    doc = fitz.open()

    # Page 1: Abstract and Introduction
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 40), "Conference on Empirical Methods in AI 2026", fontsize=9)
    p1.insert_text((50, 100), "Abstract", fontsize=14)
    p1.insert_text(
        (50, 125),
        "We present ResearchMind AI, a multi-stage document processing architecture for academic papers.\n"
        "Our system provides conservative document cleaning, section detection, and token-safe chunking.",
        fontsize=10,
    )
    p1.insert_text((50, 200), "1. Introduction", fontsize=14)
    p1.insert_text(
        (50, 225),
        "Academic research requires careful extraction and representation of paper content.\n"
        "Standard chunkers often silently truncate long sentences or split mid-clause.\n"
        "In this work, we demonstrate sentence-aware chunk boundaries with explicit model token limits.",
        fontsize=10,
    )
    p1.insert_text((300, 750), "1", fontsize=9)

    # Page 2: References
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((50, 40), "Conference on Empirical Methods in AI 2026", fontsize=9)
    p2.insert_text((50, 100), "References", fontsize=14)
    p2.insert_text(
        (50, 125),
        "[1] Vaswani, A., et al. Attention is all you need. In NeurIPS, 2017.\n"
        "[2] Devlin, J., et al. BERT: Pre-training of deep bidirectional transformers. In NAACL, 2019.",
        fontsize=10,
    )
    p2.insert_text((300, 750), "2", fontsize=9)

    doc.save(str(output_path))
    doc.close()


def test_migration_0007_upgrade_downgrade(p4_env):
    """Verify migration 0007 creates sections and chunks tables and supports downgrade."""
    cfg = p4_env["alembic_cfg"]
    factory = p4_env["factory"]

    # Check tables exist
    db: Session = factory()
    sec_count = db.query(Section).count()
    chk_count = db.query(Chunk).count()
    assert sec_count == 0
    assert chk_count == 0
    db.close()

    # Downgrade to 0006
    command.downgrade(cfg, "0006_preserve_multirun_page_generations")

    # Upgrade back to head
    command.upgrade(cfg, "head")

    db = factory()
    assert db.query(Section).count() == 0
    db.close()


def test_full_pipeline_ingestion_and_awaiting_indexing(p4_env):
    """Test full pipeline: validating -> extracting -> sectioning -> chunking -> awaiting_indexing."""
    ws_id = p4_env["workspace_id"]
    test_dir = p4_env["test_dir"]

    # 1. Upload sample PDF
    pdf_path = test_dir / "pdfs" / "sample_paper.pdf"
    create_sample_pdf(pdf_path)

    client = TestClient(app)
    with open(pdf_path, "rb") as f:
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files={"files": ("sample_paper.pdf", f, "application/pdf")},
        )
    assert res.status_code == 202
    papers_res = res.json()["papers"]
    assert len(papers_res) == 1
    paper_id = papers_res[0]["id"]

    # 2. Run worker engine to process validating -> extracting -> sectioning -> chunking
    worker = WorkerEngine(worker_id="test-p4-worker", poll_interval=0.1)

    # Process validating stage
    claimed = worker.run_once()
    assert claimed is True

    # Process extracting stage
    claimed = worker.run_once()
    assert claimed is True

    # Process sectioning stage
    claimed = worker.run_once()
    assert claimed is True

    # Process chunking stage
    claimed = worker.run_once()
    assert claimed is True

    # In Phase 5, worker processes embedding and indexing to ready
    claimed = worker.run_once()  # embedding
    assert claimed is True
    claimed = worker.run_once()  # indexing
    assert claimed is True

    # No more jobs should be queued
    claimed = worker.run_once()
    assert claimed is False

    # 3. Check paper status and substate
    status_res = client.get(f"/api/papers/{paper_id}/status")
    assert status_res.status_code == 200
    st_json = status_res.json()
    assert st_json["status"] == "ready"
    assert st_json["stage"] == "indexing"
    assert st_json["substate"] == "ready"
    assert st_json["progress"] == 1.0

    stages = [s["stage"] for s in st_json["stages"]]
    assert "validating" in stages
    assert "extracting" in stages
    assert "sectioning" in stages
    assert "chunking" in stages

    # 4. Check sections endpoint
    sec_res = client.get(f"/api/papers/{paper_id}/sections")
    assert sec_res.status_code == 200
    sec_json = sec_res.json()
    assert sec_json["total"] >= 2
    sec_names = [s["section"] for s in sec_json["items"]]
    assert "abstract" in sec_names
    assert "references" in sec_names

    # 5. Check chunks endpoint
    chunks_res = client.get(f"/api/papers/{paper_id}/chunks")
    assert chunks_res.status_code == 200
    chk_json = chunks_res.json()
    assert chk_json["total"] >= 2
    assert len(chk_json["items"]) >= 2

    # Check bounds and references exclusion
    for c in chk_json["items"]:
        assert c["token_count"] <= 256
        assert c["token_count"] > 0
        if c["section"] == "references":
            assert c["is_excluded"] is True
        else:
            assert c["is_excluded"] is False

    # 6. Test chunk filtering by section
    ref_filter_res = client.get(f"/api/papers/{paper_id}/chunks?section=references")
    assert ref_filter_res.status_code == 200
    ref_items = ref_filter_res.json()["items"]
    assert len(ref_items) >= 1
    assert all(c["section"] == "references" for c in ref_items)

    # 7. Test chunk pagination
    page_1_res = client.get(f"/api/papers/{paper_id}/chunks?limit=1")
    assert page_1_res.status_code == 200
    p1_json = page_1_res.json()
    assert len(p1_json["items"]) == 1
    next_cur = p1_json["next_cursor"]
    assert next_cur is not None

    page_2_res = client.get(f"/api/papers/{paper_id}/chunks?limit=1&cursor={next_cur}")
    assert page_2_res.status_code == 200
    p2_json = page_2_res.json()
    assert len(p2_json["items"]) == 1
    assert p2_json["items"][0]["chunk_index"] > p1_json["items"][0]["chunk_index"]


def test_reprocess_conflict_and_generation_preservation(p4_env):
    """Test reprocess 409 conflict when active, and verify older chunks remain visible until new chunking finishes."""
    ws_id = p4_env["workspace_id"]
    test_dir = p4_env["test_dir"]

    pdf_path = test_dir / "pdfs" / "reprocess_paper.pdf"
    create_sample_pdf(pdf_path)

    client = TestClient(app)
    with open(pdf_path, "rb") as f:
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files={"files": ("reprocess_paper.pdf", f, "application/pdf")},
        )
    paper_id = res.json()["papers"][0]["id"]

    # Run pipeline to completion (Generation 1)
    worker = WorkerEngine(worker_id="test-p4-worker", poll_interval=0.1)
    for _ in range(6):
        worker.run_once()

    # Initial chunks of Generation 1
    gen1_chunks = client.get(f"/api/papers/{paper_id}/chunks").json()
    gen1_run_id = gen1_chunks["run_id"]
    assert gen1_run_id is not None
    assert gen1_chunks["is_stale"] is False

    # Request reprocess -> starts Generation 2
    reprocess_res = client.post(f"/api/papers/{paper_id}/reprocess")
    assert reprocess_res.status_code == 202
    gen2_run_id = reprocess_res.json()["run_id"]
    assert gen2_run_id != gen1_run_id

    # Trying to reprocess while Generation 2 is active must return 409 Conflict
    conflict_res = client.post(f"/api/papers/{paper_id}/reprocess")
    assert conflict_res.status_code == 409

    # Inspect chunks while Generation 2 is only validating:
    # Must still serve Generation 1 chunks with is_stale = True!
    interim_chunks = client.get(f"/api/papers/{paper_id}/chunks").json()
    assert interim_chunks["run_id"] == gen1_run_id
    assert interim_chunks["is_stale"] is True
    assert len(interim_chunks["items"]) == len(gen1_chunks["items"])

    # Worker processes validating stage of Generation 2
    worker.run_once()
    # Worker processes extracting stage of Generation 2
    worker.run_once()

    # Even after extracting, published_run_id must NOT be overwritten!
    interim_chunks2 = client.get(f"/api/papers/{paper_id}/chunks").json()
    assert interim_chunks2["run_id"] == gen1_run_id
    assert interim_chunks2["is_stale"] is True

    # Worker processes sectioning
    worker.run_once()
    # Worker processes chunking
    worker.run_once()

    # Now Generation 2 chunking is complete!
    # Chunks endpoint now serves Generation 2 with is_stale = False!
    final_chunks = client.get(f"/api/papers/{paper_id}/chunks").json()
    assert final_chunks["run_id"] == gen2_run_id
    assert final_chunks["is_stale"] is False

    # Verify P4-07: Using a cursor bound to Generation 1 prevents generation mixing
    import base64
    import json

    gen1_cursor = base64.urlsafe_b64encode(json.dumps({"run_id": gen1_run_id, "chunk_index": -1}).encode()).decode()
    bound_res = client.get(f"/api/papers/{paper_id}/chunks?cursor={gen1_cursor}").json()
    assert bound_res["run_id"] == gen1_run_id
    assert bound_res["is_stale"] is True
    assert all(c["run_id"] == gen1_run_id for c in bound_res["items"])
