"""ResearchMind AI — Standalone Processing Worker Engine (Phase 3).

Implements atomic job claiming, heartbeat leasing, fencing token validation,
short database transactions, and isolated extraction handling.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import socket
import threading
import time
import uuid
from typing import Any

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import Page, Paper, ProcessingJob, utcnow_iso
from backend.app.db.session import get_session_factory
from backend.app.services import extraction_service

logger = logging.getLogger("worker.engine")


class WorkerFencingViolation(Exception):
    """Raised when an operation is attempted with an expired or superseded claim token."""

    pass


def sanitize_error_message(err: Exception | str, storage_path: str | None = None) -> str:
    """Sanitize error messages to eliminate private server paths, drive letters, or internals."""
    msg = str(err) if not isinstance(err, str) else err

    # Check for known categories with standard public strings
    low = msg.lower()
    if "not found" in low or "no such file" in low or "does not exist" in low:
        return "PDF storage file could not be found or opened."
    if "permission denied" in low:
        return "PDF storage file cannot be accessed due to file permissions."
    if "encrypted" in low:
        return "PDF is encrypted and cannot be processed."
    if "unsupported_text" in low or "no selectable text" in low:
        return "Document contains no selectable text (scanned or image-only PDF without OCR). OCR is not supported in Phase 3."
    if "magic bytes" in low or "not a valid pdf" in low or "cannot open broken document" in low:
        return "File is not a valid PDF or has corrupted structure."
    if "file size mismatch" in low:
        return "File size on disk does not match recorded document size."
    if "hash mismatch" in low:
        return "File hash on disk does not match recorded document hash."
    if "lost lease" in low or "fencing" in low or "superseded" in low:
        return "Worker lease expired or was superseded by another worker."

    # Scrub paths matching Windows drive letters or standard Unix paths
    cleaned = re.sub(r"[A-Za-z]:\\[^:\s,;\"']+", "[storage path]", msg)
    cleaned = re.sub(r"/(?:tmp|var|home|usr|dev)/[^\s,;\"']+", "[storage path]", cleaned)
    if storage_path:
        cleaned = cleaned.replace(storage_path, "[storage path]")
        cleaned = cleaned.replace(os.path.basename(storage_path), "[file]")

    return cleaned[:255].strip()


class LeaseHeartbeat:
    """Periodically renews the heartbeat timestamp on a running job and detects lease loss."""

    def __init__(self, session_factory, job_id: str, claim_token: str, interval: float = 2.0):
        self.session_factory = session_factory
        self.job_id = job_id
        self.claim_token = claim_token
        self.interval = max(0.2, interval)
        self._stop_event = threading.Event()
        self._lost_ownership = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self.interval):
            try:
                db: Session = self.session_factory()
                try:
                    stmt = (
                        update(ProcessingJob)
                        .where(
                            ProcessingJob.id == self.job_id,
                            ProcessingJob.status == "running",
                            ProcessingJob.claim_token == self.claim_token,
                        )
                        .values(heartbeat_at=utcnow_iso())
                    )
                    res = db.execute(stmt)
                    db.commit()
                    if res.rowcount == 0:
                        logger.warning(f"LeaseHeartbeat: lost lease on job {self.job_id} (affected rows: 0).")
                        self._lost_ownership.set()
                        break
                finally:
                    db.close()
            except Exception as exc:
                logger.warning(f"LeaseHeartbeat: error renewing heartbeat for {self.job_id}: {exc}")

    def stop(self) -> bool:
        """Stop heartbeat renewal and return True if ownership was held throughout, False if lost."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        return not self._lost_ownership.is_set()

    @property
    def has_lost_ownership(self) -> bool:
        return self._lost_ownership.is_set()


