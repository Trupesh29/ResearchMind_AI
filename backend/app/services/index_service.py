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

import contextlib
import hashlib
import json
import logging
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Generator

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


class WorkerFencingViolation(Exception):
    """Raised when an index publication or worker operation is attempted with an expired or superseded claim token."""

    pass


class PublicationConflictError(Exception):
    """Raised when concurrent publication conflict occurs or final directory already exists."""

    pass


class CrashBoundaryException(Exception):
    """Raised when an injected test crash boundary is triggered."""

    pass


_WORKSPACE_PUBLICATION_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK_DICT_LOCK = threading.Lock()


def _get_process_thread_lock(workspace_id: str) -> threading.Lock:
    with _GLOBAL_LOCK_DICT_LOCK:
        if workspace_id not in _WORKSPACE_PUBLICATION_LOCKS:
            _WORKSPACE_PUBLICATION_LOCKS[workspace_id] = threading.Lock()
        return _WORKSPACE_PUBLICATION_LOCKS[workspace_id]


@contextlib.contextmanager
def acquire_workspace_publication_slot(
    workspace_id: str,
    ws_dir: Path,
    owner_id: str,
    timeout: float = 30.0,
    poll_interval: float = 0.05,
) -> Generator[dict[str, Any], None, None]:
    """Acquire serialized publication slot for a workspace across threads and processes.

    Uses thread-level lock + atomic filesystem directory reservation (.publication_slot)
    with owner metadata and heartbeat/lease expiration.
    """
    t_lock = _get_process_thread_lock(workspace_id)
    acquired_thread = t_lock.acquire(timeout=timeout)
    if not acquired_thread:
        raise TimeoutError(f"Timed out waiting for publication thread lock for workspace {workspace_id}")

    lock_dir = ws_dir / ".publication_slot"
    meta_path = lock_dir / "slot_meta.json"
    start_time = time.time()
    acquired_fs = False
    slot_info = {"owner_id": owner_id, "workspace_id": workspace_id, "acquired_at": time.time()}

    try:
        while time.time() - start_time < timeout:
            try:
                lock_dir.mkdir(parents=True, exist_ok=False)
                acquired_fs = True
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "owner_id": owner_id,
                            "pid": os.getpid(),
                            "acquired_at": time.time(),
                            "timeout": timeout,
                        },
                        f,
                    )
                break
            except FileExistsError:
                # Check if existing lock is expired
                is_stale = False
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        age = time.time() - data.get("acquired_at", 0)
                        if age > data.get("timeout", timeout):
                            is_stale = True
                    except Exception:
                        is_stale = True
                else:
                    try:
                        if time.time() - lock_dir.stat().st_mtime > timeout:
                            is_stale = True
                    except Exception:
                        pass

                if is_stale:
                    try:
                        shutil.rmtree(lock_dir, ignore_errors=True)
                        continue
                    except Exception:
                        pass
                time.sleep(poll_interval)

        if not acquired_fs:
            raise TimeoutError(f"Timed out acquiring publication filesystem slot for workspace {workspace_id}")

        yield slot_info

    finally:
        if acquired_fs:
            try:
                if meta_path.exists():
                    meta_path.unlink(missing_ok=True)
                lock_dir.rmdir()
            except Exception:
                shutil.rmtree(lock_dir, ignore_errors=True)
        t_lock.release()


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


def cleanup_stale_staging_directories(
    workspace_id: str,
    data_dir: Path | None = None,
    max_age_seconds: float = 60.0,
) -> int:
    """Prune any orphaned staging directories (.tmp) left by crashes or aborted attempts.

    Ownership-aware: Reads staging_meta.json inside each directory. Never deletes an active
    unexpired staging directory owned by a competing worker.
    Strictly validates that all target paths resolve within ws_dir (prevents directory traversal).
    """
    ws_dir = get_workspace_index_base_dir(workspace_id, data_dir=data_dir).resolve()
    if not ws_dir.exists():
        return 0
    removed = 0
    now = time.time()
    for item in ws_dir.iterdir():
        # Validate path traversal: must be strictly inside ws_dir
        try:
            resolved_item = item.resolve()
            if not resolved_item.is_relative_to(ws_dir):
                raise ValueError(f"Attempted directory traversal in staging cleanup: {item}")
        except AttributeError:
            if not str(item.resolve()).startswith(str(ws_dir)):
                raise ValueError(f"Attempted directory traversal in staging cleanup: {item}")

        if item.is_dir() and item.name.endswith(".tmp"):
            # Never clean up active publication lock directory
            if item.name == ".publication_slot":
                continue

            meta_file = item / "staging_meta.json"
            should_remove = False
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    hb = meta.get("heartbeat_at", meta.get("created_at", 0))
                    ttl = meta.get("ttl_seconds", max_age_seconds)
                    if (now - hb) > ttl:
                        should_remove = True
                    else:
                        logger.debug(f"Preserving active staging attempt {item.name} for owner {meta.get('build_id')}")
                except Exception:
                    try:
                        if (now - item.stat().st_mtime) > max_age_seconds:
                            should_remove = True
                    except Exception:
                        pass
            else:
                try:
                    if (now - item.stat().st_mtime) > max_age_seconds:
                        should_remove = True
                except Exception:
                    pass

            if should_remove:
                try:
                    shutil.rmtree(item, ignore_errors=True)
                    removed += 1
                except Exception as exc:
                    logger.warning(f"Could not remove stale staging directory {item}: {exc}")
    return removed


