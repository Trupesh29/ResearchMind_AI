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

import json
import logging
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
    data_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Persist generated embeddings and chunk ID manifest for a paper generation run."""
    cache_dir = get_embedding_cache_dir(paper_id, data_dir=data_dir)
    vec_path = cache_dir / f"{run_id}_vectors.npy"
    meta_path = cache_dir / f"{run_id}_meta.json"

    # Write vectors
    np.save(str(vec_path), vectors)

    # Write chunk ID mapping
    meta = {
        "paper_id": paper_id,
        "run_id": run_id,
        "chunk_ids": chunk_ids,
        "count": len(chunk_ids),
        "dimension": vectors.shape[1] if vectors.ndim > 1 else EMBEDDING_DIMENSION,
        "model_name": EMBEDDING_MODEL_NAME,
        "model_revision": EMBEDDING_MODEL_REVISION,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return vec_path, meta_path


def load_generation_embeddings(
    paper_id: str,
    run_id: str,
    data_dir: Path | None = None,
) -> tuple[list[str], np.ndarray] | None:
    """Load cached embeddings and chunk IDs for a paper generation run if available."""
    cache_dir = get_embedding_cache_dir(paper_id, data_dir=data_dir)
    vec_path = cache_dir / f"{run_id}_vectors.npy"
    meta_path = cache_dir / f"{run_id}_meta.json"

    if not vec_path.exists() or not meta_path.exists():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        vectors = np.load(str(vec_path))
        chunk_ids = meta.get("chunk_ids", [])
        if len(chunk_ids) != len(vectors):
            logger.warning(f"Cache mismatch for {paper_id}/{run_id}: {len(chunk_ids)} chunk_ids != {len(vectors)} vecs")
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
    cached = load_generation_embeddings(paper_id, run_id, data_dir=data_dir)
    if cached is not None:
        chunk_ids, vectors = cached
        return vectors, chunk_ids

    chunk_ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    save_generation_embeddings(paper_id, run_id, chunk_ids, vectors, data_dir=data_dir)
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
