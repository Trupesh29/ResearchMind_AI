"""ResearchMind AI — Workspace Vector & Keyword Index Lifecycle Service (Phase 5).

Manages immutable versioned workspace indexes containing matching FAISS and BM25 artifacts.
Features:
- Staged atomic directory creation with SHA-256 artifact checksum verification
- Coherent FAISS FlatIP + BM25 paired generation from identical eligible chunk manifests
- Exclusion of reference chunks (is_excluded == 1) from default index membership
- Database transactional pointer updates with active/retired version management
- Fail-closed validation: reloads and verifies both FAISS and BM25 before pointer switch
- Deletion and reprocessing safety with instant tombstone filtering and rebuild capability
- Internal dense and sparse search probes for verifying index correctness and provenance
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import Chunk, EmbeddingIndex, IndexChunk, Paper, Workspace, utcnow_iso
from backend.app.services.bm25_service import BM25Index
from backend.app.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    EMBEDDING_NORMALIZATION,
    embed_texts,
    get_embedding_model,
    load_generation_embeddings,
    save_generation_embeddings,
)

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute hex SHA-256 checksum of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_data_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    try:
        from backend.app.main import app

        app_settings = getattr(app.state, "settings", None)
        if app_settings and hasattr(app_settings, "DATA_DIR"):
            return Path(app_settings.DATA_DIR)
    except Exception:
        pass
    return Path(get_settings().DATA_DIR)


def get_workspace_index_base_dir(workspace_id: str, data_dir: Path | None = None) -> Path:
    """Return filesystem path to the workspace index directory."""
    effective_data_dir = _resolve_data_dir(data_dir)
    path = Path(effective_data_dir) / "indexes" / workspace_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_active_workspace_index(db: Session, workspace_id: str) -> EmbeddingIndex | None:
    """Return the currently active EmbeddingIndex record for a workspace."""
    return (
        db.query(EmbeddingIndex)
        .filter(
            EmbeddingIndex.workspace_id == workspace_id,
            EmbeddingIndex.status == "active",
        )
        .first()
    )


def collect_eligible_workspace_chunks(
    db: Session,
    workspace_id: str,
    target_paper_id: str | None = None,
    target_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Collect all eligible chunk definitions for a workspace index.

    Includes:
    - Ready papers whose published_run_id is set
    - The target paper currently undergoing indexing (if provided with target_run_id)
    Excludes:
    - Deleted papers (not in database or status == 'failed')
    - Reference chunks (is_excluded == 1)
    - Tombstoned chunks (is_deleted == 1)
    """
    papers = (
        db.query(Paper)
        .filter(
            Paper.workspace_id == workspace_id,
        )
        .all()
    )

    eligible_chunks: list[dict[str, Any]] = []

    for paper in papers:
        effective_run_id: str | None = None
        if target_paper_id and paper.id == target_paper_id:
            effective_run_id = target_run_id or paper.current_run_id or paper.published_run_id
        elif paper.published_run_id and paper.status != "failed":
            effective_run_id = paper.published_run_id

        if not effective_run_id:
            continue

        chunk_rows = (
            db.query(Chunk)
            .filter(
                Chunk.paper_id == paper.id,
                Chunk.run_id == effective_run_id,
                Chunk.is_excluded == 0,
                Chunk.is_deleted == 0,
            )
            .order_by(Chunk.chunk_index.asc())
            .all()
        )

        for cr in chunk_rows:
            eligible_chunks.append(
                {
                    "chunk_id": cr.id,
                    "paper_id": paper.id,
                    "run_id": effective_run_id,
                    "chunk_index": cr.chunk_index,
                    "text": cr.text,
                    "token_count": cr.token_count,
                    "section": cr.section,
                    "page_start": cr.page_start,
                    "page_end": cr.page_end,
                }
            )

    return eligible_chunks


