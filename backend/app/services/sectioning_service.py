"""ResearchMind AI — Sectioning & Document Cleaning Service (Phase 4).

Implements conservative document cleaning:
- Repeated header/footer removal across >= 3 pages (leaving body text intact)
- Line-wrap hyphenation (e.g. conser-\\nvative -> conservative)
- Common and numbered heading detection
- Honest 'unknown' sections for unclassified or preamble text
- References boundary detection with exclusion flag
- Full provenance mapping: block IDs, page spans, and raw text retention.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any


@dataclasses.dataclass
class SectionResult:
    section_index: int
    section: str  # normalized name: abstract, introduction, methodology, etc. or unknown
    heading: str | None
    page_start: int
    page_end: int
    text: str
    block_ids: list[str]
    is_reference: bool = False
    block_spans: list[tuple[str, int, int, int]] = dataclasses.field(default_factory=list)


# Known section title patterns mapped to canonical section identifiers
SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?abstract(?:\s*[:\-])?$", re.IGNORECASE), "abstract"),
    (re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?introduction(?:\s*[:\-])?$", re.IGNORECASE), "introduction"),
    (
        re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?(?:background|preliminaries)(?:\s*[:\-])?$", re.IGNORECASE),
        "background",
    ),
    (re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?related\s+work(?:s)?(?:\s*[:\-])?$", re.IGNORECASE), "related_work"),
    (
        re.compile(
            r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?(?:methodology|methods|method|model|architecture|proposed\s+(?:method|model|approach)|system\s+overview)(?:\s*[:\-])?$",
            re.IGNORECASE,
        ),
        "methodology",
    ),
    (
        re.compile(
            r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?(?:experiments|experimental\s+(?:setup|results|evaluation)|results|evaluation)(?:\s*[:\-])?$",
            re.IGNORECASE,
        ),
        "results",
    ),
    (re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?discussion(?:\s*[:\-])?$", re.IGNORECASE), "discussion"),
    (
        re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?(?:conclusions?|concluding\s+remarks)(?:\s*[:\-])?$", re.IGNORECASE),
        "conclusion",
    ),
    (
        re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?acknowledg(?:e)?ments?(?:\s*[:\-])?$", re.IGNORECASE),
        "acknowledgments",
    ),
    (
        re.compile(r"^(?:(?:\d+|[IVXLCDM]+)\.?\s*)?(?:references|bibliography)(?:\s*[:\-])?$", re.IGNORECASE),
        "references",
    ),
    (re.compile(r"^(?:appendix(?:\s+[A-Z0-9]+)?)(?:\s*[:\-])?$", re.IGNORECASE), "appendix"),
]

PAGE_NUMBER_PATTERN = re.compile(r"^(?:page\s+)?-?\s*\d+\s*-?(?:\s+of\s+\d+)?$", re.IGNORECASE)


def dehyphenate_text(text: str) -> str:
    """Resolve line-wrap hyphenation conservatively.

    E.g.: 'trans-\\nformer' -> 'transformer'.
    Does not merge hyphenated words like 'state-of-the-art' when both parts are standalone capitalized or distinct.
    """
    if not text:
        return text
    # Match word piece ending with hyphen and newline followed by lowercase word piece
    return re.sub(r"(\b[A-Za-z]+)-\s*\n\s*([a-z]+)", r"\1\2", text)


def detect_repeated_headers_footers(
    pages_data: list[dict[str, Any]],
) -> set[str]:
    """Detect headers and footers that repeat across multiple pages.

    Only inspects the boundary blocks (first block and last block) of pages.
    Middle/body blocks are never collected or removed, ensuring legitimate
    repeated body text survives intact.
    """
    total_pages = len(pages_data)
    if total_pages < 3:
        return set()

    top_candidates: dict[str, int] = {}
    bot_candidates: dict[str, int] = {}

    for p in pages_data:
        blocks = p.get("blocks", [])
        if not blocks:
            continue

        h = p.get("height") or 792.0

        # Check top boundary candidate
        first_b = blocks[0]
        top_text = first_b.get("text", "").strip()
        top_bbox = first_b.get("bbox", [0, 0, 0, 0])
        # Only consider if in top 15% of page
        if top_text and len(top_text) < 120 and (top_bbox[1] <= h * 0.15 or len(blocks) == 1):
            top_candidates[top_text] = top_candidates.get(top_text, 0) + 1

        # Check bottom boundary candidate
        if len(blocks) > 1:
            last_b = blocks[-1]
            bot_text = last_b.get("text", "").strip()
            bot_bbox = last_b.get("bbox", [0, 0, 0, 0])
            if bot_text and len(bot_text) < 120 and (bot_bbox[3] >= h * 0.85):
                bot_candidates[bot_text] = bot_candidates.get(bot_text, 0) + 1

    threshold = max(3, int(total_pages * 0.5))
    repeated: set[str] = set()

    for txt, count in top_candidates.items():
        if count >= threshold:
            repeated.add(txt)

    for txt, count in bot_candidates.items():
        if count >= threshold or (PAGE_NUMBER_PATTERN.match(txt) and count >= 2):
            repeated.add(txt)

    return repeated


def identify_heading(text: str) -> tuple[bool, str, str]:
    """Check if block text constitutes a section heading.

    Returns (is_heading, canonical_section, heading_text).
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) > 100:
        return False, "unknown", ""

    # Don't treat sentences ending with full stop or multiple lines as headings
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) > 2:
        return False, "unknown", ""

    first_line = lines[0]
    if first_line.endswith(".") and not re.match(r"^\d+\.", first_line):
        return False, "unknown", ""

    for pattern, canonical in SECTION_PATTERNS:
        if pattern.match(first_line):
            return True, canonical, cleaned

    # Check for general numbered heading: e.g. "1. Problem Formulation" or "3. Model Architecture"
    numbered_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+([A-Za-z0-9\s\-_/]{3,60})$", first_line)
    if numbered_match:
        title = numbered_match.group(2).lower()
        if "experiment" in title or "result" in title or "evaluat" in title:
            return True, "results", cleaned
        if "method" in title or "model" in title or "architect" in title or "approach" in title:
            return True, "methodology", cleaned
        if "intro" in title:
            return True, "introduction", cleaned
        if "relat" in title:
            return True, "related_work", cleaned
        if "conclu" in title:
            return True, "conclusion", cleaned
        if "referen" in title or "biblio" in title:
            return True, "references", cleaned
        return True, "unknown", cleaned

    return False, "unknown", ""


