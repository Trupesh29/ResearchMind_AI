"""ResearchMind AI — Token-Safe Sentence-Aware Chunking Service (Phase 4).

Features:
- MiniLM tokenizer with pinned revision and actual 256-token model sequence limit
- Exact token measurement of final embedding input including special tokens ([CLS], [SEP])
- Baseline 200 tokens with 20% target overlap (~40 tokens)
- Sentence-aware boundaries with clause-level fallback for oversized sentences
- Strict prohibition on silent truncation (asserts <= 256 tokens)
- Provenance tracking (page_start, page_end, block_ids, section)
- Reference chunk exclusion flag (is_excluded = 1 for references section)
- Decoupled from embedding indexes (pure ingestion generation storage).
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

from transformers import AutoTokenizer

from backend.app.core.config import settings
from backend.app.services.sectioning_service import SectionResult

logger = logging.getLogger(__name__)

# Pinned tokenizer metadata and model limit
TOKENIZER_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
TOKENIZER_REVISION: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

# The actual sequence limit for MiniLM embedding is 256 tokens (not 512 or 10000 sentinel)
MODEL_MAX_SEQUENCE_LIMIT: int = 256

# Configuration baseline
TARGET_CHUNK_TOKENS: int = 200
TARGET_OVERLAP_TOKENS: int = 40  # 20% of 200

# Global cached tokenizer singleton
_tokenizer_instance: AutoTokenizer | None = None


def get_tokenizer() -> AutoTokenizer:
    """Retrieve or initialize the cached MiniLM AutoTokenizer instance.

    Raises RuntimeError with actionable message if tokenizer assets cannot be loaded.
    Never silently falls back to an unpinned revision or invalid sequence length.
    """
    global _tokenizer_instance
    if _tokenizer_instance is None:
        model_name = getattr(settings, "EMBEDDING_MODEL_NAME", TOKENIZER_MODEL_NAME) or TOKENIZER_MODEL_NAME
        revision = getattr(settings, "EMBEDDING_MODEL_REVISION", TOKENIZER_REVISION) or TOKENIZER_REVISION

        if model_name != TOKENIZER_MODEL_NAME:
            raise ValueError(
                f"Unsupported embedding model '{model_name}'. "
                f"Phase 4 ingestion requires supported baseline '{TOKENIZER_MODEL_NAME}'."
            )
        if revision != TOKENIZER_REVISION:
            raise ValueError(
                f"Unsupported revision '{revision}' for model '{model_name}'. "
                f"Expected pinned revision '{TOKENIZER_REVISION}'."
            )

        candidate: AutoTokenizer | None = None
        try:
            # First try loading locally with the pinned revision
            candidate = AutoTokenizer.from_pretrained(
                model_name,
                revision=revision,
                local_files_only=True,
            )
        except Exception:
            try:
                # If not present in local cache with pinned revision, load with revision
                candidate = AutoTokenizer.from_pretrained(
                    model_name,
                    revision=revision,
                    local_files_only=False,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Actionable Error: Could not load tokenizer '{model_name}' at pinned revision '{revision}'. "
                    f"Ensure model assets for revision '{revision}' are cached or network access is available: {exc}"
                ) from exc

        # Verify model / tokenizer configuration and sequence limit
        model_max = getattr(candidate, "model_max_length", None)
        if model_max is not None and model_max < MODEL_MAX_SEQUENCE_LIMIT:
            raise ValueError(
                f"Configured tokenizer sequence limit {model_max} is less than required limit {MODEL_MAX_SEQUENCE_LIMIT}."
            )
        _tokenizer_instance = candidate
    return _tokenizer_instance


def get_tokenizer_metadata() -> dict[str, Any]:
    """Retrieve verified tokenizer and chunking configuration metadata."""
    tok = get_tokenizer()
    model_name = getattr(settings, "EMBEDDING_MODEL_NAME", TOKENIZER_MODEL_NAME) or TOKENIZER_MODEL_NAME
    revision = getattr(settings, "EMBEDDING_MODEL_REVISION", TOKENIZER_REVISION) or TOKENIZER_REVISION
    model_max = getattr(tok, "model_max_length", None)
    return {
        "tokenizer": model_name,
        "revision": revision,
        "model_max_length": model_max,
        "max_sequence_limit": MODEL_MAX_SEQUENCE_LIMIT,
        "target_tokens": TARGET_CHUNK_TOKENS,
        "overlap_tokens": TARGET_OVERLAP_TOKENS,
    }


@dataclasses.dataclass
class ChunkResult:
    chunk_index: int
    page_start: int
    page_end: int
    section: str
    text: str
    token_count: int  # measured with special tokens
    block_ids: list[str]
    is_excluded: bool
    tokenizer_name: str
    tokenizer_revision: str


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences cleanly, preserving meaningful punctuation."""
    if not text or not text.strip():
        return []

    # Normalized text
    cleaned = text.strip()

    # Split on sentence boundaries: periods/exclamation/question marks followed by whitespace and capital letter or digit
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])", cleaned)
    sentences: list[str] = []

    for s in raw_sentences:
        s_strip = s.strip()
        if s_strip:
            sentences.append(s_strip)

    if not sentences and cleaned:
        sentences = [cleaned]

    return sentences


