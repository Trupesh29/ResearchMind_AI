"""ResearchMind AI — Processing Management & Inspection Service (Phase 3).

Handles job enqueuing, reprocess conflict checks, status synthesis,
and page/block inspection.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import Chunk, Page, ProcessingJob, Section, utcnow_iso
from backend.app.schemas.paper import (
    ChunkItem,
    ChunksListResponse,
    PageBlockItem,
    PageBlocksResponse,
    PagesListResponse,
    PageSummaryItem,
    PaperStageDetail,
    PaperStatusResponse,
    SectionItem,
    SectionsListResponse,
)
from backend.app.services import paper_service
from worker.engine import sanitize_error_message

logger = logging.getLogger(__name__)


def enqueue_validation_job(
    db: Session,
    paper_id: str,
    run_id: str | None = None,
) -> ProcessingJob:
    """Transactionally enqueue the initial validating job for a paper.

    Must be called within an active transaction before commit.
    """
    job_id = str(uuid.uuid4())
    effective_run_id = run_id or str(uuid.uuid4())
    job = ProcessingJob(
        id=job_id,
        paper_id=paper_id,
        run_id=effective_run_id,
        stage="validating",
        status="queued",
        attempt=1,
        created_at=utcnow_iso(),
    )
    db.add(job)
    return job


def request_reprocess(
    db: Session,
    user_id: str,
    paper_id: str,
) -> PaperStatusResponse:
    """Request a fresh processing generation for an existing paper.

    Rejects active runs with 409 Conflict.
    """
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    # Check for active running or queued job
    active_job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.paper_id == paper_id,
            ProcessingJob.status.in_(["queued", "running"]),
        )
        .first()
    )
    if active_job:
        raise AppException(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Paper {paper_id} has an active processing job in progress (stage={active_job.stage}).",
            status_code=409,
        )

    # Start new generation run
    new_run_id = str(uuid.uuid4())
    paper.current_run_id = new_run_id
    paper.status = "processing"
    paper.updated_at = utcnow_iso()

    try:
        enqueue_validation_job(db, paper_id=paper_id, run_id=new_run_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppException(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Paper {paper_id} has an active processing job in progress.",
            status_code=409,
        )

    return get_paper_status_details(db, user_id, paper_id)


def get_paper_status_details(
    db: Session,
    user_id: str,
    paper_id: str,
) -> PaperStatusResponse:
    """Retrieve detailed stage history and progress for the current processing generation."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    all_jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.paper_id == paper_id)
        .order_by(ProcessingJob.created_at.asc())
        .all()
    )

    if not all_jobs:
        return PaperStatusResponse(
            status=paper.status,
            stage="validating" if paper.status == "uploaded" else "ready",
            progress=1.0 if paper.status == "ready" else 0.0,
            attempt=1,
            error=None,
            stages=[],
        )

    # Target the active / current generation run
    effective_run_id = paper.current_run_id or (all_jobs[-1].run_id if all_jobs else None)
    run_jobs = [j for j in all_jobs if j.run_id == effective_run_id]
    if not run_jobs:
        run_jobs = all_jobs

    stage_details: list[PaperStageDetail] = [
        PaperStageDetail(
            stage=j.stage,
            status=j.status,
            attempt=j.attempt,
            started_at=j.started_at,
            finished_at=j.finished_at,
            error=sanitize_error_message(j.error_message) if j.error_message else None,
        )
        for j in run_jobs
    ]

    is_stale = bool(paper.published_run_id and effective_run_id and paper.published_run_id != effective_run_id)

    # Group by stage to evaluate latest attempt per stage
    validating_jobs = [j for j in run_jobs if j.stage == "validating"]
    extracting_jobs = [j for j in run_jobs if j.stage == "extracting"]

    validating_jobs = [j for j in run_jobs if j.stage == "validating"]
    extracting_jobs = [j for j in run_jobs if j.stage == "extracting"]
    sectioning_jobs = [j for j in run_jobs if j.stage == "sectioning"]
    chunking_jobs = [j for j in run_jobs if j.stage == "chunking"]

    latest_val = max(validating_jobs, key=lambda j: j.attempt) if validating_jobs else None
    latest_ext = max(extracting_jobs, key=lambda j: j.attempt) if extracting_jobs else None
    latest_sec = max(sectioning_jobs, key=lambda j: j.attempt) if sectioning_jobs else None
    latest_chk = max(chunking_jobs, key=lambda j: j.attempt) if chunking_jobs else None

    # 1. Check chunking stage first if present
    if latest_chk:
        if latest_chk.status == "running":
            return PaperStatusResponse(
                status="processing",
                stage="chunking",
                substate="chunking",
                progress=0.85,
                attempt=latest_chk.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_chk.status == "queued":
            return PaperStatusResponse(
                status="processing",
                stage="chunking",
                substate="queued",
                progress=0.75,
                attempt=latest_chk.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_chk.status == "succeeded":
            return PaperStatusResponse(
                status="ready" if paper.status == "ready" else "processing",
                stage="chunking",
                substate="awaiting_indexing",
                progress=1.0,
                attempt=latest_chk.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_chk.status == "failed":
            return PaperStatusResponse(
                status="failed",
                stage="chunking",
                substate="failed",
                progress=0.0,
                attempt=latest_chk.attempt,
                error=sanitize_error_message(latest_chk.error_message or "Chunking failed."),
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )

    # 2. Check sectioning stage
    if latest_sec:
        if latest_sec.status == "running":
            return PaperStatusResponse(
                status="processing",
                stage="sectioning",
                substate="sectioning",
                progress=0.55,
                attempt=latest_sec.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_sec.status == "queued":
            return PaperStatusResponse(
                status="processing",
                stage="sectioning",
                substate="queued",
                progress=0.45,
                attempt=latest_sec.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_sec.status == "succeeded":
            return PaperStatusResponse(
                status="processing",
                stage="sectioning",
                substate="sectioned",
                progress=0.65,
                attempt=latest_sec.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_sec.status == "failed":
            return PaperStatusResponse(
                status="failed",
                stage="sectioning",
                substate="failed",
                progress=0.0,
                attempt=latest_sec.attempt,
                error=sanitize_error_message(latest_sec.error_message or "Sectioning failed."),
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )

    # 3. Check extracting stage
    if latest_ext:
        if latest_ext.status == "running":
            return PaperStatusResponse(
                status="processing",
                stage="extracting",
                substate="extracting",
                progress=0.3,
                attempt=latest_ext.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_ext.status == "queued":
            return PaperStatusResponse(
                status="processing",
                stage="extracting",
                substate="queued",
                progress=0.2,
                attempt=latest_ext.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_ext.status == "succeeded":
            return PaperStatusResponse(
                status="processing",
                stage="extracting",
                substate="extracted",
                progress=0.5,
                attempt=latest_ext.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_ext.status == "failed":
            return PaperStatusResponse(
                status="failed",
                stage="extracting",
                substate="failed",
                progress=0.0,
                attempt=latest_ext.attempt,
                error=sanitize_error_message(latest_ext.error_message or "Processing failed."),
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )

    # 4. Check validating stage
    if latest_val:
        if latest_val.status == "running":
            return PaperStatusResponse(
                status="processing",
                stage="validating",
                substate="validating",
                progress=0.1,
                attempt=latest_val.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_val.status == "queued":
            return PaperStatusResponse(
                status="uploaded" if paper.status == "uploaded" else "processing",
                stage="validating",
                substate="queued",
                progress=0.05,
                attempt=latest_val.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_val.status == "failed":
            return PaperStatusResponse(
                status="failed",
                stage="validating",
                substate="failed",
                progress=0.0,
                attempt=latest_val.attempt,
                error=sanitize_error_message(latest_val.error_message or "Validation failed."),
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )
        elif latest_val.status == "succeeded":
            return PaperStatusResponse(
                status="processing",
                stage="validating",
                substate="validated",
                progress=0.15,
                attempt=latest_val.attempt,
                error=None,
                stages=stage_details,
                run_id=effective_run_id,
                current_run_id=paper.current_run_id,
                published_run_id=paper.published_run_id,
                is_stale=is_stale,
            )

    # 5. Fallback
    return PaperStatusResponse(
        status=paper.status,
        stage="validating",
        substate=None,
        progress=0.0,
        attempt=1,
        error=None,
        stages=stage_details,
        run_id=effective_run_id,
        current_run_id=paper.current_run_id,
        published_run_id=paper.published_run_id,
        is_stale=is_stale,
    )


def get_paper_pages(
    db: Session,
    user_id: str,
    paper_id: str,
) -> PagesListResponse:
    """Retrieve summary of extracted pages with quality flags."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    if not paper.published_run_id:
        return PagesListResponse(items=[], total_pages=0, run_id=None, is_stale=False)

    pages = (
        db.query(Page)
        .filter(Page.paper_id == paper_id, Page.run_id == paper.published_run_id)
        .order_by(Page.page_number.asc())
        .all()
    )

    items: list[PageSummaryItem] = []
    for p in pages:
        flags_parsed = []
        if p.flags_json:
            try:
                flags_parsed = json.loads(p.flags_json)
            except Exception:
                flags_parsed = []

        items.append(
            PageSummaryItem(
                page_number=p.page_number,
                char_count=p.char_count,
                extraction_status=p.extraction_status,
                flags=flags_parsed,
            )
        )

    is_stale = bool(paper.current_run_id and paper.current_run_id != paper.published_run_id)
    return PagesListResponse(
        items=items,
        total_pages=len(items),
        run_id=paper.published_run_id,
        is_stale=is_stale,
    )


def get_paper_page_blocks(
    db: Session,
    user_id: str,
    paper_id: str,
    page_number: int,
) -> PageBlocksResponse:
    """Retrieve detailed block coordinates and text for a specific page."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    if not paper.published_run_id:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message=f"Page {page_number} not found for paper {paper_id}.",
            status_code=404,
        )

    page = (
        db.query(Page)
        .filter(
            Page.paper_id == paper_id,
            Page.run_id == paper.published_run_id,
            Page.page_number == page_number,
        )
        .first()
    )

    if not page:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message=f"Page {page_number} not found for paper {paper_id}.",
            status_code=404,
        )

    blocks: list[PageBlockItem] = []
    if page.blocks_json:
        try:
            raw_blocks = json.loads(page.blocks_json)
            for b in raw_blocks:
                blocks.append(
                    PageBlockItem(
                        id=b["id"],
                        bbox=b["bbox"],
                        text=b["text"],
                        text_hash=b["text_hash"],
                    )
                )
        except Exception as exc:
            logger.error(f"Error parsing blocks_json for page {page.id}: {exc}")

    is_stale = bool(paper.current_run_id and paper.current_run_id != paper.published_run_id)
    return PageBlocksResponse(
        page_number=page.page_number,
        width=page.width,
        height=page.height,
        rotation=page.rotation,
        blocks=blocks,
        run_id=page.run_id,
        is_stale=is_stale,
    )


def get_paper_chunks(
    db: Session,
    user_id: str,
    paper_id: str,
    page: int | None = None,
    section: str | None = None,
    limit: int = 25,
    cursor: str | None = None,
) -> ChunksListResponse:
    """Retrieve chunks for the published generation of a paper with cursor pagination and filters."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    target_run_id = paper.published_run_id
    if not target_run_id:
        return ChunksListResponse(items=[], total=0, run_id=None, is_stale=False, next_cursor=None)

    # Decode generation-bound or legacy integer cursor
    cursor_val: int | None = None
    if cursor is not None and cursor.strip():
        raw_c = cursor.strip()
        try:
            padded = raw_c + "=" * (-len(raw_c) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            if isinstance(decoded, dict):
                c_run_id = decoded.get("run_id")
                if c_run_id:
                    # Bind target generation to the cursor's generation to prevent cross-generation mixing
                    target_run_id = str(c_run_id)
                if "chunk_index" in decoded:
                    cursor_val = int(decoded["chunk_index"])
        except Exception:
            # Fallback for plain integer string cursor
            try:
                cursor_val = int(raw_c)
            except ValueError:
                cursor_val = None

    query = db.query(Chunk).filter(
        Chunk.paper_id == paper_id,
        Chunk.run_id == target_run_id,
        Chunk.is_deleted == 0,
    )

    if page is not None:
        query = query.filter(Chunk.page_start <= page, Chunk.page_end >= page)

    if section is not None and section.strip():
        query = query.filter(Chunk.section.ilike(section.strip()))

    total = query.count()

    # Cursor pagination on chunk_index
    if cursor_val is not None:
        query = query.filter(Chunk.chunk_index > cursor_val)

    query = query.order_by(Chunk.chunk_index.asc())
    rows = query.limit(limit + 1).all()

    has_more = len(rows) > limit
    items_rows = rows[:limit]
    if has_more and items_rows:
        last_idx = items_rows[-1].chunk_index
        payload = json.dumps({"run_id": target_run_id, "chunk_index": last_idx}, separators=(",", ":"))
        next_cursor = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    else:
        next_cursor = None

    items: list[ChunkItem] = []
    for c in items_rows:
        block_ids = []
        if c.block_ids_json:
            try:
                block_ids = json.loads(c.block_ids_json)
            except Exception:
                block_ids = []
        items.append(
            ChunkItem(
                id=c.id,
                paper_id=c.paper_id,
                run_id=c.run_id,
                chunk_index=c.chunk_index,
                page_start=c.page_start,
                page_end=c.page_end,
                section=c.section,
                text=c.text,
                token_count=c.token_count,
                block_ids=block_ids,
                is_excluded=bool(c.is_excluded),
                tokenizer_name=c.tokenizer_name,
                tokenizer_revision=c.tokenizer_revision,
                created_at=c.created_at,
            )
        )

    is_stale = bool(
        paper.published_run_id != target_run_id or (paper.current_run_id and paper.current_run_id != target_run_id)
    )
    return ChunksListResponse(
        items=items,
        total=total,
        run_id=target_run_id,
        is_stale=is_stale,
        next_cursor=next_cursor,
    )


def get_paper_sections(
    db: Session,
    user_id: str,
    paper_id: str,
) -> SectionsListResponse:
    """Retrieve sections for the published generation of a paper."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    target_run_id = paper.published_run_id
    if not target_run_id:
        return SectionsListResponse(items=[], total=0, run_id=None, is_stale=False)

    rows = (
        db.query(Section)
        .filter(Section.paper_id == paper_id, Section.run_id == target_run_id)
        .order_by(Section.section_index.asc())
        .all()
    )

    items: list[SectionItem] = []
    for s in rows:
        block_ids = []
        if s.block_ids_json:
            try:
                block_ids = json.loads(s.block_ids_json)
            except Exception:
                block_ids = []
        items.append(
            SectionItem(
                id=s.id,
                paper_id=s.paper_id,
                run_id=s.run_id,
                section_index=s.section_index,
                section=s.section,
                heading=s.heading,
                page_start=s.page_start,
                page_end=s.page_end,
                text=s.text,
                block_ids=block_ids,
                created_at=s.created_at,
            )
        )

    is_stale = bool(paper.current_run_id and paper.current_run_id != target_run_id)
    return SectionsListResponse(
        items=items,
        total=len(items),
        run_id=target_run_id,
        is_stale=is_stale,
    )