class WorkerEngine:
    """Orchestrates job leasing, stage execution, and publication."""

    def __init__(
        self,
        worker_id: str | None = None,
        poll_interval: float = 1.0,
        lease_timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.lease_timeout_seconds = lease_timeout_seconds
        self.max_retries = max_retries
        self._stop_requested = False
        self.settings = get_settings()

    def request_stop(self) -> None:
        """Signal the worker to finish the current step and terminate."""
        logger.info(f"Worker {self.worker_id} stop requested.")
        self._stop_requested = True

    def run_once(self) -> bool:
        """Execute a single claim-and-process iteration.

        Returns True if a job was claimed and processed, False if queue was empty.
        """
        factory = get_session_factory()
        db: Session = factory()
        claimed_job_info: dict[str, Any] | None = None
        try:
            # 1. Recover expired leases
            self._recover_expired_leases(db)

            # 2. Claim next available job
            claimed_job_info = self._claim_next_job(db)
        finally:
            db.close()

        if not claimed_job_info:
            return False

        # 3. Process claimed job outside database write transaction
        self._execute_claimed_job(claimed_job_info)
        return True

    def run_loop(self) -> None:
        """Main worker execution loop."""
        logger.info(
            f"Worker {self.worker_id} starting loop (poll={self.poll_interval}s, lease={self.lease_timeout_seconds}s)"
        )
        while not self._stop_requested:
            try:
                worked = self.run_once()
                if not worked and not self._stop_requested:
                    time.sleep(self.poll_interval)
            except Exception as exc:
                logger.error(f"Unexpected error in worker loop: {exc}", exc_info=True)
                if not self._stop_requested:
                    time.sleep(self.poll_interval)
        logger.info(f"Worker {self.worker_id} loop exited cleanly.")

    def _recover_expired_leases(self, db: Session) -> None:
        """Detect running jobs whose heartbeat has expired and retry or fail them atomically."""
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        threshold_dt = now_dt - datetime.timedelta(seconds=self.lease_timeout_seconds)
        threshold_iso = threshold_dt.isoformat()

        expired_jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.status == "running",
                ProcessingJob.heartbeat_at < threshold_iso,
            )
            .all()
        )

        for job in expired_jobs:
            logger.warning(
                f"Worker {self.worker_id} recovering expired job {job.id} (stage={job.stage}, attempt={job.attempt})"
            )
            now = utcnow_iso()
            err_msg = sanitize_error_message(f"Worker lease expired after {self.lease_timeout_seconds}s.")

            # Atomically retire the stale attempt
            stmt = (
                update(ProcessingJob)
                .where(
                    ProcessingJob.id == job.id,
                    ProcessingJob.status == "running",
                    ProcessingJob.claim_token == job.claim_token,
                )
                .values(
                    status="failed",
                    finished_at=now,
                    error_message=err_msg,
                )
            )
            res = db.execute(stmt)
            if res.rowcount == 1:
                # Attempt successfully retired; queue attempt+1 if within retry bounds
                if job.attempt < self.max_retries:
                    new_job = ProcessingJob(
                        id=str(uuid.uuid4()),
                        paper_id=job.paper_id,
                        run_id=job.run_id,
                        stage=job.stage,
                        status="queued",
                        attempt=job.attempt + 1,
                        created_at=now,
                    )
                    db.add(new_job)
                else:
                    paper = db.query(Paper).filter(Paper.id == job.paper_id).first()
                    if paper and paper.status != "ready":
                        paper.status = "failed"
                        paper.updated_at = now
                db.commit()

    def _claim_next_job(self, db: Session) -> dict[str, Any] | None:
        """Atomically claim the next queued validating or extracting job."""
        candidates = (
            db.query(ProcessingJob.id, ProcessingJob.paper_id)
            .filter(
                ProcessingJob.status == "queued",
                ProcessingJob.stage.in_(["validating", "extracting"]),
            )
            .order_by(ProcessingJob.created_at.asc())
            .limit(10)
            .all()
        )

        for candidate_id, paper_id in candidates:
            # Verify paper exists before claiming
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                db.query(ProcessingJob).filter(ProcessingJob.id == candidate_id).delete()
                db.commit()
                continue

            token = str(uuid.uuid4())
            now = utcnow_iso()

            # Atomic claim update guarded by status == 'queued'
            stmt = (
                update(ProcessingJob)
                .where(
                    ProcessingJob.id == candidate_id,
                    ProcessingJob.status == "queued",
                )
                .values(
                    status="running",
                    worker_id=self.worker_id,
                    claim_token=token,
                    claimed_at=now,
                    heartbeat_at=now,
                    started_at=case(
                        (ProcessingJob.started_at.is_(None), now),
                        else_=ProcessingJob.started_at,
                    ),
                )
            )
            res = db.execute(stmt)
            db.commit()

            if res.rowcount == 1:
                job = db.query(ProcessingJob).filter(ProcessingJob.id == candidate_id).first()
                return {
                    "job_id": job.id,
                    "paper_id": job.paper_id,
                    "run_id": job.run_id,
                    "stage": job.stage,
                    "attempt": job.attempt,
                    "claim_token": token,
                    "storage_path": paper.storage_path,
                    "sha256": paper.sha256,
                    "size_bytes": paper.size_bytes,
                }

        return None

    def _execute_claimed_job(self, info: dict[str, Any]) -> None:
        """Route to appropriate stage handler."""
        stage = info["stage"]
        if stage == "validating":
            self._handle_validating_stage(info)
        elif stage == "extracting":
            self._handle_extracting_stage(info)
        else:
            logger.error(f"Unsupported stage '{stage}' claimed by worker.")

    def _handle_validating_stage(self, info: dict[str, Any]) -> None:
        """Validate PDF file presence, size, magic bytes, hash, and structure."""
        job_id = info["job_id"]
        paper_id = info["paper_id"]
        token = info["claim_token"]
        run_id = info["run_id"]
        storage_path = info["storage_path"]
        expected_sha256 = info["sha256"]
        expected_size = info["size_bytes"]

        factory = get_session_factory()
        heartbeat = LeaseHeartbeat(factory, job_id, token, interval=max(0.5, self.lease_timeout_seconds / 3.0))
        heartbeat.start()

        validation_error: str | None = None
        pdf_file = self.settings.BASE_DIR / storage_path if not os.path.isabs(storage_path) else storage_path
        pdf_path = os.fspath(pdf_file)

        try:
            if not os.path.exists(pdf_path):
                validation_error = "PDF storage file could not be found or opened."
            else:
                actual_size = os.path.getsize(pdf_path)
                if actual_size != expected_size:
                    validation_error = "File size on disk does not match recorded document size."
                else:
                    try:
                        import hashlib

                        hasher = hashlib.sha256()
                        with open(pdf_path, "rb") as f:
                            header = f.read(5)
                            if header != b"%PDF-":
                                validation_error = "File is not a valid PDF or has corrupted structure."
                            else:
                                hasher.update(header)
                                while chunk := f.read(65536):
                                    hasher.update(chunk)
                                actual_sha = hasher.hexdigest()
                                if actual_sha != expected_sha256:
                                    validation_error = "File hash on disk does not match recorded document hash."
                    except Exception as exc:
                        validation_error = sanitize_error_message(exc, storage_path=storage_path)
        finally:
            active_lease = heartbeat.stop()

        if not active_lease:
            logger.warning(f"Validation job {job_id} lost lease during validation; aborting publication.")
            return

        db: Session = factory()
        try:
            now = utcnow_iso()
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                logger.info(f"Paper {paper_id} deleted during validation; dropping publication.")
                return

            if validation_error:
                sanitized_err = sanitize_error_message(validation_error, storage_path=storage_path)
                stmt = (
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.id == job_id,
                        ProcessingJob.status == "running",
                        ProcessingJob.claim_token == token,
                    )
                    .values(
                        status="failed",
                        finished_at=now,
                        error_message=sanitized_err,
                    )
                )
                res = db.execute(stmt)
                if res.rowcount == 0:
                    db.rollback()
                    raise WorkerFencingViolation(f"Lost claim token on validation job {job_id}")
                paper.status = "failed"
                paper.updated_at = now
                db.commit()
            else:
                stmt = (
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.id == job_id,
                        ProcessingJob.status == "running",
                        ProcessingJob.claim_token == token,
                    )
                    .values(
                        status="succeeded",
                        finished_at=now,
                    )
                )
                res = db.execute(stmt)
                if res.rowcount == 0:
                    db.rollback()
                    raise WorkerFencingViolation(f"Lost claim token on validation job {job_id}")

                # Enqueue extracting stage
                next_job = ProcessingJob(
                    id=str(uuid.uuid4()),
                    paper_id=paper_id,
                    run_id=run_id,
                    stage="extracting",
                    status="queued",
                    attempt=1,
                    created_at=now,
                )
                db.add(next_job)
                paper.status = "processing"
                paper.updated_at = now
                db.commit()
        finally:
            db.close()

    def _handle_extracting_stage(self, info: dict[str, Any]) -> None:
        """Extract pages, blocks, metadata provenance, and quality indicators."""
        job_id = info["job_id"]
        paper_id = info["paper_id"]
        token = info["claim_token"]
        run_id = info["run_id"]
        storage_path = info["storage_path"]

        pdf_file = self.settings.BASE_DIR / storage_path if not os.path.isabs(storage_path) else storage_path
        pdf_path = os.fspath(pdf_file)

        factory = get_session_factory()
        heartbeat = LeaseHeartbeat(factory, job_id, token, interval=max(0.5, self.lease_timeout_seconds / 3.0))
        heartbeat.start()

        extraction_result: extraction_service.ExtractionResult | None = None
        extraction_error: str | None = None

        try:
            extraction_result = extraction_service.extract_pdf(pdf_path)
        except extraction_service.UnsupportedTextError as ute:
            extraction_error = sanitize_error_message(ute, storage_path=storage_path)
        except Exception as exc:
            extraction_error = sanitize_error_message(exc, storage_path=storage_path)
        finally:
            active_lease = heartbeat.stop()

        if not active_lease:
            logger.warning(f"Extraction job {job_id} lost lease during extraction; aborting publication.")
            return

        db: Session = factory()
        try:
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                logger.info(f"Paper {paper_id} deleted during extraction; dropping publication.")
                return

            # Check generation freshness (R3): if paper.current_run_id changed to newer run, abort
            if paper.current_run_id and paper.current_run_id != run_id:
                logger.warning(
                    f"Paper {paper_id} has a newer generation ({paper.current_run_id} != {run_id}); discarding stale extraction."
                )
                return

            now = utcnow_iso()

            if extraction_error:
                stmt = (
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.id == job_id,
                        ProcessingJob.status == "running",
                        ProcessingJob.claim_token == token,
                    )
                    .values(
                        status="failed",
                        finished_at=now,
                        error_message=extraction_error,
                    )
                )
                res = db.execute(stmt)
                if res.rowcount == 0:
                    db.rollback()
                    raise WorkerFencingViolation(f"Lost claim token on extraction job {job_id}")
                paper.status = "failed"
                paper.updated_at = now
                db.commit()
            elif extraction_result:
                stmt = (
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.id == job_id,
                        ProcessingJob.status == "running",
                        ProcessingJob.claim_token == token,
                    )
                    .values(
                        status="succeeded",
                        finished_at=now,
                        versions_json=json.dumps(extraction_result.versions),
                    )
                )
                res = db.execute(stmt)
                if res.rowcount == 0:
                    db.rollback()
                    raise WorkerFencingViolation(f"Lost claim token on extraction job {job_id}")

                # Save new extracted pages with run_id
                for p in extraction_result.pages:
                    blocks_dict = [
                        {
                            "id": b.id,
                            "bbox": b.bbox,
                            "text": b.text,
                            "text_hash": b.text_hash,
                        }
                        for b in p.blocks
                    ]
                    page_row = Page(
                        id=str(uuid.uuid4()),
                        paper_id=paper_id,
                        run_id=run_id,
                        page_number=p.page_number,
                        char_count=p.char_count,
                        width=p.width,
                        height=p.height,
                        rotation=p.rotation,
                        extraction_status=p.extraction_status,
                        flags_json=json.dumps(p.flags),
                        raw_text=p.raw_text,
                        blocks_json=json.dumps(blocks_dict),
                        created_at=now,
                    )
                    db.add(page_row)

                # Update paper metadata and quality
                meta = extraction_result.metadata
                paper.title = meta.title if meta.title else (paper.title or paper.original_filename)
                paper.authors_json = json.dumps(meta.authors) if meta.authors else "[]"
                paper.publication_year = meta.publication_year
                paper.keywords_json = json.dumps(meta.keywords) if meta.keywords else "[]"
                paper.metadata_source_json = json.dumps(meta.sources) if meta.sources else "{}"

                paper.page_count = extraction_result.page_count
                paper.quality_json = json.dumps(extraction_result.quality.to_dict())
                paper.published_run_id = run_id
                paper.status = "processing"
                paper.updated_at = now

                db.commit()
                logger.info(f"Published extraction output for paper {paper_id} run {run_id} (job {job_id}).")
        finally:
            db.close()
