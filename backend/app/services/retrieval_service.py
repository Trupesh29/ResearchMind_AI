"""ResearchMind AI — Scoped Hybrid Retrieval Service (Phase 6).

Implements:
- Workspace isolation and strict selected paper validation
- Exclusion of reference chunks (is_excluded == 1) and deleted chunks (is_deleted == 1)
- Anti-starvation candidate retrieval: evaluates dense and sparse candidates scoped
  strictly to the selected papers
- Deterministic Reciprocal-Rank Fusion (RRF, k=60)
- Execution timings and diagnostic provenance
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import faiss
import numpy as np
from sqlalchemy.orm import Session
from starlette import status

from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import Chunk, EmbeddingIndex, IndexChunk, Paper, Workspace
from backend.app.schemas.retrieval import (
    RetrievalDiagnostics,
    RetrievalPassage,
    RetrievalQueryData,
    RetrievalQueryRequest,
    RetrievalTimings,
)
from backend.app.services.bm25_service import BM25Index
from backend.app.services.embedding_service import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    get_embedding_model,
)
from backend.app.services.index_service import (
    get_active_workspace_index,
    verify_index_artifacts_integrity,
)

logger = logging.getLogger(__name__)


def retrieve_passages(
    db: Session,
    user_id: str,
    request: RetrievalQueryRequest,
) -> RetrievalQueryData:
    """Execute scoped hybrid, dense, or sparse retrieval over explicitly selected papers."""
    t_start = time.perf_counter()

    # 1. Workspace ownership verification
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == request.workspace_id, Workspace.user_id == user_id)
        .first()
    )
    if not workspace:
        raise AppException(
            ErrorCode.NOT_FOUND,
            f"Workspace '{request.workspace_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. Selected papers validation
    if not request.selected_paper_ids:
        raise AppException(
            ErrorCode.INVALID_REQUEST,
            "At least one paper must be explicitly selected for retrieval.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Deduplicate while preserving order
    selected_ids = list(dict.fromkeys(request.selected_paper_ids))
    papers = db.query(Paper).filter(Paper.id.in_(selected_ids)).all()
    paper_map = {p.id: p for p in papers}

    # Reject missing papers
    missing = [pid for pid in selected_ids if pid not in paper_map]
    if missing:
        raise AppException(
            ErrorCode.NOT_FOUND,
            f"Selected paper(s) not found: {missing}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"missing_paper_ids": missing},
        )

    # Reject foreign papers not belonging to workspace
    foreign = [pid for pid in selected_ids if paper_map[pid].workspace_id != request.workspace_id]
    if foreign:
        raise AppException(
            ErrorCode.FORBIDDEN,
            f"Selected paper(s) do not belong to workspace '{request.workspace_id}': {foreign}",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"foreign_paper_ids": foreign},
        )

    # Reject papers not in ready state
    not_ready = [p for p in paper_map.values() if p.status != "ready"]
    if not_ready:
        nr = not_ready[0]
        raise AppException(
            ErrorCode.PAPER_NOT_READY,
            f"Paper '{nr.id}' is not ready for retrieval (status: '{nr.status}').",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"paper_id": nr.id, "status": nr.status},
        )

    # 3. Active index verification
    active_idx = get_active_workspace_index(db, request.workspace_id)
    if not active_idx:
        building = (
            db.query(EmbeddingIndex)
            .filter(
                EmbeddingIndex.workspace_id == request.workspace_id,
                EmbeddingIndex.status == "building",
            )
            .first()
        )
        if building:
            raise AppException(
                ErrorCode.INDEX_BUILDING,
                "Workspace index is currently building. Please retry once indexing completes.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        raise AppException(
            ErrorCode.NO_ACTIVE_INDEX,
            f"No active search index available for workspace '{request.workspace_id}'.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if (
        not active_idx.faiss_path
        or not os.path.exists(active_idx.faiss_path)
        or not active_idx.bm25_path
        or not os.path.exists(active_idx.bm25_path)
    ):
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "Active index artifact files are missing on disk.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not verify_index_artifacts_integrity(active_idx, db=db):
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "Active index failed artifact integrity or checksum verification.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 4. Resolve eligible chunks for selected papers (Anti-starvation & Reference exclusion)
    # Exclude reference chunks (is_excluded == 1) and soft-deleted chunks (is_deleted == 1)
    eligible_rows = (
        db.query(IndexChunk, Chunk, Paper)
        .join(Chunk, Chunk.id == IndexChunk.chunk_id)
        .join(Paper, Paper.id == IndexChunk.paper_id)
        .filter(
            IndexChunk.index_id == active_idx.id,
            IndexChunk.paper_id.in_(selected_ids),
            Chunk.is_deleted == 0,
            Chunk.is_excluded == 0,
            Paper.status == "ready",
            Paper.published_run_id == IndexChunk.run_id,
        )
        .all()
    )

    total_eligible = len(eligible_rows)
    if total_eligible == 0:
        total_ms = (time.perf_counter() - t_start) * 1000
        return RetrievalQueryData(
            query=request.query,
            workspace_id=request.workspace_id,
            selected_paper_ids=selected_ids,
            passages=[],
            diagnostics=RetrievalDiagnostics(
                total_eligible_chunks=0,
                dense_candidate_count=0,
                sparse_candidate_count=0,
                fused_count=0,
                timings=RetrievalTimings(dense_ms=0.0, sparse_ms=0.0, fusion_ms=0.0, total_ms=round(total_ms, 2)),
                index_version=active_idx.version,
                index_id=active_idx.id,
                mode=request.mode,
            ),
        )

    # Map faiss_id to metadata
    eligible_faiss_ids: list[int] = []
    chunk_meta: dict[int, dict[str, Any]] = {}
    for ic, ch, p in eligible_rows:
        eligible_faiss_ids.append(ic.faiss_id)
        chunk_meta[ic.faiss_id] = {
            "chunk_id": ch.id,
            "paper_id": p.id,
            "paper_title": p.title or p.original_filename,
            "section": ch.section,
            "page_start": ch.page_start,
            "page_end": ch.page_end,
            "text": ch.text,
            "faiss_id": ic.faiss_id,
        }

    dense_candidates: list[tuple[int, float]] = []
    dense_ms = 0.0

    # 5. Filtered Dense Retrieval (FAISS FlatIP)
    if request.mode in ("hybrid", "dense"):
        t_dense0 = time.perf_counter()
        try:
            model = get_embedding_model()
            q_vec = model.encode(
                [request.query],
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype(np.float32)

            faiss_index = faiss.read_index(active_idx.faiss_path)
            all_vectors = faiss_index.reconstruct_n(0, faiss_index.ntotal)
            sub_vectors = all_vectors[eligible_faiss_ids]

            sims = np.dot(sub_vectors, q_vec.T).squeeze()
            sims = np.atleast_1d(sims)

            # Deterministic sorting: highest similarity descending, tie break by faiss_id ascending
            candidate_pairs = list(zip(eligible_faiss_ids, [float(s) for s in sims]))
            candidate_pairs.sort(key=lambda x: (-x[1], x[0]))
            dense_candidates = candidate_pairs[:30]
        except Exception as exc:
            logger.error(f"Error during dense retrieval: {exc}", exc_info=True)
            raise AppException(
                ErrorCode.INTERNAL_ERROR,
                f"Dense retrieval failed: {exc}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
        dense_ms = (time.perf_counter() - t_dense0) * 1000

    sparse_candidates: list[tuple[int, float]] = []
    sparse_ms = 0.0

    # 6. Filtered Sparse Retrieval (BM25Okapi)
    if request.mode in ("hybrid", "sparse"):
        t_sparse0 = time.perf_counter()
        try:
            bm25 = BM25Index.load(active_idx.bm25_path)
            sparse_hits = bm25.search(
                request.query,
                top_k=30,
                eligible_indices=set(eligible_faiss_ids),
            )
            sparse_candidates = sparse_hits
        except Exception as exc:
            logger.error(f"Error during sparse retrieval: {exc}", exc_info=True)
            raise AppException(
                ErrorCode.INTERNAL_ERROR,
                f"Sparse retrieval failed: {exc}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
        sparse_ms = (time.perf_counter() - t_sparse0) * 1000

    # 7. Fusion / Selection
    t_fusion0 = time.perf_counter()
    dense_ranks = {fid: rank for rank, (fid, _) in enumerate(dense_candidates, start=1)}
    dense_scores = {fid: sc for fid, sc in dense_candidates}
    sparse_ranks = {fid: rank for rank, (fid, _) in enumerate(sparse_candidates, start=1)}
    sparse_scores = {fid: sc for fid, sc in sparse_candidates}

    passages: list[RetrievalPassage] = []

    if request.mode == "hybrid":
        # Reciprocal-Rank Fusion (RRF, k=60)
        rrf_k = 60.0
        all_candidate_fids = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        fused_items: list[tuple[int, float]] = []

        for fid in all_candidate_fids:
            score = 0.0
            if fid in dense_ranks:
                score += 1.0 / (rrf_k + dense_ranks[fid])
            if fid in sparse_ranks:
                score += 1.0 / (rrf_k + sparse_ranks[fid])
            fused_items.append((fid, score))

        # Deterministic tie-breaking:
        # 1. Fused score descending
        # 2. Best individual rank (min of dense_rank or sparse_rank) ascending
        # 3. faiss_id ascending
        fused_items.sort(
            key=lambda x: (
                -x[1],
                min(dense_ranks.get(x[0], 9999), sparse_ranks.get(x[0], 9999)),
                x[0],
            )
        )

        for rank, (fid, score) in enumerate(fused_items[: request.top_k], start=1):
            meta = chunk_meta[fid]
            passages.append(
                RetrievalPassage(
                    chunk_id=meta["chunk_id"],
                    paper_id=meta["paper_id"],
                    paper_title=meta["paper_title"],
                    section=meta["section"],
                    heading=None,
                    page_start=meta["page_start"],
                    page_end=meta["page_end"],
                    text=meta["text"],
                    score=round(score, 6),
                    rank=rank,
                    dense_rank=dense_ranks.get(fid),
                    dense_score=round(dense_scores[fid], 4) if fid in dense_scores else None,
                    sparse_rank=sparse_ranks.get(fid),
                    sparse_score=round(sparse_scores[fid], 4) if fid in sparse_scores else None,
                    index_version=active_idx.version,
                    model_name=active_idx.model_name or EMBEDDING_MODEL_NAME,
                    model_revision=active_idx.model_revision or EMBEDDING_MODEL_REVISION,
                )
            )

    elif request.mode == "dense":
        for rank, (fid, score) in enumerate(dense_candidates[: request.top_k], start=1):
            meta = chunk_meta[fid]
            passages.append(
                RetrievalPassage(
                    chunk_id=meta["chunk_id"],
                    paper_id=meta["paper_id"],
                    paper_title=meta["paper_title"],
                    section=meta["section"],
                    heading=None,
                    page_start=meta["page_start"],
                    page_end=meta["page_end"],
                    text=meta["text"],
                    score=round(score, 4),
                    rank=rank,
                    dense_rank=rank,
                    dense_score=round(score, 4),
                    sparse_rank=None,
                    sparse_score=None,
                    index_version=active_idx.version,
                    model_name=active_idx.model_name or EMBEDDING_MODEL_NAME,
                    model_revision=active_idx.model_revision or EMBEDDING_MODEL_REVISION,
                )
            )

    elif request.mode == "sparse":
        for rank, (fid, score) in enumerate(sparse_candidates[: request.top_k], start=1):
            meta = chunk_meta[fid]
            passages.append(
                RetrievalPassage(
                    chunk_id=meta["chunk_id"],
                    paper_id=meta["paper_id"],
                    paper_title=meta["paper_title"],
                    section=meta["section"],
                    heading=None,
                    page_start=meta["page_start"],
                    page_end=meta["page_end"],
                    text=meta["text"],
                    score=round(score, 4),
                    rank=rank,
                    dense_rank=None,
                    dense_score=None,
                    sparse_rank=rank,
                    sparse_score=round(score, 4),
                    index_version=active_idx.version,
                    model_name=active_idx.model_name or EMBEDDING_MODEL_NAME,
                    model_revision=active_idx.model_revision or EMBEDDING_MODEL_REVISION,
                )
            )

    fusion_ms = (time.perf_counter() - t_fusion0) * 1000
    total_ms = (time.perf_counter() - t_start) * 1000

    diagnostics = RetrievalDiagnostics(
        total_eligible_chunks=total_eligible,
        dense_candidate_count=len(dense_candidates),
        sparse_candidate_count=len(sparse_candidates),
        fused_count=len(passages),
        timings=RetrievalTimings(
            dense_ms=round(dense_ms, 2),
            sparse_ms=round(sparse_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            total_ms=round(total_ms, 2),
        ),
        index_version=active_idx.version,
        index_id=active_idx.id,
        mode=request.mode,
    )

    return RetrievalQueryData(
        query=request.query,
        workspace_id=request.workspace_id,
        selected_paper_ids=selected_ids,
        passages=passages,
        diagnostics=diagnostics,
    )
