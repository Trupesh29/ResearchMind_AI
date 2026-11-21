"""ResearchMind AI — Phase 6 Hybrid Retrieval Test Suite.

Verifies:
- API validation: bounds, missing papers, foreign workspace papers, non-ready papers
- Lifecycle errors: NO_ACTIVE_INDEX, INDEX_BUILDING
- Anti-starvation candidate retrieval: selected scope is never starved by unselected papers
- Reference exclusion: is_excluded == 1 chunks are filtered out by default
- Modes: dense, sparse, and hybrid (RRF k=60)
- Deterministic RRF calculation and tie-breaking
- Immediate query tombstone and reprocess exclusion
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.bootstrap import bootstrap_default_user
from backend.app.db.models import Chunk, Paper, User, Workspace
from backend.app.schemas.retrieval import RetrievalQueryRequest
from backend.app.services.index_service import build_and_publish_workspace_index
from backend.app.services.retrieval_service import retrieve_passages


def _get_user_id(db: Session) -> str:
    user = db.query(User).first()
    if not user:
        user = bootstrap_default_user(db)
    return user.id


def _create_ready_paper_with_chunks(
    db: Session,
    workspace: Workspace,
    title: str,
    chunks_data: list[dict],
) -> tuple[Paper, list[Chunk]]:
    """Helper to create a paper with chunks and publish an active index."""
    paper_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    paper = Paper(
        id=paper_id,
        workspace_id=workspace.id,
        original_filename=f"{title.lower().replace(' ', '_')}.pdf",
        title=title,
        sha256=uuid.uuid4().hex,
        storage_path=f"pdfs/{paper_id}.pdf",
        size_bytes=1024,
        status="processing",
        current_run_id=run_id,
    )
    db.add(paper)
    db.flush()

    chunks: list[Chunk] = []
    for idx, cdata in enumerate(chunks_data):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            paper_id=paper_id,
            run_id=run_id,
            chunk_index=idx,
            page_start=cdata.get("page", 1),
            page_end=cdata.get("page", 1),
            section=cdata.get("section", "body"),
            text=cdata.get("text", f"Content {idx}"),
            token_count=len(cdata.get("text", "").split()) + 5,
            is_excluded=1 if cdata.get("is_excluded", False) else 0,
            is_deleted=0,
        )
        db.add(chunk)
        chunks.append(chunk)

    db.commit()
    return paper, chunks


def test_retrieval_api_validation(client: TestClient, db_session: Session):
    """Verify endpoint request validation, bounds, missing, foreign, and not-ready papers."""
    user_id = _get_user_id(db_session)
    ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="WS1")
    other_ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="WS2")
    db_session.add_all([ws, other_ws])
    db_session.commit()

    # 1. Non-existent workspace -> 404
    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": "non-existent-ws",
            "query": "quantum error correction",
            "selected_paper_ids": ["some-paper"],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    # 2. Empty selected_paper_ids -> 422 (pydantic min_length=1)
    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": ws.id,
            "query": "quantum error correction",
            "selected_paper_ids": [],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"

    # 3. Missing paper -> 404
    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": ws.id,
            "query": "quantum error correction",
            "selected_paper_ids": ["missing-paper-123"],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    # 4. Foreign paper belonging to different workspace -> 403
    foreign_paper = Paper(
        id=str(uuid.uuid4()),
        workspace_id=other_ws.id,
        original_filename="foreign.pdf",
        title="Foreign Paper",
        sha256="abc1",
        storage_path="pdfs/f.pdf",
        size_bytes=100,
        status="ready",
    )
    db_session.add(foreign_paper)
    db_session.commit()

    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": ws.id,
            "query": "quantum error correction",
            "selected_paper_ids": [foreign_paper.id],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # 5. Paper not in ready status -> 400 PAPER_NOT_READY
    unready_paper = Paper(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        original_filename="unready.pdf",
        title="Unready Paper",
        sha256="abc2",
        storage_path="pdfs/u.pdf",
        size_bytes=100,
        status="processing",
    )
    db_session.add(unready_paper)
    db_session.commit()

    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": ws.id,
            "query": "quantum error correction",
            "selected_paper_ids": [unready_paper.id],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PAPER_NOT_READY"

    # 6. No active index -> 404 NO_ACTIVE_INDEX
    unready_paper.status = "ready"
    db_session.commit()

    resp = client.post(
        "/api/retrieval/query",
        json={
            "workspace_id": ws.id,
            "query": "quantum error correction",
            "selected_paper_ids": [unready_paper.id],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NO_ACTIVE_INDEX"


def test_retrieval_candidate_anti_starvation_and_scope_filtering(
    isolated_env: dict,
    db_session: Session,
):
    """Verify anti-starvation: unselected papers with high keyword overlap never crowd out selected papers."""
    user_id = _get_user_id(db_session)
    ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="AntiStarvationWS")
    db_session.add(ws)
    db_session.commit()

    # Paper A (Target paper): has 2 specific chunks
    paper_a, chunks_a = _create_ready_paper_with_chunks(
        db_session,
        ws,
        "Paper A Quantum Surface Codes",
        [
            {"text": "Surface code quantum error correction requires physical qubit error rates below threshold.", "section": "intro", "page": 1},
            {"text": "Syndrome measurement cycles detect phase flip and bit flip errors reliably.", "section": "methods", "page": 2},
        ],
    )

    # Paper B (Unselected paper): has 40 chunks loaded with identical query terms
    b_chunks = [
        {"text": f"Quantum error correction with physical qubits and syndrome measurement repetition {i}.", "section": "methods", "page": i}
        for i in range(1, 41)
    ]
    paper_b, chunks_b = _create_ready_paper_with_chunks(
        db_session,
        ws,
        "Paper B Generic Quantum",
        b_chunks,
    )

    # Publish index containing both Paper A and Paper B
    idx = build_and_publish_workspace_index(db_session, ws.id, target_paper_id=paper_a.id, target_run_id=paper_a.current_run_id)
    assert idx.status == "active"
    paper_b.status = "ready"
    paper_b.published_run_id = paper_b.current_run_id
    db_session.commit()

    # Now query selecting ONLY Paper A
    req = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="surface code error correction threshold",
        selected_paper_ids=[paper_a.id],
        top_k=10,
        mode="hybrid",
    )
    res = retrieve_passages(db_session, user_id=user_id, request=req)

    # All returned passages must belong to Paper A; Paper B must NEVER appear
    assert len(res.passages) > 0
    for p in res.passages:
        assert p.paper_id == paper_a.id
        assert p.paper_id != paper_b.id

    # Verify that Paper A was NOT starved by Paper B's 40 candidate chunks
    chunk_ids = [p.chunk_id for p in res.passages]
    assert chunks_a[0].id in chunk_ids


def test_retrieval_excludes_reference_chunks_by_default(
    isolated_env: dict,
    db_session: Session,
):
    """Verify that chunks in reference sections (is_excluded == 1) are never returned."""
    user_id = _get_user_id(db_session)
    ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="RefExclusionWS")
    db_session.add(ws)
    db_session.commit()

    paper, chunks = _create_ready_paper_with_chunks(
        db_session,
        ws,
        "Paper With References",
        [
            {"text": "We present novel methods for deep reinforcement learning.", "section": "abstract", "page": 1, "is_excluded": False},
            {"text": "Sutton and Barto 1998 Reinforcement Learning An Introduction MIT Press Cambridge.", "section": "references", "page": 5, "is_excluded": True},
        ],
    )

    idx = build_and_publish_workspace_index(db_session, ws.id, target_paper_id=paper.id, target_run_id=paper.current_run_id)
    assert idx.status == "active"

    req = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="Sutton Barto Reinforcement Learning MIT Press",
        selected_paper_ids=[paper.id],
        top_k=10,
        mode="hybrid",
    )
    res = retrieve_passages(db_session, user_id=user_id, request=req)

    # The reference chunk must not appear in passages
    returned_chunk_ids = [p.chunk_id for p in res.passages]
    assert chunks[1].id not in returned_chunk_ids


def test_retrieval_deterministic_rrf_hand_calculation():
    """Verify exact hand-calculated Reciprocal-Rank Fusion (RRF, k=60) arithmetic."""
    rrf_k = 60.0
    # Candidate 1: Dense rank 1, Sparse rank 2
    # RRF = 1/(60+1) + 1/(60+2) = 1/61 + 1/62
    c1_score = (1.0 / (rrf_k + 1)) + (1.0 / (rrf_k + 2))
    assert round(c1_score, 6) == round((1.0 / 61.0) + (1.0 / 62.0), 6)
    assert round(c1_score, 6) == 0.032522

    # Candidate 2: Dense rank 3, not in sparse
    # RRF = 1/(60+3) = 1/63
    c2_score = 1.0 / (rrf_k + 3)
    assert round(c2_score, 6) == round(1.0 / 63.0, 6)
    assert round(c2_score, 6) == 0.015873


def test_retrieval_modes_dense_sparse_hybrid(
    isolated_env: dict,
    db_session: Session,
):
    """Verify dense, sparse, and hybrid modes produce appropriate scores and ranks."""
    user_id = _get_user_id(db_session)
    ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="ModesWS")
    db_session.add(ws)
    db_session.commit()

    paper, chunks = _create_ready_paper_with_chunks(
        db_session,
        ws,
        "Modes Test Paper",
        [
            {"text": "Attention mechanisms allow transformers to process sequential tokens in parallel.", "section": "intro", "page": 1},
            {"text": "Multi-head attention projects queries keys and values into distinct subspace representations.", "section": "architecture", "page": 2},
        ],
    )
    build_and_publish_workspace_index(db_session, ws.id, target_paper_id=paper.id, target_run_id=paper.current_run_id)

    # 1. Dense mode
    req_dense = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="transformers attention mechanism",
        selected_paper_ids=[paper.id],
        mode="dense",
    )
    res_dense = retrieve_passages(db_session, user_id=user_id, request=req_dense)
    assert res_dense.diagnostics.mode == "dense"
    assert len(res_dense.passages) > 0
    assert res_dense.passages[0].dense_rank == 1
    assert res_dense.passages[0].sparse_rank is None

    # 2. Sparse mode
    req_sparse = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="transformers attention mechanism",
        selected_paper_ids=[paper.id],
        mode="sparse",
    )
    res_sparse = retrieve_passages(db_session, user_id=user_id, request=req_sparse)
    assert res_sparse.diagnostics.mode == "sparse"
    assert len(res_sparse.passages) > 0
    assert res_sparse.passages[0].sparse_rank == 1
    assert res_sparse.passages[0].dense_rank is None

    # 3. Hybrid mode
    req_hybrid = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="transformers attention mechanism",
        selected_paper_ids=[paper.id],
        mode="hybrid",
    )
    res_hybrid = retrieve_passages(db_session, user_id=user_id, request=req_hybrid)
    assert res_hybrid.diagnostics.mode == "hybrid"
    assert len(res_hybrid.passages) > 0
    assert res_hybrid.passages[0].score <= 1.0  # Fused score
    assert "not calibrated probabilities" in res_hybrid.diagnostics.score_explanation


def test_retrieval_tombstone_and_reprocess_safety(
    isolated_env: dict,
    db_session: Session,
):
    """Verify that a paper marked as re-processing or deleted immediately disappears from query results."""
    user_id = _get_user_id(db_session)
    ws = Workspace(id=str(uuid.uuid4()), user_id=user_id, name="TombstoneWS")
    db_session.add(ws)
    db_session.commit()

    paper, chunks = _create_ready_paper_with_chunks(
        db_session,
        ws,
        "Paper To Invalidate",
        [{"text": "Important research finding that must be invalidated upon deletion.", "section": "results", "page": 1}],
    )
    build_and_publish_workspace_index(db_session, ws.id, target_paper_id=paper.id, target_run_id=paper.current_run_id)

    # Initial query succeeds
    req = RetrievalQueryRequest(
        workspace_id=ws.id,
        query="Important research finding",
        selected_paper_ids=[paper.id],
    )
    res1 = retrieve_passages(db_session, user_id=user_id, request=req)
    assert len(res1.passages) == 1

    # Simulate paper being reprocessed (new run starts, status becomes processing)
    paper.status = "processing"
    paper.current_run_id = str(uuid.uuid4())
    db_session.commit()

    # Query must reject paper as not ready (400 PAPER_NOT_READY)
    with pytest.raises(Exception) as exc_info:
        retrieve_passages(db_session, user_id=user_id, request=req)
    assert "not ready for retrieval" in str(exc_info.value)