def build_and_publish_workspace_index(
    db: Session,
    workspace_id: str,
    target_paper_id: str | None = None,
    target_run_id: str | None = None,
    data_dir: Path | None = None,
) -> EmbeddingIndex | None:
    """Build paired FAISS and BM25 index artifacts, validate them, and atomically publish a new index version.

    Follows a crash-safe filesystem and database protocol:
    1. Collects exact eligible chunk manifest across the workspace.
    2. Builds FAISS FlatIP and BM25 in an isolated staging folder (v{version}.tmp).
    3. Validates reloadability, count matching, and calculates SHA-256 checksums.
    4. Atomically commits database pointers and updates paper ready statuses.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise ValueError(f"Workspace {workspace_id} not found.")

    # 1. Determine next version number
    max_v = (
        db.query(EmbeddingIndex.version)
        .filter(EmbeddingIndex.workspace_id == workspace_id)
        .order_by(EmbeddingIndex.version.desc())
        .first()
    )
    next_version = (max_v[0] + 1) if max_v else 1

    # 2. Collect eligible chunks
    eligible_manifest = collect_eligible_workspace_chunks(
        db,
        workspace_id=workspace_id,
        target_paper_id=target_paper_id,
        target_run_id=target_run_id,
    )

    if not eligible_manifest:
        logger.warning(f"No eligible chunks found for workspace {workspace_id}. Cannot publish empty index.")
        return None

    # 3. Setup staging filesystem directory
    ws_dir = get_workspace_index_base_dir(workspace_id, data_dir=data_dir)
    staging_dir = ws_dir / f"v{next_version}.tmp"
    final_dir = ws_dir / f"v{next_version}"

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 4. Generate / collect embeddings for each chunk in manifest
        # Group by (paper_id, run_id) to leverage cached generation embeddings
        manifest_chunks_with_vecs: list[tuple[dict[str, Any], np.ndarray]] = []
        grouped_runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in eligible_manifest:
            key = (item["paper_id"], item["run_id"])
            grouped_runs.setdefault(key, []).append(item)

        for (p_id, r_id), run_items in grouped_runs.items():
            cached = load_generation_embeddings(p_id, r_id, data_dir=data_dir)
            if cached is not None:
                cached_chunk_ids, cached_vecs = cached
                id_to_vec = {cid: cached_vecs[i] for i, cid in enumerate(cached_chunk_ids)}
                # Verify all run items are in cached vectors
                if all(item["chunk_id"] in id_to_vec for item in run_items):
                    for item in run_items:
                        manifest_chunks_with_vecs.append((item, id_to_vec[item["chunk_id"]]))
                    continue

            # Compute embeddings if not cached
            texts = [item["text"] for item in run_items]
            chunk_ids = [item["chunk_id"] for item in run_items]
            computed_vecs = embed_texts(texts)
            save_generation_embeddings(p_id, r_id, chunk_ids, computed_vecs, data_dir=data_dir)
            for i, item in enumerate(run_items):
                manifest_chunks_with_vecs.append((item, computed_vecs[i]))

        # Ensure order matches eligible_manifest
        all_vectors = np.vstack([vec for _, vec in manifest_chunks_with_vecs]).astype(np.float32)

        # 5. Build FAISS FlatIP index
        faiss_index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        faiss_index.add(all_vectors)
        faiss_file = staging_dir / "index.faiss"
        faiss.write_index(faiss_index, str(faiss_file))

        # 6. Build BM25 index
        bm25 = BM25Index()
        bm25.fit(eligible_manifest)
        bm25_file = staging_dir / "bm25.json"
        bm25.save(bm25_file)

        # 7. Compute artifact checksums
        faiss_sha256 = compute_file_sha256(faiss_file)
        bm25_sha256 = compute_file_sha256(bm25_file)

        # 8. Write manifest.json
        manifest_data = {
            "workspace_id": workspace_id,
            "version": next_version,
            "model_name": EMBEDDING_MODEL_NAME,
            "model_revision": EMBEDDING_MODEL_REVISION,
            "dimension": EMBEDDING_DIMENSION,
            "normalization": EMBEDDING_NORMALIZATION,
            "count": len(eligible_manifest),
            "chunk_count": len(eligible_manifest),
            "faiss_sha256": faiss_sha256,
            "bm25_sha256": bm25_sha256,
            "chunks": [
                {
                    "faiss_id": i,
                    "chunk_id": item["chunk_id"],
                    "paper_id": item["paper_id"],
                    "run_id": item["run_id"],
                    "token_count": item["token_count"],
                    "page_start": item["page_start"],
                    "page_end": item["page_end"],
                    "section": item["section"],
                }
                for i, item in enumerate(eligible_manifest)
            ],
        }
        manifest_file = staging_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 9. Reload and validate artifacts before commit (Fail-Closed Barrier)
        reloaded_faiss = faiss.read_index(str(faiss_file))
        if reloaded_faiss.ntotal != len(eligible_manifest):
            raise RuntimeError(
                f"FAISS artifact validation failed: reloaded ntotal {reloaded_faiss.ntotal} != {len(eligible_manifest)}"
            )

        reloaded_bm25 = BM25Index.load(bm25_file)
        if reloaded_bm25.corpus_size != len(eligible_manifest):
            raise RuntimeError(
                f"BM25 artifact validation failed: reloaded corpus_size {reloaded_bm25.corpus_size} != {len(eligible_manifest)}"
            )

        # 10. Compute complete checksums bundle
        checksums = {
            "faiss_sha256": faiss_sha256,
            "bm25_sha256": bm25_sha256,
            "manifest_sha256": compute_file_sha256(manifest_file),
        }

        # 11. Atomic directory switch
        if final_dir.exists():
            shutil.rmtree(final_dir)
        staging_dir.rename(final_dir)

    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    # 12. Transactional Database Publication
    now = utcnow_iso()
    final_faiss_path = str(final_dir / "index.faiss")
    final_bm25_path = str(final_dir / "bm25.json")
    final_manifest_path = str(final_dir / "manifest.json")

    # Retire existing active index for this workspace
    db.query(EmbeddingIndex).filter(
        EmbeddingIndex.workspace_id == workspace_id,
        EmbeddingIndex.status == "active",
    ).update({"status": "retired", "updated_at": now})

    # Create new active index record
    chunk_params = {
        "model_name": EMBEDDING_MODEL_NAME,
        "model_revision": EMBEDDING_MODEL_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "normalization": EMBEDDING_NORMALIZATION,
        "chunk_count": len(eligible_manifest),
    }

    new_index = EmbeddingIndex(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        version=next_version,
        model_name=EMBEDDING_MODEL_NAME,
        model_revision=EMBEDDING_MODEL_REVISION,
        dimension=EMBEDDING_DIMENSION,
        normalization=EMBEDDING_NORMALIZATION,
        chunk_params_json=json.dumps(chunk_params),
        faiss_path=final_faiss_path,
        bm25_path=final_bm25_path,
        manifest_path=final_manifest_path,
        index_checksums_json=json.dumps(checksums),
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(new_index)

    # Insert explicit IndexChunk membership rows
    for i, item in enumerate(eligible_manifest):
        ic_row = IndexChunk(
            id=str(uuid.uuid4()),
            index_id=new_index.id,
            paper_id=item["paper_id"],
            run_id=item["run_id"],
            chunk_id=item["chunk_id"],
            faiss_id=i,
            created_at=now,
        )
        db.add(ic_row)

    # Atomically mark all constituent papers as 'ready'
    distinct_paper_ids = list({item["paper_id"] for item in eligible_manifest})
    for p_id in distinct_paper_ids:
        paper = db.query(Paper).filter(Paper.id == p_id).first()
        if paper:
            paper.status = "ready"
            if target_paper_id and paper.id == target_paper_id and target_run_id:
                paper.published_run_id = target_run_id
            paper.updated_at = now

    db.commit()
    logger.info(
        f"Successfully published active EmbeddingIndex v{next_version} for workspace {workspace_id} "
        f"with {len(eligible_manifest)} chunks across {len(distinct_paper_ids)} papers."
    )
    return new_index


def search_dense(
    db: Session,
    workspace_id: str,
    query: str,
    top_k: int = 30,
    selected_paper_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Internal dense search probe for index verification and retrieval correctness."""
    active_idx = get_active_workspace_index(db, workspace_id)
    if not active_idx or not active_idx.faiss_path or not os.path.exists(active_idx.faiss_path):
        return []

    # 1. Load active FAISS index
    index = faiss.read_index(active_idx.faiss_path)
    if index.ntotal == 0:
        return []

    # 2. Encode query with normalization
    model = get_embedding_model()
    query_vec = model.encode([query], convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)

    # 3. Retrieve top candidates
    k = min(top_k * 3, index.ntotal)  # Over-fetch for eligibility filtering
    distances, indices = index.search(query_vec, k)

    # 4. Map and filter by liveness, membership, and selected papers
    results: list[dict[str, Any]] = []
    for rank, (faiss_id, score) in enumerate(zip(indices[0], distances[0])):
        if faiss_id < 0:
            continue

        ic = (
            db.query(IndexChunk)
            .filter(
                IndexChunk.index_id == active_idx.id,
                IndexChunk.faiss_id == int(faiss_id),
            )
            .first()
        )
        if not ic:
            continue

        # Check paper selection scope
        if selected_paper_ids is not None and ic.paper_id not in selected_paper_ids:
            continue

        # Recheck liveness at query boundary (Tombstone & generation filter)
        paper = db.query(Paper).filter(Paper.id == ic.paper_id).first()
        if not paper or paper.status != "ready" or paper.published_run_id != ic.run_id:
            continue

        chunk = db.query(Chunk).filter(Chunk.id == ic.chunk_id, Chunk.is_deleted == 0).first()
        if not chunk:
            continue

        results.append(
            {
                "chunk_id": chunk.id,
                "paper_id": chunk.paper_id,
                "section": chunk.section,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "text": chunk.text,
                "score": float(score),
                "rank": len(results) + 1,
                "faiss_id": int(faiss_id),
                "index_version": active_idx.version,
            }
        )

        if len(results) >= top_k:
            break

    return results