def section_pages(pages_data: list[dict[str, Any]]) -> list[SectionResult]:
    """Segment extracted pages into conservative cleaned sections.

    pages_data: list of dicts with:
      page_number: int
      blocks: list of dict(id, bbox, text, text_hash)
      height: float | None
      width: float | None
    """
    if not pages_data:
        return []

    repeated_headers_footers = detect_repeated_headers_footers(pages_data)

    current_section = "unknown"
    current_heading: str | None = None
    current_blocks: list[str] = []
    current_items: list[tuple[str, int, str]] = []  # (b_id, page_num, text)
    current_page_start: int | None = None
    current_page_end: int | None = None

    sections: list[SectionResult] = []

    def flush_current():
        nonlocal current_section, current_heading, current_blocks, current_items
        nonlocal current_page_start, current_page_end

        parts: list[str] = []
        block_spans: list[tuple[str, int, int, int]] = []
        curr_offset = 0

        for b_id, p_num, b_text in current_items:
            t = b_text.strip()
            if not t:
                continue
            if parts:
                curr_offset += 2  # for separator "\n\n"
            start_c = curr_offset
            end_c = start_c + len(t)
            block_spans.append((b_id, p_num, start_c, end_c))
            parts.append(t)
            curr_offset = end_c

        joined = "\n\n".join(parts)
        cleaned = dehyphenate_text(joined)

        # Scale offsets if dehyphenation altered character length
        if len(joined) > 0 and len(cleaned) != len(joined):
            scale = len(cleaned) / len(joined)
            adjusted_spans: list[tuple[str, int, int, int]] = []
            for b_id, p_num, s_c, e_c in block_spans:
                adj_s = int(s_c * scale)
                adj_e = int(e_c * scale)
                adjusted_spans.append((b_id, p_num, adj_s, max(adj_s + 1, adj_e)))
            block_spans = adjusted_spans

        if cleaned or current_blocks:
            sec_idx = len(sections)
            is_ref = current_section == "references"
            sections.append(
                SectionResult(
                    section_index=sec_idx,
                    section=current_section,
                    heading=current_heading,
                    page_start=current_page_start or 1,
                    page_end=current_page_end or current_page_start or 1,
                    text=cleaned,
                    block_ids=list(current_blocks),
                    is_reference=is_ref,
                    block_spans=block_spans,
                )
            )

        current_blocks = []
        current_items = []
        current_page_start = None
        current_page_end = None

    for p in pages_data:
        page_num = p.get("page_number", 1)
        blocks = p.get("blocks", [])

        h = p.get("height") or 792.0

        for idx, b in enumerate(blocks):
            raw_b_text = b.get("text", "").strip()
            if not raw_b_text:
                continue

            b_id = b.get("id") or f"p{page_num}_b{idx}"
            bbox = b.get("bbox", [0, 0, 0, 0])

            # Filter out top/bottom boundary repeated headers/footers
            is_boundary = (idx == 0 and bbox[1] <= h * 0.15) or (idx == len(blocks) - 1 and bbox[3] >= h * 0.85)
            if is_boundary and raw_b_text in repeated_headers_footers:
                continue
            if is_boundary and PAGE_NUMBER_PATTERN.match(raw_b_text):
                continue

            # Check if this block is a section heading
            is_heading, detected_section, heading_text = identify_heading(raw_b_text)

            if is_heading:
                # Flush previous section
                flush_current()

                # Start new section
                current_section = detected_section
                current_heading = heading_text
                current_page_start = page_num
                current_page_end = page_num
                current_blocks.append(b_id)
                current_items.append((b_id, page_num, heading_text))
            else:
                if current_page_start is None:
                    current_page_start = page_num
                current_page_end = page_num
                current_blocks.append(b_id)
                current_items.append((b_id, page_num, raw_b_text))

    flush_current()

    # If document had no text or only headings with no content, ensure at least one section if blocks exist
    if not sections and pages_data:
        sections.append(
            SectionResult(
                section_index=0,
                section="unknown",
                heading=None,
                page_start=1,
                page_end=len(pages_data),
                text="",
                block_ids=[],
                is_reference=False,
            )
        )

    return sections
