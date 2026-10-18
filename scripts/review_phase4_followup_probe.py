"""Disposable diagnostics for Phase 4 repair source attribution and loader state."""

import dataclasses
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transformers import AutoTokenizer

from backend.app.services import chunking_service as cs
from backend.app.services.sectioning_service import section_pages

tokenizer = AutoTokenizer.from_pretrained(cs.TOKENIZER_MODEL_NAME, local_files_only=True)
alpha = "Alpha evidence exists only on page one. " * 100
beta = "Beta evidence exists only on page two."
section = section_pages(
    [
        {"page_number": 1, "height": 792, "blocks": [{"id": "a", "bbox": [20, 100, 500, 600], "text": alpha}]},
        {"page_number": 2, "height": 792, "blocks": [{"id": "b", "bbox": [20, 100, 500, 600], "text": beta}]},
    ]
)[0]
# Worker persists section text and block IDs, but not block_spans; reconstruction loses them.
reconstructed = dataclasses.replace(section, block_spans=[])
bad = [c for c in cs.chunk_section(reconstructed, tokenizer) if "Beta" not in c.text and "b" in c.block_ids]
print("ALPHA_ONLY_CHUNKS_ATTRIBUTED_TO_PAGE2", len(bad))
if bad:
    print("EXAMPLE", bad[0].page_start, bad[0].page_end, bad[0].block_ids)


class TooSmallTokenizer:
    model_max_length = 128


previous = cs._tokenizer_instance
try:
    cs._tokenizer_instance = None
    with patch.object(cs.AutoTokenizer, "from_pretrained", return_value=TooSmallTokenizer()):
        try:
            cs.get_tokenizer()
        except ValueError:
            print("FIRST_INVALID_LOAD_REJECTED", True)
        print("SECOND_INVALID_LOAD_ACCEPTED", cs.get_tokenizer().model_max_length == 128)
finally:
    cs._tokenizer_instance = previous