def split_oversized_sentence(
    sentence: str,
    tokenizer: AutoTokenizer,
    max_tokens: int = TARGET_CHUNK_TOKENS - 20,
) -> list[str]:
    """Losslessly and progressively split an oversized sentence that exceeds max_tokens.

    Splits by clauses (semicolons, colons, commas, dashes, words), and falls back
    to guaranteed-progress binary bisection for giant continuous tokens, unbroken CJK,
    or uninterrupted identifiers. Zero truncation or character loss.
    """
    enc = tokenizer.encode(sentence, add_special_tokens=False)
    if len(enc) <= max_tokens:
        return [sentence]

    if len(sentence) <= 1:
        return [sentence]

    # Try splitting by semicolons or colons
    parts = re.split(r"(?<=[;:])\s+", sentence)
    if len(parts) > 1 and all(len(p) < len(sentence) for p in parts):
        result: list[str] = []
        for part in parts:
            result.extend(split_oversized_sentence(part, tokenizer, max_tokens))
        return result

    # Try splitting by commas or dashes
    parts = re.split(r"(?<=[,\—\–])\s+", sentence)
    if len(parts) > 1 and all(len(p) < len(sentence) for p in parts):
        result = []
        for part in parts:
            result.extend(split_oversized_sentence(part, tokenizer, max_tokens))
        return result

    # Try splitting by words
    words = sentence.split()
    if len(words) > 1:
        chunks: list[str] = []
        current_words: list[str] = []

        for word in words:
            candidate = " ".join(current_words + [word])
            cand_tokens = len(tokenizer.encode(candidate, add_special_tokens=False))
            if cand_tokens > max_tokens and current_words:
                sub_res = split_oversized_sentence(" ".join(current_words), tokenizer, max_tokens)
                chunks.extend(sub_res)
                # Word itself might exceed max_tokens
                word_tokens = len(tokenizer.encode(word, add_special_tokens=False))
                if word_tokens > max_tokens:
                    chunks.extend(split_oversized_sentence(word, tokenizer, max_tokens))
                    current_words = []
                else:
                    current_words = [word]
            else:
                current_words.append(word)

        if current_words:
            sub_res = split_oversized_sentence(" ".join(current_words), tokenizer, max_tokens)
            chunks.extend(sub_res)

        if len(chunks) > 1 or (len(chunks) == 1 and chunks[0] != sentence):
            return chunks

    # Guaranteed-progress binary bisection for continuous strings (CJK, DNA, uninterrupted runs)
    # Strictly reduces length on each branch, preserving all characters losslessly.
    mid = len(sentence) // 2
    if mid > 0:
        left = sentence[:mid]
        right = sentence[mid:]
        return split_oversized_sentence(left, tokenizer, max_tokens) + split_oversized_sentence(
            right, tokenizer, max_tokens
        )

    return [sentence]


