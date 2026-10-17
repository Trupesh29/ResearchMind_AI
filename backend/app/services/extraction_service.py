"""ResearchMind AI — PDF Extraction and Quality Analysis Service (Phase 3).

Uses PyMuPDF (fitz) to extract text, bounding boxes, dimensions, rotation,
and metadata provenance while evaluating page and document quality heuristics.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Base exception for extraction failures."""

    pass


class UnsupportedTextError(ExtractionError):
    """Raised when a document contains no extractable text (e.g. image-only / scan)."""

    pass


class ProvenanceInfo(dict):
    """Structured metadata provenance supporting evidence fields while comparing with source strings."""

    def __init__(self, source: str, **kwargs):
        super().__init__(source=source, **kwargs)

    @property
    def source(self) -> str:
        return self.get("source", "")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.get("source") == other
        return super().__eq__(other)


@dataclass
class ExtractedBlock:
    id: str
    bbox: list[float]  # [x0, y0, x1, y1] in PDF points (72 DPI, top-left origin)
    text: str
    text_hash: str


@dataclass
class ExtractedPage:
    page_number: int  # 1-based
    char_count: int
    width: float
    height: float
    rotation: int
    extraction_status: str  # 'ok', 'partial', 'failed'
    flags: list[str] = field(default_factory=list)
    raw_text: str = ""
    blocks: list[ExtractedBlock] = field(default_factory=list)


@dataclass
class ExtractedMetadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    keywords: list[str] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)  # field -> ProvenanceInfo or dict

    def get_source(self, field_name: str) -> str | None:
        val = self.sources.get(field_name)
        if isinstance(val, dict):
            return val.get("source")
        if isinstance(val, str):
            return val
        return None


@dataclass
class DocumentQualitySummary:
    readable_pages: int = 0
    flagged_pages: int = 0
    possible_scan_pages: list[int] = field(default_factory=list)
    table_unreliable_pages: list[int] = field(default_factory=list)
    equations_missing_pages: list[int] = field(default_factory=list)
    total_chars: int = 0
    all_image_document: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "readable_pages": self.readable_pages,
            "flagged_pages": self.flagged_pages,
            "possible_scan_pages": self.possible_scan_pages,
            "table_unreliable_pages": self.table_unreliable_pages,
            "equations_missing_pages": self.equations_missing_pages,
            "total_chars": self.total_chars,
            "all_image_document": self.all_image_document,
        }


@dataclass
class ExtractionResult:
    pages: list[ExtractedPage]
    metadata: ExtractedMetadata
    quality: DocumentQualitySummary
    page_count: int
    versions: dict[str, str]


