"""ResearchMind AI — Phase 5 Vector Embedding & Index Lifecycle Test Suite.

Verifies:
1. Alembic migration 0011 upgrade and downgrade integrity (embedding_indexes, index_chunks).
2. Token-safe embedding bounds (<= 256 tokens) with strict ValueError rejection (no silent truncation).
3. Embedding vector properties: finite float32, L2 normalization, dimension 384.
4. BM25 sparse index serialization, deserialization, and deterministic scoring.
5. Paired FAISS FlatIP and BM25 atomic publication with matching manifests and SHA-256 checksums.
6. Exclusion of reference chunks (is_excluded == 1) from both dense and sparse indexes.
7. Crash-safe and fail-closed publication: failures preserve prior active index and clean up staging.
8. Query-boundary deletion safety: soft-deleted papers/chunks immediately tombstoned from retrieval.
9. Reprocessing lifecycle: old generation excluded, new generation builds and activates.
10. Full 6-stage worker pipeline execution: validating -> extracting -> sectioning -> chunking -> embedding -> indexing -> ready.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator

import fitz  # PyMuPDF
import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import (
    Chunk,
    EmbeddingIndex,
    IndexChunk,
    Paper,
    ProcessingJob,
    Workspace,
    utcnow_iso,
)
from backend.app.db.session import get_session_factory, set_session_factory
from backend.app.main import app
from backend.app.services.bm25_service import BM25Index
from backend.app.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    embed_texts,
    get_or_compute_generation_embeddings,
    load_generation_embeddings,
    save_generation_embeddings,
    validate_text_for_embedding,
)
from backend.app.services.index_service import (
    CrashBoundaryException,
    PublicationConflictError,
    WorkerFencingViolation,
    build_and_publish_workspace_index,
    cleanup_stale_staging_directories,
    compute_file_sha256,
    get_active_workspace_index,
    search_dense,
    search_sparse,
    verify_index_artifacts_integrity,
)
from backend.app.services.processing_service import get_paper_status_details
from worker.engine import WorkerEngine


@pytest.fixture
def p5_env(temp_test_dir: Path) -> Generator[dict, None, None]:
    """Provides isolated storage and disposable database migrated to head (0011)."""
    run_id = os.urandom(6).hex()
    test_dir = temp_test_dir / f"p5_{run_id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["pdfs", "indexes", "models", "reports", "embeddings", ".trash"]:
        (test_dir / sub).mkdir(parents=True, exist_ok=True)

    db_path = test_dir / "test_p5.db"
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

    old_session_factory = get_session_factory()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    set_session_factory(factory)

    test_settings = Settings(
        BASE_DIR=test_dir,
        DATA_DIR=test_dir,
        DATABASE_URL=db_url,
        AUTH_ENABLED=False,
    )
    app.state.settings = test_settings

    db = factory()
    user = bootstrap_default_user(db, test_settings)
    ws = Workspace(
        id=f"ws-{run_id}",
        user_id=user.id,
        name="Phase 5 Index Lifecycle Test Workspace",
        created_at=utcnow_iso(),
    )
    db.add(ws)
    db.commit()
    ws_id = ws.id
    user_id = user.id
    db.close()

    try:
        yield {
            "engine": engine,
            "factory": factory,
            "settings": test_settings,
            "test_dir": test_dir,
            "workspace_id": ws_id,
            "user_id": user_id,
            "db_url": db_url,
            "alembic_cfg": alembic_cfg,
        }
    finally:
        engine.dispose()
        set_session_factory(old_session_factory)


def _create_sample_pdf(path: Path, title: str = "Attention and Transformers") -> Path:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        f"{title}\n\nAbstract\nWe propose the Transformer architecture based on attention mechanisms.\n\n"
        "1. Introduction\nRecurrent neural networks have long been the state of the art for sequence modeling.\n"
        "However, recurrent models typically factor computation along the symbol positions of input and output sequences.",
        fontsize=11,
    )
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "2. Architecture\nSelf-attention is an attention mechanism relating different positions of a single sequence.\n\n"
        "References\n[1] Vaswani et al. Attention is All You Need. NeurIPS 2017.",
        fontsize=11,
    )
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# Test 1: Migration 0011 Upgrade & Downgrade Integrity
# ---------------------------------------------------------------------------
def test_migration_0011_upgrade_downgrade(p5_env):
    """Verifies Alembic migration 0011 creates and cleanly reverts versioned index tables."""
    alembic_cfg = p5_env["alembic_cfg"]
    engine = p5_env["engine"]

    with engine.connect() as conn:
        from sqlalchemy import inspect
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert "embedding_indexes" in tables
        assert "index_chunks" in tables

    # Test downgrade to 0010
    command.downgrade(alembic_cfg, "0010_repair_chunk_provenance")
    with engine.connect() as conn:
        from sqlalchemy import inspect
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert "embedding_indexes" not in tables
        assert "index_chunks" not in tables

    # Test re-upgrade to head
    command.upgrade(alembic_cfg, "head")
    with engine.connect() as conn:
        from sqlalchemy import inspect
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert "embedding_indexes" in tables
        assert "index_chunks" in tables


# ---------------------------------------------------------------------------
# Test 2: Token Limit Validation (No Silent Truncation)
# ---------------------------------------------------------------------------
def test_embedding_token_limit_validation():
    """Verifies texts within 256 tokens pass and texts exceeding 256 tokens raise ValueError."""
    valid_text = "Attention mechanisms have become an integral part of sequence modeling."
    token_count = validate_text_for_embedding(valid_text)
    assert 0 < token_count <= 256

    # 300 words of distinct text will exceed 256 subword tokens
    long_text = " ".join([f"token_{i}" for i in range(300)])
    with pytest.raises(ValueError, match="exceeds model sequence limit of 256 tokens"):
        validate_text_for_embedding(long_text)


# ---------------------------------------------------------------------------
# Test 3: Embedding Vectors Finite & L2 Normalized
# ---------------------------------------------------------------------------
def test_embedding_vectors_finite_and_l2_normalized():
    """Verifies computed embeddings are float32, finite, dimension 384, and L2 normalized."""
    texts = [
        "Self-attention connects all pairs of positions in a sequence.",
        "Deep learning models require careful initialization and optimization.",
    ]
    vectors = embed_texts(texts)
    assert vectors.shape == (2, 384)
    assert vectors.dtype == np.float32
    assert np.all(np.isfinite(vectors))

    # Norms must equal 1.0 (within float32 precision)
    norms = np.linalg.norm(vectors, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)


# ---------------------------------------------------------------------------
# Test 4: Generation Embedding Cache
# ---------------------------------------------------------------------------
def test_generation_embedding_cache(p5_env):
    """Verifies embedding cache stores and reloads generation vectors idempotently."""
    data_dir = p5_env["test_dir"]
    paper_id = "test-paper-1"
    run_id = "run-gen-1"

    chunks = [
        {"id": "c1", "text": "First chunk text about neural networks."},
        {"id": "c2", "text": "Second chunk text about attention mechanisms."},
    ]

    # First computation writes cache
    vecs1, ids1 = get_or_compute_generation_embeddings(data_dir, paper_id, run_id, chunks)
    assert len(ids1) == 2
    assert vecs1.shape == (2, 384)

    cache_file = data_dir / "embeddings" / paper_id / f"{run_id}_vectors.npy"
    meta_file = data_dir / "embeddings" / paper_id / f"{run_id}_meta.json"
    assert cache_file.exists()
    assert meta_file.exists()

    # Second computation reads from cache
    vecs2, ids2 = get_or_compute_generation_embeddings(data_dir, paper_id, run_id, chunks)
    assert ids1 == ids2
    np.testing.assert_array_equal(vecs1, vecs2)


# ---------------------------------------------------------------------------
# Test 5: BM25 Serialization & Querying
# ---------------------------------------------------------------------------
def test_bm25_serialization_and_querying(p5_env):
    """Verifies BM25 index builds, saves, loads, and scores queries deterministically."""
    data_dir = p5_env["test_dir"]
    chunks = [
        {"id": "c1", "text": "The transformer model utilizes multi-head attention."},
        {"id": "c2", "text": "Convolutional networks process grid-structured data like images."},
        {"id": "c3", "text": "Attention mechanisms allow dynamic routing of representations."},
    ]

    index = BM25Index()
    index.build(chunks)
    assert index.doc_count == 3

    # Query matching c1 and c3
    results = index.search("multi-head attention", top_k=2)
    assert len(results) == 2
    assert results[0][0] == 0  # c1 is at index 0
    assert index.doc_ids[results[0][0]] == "c1"

    # Save and reload
    save_path = data_dir / "bm25_test.json"
    index.save(save_path)
    assert save_path.exists()

    loaded_index = BM25Index.load(save_path)
    assert loaded_index.doc_count == 3
    results_loaded = loaded_index.search("multi-head attention", top_k=2)
    assert results == results_loaded


# ---------------------------------------------------------------------------
# Test 6: Paired Atomic Publication & Reference Chunk Exclusion
# ---------------------------------------------------------------------------
def test_build_and_publish_paired_workspace_index(p5_env):
    """Verifies publishing creates FAISS FlatIP and BM25 artifacts, excluding reference chunks."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    db = factory()
    # Create a paper with 2 accepted chunks: 1 body chunk, 1 reference chunk
    paper = Paper(
        id="p-index-1",
        workspace_id=ws_id,
        original_filename="test.pdf",
        storage_path="pdfs/test.pdf",
        sha256="sha256:test1",
        size_bytes=1000,
        status="processing",
        published_run_id="run-1",
        current_run_id="run-1",
        created_at=utcnow_iso(),
    )
    db.add(paper)

    c1 = Chunk(
        id="chk-body-1",
        paper_id=paper.id,
        run_id="run-1",
        chunk_index=0,
        page_start=1,
        page_end=1,
        section="Abstract",
        text="Transformers replace recurrence with attention mechanisms completely.",
        token_count=10,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    c2 = Chunk(
        id="chk-ref-1",
        paper_id=paper.id,
        run_id="run-1",
        chunk_index=1,
        page_start=2,
        page_end=2,
        section="References",
        text="[1] Vaswani et al. Attention is All You Need. NeurIPS 2017.",
        token_count=12,
        is_excluded=1,  # Must be excluded from index
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add_all([c1, c2])
    db.commit()

    # Publish index
    index_record = build_and_publish_workspace_index(db, ws_id)
    assert index_record is not None
    assert index_record.status == "active"
    assert index_record.version == 1
    assert index_record.chunk_count == 1  # Only c1, c2 excluded

    # Verify disk artifacts
    index_dir = data_dir / "indexes" / ws_id / "v1"
    assert (index_dir / "index.faiss").exists()
    assert (index_dir / "bm25.json").exists()
    assert (index_dir / "manifest.json").exists()

    with open(index_dir / "manifest.json") as f:
        manifest = json.load(f)
    assert manifest["chunk_count"] == 1
    assert manifest["chunks"][0]["chunk_id"] == "chk-body-1"
    assert "faiss_sha256" in manifest
    assert "bm25_sha256" in manifest

    # Verify paper transitioned to ready
    db.refresh(paper)
    assert paper.status == "ready"

    # Verify membership mapping in DB
    mappings = db.query(IndexChunk).filter(IndexChunk.index_id == index_record.id).all()
    assert len(mappings) == 1
    assert mappings[0].chunk_id == "chk-body-1"
    assert mappings[0].faiss_id == 0

    db.close()


# ---------------------------------------------------------------------------
# Test 7: Fail-Closed Boundaries & Crash Safety
# ---------------------------------------------------------------------------
def test_fail_closed_and_crash_safety(p5_env):
    """Verifies failures during index building do not switch active pointer or leave corrupted state."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    db = factory()
    paper = Paper(
        id="p-crash-1",
        workspace_id=ws_id,
        original_filename="crash.pdf",
        storage_path="pdfs/crash.pdf",
        sha256="sha256:crash1",
        size_bytes=1000,
        status="processing",
        published_run_id="run-1",
        current_run_id="run-1",
        created_at=utcnow_iso(),
    )
    db.add(paper)
    c1 = Chunk(
        id="chk-valid-1",
        paper_id=paper.id,
        run_id="run-1",
        chunk_index=0,
        page_start=1,
        page_end=1,
        section="Introduction",
        text="Valid chunk for index version 1.",
        token_count=8,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add(c1)
    db.commit()

    # Step 1: Successfully publish v1
    v1 = build_and_publish_workspace_index(db, ws_id)
    assert v1.version == 1
    assert v1.status == "active"

    # Step 2: Simulate failure during v2 build (add a chunk that will fail embedding token validation)
    c_bad = Chunk(
        id="chk-bad-token",
        paper_id=paper.id,
        run_id="run-1",
        chunk_index=1,
        page_start=2,
        page_end=2,
        section="Corrupt",
        text=" ".join([f"overflow_{i}" for i in range(350)]),  # > 256 tokens!
        token_count=350,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add(c_bad)
    db.commit()

    # Publication of v2 must fail
    with pytest.raises(ValueError, match="exceeds model sequence limit"):
        build_and_publish_workspace_index(db, ws_id)

    # Assert active index is STILL v1
    active_idx = get_active_workspace_index(db, ws_id)
    assert active_idx is not None
    assert active_idx.id == v1.id
    assert active_idx.version == 1
    assert active_idx.status == "active"

    # Assert staging directory v2.tmp was cleaned up
    tmp_dir = data_dir / "indexes" / ws_id / "v2.tmp"
    assert not tmp_dir.exists()

    db.close()


# ---------------------------------------------------------------------------
# Test 8: Query-Boundary Deletion Safety (Tombstone Exclusion)
# ---------------------------------------------------------------------------
def test_query_boundary_deletion_safety(p5_env):
    """Verifies soft-deleted papers/chunks are immediately excluded from dense and sparse retrieval."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]

    db = factory()
    paper = Paper(
        id="p-delete-1",
        workspace_id=ws_id,
        original_filename="delete_test.pdf",
        storage_path="pdfs/delete_test.pdf",
        sha256="sha256:delete1",
        size_bytes=1000,
        status="processing",
        published_run_id="run-del",
        current_run_id="run-del",
        created_at=utcnow_iso(),
    )
    db.add(paper)
    c1 = Chunk(
        id="chk-del-1",
        paper_id=paper.id,
        run_id="run-del",
        chunk_index=0,
        page_start=1,
        page_end=1,
        section="Abstract",
        text="Quantum key distribution offers provable cryptographic security bounds.",
        token_count=9,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add(c1)
    db.commit()

    build_and_publish_workspace_index(db, ws_id)

    # Dense and sparse queries find the chunk
    dense_res = search_dense(db, ws_id, "cryptographic security", top_k=5)
    sparse_res = search_sparse(db, ws_id, "cryptographic security", top_k=5)
    assert len(dense_res) == 1
    assert len(sparse_res) == 1
    assert dense_res[0]["chunk_id"] == "chk-del-1"
    assert sparse_res[0]["chunk_id"] == "chk-del-1"

    # Soft-delete paper / tombstone chunk
    c1.is_deleted = 1
    db.commit()

    # Query boundary must immediately filter out tombstoned chunk
    dense_after = search_dense(db, ws_id, "cryptographic security", top_k=5)
    sparse_after = search_sparse(db, ws_id, "cryptographic security", top_k=5)
    assert len(dense_after) == 0
    assert len(sparse_after) == 0

    # Also test paper deletion boundary
    c1.is_deleted = 0
    db.delete(paper)
    db.commit()

    dense_after_del = search_dense(db, ws_id, "cryptographic security", top_k=5)
    sparse_after_del = search_sparse(db, ws_id, "cryptographic security", top_k=5)
    assert len(dense_after_del) == 0
    assert len(sparse_after_del) == 0

    db.close()


# ---------------------------------------------------------------------------
# Test 9: Reprocessing Lifecycle & Generation Isolation
# ---------------------------------------------------------------------------
def test_reprocessing_generation_isolation(p5_env):
    """Verifies reprocessing excludes obsolete chunks and activates replacement generation."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]

    db = factory()
    paper = Paper(
        id="p-reproc-1",
        workspace_id=ws_id,
        original_filename="reproc.pdf",
        storage_path="pdfs/reproc.pdf",
        sha256="sha256:reproc1",
        size_bytes=1000,
        status="processing",
        published_run_id="run-old",
        current_run_id="run-old",
        created_at=utcnow_iso(),
    )
    db.add(paper)
    c_old = Chunk(
        id="chk-old-gen",
        paper_id=paper.id,
        run_id="run-old",
        chunk_index=0,
        page_start=1,
        page_end=1,
        section="Legacy",
        text="Old generation text describing preliminary convolutional results.",
        token_count=9,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add(c_old)
    db.commit()

    v1 = build_and_publish_workspace_index(db, ws_id)
    assert v1.version == 1

    # Simulate reprocessing: paper current_run_id changes to run-new
    paper.current_run_id = "run-new"
    paper.status = "processing"
    c_new = Chunk(
        id="chk-new-gen",
        paper_id=paper.id,
        run_id="run-new",
        chunk_index=0,
        page_start=1,
        page_end=1,
        section="Updated",
        text="New generation text presenting state of the art transformer architecture.",
        token_count=10,
        is_excluded=0,
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        created_at=utcnow_iso(),
    )
    db.add(c_new)
    # New run published
    paper.published_run_id = "run-new"
    db.commit()

    v2 = build_and_publish_workspace_index(db, ws_id)
    assert v2.version == 2
    assert v2.status == "active"

    db.refresh(v1)
    assert v1.status == "retired"

    # Search must find new chunk and not old chunk
    dense_res = search_dense(db, ws_id, "transformer architecture", top_k=5)
    assert len(dense_res) == 1
    assert dense_res[0]["chunk_id"] == "chk-new-gen"

    db.close()


# ---------------------------------------------------------------------------
# Test 10: Full 6-Stage Persistent Worker Pipeline to Ready
# ---------------------------------------------------------------------------
def test_full_worker_pipeline_to_ready(p5_env):
    """Ingests a real PDF through all 6 worker stages until paper becomes ready."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    user_id = p5_env["user_id"]
    data_dir = p5_env["test_dir"]

    pdf_path = data_dir / "pdfs" / "attention_test.pdf"
    _create_sample_pdf(pdf_path, title="Attention and Transformer Networks")

    client = TestClient(app)
    with open(pdf_path, "rb") as f:
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files={"files": ("attention_test.pdf", f, "application/pdf")},
        )
    assert res.status_code == 202
    papers_res = res.json()["papers"]
    assert len(papers_res) == 1
    paper_id = papers_res[0]["id"]

    # Run worker until all stages complete
    worker = WorkerEngine(worker_id="test-p5-worker", poll_interval=0.1)

    # Process all 6 stages
    max_steps = 15
    for _ in range(max_steps):
        processed = worker.run_once()
        if not processed:
            break

    db = factory()
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    assert paper is not None
    assert paper.status == "ready"
    assert paper.published_run_id is not None
    run_id = paper.published_run_id

    # Assert paper reached ready
    assert paper.status == "ready"
    assert paper.published_run_id == run_id

    # Check status response details
    status_details = get_paper_status_details(db, user_id, paper.id)
    assert status_details.status == "ready"
    assert status_details.stage == "indexing"
    assert status_details.substate == "ready"
    assert status_details.progress == 1.0

    # Verify active index exists and contains chunks
    active_idx = get_active_workspace_index(db, ws_id)
    assert active_idx is not None
    assert active_idx.status == "active"
    assert active_idx.chunk_count > 0

    # Query internal dense probe
    dense_matches = search_dense(db, ws_id, "Transformer architecture", top_k=3)
    assert len(dense_matches) > 0
    assert "transformer" in dense_matches[0]["text"].lower()

    db.close()


# ---------------------------------------------------------------------------
# Test 11: Embedding Cache Hardening & Rejection of Corrupt/Incompatible Data (P5-R4)
# ---------------------------------------------------------------------------
def test_embedding_cache_corrupt_data_rejected(p5_env):
    """Verifies that corrupted, tampered, non-finite, or incompatible cached embeddings fail closed (return None)."""
    data_dir = p5_env["test_dir"]
    paper_id = "paper-cache-test"
    run_id = "run-cache-test"

    chunks = [
        {"id": "c1", "text": "Self-attention mechanism in Transformers."},
        {"id": "c2", "text": "Positional encodings inject token order."},
    ]
    texts = [c["text"] for c in chunks]
    chunk_ids = [c["id"] for c in chunks]

    # 1. Normal save
    vecs = embed_texts(texts)
    vec_path, meta_path = save_generation_embeddings(
        paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir
    )
    assert vec_path.exists()
    assert meta_path.exists()

    # Verify normal load works
    loaded = load_generation_embeddings(paper_id, run_id, data_dir=data_dir, expected_chunk_ids=chunk_ids)
    assert loaded is not None
    loaded_ids, loaded_vecs = loaded
    assert loaded_ids == chunk_ids
    assert loaded_vecs.shape == (2, EMBEDDING_DIMENSION)

    # 2. Corrupted vector file (checksum mismatch)
    with open(vec_path, "wb") as f:
        f.write(b"corrupted bytes invalid npy")
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # Resave valid
    save_generation_embeddings(paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir)

    # 3. Model revision mismatch
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["model_revision"] = "wrong_revision_hash_12345"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # 4. Dimension mismatch
    meta["model_revision"] = EMBEDDING_MODEL_REVISION
    meta["dimension"] = 512
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # 5. Non-finite values (NaN / Inf)
    nan_vecs = vecs.copy()
    nan_vecs[0, 0] = np.nan
    save_generation_embeddings(paper_id, "run-nan", chunk_ids, nan_vecs, data_dir=data_dir)
    assert load_generation_embeddings(paper_id, "run-nan", data_dir=data_dir) is None

    # 6. Unnormalized vectors
    unnorm_vecs = vecs.copy() * 5.0
    save_generation_embeddings(paper_id, "run-unnorm", chunk_ids, unnorm_vecs, data_dir=data_dir)
    assert load_generation_embeddings(paper_id, "run-unnorm", data_dir=data_dir) is None


# ---------------------------------------------------------------------------
# Test 12: Stale Worker Fencing & Publication Rejection (P5-R1)
# ---------------------------------------------------------------------------
def test_stale_worker_publication_fencing_rejection(p5_env):
    """Verifies that a worker attempting to publish with an expired/superseded claim token is rejected."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    db = factory()
    now = utcnow_iso()

    # Create paper
    paper = Paper(
        id="paper-fencing-test",
        workspace_id=ws_id,
        original_filename="fencing.pdf",
        storage_path=str(data_dir / "pdfs" / "fencing.pdf"),
        sha256="dummy_hash_fencing",
        size_bytes=1024,
        status="processing",
        current_run_id="run-fence-1",
        created_at=now,
        updated_at=now,
    )
    db.add(paper)
    chunk = Chunk(
        id="c-fence-1",
        paper_id=paper.id,
        run_id="run-fence-1",
        chunk_index=0,
        text="A test chunk for fencing token validation.",
        token_count=10,
        section="Intro",
        page_start=1,
        page_end=1,
        is_excluded=0,
        is_deleted=0,
        created_at=now,
    )
    db.add(chunk)

    job = ProcessingJob(
        id="job-fence-1",
        paper_id=paper.id,
        run_id="run-fence-1",
        stage="indexing",
        status="running",
        claim_token="valid-token-alpha",
        attempt=1,
        created_at=now,
    )
    db.add(job)
    db.commit()

    # 1. Stale token attempt: token does not match job.claim_token
    with pytest.raises(WorkerFencingViolation):
        build_and_publish_workspace_index(
            db,
            workspace_id=ws_id,
            target_paper_id=paper.id,
            target_run_id="run-fence-1",
            data_dir=data_dir,
            job_id=job.id,
            claim_token="stale-invalid-token",
        )

    # Verify no index was published
    assert get_active_workspace_index(db, ws_id) is None
    paper_check = db.query(Paper).filter(Paper.id == paper.id).first()
    assert paper_check.status == "processing"
    assert paper_check.published_run_id is None

    # 2. Valid token attempt succeeds
    idx = build_and_publish_workspace_index(
        db,
        workspace_id=ws_id,
        target_paper_id=paper.id,
        target_run_id="run-fence-1",
        data_dir=data_dir,
        job_id=job.id,
        claim_token="valid-token-alpha",
    )
    assert idx is not None
    assert idx.status == "active"
    paper_check = db.query(Paper).filter(Paper.id == paper.id).first()
    assert paper_check.status == "ready"
    assert paper_check.published_run_id == "run-fence-1"

    # Verify job was marked succeeded atomically
    job_check = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    assert job_check.status == "succeeded"

    db.close()


# ---------------------------------------------------------------------------
# Test 13: Reprocessing Paper Isolation — Not Prematurely Marked Ready (P5-R3)
# ---------------------------------------------------------------------------
def test_reprocessing_paper_isolation_not_marked_ready(p5_env):
    """Verifies that publishing an index for Paper A does NOT mark reprocessing Paper B as ready."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    db = factory()
    now = utcnow_iso()

    # Paper A: about to publish run A
    paper_a = Paper(
        id="paper-a-iso",
        workspace_id=ws_id,
        original_filename="a.pdf",
        storage_path="a.pdf",
        sha256="hash_a",
        size_bytes=100,
        status="processing",
        current_run_id="run-a-1",
        created_at=now,
        updated_at=now,
    )
    # Paper B: currently reprocessing
    paper_b = Paper(
        id="paper-b-iso",
        workspace_id=ws_id,
        original_filename="b.pdf",
        storage_path="b.pdf",
        sha256="hash_b",
        size_bytes=100,
        status="processing",
        current_run_id="run-b-2",
        published_run_id="run-b-1",  # previous old run
        created_at=now,
        updated_at=now,
    )
    db.add(paper_a)
    db.add(paper_b)

    db.add(
        Chunk(
            id="c-a-1",
            paper_id=paper_a.id,
            run_id="run-a-1",
            chunk_index=0,
            text="Paper A introduction text.",
            token_count=10,
            section="Intro",
            page_start=1,
            page_end=1,
            is_excluded=0,
            is_deleted=0,
            created_at=now,
        )
    )
    db.add(
        Chunk(
            id="c-b-old",
            paper_id=paper_b.id,
            run_id="run-b-1",
            chunk_index=0,
            text="Paper B old generation text.",
            token_count=10,
            section="Intro",
            page_start=1,
            page_end=1,
            is_excluded=0,
            is_deleted=0,
            created_at=now,
        )
    )
    db.add(
        Chunk(
            id="c-b-new",
            paper_id=paper_b.id,
            run_id="run-b-2",
            chunk_index=0,
            text="Paper B new generation text.",
            token_count=10,
            section="Intro",
            page_start=1,
            page_end=1,
            is_excluded=0,
            is_deleted=0,
            created_at=now,
        )
    )
    db.commit()

    # Publish index for Paper A
    idx = build_and_publish_workspace_index(
        db,
        workspace_id=ws_id,
        target_paper_id=paper_a.id,
        target_run_id="run-a-1",
        data_dir=data_dir,
    )
    assert idx is not None

    # Check statuses
    pa_check = db.query(Paper).filter(Paper.id == paper_a.id).first()
    pb_check = db.query(Paper).filter(Paper.id == paper_b.id).first()

    assert pa_check.status == "ready"
    assert pa_check.published_run_id == "run-a-1"

    # CRITICAL: Paper B must STILL be 'processing' and NOT marked ready!
    assert pb_check.status == "processing"
    assert pb_check.published_run_id == "run-b-1"

    # Index chunks should ONLY contain Paper A's chunks (Paper B was reprocessing so its old generation was not included)
    member_chunks = db.query(IndexChunk).filter(IndexChunk.index_id == idx.id).all()
    member_paper_ids = {mc.paper_id for mc in member_chunks}
    assert paper_a.id in member_paper_ids
    assert paper_b.id not in member_paper_ids

    db.close()


# ---------------------------------------------------------------------------
# Test 14: Artifact Integrity Verification & Fail-Closed Behavior (P5-R6)
# ---------------------------------------------------------------------------
def test_artifact_integrity_verification_fail_closed(p5_env):
    """Verifies that modified/corrupted physical artifacts fail closed and prevent retrieval."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    db = factory()
    now = utcnow_iso()

    paper = Paper(
        id="paper-integ-test",
        workspace_id=ws_id,
        original_filename="integ.pdf",
        storage_path="integ.pdf",
        sha256="hash_integ",
        size_bytes=100,
        status="processing",
        current_run_id="run-integ-1",
        created_at=now,
        updated_at=now,
    )
    db.add(paper)
    db.add(
        Chunk(
            id="c-integ-1",
            paper_id=paper.id,
            run_id="run-integ-1",
            chunk_index=0,
            text="Integrity verification test chunk text.",
            token_count=10,
            section="Intro",
            page_start=1,
            page_end=1,
            is_excluded=0,
            is_deleted=0,
            created_at=now,
        )
    )
    db.commit()

    idx = build_and_publish_workspace_index(
        db,
        workspace_id=ws_id,
        target_paper_id=paper.id,
        target_run_id="run-integ-1",
        data_dir=data_dir,
    )
    assert idx is not None
    assert verify_index_artifacts_integrity(idx, db=db) is True

    # Search works before corruption
    dense_results = search_dense(db, ws_id, "Integrity verification", top_k=5)
    assert len(dense_results) > 0
    sparse_results = search_sparse(db, ws_id, "verification", top_k=5)
    assert len(sparse_results) > 0

    # Corrupt FAISS file
    with open(idx.faiss_path, "ab") as f:
        f.write(b"tampered byte append")

    # Integrity check must fail closed
    assert verify_index_artifacts_integrity(idx, db=db) is False

    # Queries must fail closed and return []
    assert search_dense(db, ws_id, "Integrity verification", top_k=5) == []

    db.close()


# ---------------------------------------------------------------------------
# Test 15: Concurrent Workspace Staging & Ownership-Aware Cleanup (A3)
# ---------------------------------------------------------------------------
def test_ownership_aware_staging_cleanup_and_traversal_safety(p5_env):
    """Verifies that active staging attempts with valid TTL are preserved,
    expired staging attempts are cleaned up, and path traversal attempts raise ValueError.
    """
    import time

    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    ws_base = data_dir / "indexes" / ws_id
    ws_base.mkdir(parents=True, exist_ok=True)

    # 1. Create active staging directory with unexpired heartbeat
    active_dir = ws_base / "v2_prep_active1.tmp"
    active_dir.mkdir(parents=True, exist_ok=True)
    with open(active_dir / "staging_meta.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "build_id": "active1",
                "workspace_id": ws_id,
                "target_version": 2,
                "created_at": time.time(),
                "heartbeat_at": time.time(),
                "ttl_seconds": 300.0,
            },
            f,
        )

    # 2. Create expired staging directory
    expired_dir = ws_base / "v2_prep_expired1.tmp"
    expired_dir.mkdir(parents=True, exist_ok=True)
    with open(expired_dir / "staging_meta.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "build_id": "expired1",
                "workspace_id": ws_id,
                "target_version": 2,
                "created_at": time.time() - 200,
                "heartbeat_at": time.time() - 200,
                "ttl_seconds": 60.0,
            },
            f,
        )

    # 3. Create legacy unmanaged .tmp directory with old mtime
    unmanaged_dir = ws_base / "v2_prep_legacy.tmp"
    unmanaged_dir.mkdir(parents=True, exist_ok=True)
    old_time = time.time() - 150
    os.utime(unmanaged_dir, (old_time, old_time))

    # 4. Final version directory
    (ws_base / "v1").mkdir(parents=True, exist_ok=True)

    # Run cleanup
    removed = cleanup_stale_staging_directories(ws_id, data_dir=data_dir, max_age_seconds=60.0)

    # Expired and legacy unmanaged must be removed, active must be PRESERVED
    assert removed == 2
    assert active_dir.exists(), "Active staging directory must be preserved!"
    assert not expired_dir.exists(), "Expired staging directory must be pruned!"
    assert not unmanaged_dir.exists(), "Old unmanaged staging directory must be pruned!"
    assert (ws_base / "v1").exists(), "Final version directory must be preserved!"


# ---------------------------------------------------------------------------
# Test 16: Competing Worker Publication Serialization (A1)
# ---------------------------------------------------------------------------
def test_concurrent_competing_workers_publication_serialization(p5_env):
    """Executes two independent sessions/workers attempting concurrent publication
    from an overlapping active-index state.

    Proves:
    - Independent staging directories (never shared)
    - One worker's preparation cannot overwrite or delete the other worker's staging or final artifacts
    - Losing worker detects CAS version advancement, discards only its own staging, and retries
    - Accepted generations from both papers eventually appear in one valid active workspace snapshot
    - Exactly one coherent active version remains with matching FAISS, BM25, manifest, and DB membership
    """
    import threading

    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    # 1. Setup two papers in the workspace with chunks
    now = utcnow_iso()
    with factory() as db:
        pa = Paper(
            id="comp-paper-a",
            workspace_id=ws_id,
            original_filename="paper_a.pdf",
            storage_path="paper_a.pdf",
            sha256="hash_a",
            size_bytes=100,
            status="processing",
            current_run_id="run-a-1",
            created_at=now,
            updated_at=now,
        )
        pb = Paper(
            id="comp-paper-b",
            workspace_id=ws_id,
            original_filename="paper_b.pdf",
            storage_path="paper_b.pdf",
            sha256="hash_b",
            size_bytes=100,
            status="processing",
            current_run_id="run-b-1",
            created_at=now,
            updated_at=now,
        )
        db.add_all([pa, pb])
        db.add(
            Chunk(
                id="c-a-1",
                paper_id="comp-paper-a",
                run_id="run-a-1",
                chunk_index=0,
                text="Attention mechanism and transformer networks paper A.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.add(
            Chunk(
                id="c-b-1",
                paper_id="comp-paper-b",
                run_id="run-b-1",
                chunk_index=0,
                text="Convolutional neural networks and residual learning paper B.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

    # Synchronization primitives
    worker_1_prepared = threading.Event()
    worker_2_prepared = threading.Event()
    release_worker_1 = threading.Event()
    release_worker_2 = threading.Event()

    worker_1_staging = []
    worker_2_staging = []
    results = {}
    errors = {}

    def run_worker_1():
        try:
            with factory() as db1:
                def pause_hook(stg, v):
                    worker_1_staging.append(stg)
                    worker_1_prepared.set()
                    release_worker_1.wait(timeout=10.0)

                idx = build_and_publish_workspace_index(
                    db1,
                    workspace_id=ws_id,
                    target_paper_id="comp-paper-a",
                    target_run_id="run-a-1",
                    data_dir=data_dir,
                    _pause_hook=pause_hook,
                )
                results["w1_version"] = idx.version
                results["w1_id"] = idx.id
        except Exception as e:
            errors["w1"] = e

    def run_worker_2():
        try:
            with factory() as db2:
                attempts = [0]

                def pause_hook(stg, v):
                    attempts[0] += 1
                    if attempts[0] == 1:
                        worker_2_staging.append(stg)
                        worker_2_prepared.set()
                        release_worker_2.wait(timeout=10.0)

                idx = build_and_publish_workspace_index(
                    db2,
                    workspace_id=ws_id,
                    target_paper_id="comp-paper-b",
                    target_run_id="run-b-1",
                    data_dir=data_dir,
                    _pause_hook=pause_hook,
                )
                results["w2_version"] = idx.version
                results["w2_id"] = idx.id
        except Exception as e:
            errors["w2"] = e

    t1 = threading.Thread(target=run_worker_1)
    t2 = threading.Thread(target=run_worker_2)

    t1.start()
    t2.start()

    # Wait for both workers to finish artifact preparation
    assert worker_1_prepared.wait(timeout=15.0), "Worker 1 failed to prepare artifacts in time"
    assert worker_2_prepared.wait(timeout=15.0), "Worker 2 failed to prepare artifacts in time"

    # Prove that both workers used distinct staging directories
    assert len(worker_1_staging) == 1
    assert len(worker_2_staging) == 1
    assert worker_1_staging[0] != worker_2_staging[0]
    assert worker_1_staging[0].exists()
    assert worker_2_staging[0].exists()

    # Release worker 1 first to complete publication of version 1
    release_worker_1.set()
    t1.join(timeout=10.0)
    assert "w1" not in errors, f"Worker 1 failed: {errors.get('w1')}"
    assert results.get("w1_version") == 1

    # Now release worker 2; it will encounter CAS version advancement (v1 published),
    # discard its staging directory v1_prep_*.tmp, retry, and publish v2
    release_worker_2.set()
    t2.join(timeout=15.0)
    assert "w2" not in errors, f"Worker 2 failed: {errors.get('w2')}"
    assert results.get("w2_version") == 2

    # Verification on final database and filesystem state
    with factory() as db_check:
        active_idx = get_active_workspace_index(db_check, ws_id)
        assert active_idx is not None
        assert active_idx.version == 2

        # Both papers must be ready
        p_a = db_check.query(Paper).filter(Paper.id == "comp-paper-a").first()
        p_b = db_check.query(Paper).filter(Paper.id == "comp-paper-b").first()
        assert p_a.status == "ready"
        assert p_a.published_run_id == "run-a-1"
        assert p_b.status == "ready"
        assert p_b.published_run_id == "run-b-1"

        # Check membership: version 2 contains both papers
        chunks = db_check.query(IndexChunk).filter(IndexChunk.index_id == active_idx.id).all()
        chunk_paper_ids = {c.paper_id for c in chunks}
        assert "comp-paper-a" in chunk_paper_ids
        assert "comp-paper-b" in chunk_paper_ids
        assert len(chunks) == 2

        # Artifact integrity verification
        assert verify_index_artifacts_integrity(active_idx, db=db_check) is True

        # Ensure exactly one active index exists for workspace
        active_count = (
            db_check.query(EmbeddingIndex)
            .filter(EmbeddingIndex.workspace_id == ws_id, EmbeddingIndex.status == "active")
            .count()
        )
        assert active_count == 1


# ---------------------------------------------------------------------------
# Test 17: Competing Workers Negative Control (Pre-Repair Conflict) (A1)
# ---------------------------------------------------------------------------
def test_competing_workers_negative_control_pre_repair_conflict(p5_env):
    """Verifies that an attempt to overwrite an existing final directory raises
    PublicationConflictError and never removes or replaces the existing final directory.
    """
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    now = utcnow_iso()
    with factory() as db:
        p = Paper(
            id="neg-paper-1",
            workspace_id=ws_id,
            original_filename="neg.pdf",
            storage_path="neg.pdf",
            sha256="hash_neg",
            size_bytes=100,
            status="processing",
            current_run_id="run-neg-1",
            created_at=now,
            updated_at=now,
        )
        db.add(p)
        db.add(
            Chunk(
                id="c-neg-1",
                paper_id="neg-paper-1",
                run_id="run-neg-1",
                chunk_index=0,
                text="Negative control chunk text.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

        # Build initial version 1
        idx1 = build_and_publish_workspace_index(
            db,
            workspace_id=ws_id,
            target_paper_id="neg-paper-1",
            target_run_id="run-neg-1",
            data_dir=data_dir,
        )
        assert idx1.version == 1

        # Simulate collision: final v2 directory already exists unexpectedly
        ws_base = data_dir / "indexes" / ws_id
        v2_dir = ws_base / "v2"
        v2_dir.mkdir(parents=True, exist_ok=True)
        sentinel_file = v2_dir / "sentinel.txt"
        sentinel_file.write_text("must not be overwritten")

        # Adding a new chunk so there are eligible chunks to publish
        db.add(
            Chunk(
                id="c-neg-2",
                paper_id="neg-paper-1",
                run_id="run-neg-1",
                chunk_index=1,
                text="Second negative control chunk.",
                token_count=10,
                section="Body",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

        # Publishing must fail with PublicationConflictError because v2 already exists
        with pytest.raises(Exception) as exc_info:
            build_and_publish_workspace_index(
                db,
                workspace_id=ws_id,
                target_paper_id="neg-paper-1",
                target_run_id="run-neg-1",
                data_dir=data_dir,
                max_retries=1,
            )
        assert "already exists" in str(exc_info.value) or isinstance(exc_info.value, PublicationConflictError)

        # Sentinel file must remain untouched
        assert sentinel_file.exists()
        assert sentinel_file.read_text() == "must not be overwritten"


# ---------------------------------------------------------------------------
# Test 18: Deterministic Crash Boundary Recovery (A4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "boundary",
    [
        "before_artifacts",
        "lease_loss_during_prep",
        "before_slot_acquire",
        "before_promotion",
        "after_promotion",
        "during_commit",
    ],
)
def test_crash_boundaries_preservation_and_recovery(p5_env, boundary):
    """Injects failures across all publication crash boundaries and verifies that:
    - Previous active index remains intact
    - Target paper is not marked ready without valid published index membership
    - Failed staging and uncommitted final directories are cleaned up
    """
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    now = utcnow_iso()
    with factory() as db:
        # Initial baseline paper and index
        base_paper = Paper(
            id=f"base-paper-{boundary}",
            workspace_id=ws_id,
            original_filename="base.pdf",
            storage_path="base.pdf",
            sha256=f"hash_base_{boundary}",
            size_bytes=100,
            status="processing",
            current_run_id="run-base-1",
            created_at=now,
            updated_at=now,
        )
        db.add(base_paper)
        db.add(
            Chunk(
                id=f"c-base-{boundary}",
                paper_id=base_paper.id,
                run_id="run-base-1",
                chunk_index=0,
                text="Baseline stable chunk text.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

        v1_idx = build_and_publish_workspace_index(
            db,
            workspace_id=ws_id,
            target_paper_id=base_paper.id,
            target_run_id="run-base-1",
            data_dir=data_dir,
        )
        assert v1_idx.version == 1

        # Now introduce a new paper that will crash during publication
        crash_paper = Paper(
            id=f"crash-paper-{boundary}",
            workspace_id=ws_id,
            original_filename="crash.pdf",
            storage_path="crash.pdf",
            sha256=f"hash_crash_{boundary}",
            size_bytes=100,
            status="processing",
            current_run_id="run-crash-1",
            created_at=now,
            updated_at=now,
        )
        db.add(crash_paper)
        db.add(
            Chunk(
                id=f"c-crash-{boundary}",
                paper_id=crash_paper.id,
                run_id="run-crash-1",
                chunk_index=0,
                text="Crash test chunk text.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

        # Attempt build with injected crash boundary
        with pytest.raises((CrashBoundaryException, WorkerFencingViolation)):
            build_and_publish_workspace_index(
                db,
                workspace_id=ws_id,
                target_paper_id=crash_paper.id,
                target_run_id="run-crash-1",
                data_dir=data_dir,
                max_retries=1,
                _crash_boundary=boundary,
            )

        # Invariant checks:
        # 1. Active index must STILL be v1
        act = get_active_workspace_index(db, ws_id)
        assert act is not None
        assert act.version == 1
        assert act.id == v1_idx.id

        # 2. Crash paper must NOT be marked ready
        p_check = db.query(Paper).filter(Paper.id == crash_paper.id).first()
        assert p_check.status == "processing"
        assert p_check.published_run_id is None

        # 3. v2 final directory must NOT exist on disk
        v2_dir = data_dir / "indexes" / ws_id / "v2"
        assert not v2_dir.exists(), f"Uncommitted v2 directory must not remain on disk for boundary {boundary}"


# ---------------------------------------------------------------------------
# Test 19: Cache & Artifact Negative Controls (A5)
# ---------------------------------------------------------------------------
def test_embedding_cache_negative_controls_extended(p5_env):
    """Verifies that all embedding cache tampering/corruption scenarios fail closed (return None)."""
    data_dir = p5_env["test_dir"]
    paper_id = "paper-neg-cache"
    run_id = "run-neg-cache"

    chunks = [
        {"id": "c1", "text": "First chunk text about attention mechanisms."},
        {"id": "c2", "text": "Second chunk text about feed-forward layers."},
    ]
    texts = [c["text"] for c in chunks]
    chunk_ids = [c["id"] for c in chunks]

    # Save baseline cache
    vecs = embed_texts(texts)
    vec_path, meta_path = save_generation_embeddings(
        paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir
    )
    assert vec_path.exists() and meta_path.exists()

    # Baseline valid load
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir, expected_chunk_ids=chunk_ids) is not None

    # Scenario A: Wrong model name
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["model_name"] = "wrong-model-name-unsupported"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # Reset
    save_generation_embeddings(paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir)

    # Scenario B: Wrong vector dtype (not float32)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["dtype"] = "float64"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # Reset
    save_generation_embeddings(paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir)

    # Scenario C: Reordered or missing chunk IDs
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir, expected_chunk_ids=["c2", "c1"]) is None
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir, expected_chunk_ids=["c1"]) is None
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir, expected_chunk_ids=["c1", "c2", "c3"]) is None

    # Scenario D: Changed chunk text with reused IDs
    tampered_texts = ["Completely altered text that does not match original", "Second altered chunk text"]
    assert load_generation_embeddings(
        paper_id, run_id, data_dir=data_dir, expected_chunk_ids=chunk_ids, expected_chunk_texts=tampered_texts
    ) is None

    # Scenario E: Vectors / metadata checksum mismatch
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["vectors_sha256"] = "deadbeef" * 8
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # Reset
    save_generation_embeddings(paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir)

    # Scenario F: Partial cache write (missing .json)
    meta_path.unlink()
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None

    # Scenario G: Partial cache write (missing .npy)
    save_generation_embeddings(paper_id, run_id, chunk_ids, vecs, chunk_texts=texts, data_dir=data_dir)
    vec_path.unlink()
    assert load_generation_embeddings(paper_id, run_id, data_dir=data_dir) is None


def test_index_artifacts_negative_controls_extended(p5_env):
    """Verifies that tampering with published index artifacts strictly fails closed."""
    factory = p5_env["factory"]
    ws_id = p5_env["workspace_id"]
    data_dir = p5_env["test_dir"]

    now = utcnow_iso()
    with factory() as db:
        p = Paper(
            id="p-neg-art",
            workspace_id=ws_id,
            original_filename="art.pdf",
            storage_path="art.pdf",
            sha256="hash_art",
            size_bytes=100,
            status="processing",
            current_run_id="run-art-1",
            created_at=now,
            updated_at=now,
        )
        db.add(p)
        db.add(
            Chunk(
                id="c-art-1",
                paper_id="p-neg-art",
                run_id="run-art-1",
                chunk_index=0,
                text="Artifact negative control chunk text one.",
                token_count=10,
                section="Intro",
                page_start=1,
                page_end=1,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.add(
            Chunk(
                id="c-art-2",
                paper_id="p-neg-art",
                run_id="run-art-1",
                chunk_index=1,
                text="Artifact negative control chunk text two.",
                token_count=10,
                section="Methods",
                page_start=2,
                page_end=2,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.commit()

        idx = build_and_publish_workspace_index(
            db,
            workspace_id=ws_id,
            target_paper_id="p-neg-art",
            target_run_id="run-art-1",
            data_dir=data_dir,
        )
        assert idx is not None
        assert verify_index_artifacts_integrity(idx, db=db) is True

        # 1. Missing FAISS index
        orig_faiss = idx.faiss_path
        renamed_faiss = orig_faiss + ".bak"
        os.rename(orig_faiss, renamed_faiss)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        os.rename(renamed_faiss, orig_faiss)
        assert verify_index_artifacts_integrity(idx, db=db) is True

        # 2. Missing BM25 index
        orig_bm25 = idx.bm25_path
        renamed_bm25 = orig_bm25 + ".bak"
        os.rename(orig_bm25, renamed_bm25)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        os.rename(renamed_bm25, orig_bm25)
        assert verify_index_artifacts_integrity(idx, db=db) is True

        # 3. Missing manifest.json
        orig_manifest = idx.manifest_path
        renamed_manifest = orig_manifest + ".bak"
        os.rename(orig_manifest, renamed_manifest)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        os.rename(renamed_manifest, orig_manifest)
        assert verify_index_artifacts_integrity(idx, db=db) is True

        # 4. Manifest workspace_id mismatch
        with open(orig_manifest, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        orig_ws = m_data["workspace_id"]
        m_data["workspace_id"] = "different-workspace-uuid"
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        m_data["workspace_id"] = orig_ws
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)

        # 5. Manifest version mismatch
        m_data["version"] = 999
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        m_data["version"] = idx.version
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)

        # 6. Manifest model_name mismatch
        m_data["model_name"] = "unsupported-model-xyz"
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        m_data["model_name"] = EMBEDDING_MODEL_NAME
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)

        # 7. Manifest chunk_count mismatch with database
        m_data["chunk_count"] = 99
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)
        assert verify_index_artifacts_integrity(idx, db=db) is False
        m_data["chunk_count"] = 2
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)

        # 8. Manifest checksum mismatch (tampered content without updating DB checksum record)
        m_data["extra_field"] = "tampered"
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f)
        assert verify_index_artifacts_integrity(idx, db=db) is False

        # Reset manifest cleanly
        del m_data["extra_field"]
        with open(orig_manifest, "w", encoding="utf-8") as f:
            json.dump(m_data, f, indent=2)
        # Restore original manifest file with checksum
        idx.index_checksums_json = json.dumps({
            "faiss_sha256": compute_file_sha256(idx.faiss_path),
            "bm25_sha256": compute_file_sha256(idx.bm25_path),
            "manifest_sha256": compute_file_sha256(idx.manifest_path),
        })
        db.commit()
        assert verify_index_artifacts_integrity(idx, db=db) is True

        # 9. FAISS / BM25 / DB chunk count mismatch (simulate orphan chunk in DB)
        db.add(
            Chunk(
                id="c-art-3",
                paper_id="p-neg-art",
                run_id="run-art-1",
                chunk_index=2,
                text="Extra chunk in DB not indexed.",
                token_count=10,
                section="Discussion",
                page_start=3,
                page_end=3,
                is_excluded=0,
                is_deleted=0,
                created_at=now,
            )
        )
        db.flush()
        db.add(
            IndexChunk(
                id="ic-orphan",
                index_id=idx.id,
                paper_id="p-neg-art",
                run_id="run-art-1",
                chunk_id="c-art-3",
                faiss_id=99,
                created_at=now,
            )
        )
        db.commit()
        assert verify_index_artifacts_integrity(idx, db=db) is False