def chunk_section(
    section: SectionResult,
    tokenizer: AutoTokenizer,
    start_chunk_index: int = 0,
) -> list[ChunkResult]:
    """Generate sentence-aware, token-safe chunks from a single document section.

    - Target: ~200 tokens
    - Overlap: ~40 tokens (20%)
    - Strict ceiling: measured tokens with special tokens <= 256
    - Never silently truncates.
    - True fine-grained provenance: maps each chunk only to contributing blocks and pages.
    """
    text = section.text.strip()
    if not text:
        return []

    # 1. Resolve block spans for provenance
    block_spans = list(section.block_spans)

    # 2. Split into base sentences
    raw_sentences = split_into_sentences(text)

    # 3. Decompose oversized sentences into token-safe units
    safe_units: list[str] = []
    for s in raw_sentences:
        # Leave headroom for special tokens ([CLS] and [SEP] = 2 tokens) + sentence assembly
        safe_units.extend(split_oversized_sentence(s, tokenizer, max_tokens=TARGET_CHUNK_TOKENS - 10))

    if not safe_units:
        return []

    # Pre-calculate token counts for units (without special tokens) and map character spans
    unit_token_counts = [len(tokenizer.encode(u, add_special_tokens=False)) for u in safe_units]
    safe_unit_spans: list[tuple[int, int]] = []
    search_pos = 0
    for u in safe_units:
        u_clean = u.strip()
        idx = text.find(u_clean, search_pos)
        if idx != -1:
            u_start = idx
            u_end = idx + len(u_clean)
            search_pos = u_end
        else:
            u_start = search_pos
            u_end = min(len(text), search_pos + len(u_clean))
            search_pos = u_end
        safe_unit_spans.append((u_start, u_end))

    chunks: list[ChunkResult] = []
    chunk_idx = start_chunk_index

    i = 0
    total_units = len(safe_units)

    while i < total_units:
        current_chunk_units: list[str] = []
        end_idx = i

        while end_idx < total_units:
            u_text = safe_units[end_idx]

            # Projected tokens if we add u_text: measure with special tokens
            candidate_text = " ".join(current_chunk_units + [u_text])
            candidate_total = len(tokenizer.encode(candidate_text, add_special_tokens=True))

            # Must strictly obey hard limit <= MODEL_MAX_SEQUENCE_LIMIT (256)
            if candidate_total > MODEL_MAX_SEQUENCE_LIMIT:
                if not current_chunk_units:
                    # Single unit too large for limit: bisect further
                    further_split = split_oversized_sentence(u_text, tokenizer, max_tokens=150)
                    safe_units[end_idx : end_idx + 1] = further_split
                    unit_token_counts[end_idx : end_idx + 1] = [
                        len(tokenizer.encode(fu, add_special_tokens=False)) for fu in further_split
                    ]
                    # Update spans for split units
                    orig_span = safe_unit_spans[end_idx]
                    split_spans: list[tuple[int, int]] = []
                    sub_pos = orig_span[0]
                    for fu in further_split:
                        fu_len = len(fu.strip())
                        split_spans.append((sub_pos, min(orig_span[1], sub_pos + fu_len)))
                        sub_pos += fu_len
                    safe_unit_spans[end_idx : end_idx + 1] = split_spans
                    total_units = len(safe_units)
                    continue
                break

            # If we've reached target 200 tokens and have at least 1 unit, stop accumulating
            if candidate_total >= TARGET_CHUNK_TOKENS and current_chunk_units:
                # Add this unit if candidate_total <= TARGET_CHUNK_TOKENS + 15, else break
                if candidate_total <= TARGET_CHUNK_TOKENS + 15 and candidate_total <= MODEL_MAX_SEQUENCE_LIMIT:
                    current_chunk_units.append(u_text)
                    end_idx += 1
                break

            current_chunk_units.append(u_text)
            end_idx += 1

        chunk_text = " ".join(current_chunk_units).strip()
        final_measured_tokens = len(tokenizer.encode(chunk_text, add_special_tokens=True))

        # Hard assertion: never exceed actual model limit
        if final_measured_tokens > MODEL_MAX_SEQUENCE_LIMIT:
            raise ValueError(
                f"Chunk token count {final_measured_tokens} strictly exceeds model limit {MODEL_MAX_SEQUENCE_LIMIT}!"
            )

        # Attribute contributing block IDs and page spans based on chunk character coverage
        chunk_c_start = safe_unit_spans[i][0]
        chunk_c_end = safe_unit_spans[end_idx - 1][1]

        chunk_blocks: list[str] = []
        chunk_pages: list[int] = []

        if block_spans:
            for b_id, p_num, b_start, b_end in block_spans:
                if max(chunk_c_start, b_start) < min(chunk_c_end, b_end):
                    chunk_blocks.append(b_id)
                    chunk_pages.append(p_num)

        distinct_blocks = list(dict.fromkeys(chunk_blocks))
        page_start = min(chunk_pages) if chunk_pages else section.page_start
        page_end = max(chunk_pages) if chunk_pages else section.page_end

        meta = get_tokenizer_metadata()
        chunks.append(
            ChunkResult(
                chunk_index=chunk_idx,
                page_start=page_start,
                page_end=page_end,
                section=section.section,
                text=chunk_text,
                token_count=final_measured_tokens,
                block_ids=distinct_blocks,
                is_excluded=section.is_reference,
                tokenizer_name=meta["tokenizer"],
                tokenizer_revision=meta["revision"],
            )
        )
        chunk_idx += 1

        if end_idx >= total_units:
            break

        # Calculate overlap of ~40 tokens from the tail of current_chunk_units
        overlap_units_count = 0
        overlap_tokens = 0
        back_idx = end_idx - 1

        while back_idx >= i and overlap_units_count < len(current_chunk_units) - 1:
            u_tok = unit_token_counts[back_idx]
            if overlap_tokens + u_tok > TARGET_OVERLAP_TOKENS and overlap_units_count > 0:
                break
            overlap_tokens += u_tok
            overlap_units_count += 1
            back_idx -= 1

        # Advance i, guaranteeing strictly forward progress (i < next_i)
        next_i = max(i + 1, end_idx - overlap_units_count)
        i = next_i

    return chunks


def chunk_document_sections(sections: list[SectionResult]) -> list[ChunkResult]:
    """Generate sequential chunks across all sections of a document."""
    tokenizer = get_tokenizer()
    all_chunks: list[ChunkResult] = []
    current_idx = 0

    for sec in sections:
        sec_chunks = chunk_section(sec, tokenizer, start_chunk_index=current_idx)
        all_chunks.extend(sec_chunks)
        current_idx += len(sec_chunks)

    return all_chunks