# Regex patterns for quality heuristics
EQUATION_PATTERN = re.compile(
    r"(\\(?:sum|int|prod|frac|sqrt|partial|alpha|beta|gamma|theta|lambda|sigma|omega|Delta|Sigma|Omega)\b|"
    r"[∑∫∏√±≤≥≠≈∈∉⊂⊆αβγθλμσωΔΣΩ]|\(cid:\d+\)|\b[a-zA-Z]_[a-zA-Z0-9]\b|\b[a-zA-Z]\^[0-9]\b)",
    re.UNICODE,
)
TABLE_PATTERN = re.compile(
    r"(\t| {4,}\d+ {4,}|\bTable \d+[:\.]|\bTABLE [IVXLCDM]+[:\.]|\|.+\|)",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


def extract_pdf(pdf_path: Path | str) -> ExtractionResult:
    """Extract pages, blocks, metadata provenance, and quality indicators from a PDF file.

    Raises:
        ExtractionError: If PDF cannot be opened or is corrupted.
        UnsupportedTextError: If PDF contains no selectable text across all pages.
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists():
        raise ExtractionError(f"PDF file does not exist at {path_obj}")

    doc: fitz.Document | None = None
    try:
        doc = fitz.open(str(path_obj))
    except Exception as exc:
        raise ExtractionError(f"Failed to open PDF with PyMuPDF: {exc}") from exc

    try:
        if doc.is_encrypted:
            raise ExtractionError("PDF is encrypted and cannot be processed.")

        page_count = doc.page_count
        if page_count <= 0:
            raise ExtractionError("PDF has no pages.")

        extracted_pages: list[ExtractedPage] = []
        possible_scan_pages: list[int] = []
        table_unreliable_pages: list[int] = []
        equations_missing_pages: list[int] = []
        total_chars = 0
        readable_pages = 0

        first_page_text = ""

        for page_idx in range(page_count):
            page_num = page_idx + 1  # 1-based
            page = doc[page_idx]

            rect = page.rect
            width = round(float(rect.width), 2)
            height = round(float(rect.height), 2)
            rotation = int(page.rotation)

            raw_text = page.get_text("text") or ""
            char_count = len(raw_text.strip())
            total_chars += char_count

            if page_idx == 0:
                first_page_text = raw_text

            # Extract text blocks
            # page.get_text("blocks") returns (x0, y0, x1, y1, text, block_no, block_type)
            # block_type == 0 indicates text; 1 indicates image
            blocks_raw = page.get_text("blocks")
            extracted_blocks: list[ExtractedBlock] = []

            for b_idx, block_tuple in enumerate(blocks_raw):
                b_type = block_tuple[6]
                if b_type != 0:
                    continue
                b_text = block_tuple[4].strip()
                if not b_text:
                    continue

                raw_rect = fitz.Rect(block_tuple[:4])
                if rotation != 0:
                    vis_rect = raw_rect * page.rotation_matrix
                else:
                    vis_rect = raw_rect
                vis_rect.normalize()
                bbox = [
                    round(max(0.0, min(width, float(vis_rect.x0))), 2),
                    round(max(0.0, min(height, float(vis_rect.y0))), 2),
                    round(max(0.0, min(width, float(vis_rect.x1))), 2),
                    round(max(0.0, min(height, float(vis_rect.y1))), 2),
                ]
                text_hash = hashlib.sha256(b_text.encode("utf-8")).hexdigest()[:16]
                block_id = f"p{page_num}_b{b_idx}"

                extracted_blocks.append(
                    ExtractedBlock(
                        id=block_id,
                        bbox=bbox,
                        text=b_text,
                        text_hash=text_hash,
                    )
                )

            # Evaluate Page Flags
            flags: list[str] = []

            # 1. Possible Scan: very low characters but contains image or non-empty page
            images = page.get_images()
            if char_count < 50 and len(images) > 0:
                flags.append("possible_scan")
                possible_scan_pages.append(page_num)
            elif char_count == 0:
                flags.append("possible_scan")
                possible_scan_pages.append(page_num)

            # 2. Table Unreliable: irregular spacing, tabs, or table structure
            if TABLE_PATTERN.search(raw_text):
                flags.append("table_unreliable")
                table_unreliable_pages.append(page_num)

            # 3. Equations May Be Missing: LaTeX / unicode math symbols / cid fonts
            if EQUATION_PATTERN.search(raw_text):
                flags.append("equations_may_be_missing")
                equations_missing_pages.append(page_num)

            # Determine extraction status for this page
            if char_count > 0:
                readable_pages += 1
                extraction_status = "partial" if flags else "ok"
            else:
                extraction_status = "failed"

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_num,
                    char_count=char_count,
                    width=width,
                    height=height,
                    rotation=rotation,
                    extraction_status=extraction_status,
                    flags=flags,
                    raw_text=raw_text,
                    blocks=extracted_blocks,
                )
            )

        all_image_document = total_chars == 0 or readable_pages == 0

        # Construct Quality Summary
        flagged_count = len(set(possible_scan_pages + table_unreliable_pages + equations_missing_pages))
        quality_summary = DocumentQualitySummary(
            readable_pages=readable_pages,
            flagged_pages=flagged_count,
            possible_scan_pages=sorted(set(possible_scan_pages)),
            table_unreliable_pages=sorted(set(table_unreliable_pages)),
            equations_missing_pages=sorted(set(equations_missing_pages)),
            total_chars=total_chars,
            all_image_document=all_image_document,
        )

        # Enforce all-image / unsupported text outcome
        if all_image_document:
            raise UnsupportedTextError(
                "UNSUPPORTED_TEXT_NO_SELECTABLE_TEXT: Document contains no selectable text (scanned or image-only PDF without OCR). OCR is not supported in Phase 3."
            )

        # Extract metadata with provenance
        doc_meta = doc.metadata or {}
        extracted_metadata = _extract_metadata_with_provenance(doc_meta, first_page_text, extracted_pages)

        version_str = getattr(fitz, "VersionBind", getattr(fitz, "__version__", "1.24.x"))

        return ExtractionResult(
            pages=extracted_pages,
            metadata=extracted_metadata,
            quality=quality_summary,
            page_count=page_count,
            versions={
                "extractor": f"pymupdf {version_str}",
                "pipeline": "0.1.0-phase3",
            },
        )

    finally:
        if doc is not None:
            doc.close()


def _extract_metadata_with_provenance(
    doc_meta: dict[str, Any],
    first_page_text: str,
    pages: list[ExtractedPage],
) -> ExtractedMetadata:
    """Extract metadata while strictly tracking the source ('pdf', 'text', 'inferred').

    Missing data stays None / empty; filenames are never asserted as metadata.
    """
    sources: dict[str, Any] = {}
    title: str | None = None
    authors: list[str] = []
    publication_year: int | None = None
    keywords: list[str] = []

    # 1. Title
    raw_title = doc_meta.get("title")
    if raw_title and raw_title.strip() and not _is_generic_title(raw_title.strip()):
        title = raw_title.strip()
        sources["title"] = ProvenanceInfo("pdf", file_property="title", evidence=title)
    elif pages and pages[0].blocks:
        first_block_text = pages[0].blocks[0].text.strip()
        if len(first_block_text) > 5 and len(first_block_text.splitlines()) <= 4:
            first_line = " ".join(first_block_text.splitlines()).strip()
            if not _is_generic_title(first_line):
                title = first_line
                sources["title"] = ProvenanceInfo(
                    "text", page_number=1, block_id=pages[0].blocks[0].id, evidence=first_line
                )

    # 2. Authors
    raw_author = doc_meta.get("author")
    if raw_author and raw_author.strip() and not _is_generic_author(raw_author.strip()):
        parsed = [a.strip() for a in re.split(r"[,;]|\band\b", raw_author) if a.strip()]
        if parsed:
            authors = parsed
            sources["authors"] = ProvenanceInfo("pdf", file_property="author", evidence=raw_author.strip())
    elif pages and len(pages[0].blocks) > 1:
        second_block = pages[0].blocks[1]
        second_block_text = second_block.text.strip()
        if (
            0 < len(second_block_text) <= 120
            and not _is_generic_author(second_block_text)
            and not any(
                kw in second_block_text.lower()
                for kw in ["abstract", "introduction", "university", "department", "http", "doi", "vol.", "issue"]
            )
        ):
            candidate_names = [a.strip() for a in re.split(r"[,;]|\band\b", second_block_text) if a.strip()]
            valid_names = []
            for name in candidate_names:
                words = name.split()
                if 1 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                    valid_names.append(name)
            if valid_names and len(valid_names) == len(candidate_names):
                authors = valid_names
                sources["authors"] = ProvenanceInfo(
                    "text", page_number=1, block_id=second_block.id, evidence=second_block_text
                )

    # 3. Publication Year
    # Note (R6): PDF file creationDate/modDate is a file-system property, NOT publication year.
    # We only extract publication_year if explicit textual or bibliographic evidence exists.
    if first_page_text:
        match = YEAR_PATTERN.search(first_page_text[:2000])
        if match:
            year_val = int(match.group(1))
            if 1900 <= year_val <= 2100:
                publication_year = year_val
                sources["publication_year"] = ProvenanceInfo("inferred", page_number=1, evidence=match.group(0).strip())

    # 4. Keywords
    raw_keywords = doc_meta.get("keywords")
    if raw_keywords and raw_keywords.strip():
        keywords = [k.strip() for k in re.split(r"[,;]", raw_keywords) if k.strip()]
        sources["keywords"] = ProvenanceInfo("pdf", file_property="keywords", evidence=raw_keywords.strip())
    elif first_page_text:
        kw_match = re.search(r"(?:Keywords|Index Terms)[:\s]([^\.\n]+)", first_page_text, re.IGNORECASE)
        if kw_match:
            kw_str = kw_match.group(1).strip()
            keywords = [k.strip() for k in re.split(r"[,;—–-]", kw_str) if k.strip()]
            if keywords:
                sources["keywords"] = ProvenanceInfo("text", page_number=1, evidence=kw_str)

    return ExtractedMetadata(
        title=title,
        authors=authors,
        publication_year=publication_year,
        keywords=keywords,
        sources=sources,
    )


def _is_generic_title(val: str) -> bool:
    low = val.lower().strip()
    return low in {"untitled", "document", "pdf", "microsoft word", "latex", "presentation"} or low.endswith(".pdf")


def _is_generic_author(val: str) -> bool:
    low = val.lower().strip()
    return low in {"user", "author", "admin", "administrator", "unknown"}