def search_sparse(
    db: Session,
    workspace_id: str,
    query: str,
    top_k: int = 30,
    selected_paper_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Internal sparse BM25 search probe for index verification and retrieval correctness."""
    active_idx = get_active_workspace_index(db, workspace_id)
    if not active_idx or not active_idx.bm25_path or not os.path.exists(active_idx.bm25_path):
        return []

    # 1. Load BM25 index
    bm25 = BM25Index.load(active_idx.bm25_path)
    if bm25.corpus_size == 0:
        return []

    # 2. Search BM25
    hits = bm25.search(query, top_k=top_k * 3)

    # 3. Filter by liveness and scope
    results: list[dict[str, Any]] = []
    for doc_idx, score in hits:
        ic = (
            db.query(IndexChunk)
            .filter(
                IndexChunk.index_id == active_idx.id,
                IndexChunk.faiss_id == doc_idx,
            )
            .first()
        )
        if not ic:
            continue

        if selected_paper_ids is not None and ic.paper_id not in selected_paper_ids:
            continue

        paper = db.query(Paper).filter(Paper.id == ic.paper_id).first()
        if not paper or paper.status != "ready" or paper.published_run_id != ic.run_id:
            continue

        chunk = db.query(Chunk).filter(Chunk.id == ic.chunk_id, Chunk.is_deleted == 0).first()
        if not chunk:
            continue

        results.append(
            {
                "chunk_id": chunk.id,
                "paper_id": chunk.paper_id,
                "section": chunk.section,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "text": chunk.text,
                "score": float(score),
                "rank": len(results) + 1,
                "doc_idx": doc_idx,
                "index_version": active_idx.version,
            }
        )

        if len(results) >= top_k:
            break

    return results
