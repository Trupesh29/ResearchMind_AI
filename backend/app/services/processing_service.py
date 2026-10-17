"""ResearchMind AI — Processing Management & Inspection Service (Phase 3).

Handles job enqueuing, reprocess conflict checks, status synthesis,
and page/block inspection.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import Page, ProcessingJob, utcnow_iso
from backend.app.schemas.paper import (
    PageBlockItem,
    PageBlocksResponse,
    PagesListResponse,
    PageSummaryItem,
    PaperStageDetail,
    PaperStatusResponse,
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
    effective_run_id = paper.current_run_id or all_jobs[-1].run_id
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

    # Compute status, active stage, and progress
    failing_jobs = [j for j in run_jobs if j.status == "failed"]
    if failing_jobs or paper.status == "failed":
        last_failed = failing_jobs[-1] if failing_jobs else run_jobs[-1]
        raw_err = last_failed.error_message or "Processing failed."
        return PaperStatusResponse(
            status="failed",
            stage=last_failed.stage,
            progress=0.0,
            attempt=last_failed.attempt,
            error=sanitize_error_message(raw_err),
            stages=stage_details,
        )

    # Check stages in progress / completed
    extracting_job = next((j for j in run_jobs if j.stage == "extracting"), None)
    validating_job = next((j for j in run_jobs if j.stage == "validating"), None)

    if extracting_job and extracting_job.status == "succeeded":
        # Phase 3 boundary: extraction succeeded, holding in processing state awaiting sectioning
        return PaperStatusResponse(
            status="processing",
            stage="extracting",
            progress=0.5,
            attempt=extracting_job.attempt,
            error=None,
            stages=stage_details,
        )
    elif extracting_job and extracting_job.status == "running":
        return PaperStatusResponse(
            status="processing",
            stage="extracting",
            progress=0.3,
            attempt=extracting_job.attempt,
            error=None,
            stages=stage_details,
        )
    elif extracting_job and extracting_job.status == "queued":
        return PaperStatusResponse(
            status="processing",
            stage="extracting",
            progress=0.2,
            attempt=extracting_job.attempt,
            error=None,
            stages=stage_details,
        )
    elif validating_job and validating_job.status == "running":
        return PaperStatusResponse(
            status="processing",
            stage="validating",
            progress=0.1,
            attempt=validating_job.attempt,
            error=None,
            stages=stage_details,
        )
    else:
        # Default / validating queued
        return PaperStatusResponse(
            status=paper.status,
            stage="validating",
            progress=0.05,
            attempt=validating_job.attempt if validating_job else 1,
            error=None,
            stages=stage_details,
        )


def get_paper_pages(
    db: Session,
    user_id: str,
    paper_id: str,
) -> PagesListResponse:
    """Retrieve summary of extracted pages with quality flags."""
    paper = paper_service.get_paper_or_404(db, user_id, paper_id)

    if not paper.published_run_id:
        return PagesListResponse(items=[], total_pages=0)

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

    return PagesListResponse(items=items, total_pages=len(items))


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

    return PageBlocksResponse(
        page_number=page.page_number,
        width=page.width,
        height=page.height,
        rotation=page.rotation,
        blocks=blocks,
    )
