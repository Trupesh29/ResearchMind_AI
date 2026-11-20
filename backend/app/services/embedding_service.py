"""ResearchMind AI — Pinned MiniLM Embedding Service (Phase 5).

Features:
- SentenceTransformers with pinned all-MiniLM-L6-v2 revision
- Strict sequence limit validation (<= 256 tokens including special tokens)
- CPU execution with graceful hardware fallback
- L2-normalized float32 vectors (384 dimensions)
- Bounded batch encoding
- Nonfinite vector (NaN / Inf) detection and rejection
- Idempotent generation embedding cache to ensure restart safety
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.app.core.config import get_settings
from backend.app.services.chunking_service import (
    MODEL_MAX_SEQUENCE_LIMIT,
    TOKENIZER_MODEL_NAME,
    TOKENIZER_REVISION,
    get_tokenizer,
)

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME: str = TOKENIZER_MODEL_NAME
EMBEDDING_MODEL_REVISION: str = TOKENIZER_REVISION
EMBEDDING_DIMENSION: int = 384
EMBEDDING_NORMALIZATION: str = "l2"

_embedding_model_instance: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Retrieve or initialize the cached SentenceTransformer singleton on CPU/configured device."""
    global _embedding_model_instance
    if _embedding_model_instance is None:
        current_settings = get_settings()
        model_name = getattr(current_settings, "EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_NAME) or EMBEDDING_MODEL_NAME
        revision = getattr(current_settings, "EMBEDDING_MODEL_REVISION", EMBEDDING_MODEL_REVISION) or EMBEDDING_MODEL_REVISION

        if model_name != EMBEDDING_MODEL_NAME:
            raise ValueError(
                f"Unsupported embedding model '{model_name}'. Expected baseline '{EMBEDDING_MODEL_NAME}'."
            )
        if revision != EMBEDDING_MODEL_REVISION:
            raise ValueError(
                f"Unsupported revision '{revision}' for model '{model_name}'. Expected '{EMBEDDING_MODEL_REVISION}'."
            )

        configured_device = getattr(current_settings, "EMBEDDING_DEVICE", "cpu") or "cpu"
        if configured_device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        else:
            device = configured_device

        try:
            model = SentenceTransformer(model_name, device=device)
        except Exception as exc:
            raise RuntimeError(
                f"Actionable Error: Could not load SentenceTransformer '{model_name}'. "
                f"Ensure model weights are cached locally: {exc}"
            ) from exc

        _embedding_model_instance = model
    return _embedding_model_instance


def validate_text_for_embedding(text: str) -> int:
    """Validate that text does not exceed the model's exact sequence limit including special tokens.

    Raises ValueError if sequence exceeds MODEL_MAX_SEQUENCE_LIMIT (256).
    Never silently truncates input.
    """
    tok = get_tokenizer()
    encoded = tok(text, add_special_tokens=True, truncation=False)
    input_ids = encoded["input_ids"]
    token_count = len(input_ids)
    if token_count > MODEL_MAX_SEQUENCE_LIMIT:
        raise ValueError(
            f"Chunk token count {token_count} exceeds model sequence limit of {MODEL_MAX_SEQUENCE_LIMIT} tokens. "
            f"Silent truncation is strictly prohibited."
        )
    return token_count


def embed_texts(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """Embed a list of pre-validated texts into L2-normalized float32 vectors.

    Validates every text sequence length before encoding.
    Asserts finite float values and exact dimension (384).
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIMENSION), dtype=np.float32)

    # 1. Validate every input token count
    for idx, text in enumerate(texts):
        validate_text_for_embedding(text)

    # 2. Encode in bounded batches with normalization
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        batch_size=max(1, batch_size),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # 3. Shape and value assertions
    if embeddings.shape != (len(texts), EMBEDDING_DIMENSION):
        raise ValueError(
            f"Expected embedding matrix shape ({len(texts)}, {EMBEDDING_DIMENSION}), got {embeddings.shape}"
        )
    if not np.all(np.isfinite(embeddings)):
        raise ValueError("Generated embeddings contain non-finite values (NaN or Inf).")

    return embeddings.astype(np.float32)


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


def get_embedding_cache_dir(paper_id: str, data_dir: Path | None = None) -> Path:
    """Return the filesystem directory used to cache per-paper generation embeddings."""
    base_dir = _resolve_data_dir(data_dir)
    target_dir = Path(base_dir) / "embeddings" / paper_id
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def save_generation_embeddings(
    paper_id: str,
    run_id: str,
    chunk_ids: list[str],
    vectors: np.ndarray,
    chunk_texts: list[str] | None = None,
    data_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Persist generated embeddings and chunk ID manifest for a paper generation run.

    Uses an atomic staging file write and rename to prevent partial/corrupt caches.
    Computes and records SHA-256 checksums, exact model metadata, float32 dtype, and L2 normalization.
    """
    cache_dir = get_embedding_cache_dir(paper_id, data_dir=data_dir)
    vec_path = cache_dir / f"{run_id}_vectors.npy"
    meta_path = cache_dir / f"{run_id}_meta.json"
    vec_tmp = cache_dir / f"{run_id}_vectors_{uuid.uuid4().hex[:8]}.tmp.npy"
    meta_tmp = cache_dir / f"{run_id}_meta_{uuid.uuid4().hex[:8]}.tmp.json"

    vecs_f32 = vectors.astype(np.float32)
    with open(vec_tmp, "wb") as f:
        np.save(f, vecs_f32)

    hasher = hashlib.sha256()
    with open(vec_tmp, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    vec_sha256 = hasher.hexdigest()

    chunk_hashes: list[str] = []
    if chunk_texts is not None:
        chunk_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in chunk_texts]

    meta = {
        "paper_id": paper_id,
        "run_id": run_id,
        "chunk_ids": chunk_ids,
        "chunk_hashes": chunk_hashes,
        "count": len(chunk_ids),
        "dimension": vecs_f32.shape[1] if vecs_f32.ndim > 1 else EMBEDDING_DIMENSION,
        "dtype": "float32",
        "normalization": EMBEDDING_NORMALIZATION,
        "model_name": EMBEDDING_MODEL_NAME,
        "model_revision": EMBEDDING_MODEL_REVISION,
        "vectors_sha256": vec_sha256,
    }
    with open(meta_tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    os.replace(vec_tmp, vec_path)
    os.replace(meta_tmp, meta_path)

    return vec_path, meta_path


def load_generation_embeddings(
    paper_id: str,
    run_id: str,
    data_dir: Path | None = None,
    expected_chunk_ids: list[str] | None = None,
    expected_chunk_texts: list[str] | None = None,
) -> tuple[list[str], np.ndarray] | None:
    """Load cached embeddings and chunk IDs for a paper generation run if available and valid.

    Strictly validates:
    - Metadata model name, model revision, dimension, and normalization
    - Vector file SHA-256 checksum matching metadata
    - Array shape, float32 type, and non-empty vector dimensions
    - Finite float values (strictly rejects NaN and Inf)
    - Unit L2 normalization (tolerance 1e-3)
    - Consistency with expected chunk IDs and chunk content hashes if provided
    Returns None on any corruption, mismatch, or error, triggering clean re-embedding.
    """
    cache_dir = get_embedding_cache_dir(paper_id, data_dir=data_dir)
    vec_path = cache_dir / f"{run_id}_vectors.npy"
    meta_path = cache_dir / f"{run_id}_meta.json"

    if not vec_path.exists() or not meta_path.exists():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # 1. Model and parameter verification
        if meta.get("model_name") != EMBEDDING_MODEL_NAME:
            logger.warning(
                f"Embedding cache model mismatch for {paper_id}/{run_id}: "
                f"{meta.get('model_name')} != {EMBEDDING_MODEL_NAME}"
            )
            return None
        if meta.get("model_revision") != EMBEDDING_MODEL_REVISION:
            logger.warning(
                f"Embedding cache revision mismatch for {paper_id}/{run_id}: "
                f"{meta.get('model_revision')} != {EMBEDDING_MODEL_REVISION}"
            )
            return None
        if meta.get("dimension") != EMBEDDING_DIMENSION:
            logger.warning(
                f"Embedding cache dimension mismatch for {paper_id}/{run_id}: "
                f"{meta.get('dimension')} != {EMBEDDING_DIMENSION}"
            )
            return None
        if meta.get("dtype") != "float32":
            logger.warning(
                f"Embedding cache dtype mismatch for {paper_id}/{run_id}: "
                f"{meta.get('dtype')} != float32"
            )
            return None
        if meta.get("normalization") != EMBEDDING_NORMALIZATION:
            logger.warning(
                f"Embedding cache normalization mismatch for {paper_id}/{run_id}: "
                f"{meta.get('normalization')} != {EMBEDDING_NORMALIZATION}"
            )
            return None

        # 2. Vector file checksum verification
        expected_sha = meta.get("vectors_sha256")
        if expected_sha:
            hasher = hashlib.sha256()
            with open(vec_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha = hasher.hexdigest()
            if actual_sha != expected_sha:
                logger.warning(
                    f"Embedding cache checksum mismatch for {paper_id}/{run_id}: {actual_sha} != {expected_sha}"
                )
                return None

        # 3. Load vectors and validate dimensions and counts
        vectors = np.load(str(vec_path))
        chunk_ids = meta.get("chunk_ids", [])
        if len(chunk_ids) != len(vectors):
            logger.warning(f"Cache mismatch for {paper_id}/{run_id}: {len(chunk_ids)} chunk_ids != {len(vectors)} vecs")
            return None

        if len(vectors) > 0 and (vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIMENSION):
            logger.warning(
                f"Embedding cache invalid shape for {paper_id}/{run_id}: expected (N, {EMBEDDING_DIMENSION}), got {vectors.shape}"
            )
            return None

        # 4. Finite checks (NaN / Inf)
        if not np.all(np.isfinite(vectors)):
            logger.warning(f"Embedding cache contains non-finite values (NaN / Inf) for {paper_id}/{run_id}")
            return None

        # 5. Unit L2 norm verification
        if len(vectors) > 0:
            norms = np.linalg.norm(vectors, axis=1)
            if not np.all(np.abs(norms - 1.0) < 1e-3):
                logger.warning(f"Embedding cache contains unnormalized vectors for {paper_id}/{run_id}")
                return None

        # 6. Expected chunk IDs / hashes verification if supplied
        if expected_chunk_ids is not None and chunk_ids != expected_chunk_ids:
            logger.warning(f"Embedding cache chunk ID ordering mismatch for {paper_id}/{run_id}")
            return None

        if expected_chunk_texts is not None:
            expected_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in expected_chunk_texts]
            cached_hashes = meta.get("chunk_hashes", [])
            if cached_hashes and cached_hashes != expected_hashes:
                logger.warning(f"Embedding cache chunk text content hash mismatch for {paper_id}/{run_id}")
                return None

        return chunk_ids, vectors.astype(np.float32)
    except Exception as exc:
        logger.warning(f"Failed to load cached embeddings for {paper_id}/{run_id}: {exc}")
        return None


def get_or_compute_generation_embeddings(
    data_dir: Path,
    paper_id: str,
    run_id: str,
    chunks: list[dict],
) -> tuple[np.ndarray, list[str]]:
    """Retrieve cached generation embeddings or compute, validate, and cache them idempotently."""
    chunk_ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]

    cached = load_generation_embeddings(
        paper_id,
        run_id,
        data_dir=data_dir,
        expected_chunk_ids=chunk_ids,
        expected_chunk_texts=texts,
    )
    if cached is not None:
        cached_chunk_ids, vectors = cached
        return vectors, cached_chunk_ids

    vectors = embed_texts(texts)
    save_generation_embeddings(
        paper_id,
        run_id,
        chunk_ids,
        vectors,
        chunk_texts=texts,
        data_dir=data_dir,
    )
    return vectors, chunk_ids


def get_embedding_metadata() -> dict[str, Any]:
    """Return dictionary of verified embedding model metadata and parameters."""
    return {
        "model_name": EMBEDDING_MODEL_NAME,
        "model_revision": EMBEDDING_MODEL_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "normalization": EMBEDDING_NORMALIZATION,
        "sequence_limit": MODEL_MAX_SEQUENCE_LIMIT,
    }
