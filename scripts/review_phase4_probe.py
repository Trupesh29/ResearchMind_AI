"""Read-only Phase 4 tokenizer and provenance diagnostics (no user data)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transformers import AutoTokenizer

from backend.app.services.chunking_service import (
    TOKENIZER_MODEL_NAME,
    TOKENIZER_REVISION,
    chunk_section,
    split_oversized_sentence,
)
from backend.app.services.sectioning_service import SectionResult

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_MODEL_NAME, local_files_only=True)
print("DECLARED_REVISION", TOKENIZER_REVISION)
print("LOADED_TOKENIZER_PATH", tokenizer.name_or_path)
for size in (400, 1200):
    text = "研" * size
    pieces = split_oversized_sentence(text, tokenizer, max_tokens=150)
    print("INPUT_CHARS", size, "OUTPUT_CHARS", sum(map(len, pieces)))
    print("PIECE_TOKENS", [len(tokenizer.encode(p, add_special_tokens=True)) for p in pieces])
    print("SPLIT_UNCHANGED", pieces == [text])

section = SectionResult(
    section_index=0,
    section="unknown",
    heading=None,
    page_start=1,
    page_end=2,
    text=("Alpha evidence appears only on the first page. " * 35)
    + ("Beta evidence appears only on the second page. " * 35),
    block_ids=["page1-alpha", "page2-beta"],
)
chunks = chunk_section(section, tokenizer)
print("FIRST_CHUNK_CONTAINS_BETA", "Beta" in chunks[0].text)
print("FIRST_CHUNK_SOURCE", chunks[0].page_start, chunks[0].page_end, chunks[0].block_ids)
print("LAST_CHUNK_CONTAINS_ALPHA", "Alpha" in chunks[-1].text)
print("LAST_CHUNK_SOURCE", chunks[-1].page_start, chunks[-1].page_end, chunks[-1].block_ids)