def verify_index_artifacts_integrity(
    index_record: EmbeddingIndex,
    db: Session | None = None,
) -> bool:
    """Validate that index artifacts exist on disk, match SHA-256 checksums, and match DB count.

    Fails closed on any corruption, missing artifact, or mismatch.
    """
    if not index_record.faiss_path or not os.path.exists(index_record.faiss_path):
        logger.error(f"Active index {index_record.id} FAISS artifact missing on disk: {index_record.faiss_path}")
        return False
    if not index_record.bm25_path or not os.path.exists(index_record.bm25_path):
        logger.error(f"Active index {index_record.id} BM25 artifact missing on disk: {index_record.bm25_path}")
        return False
    if not index_record.manifest_path or not os.path.exists(index_record.manifest_path):
        logger.error(f"Active index {index_record.id} manifest missing on disk: {index_record.manifest_path}")
        return False

    if index_record.index_checksums_json:
        try:
            checksums = json.loads(index_record.index_checksums_json)
            exp_faiss = checksums.get("faiss_sha256")
            exp_bm25 = checksums.get("bm25_sha256")
            exp_manifest = checksums.get("manifest_sha256")

            if exp_faiss and compute_file_sha256(index_record.faiss_path) != exp_faiss:
                logger.error(f"Active index {index_record.id} FAISS checksum mismatch!")
                return False
            if exp_bm25 and compute_file_sha256(index_record.bm25_path) != exp_bm25:
                logger.error(f"Active index {index_record.id} BM25 checksum mismatch!")
                return False
            if exp_manifest and compute_file_sha256(index_record.manifest_path) != exp_manifest:
                logger.error(f"Active index {index_record.id} manifest checksum mismatch!")
                return False
        except Exception as exc:
            logger.error(f"Failed to verify checksums for index {index_record.id}: {exc}")
            return False

    if db is not None:
        try:
            db_chunk_count = (
                db.query(IndexChunk)
                .filter(IndexChunk.index_id == index_record.id)
                .count()
            )
            faiss_idx = faiss.read_index(index_record.faiss_path)
            if faiss_idx.ntotal != db_chunk_count:
                logger.error(
                    f"Active index {index_record.id} FAISS ntotal {faiss_idx.ntotal} != db_chunk_count {db_chunk_count}"
                )
                return False
            bm25 = BM25Index.load(index_record.bm25_path)
            if bm25.corpus_size != db_chunk_count:
                logger.error(
                    f"Active index {index_record.id} BM25 corpus_size {bm25.corpus_size} != db_chunk_count {db_chunk_count}"
                )
                return False
        except Exception as exc:
            logger.error(f"Active index {index_record.id} structure check failed: {exc}")
            return False

    return True


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
    - Ready papers whose published_run_id is set (and status is 'ready')
    - The target paper currently undergoing indexing (if provided with target_run_id)
    Excludes:
    - Deleted papers (not in database or status == 'failed')
    - Reprocessing papers (status == 'processing') unless it is the target_paper_id
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
        if target_paper_id:
            if paper.id == target_paper_id:
                effective_run_id = target_run_id or paper.current_run_id or paper.published_run_id
            elif paper.status == "ready" and paper.published_run_id:
                effective_run_id = paper.published_run_id
            else:
                # Other paper is processing (reprocessing), failed, etc.
                continue
        else:
            # Workspace-level build (e.g. index rebuild or testing)
            if paper.status != "failed":
                effective_run_id = paper.published_run_id or paper.current_run_id
            else:
                continue

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
    job_id: str | None = None,
    claim_token: str | None = None,
    max_retries: int = 3,
    _crash_boundary: str | None = None,
    _pause_hook: Any | None = None,
) -> EmbeddingIndex | None:
    """Build paired FAISS and BM25 index artifacts, validate them, and atomically publish a new index version.

    Follows a crash-safe filesystem and database protocol:
    1. Collects exact eligible chunk manifest across the workspace.
    2. Builds FAISS FlatIP and BM25 in an isolated, unique staging folder (v{version}_prep_{build_id}.tmp).
    3. Validates reloadability, count matching, and calculates SHA-256 checksums.
    4. Serializes publication slot per-workspace before touching final filesystem paths.
    5. Enforces fencing token and lease validation atomically before final path promotion.
    6. Promotes staging directory to immutable final path without overwriting pre-existing targets.
    7. Atomically commits database pointers and updates ONLY the target paper ready status.
    8. Discards only own staging artifacts on CAS conflict; cleans up filesystem changes on rollback.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise ValueError(f"Workspace {workspace_id} not found.")

    ws_dir = get_workspace_index_base_dir(workspace_id, data_dir=data_dir)
    cleanup_stale_staging_directories(workspace_id, data_dir=data_dir)

    for attempt in range(max_retries):
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

        # 3. Setup staging filesystem directory with unique attempt suffix
        build_id = uuid.uuid4().hex[:8]
        staging_dir = ws_dir / f"v{next_version}_prep_{build_id}.tmp"
        final_dir = ws_dir / f"v{next_version}"

        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Write staging_meta.json for ownership-aware staging preservation & cleanup
        staging_meta = {
            "build_id": build_id,
            "workspace_id": workspace_id,
            "target_version": next_version,
            "created_at": time.time(),
            "heartbeat_at": time.time(),
            "ttl_seconds": 120.0,
        }
        with open(staging_dir / "staging_meta.json", "w", encoding="utf-8") as f:
            json.dump(staging_meta, f)

        try:
            if _crash_boundary == "before_artifacts":
                raise CrashBoundaryException("Simulated crash before artifacts finish")

            # 4. Generate / collect embeddings for each chunk in manifest
            manifest_chunks_with_vecs: list[tuple[dict[str, Any], np.ndarray]] = []
            grouped_runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for item in eligible_manifest:
                key = (item["paper_id"], item["run_id"])
                grouped_runs.setdefault(key, []).append(item)

            for (p_id, r_id), run_items in grouped_runs.items():
                expected_ids = [item["chunk_id"] for item in run_items]
                expected_texts = [item["text"] for item in run_items]
                cached = load_generation_embeddings(
                    p_id,
                    r_id,
                    data_dir=data_dir,
                    expected_chunk_ids=expected_ids,
                    expected_chunk_texts=expected_texts,
                )
                if cached is not None:
                    cached_chunk_ids, cached_vecs = cached
                    id_to_vec = {cid: cached_vecs[i] for i, cid in enumerate(cached_chunk_ids)}
                    if all(item["chunk_id"] in id_to_vec for item in run_items):
                        for item in run_items:
                            manifest_chunks_with_vecs.append((item, id_to_vec[item["chunk_id"]]))
                        continue

                # Compute embeddings if not cached or cache invalid
                texts = [item["text"] for item in run_items]
                chunk_ids = [item["chunk_id"] for item in run_items]
                computed_vecs = embed_texts(texts)
                save_generation_embeddings(
                    p_id,
                    r_id,
                    chunk_ids,
                    computed_vecs,
                    chunk_texts=texts,
                    data_dir=data_dir,
                )
                for i, item in enumerate(run_items):
                    manifest_chunks_with_vecs.append((item, computed_vecs[i]))

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

            manifest_sha256 = compute_file_sha256(manifest_file)

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

            checksums = {
                "faiss_sha256": faiss_sha256,
                "bm25_sha256": bm25_sha256,
                "manifest_sha256": manifest_sha256,
            }

            # Optional synchronization hook for deterministic concurrency testing
            if _pause_hook is not None:
                _pause_hook(staging_dir, next_version)

            if _crash_boundary == "lease_loss_during_prep":
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                raise WorkerFencingViolation("Simulated worker lease loss during preparation")

            if _crash_boundary == "before_slot_acquire":
                raise CrashBoundaryException("Simulated crash before publication slot acquisition")

            # 10. Serialized publication slot reservation before mutating final paths
            with acquire_workspace_publication_slot(workspace_id, ws_dir, owner_id=build_id, timeout=30.0):
                # A2: Revalidate processing-job claim token and lease before final-path mutation
                if job_id and claim_token:
                    from backend.app.db.models import ProcessingJob

                    job = (
                        db.query(ProcessingJob)
                        .filter(
                            ProcessingJob.id == job_id,
                            ProcessingJob.claim_token == claim_token,
                            ProcessingJob.status == "running",
                        )
                        .first()
                    )
                    if not job:
                        if staging_dir.exists():
                            shutil.rmtree(staging_dir, ignore_errors=True)
                        raise WorkerFencingViolation(
                            f"Lost claim token or job {job_id} is no longer running before final path mutation"
                        )

                # Pre-publication CAS check within publication slot
                latest_v_check = (
                    db.query(EmbeddingIndex.version)
                    .filter(EmbeddingIndex.workspace_id == workspace_id)
                    .order_by(EmbeddingIndex.version.desc())
                    .first()
                )
                current_max_v = latest_v_check[0] if latest_v_check else 0
                if current_max_v >= next_version:
                    logger.info(
                        f"Workspace {workspace_id} version advanced from {next_version - 1} to {current_max_v} "
                        f"during preparation; discarding own staging and retrying build (attempt {attempt + 1}/{max_retries})."
                    )
                    if staging_dir.exists():
                        shutil.rmtree(staging_dir, ignore_errors=True)
                    continue

                # A2: Check that final directory does NOT exist (never overwrite or delete existing final directory)
                if final_dir.exists():
                    if staging_dir.exists():
                        shutil.rmtree(staging_dir, ignore_errors=True)
                    raise PublicationConflictError(
                        f"Final directory {final_dir} already exists on disk; refusing to overwrite as conflict resolution"
                    )

                if _crash_boundary == "before_promotion":
                    raise CrashBoundaryException("Simulated crash before promotion")

                # 11. Atomic directory promotion to final path
                staging_dir.rename(final_dir)

                if _crash_boundary == "after_promotion":
                    if final_dir.exists():
                        shutil.rmtree(final_dir, ignore_errors=True)
                    raise CrashBoundaryException("Simulated crash after promotion before database activation")

                try:
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

                    # P5-R1: If job_id and claim_token provided, atomically validate fencing and complete job
                    if job_id and claim_token:
                        from backend.app.db.models import ProcessingJob

                        job = (
                            db.query(ProcessingJob)
                            .filter(
                                ProcessingJob.id == job_id,
                                ProcessingJob.claim_token == claim_token,
                                ProcessingJob.status == "running",
                            )
                            .first()
                        )
                        if not job:
                            raise WorkerFencingViolation(
                                f"Lost claim token or job {job_id} is no longer running at index publication boundary"
                            )
                        job.status = "succeeded"
                        job.finished_at = now
                        job.versions_json = json.dumps(
                            {
                                "index_id": new_index.id,
                                "index_version": new_index.version,
                                "model_name": EMBEDDING_MODEL_NAME,
                            }
                        )

                    # P5-R3: ONLY mark the target paper ready if its current run matches target_run_id
                    if target_paper_id:
                        target_paper = db.query(Paper).filter(Paper.id == target_paper_id).first()
                        if target_paper and (target_paper.current_run_id == target_run_id or not target_run_id):
                            target_paper.status = "ready"
                            if target_run_id:
                                target_paper.published_run_id = target_run_id
                            target_paper.updated_at = now
                    else:
                        # Workspace-level build without explicit target paper
                        distinct_paper_ids = list({item["paper_id"] for item in eligible_manifest})
                        for p_id in distinct_paper_ids:
                            p = db.query(Paper).filter(Paper.id == p_id).first()
                            if p and (p.current_run_id == p.published_run_id or not p.current_run_id or p.status == "processing"):
                                p.status = "ready"
                                if p.current_run_id and not p.published_run_id:
                                    p.published_run_id = p.current_run_id
                                p.updated_at = now

                    if _crash_boundary == "during_commit":
                        raise CrashBoundaryException("Simulated crash during database commit")

                    db.commit()
                    db.refresh(new_index)

                    if _crash_boundary == "after_commit":
                        raise CrashBoundaryException("Simulated crash after database commit")

                    logger.info(
                        f"Successfully published active EmbeddingIndex v{next_version} for workspace {workspace_id} "
                        f"with {len(eligible_manifest)} chunks."
                    )
                    return new_index

                except Exception:
                    db.rollback()
                    if final_dir.exists():
                        shutil.rmtree(final_dir, ignore_errors=True)
                    raise

        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    raise RuntimeError(f"Failed to publish workspace index for {workspace_id} after {max_retries} attempts.")


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

    # P5-R6: Artifact integrity & checksum verification (Fail-closed)
    if not verify_index_artifacts_integrity(active_idx, db=db):
        logger.error(f"Integrity check failed for active index {active_idx.id}; returning empty results.")
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

    # P5-R6: Artifact integrity & checksum verification (Fail-closed)
    if not verify_index_artifacts_integrity(active_idx, db=db):
        logger.error(f"Integrity check failed for active index {active_idx.id}; returning empty results.")
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
