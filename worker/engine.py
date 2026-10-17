"""ResearchMind AI — Standalone Processing Worker Engine (Phase 3).

Implements atomic job claiming, heartbeat leasing, fencing token validation,
short database transactions, and isolated extraction handling.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import socket
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import Page, Paper, ProcessingJob, utcnow_iso
from backend.app.db.session import get_session_factory
from backend.app.services import extraction_service

logger = logging.getLogger("worker.engine")


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
        """Detect running jobs whose heartbeat has expired and either retry or fail them."""
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
            if job.attempt < self.max_retries:
                job.attempt += 1
                job.status = "queued"
                job.claim_token = None
                job.worker_id = None
                job.heartbeat_at = None
                job.error_message = (
                    f"Lease expired after {self.lease_timeout_seconds}s; retrying attempt {job.attempt}."
                )
            else:
                job.status = "failed"
                job.finished_at = utcnow_iso()
                job.error_message = f"Lease expired and maximum retries ({self.max_retries}) exceeded."
                # Mark paper failed
                paper = db.query(Paper).filter(Paper.id == job.paper_id).first()
                if paper:
                    paper.status = "failed"
                    paper.updated_at = utcnow_iso()
        if expired_jobs:
            db.commit()

    def _claim_next_job(self, db: Session) -> dict[str, Any] | None:
        """Atomically claim the next queued validating or extracting job."""
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.status == "queued",
                ProcessingJob.stage.in_(["validating", "extracting"]),
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )

        if not job:
            return None

        # Verify paper exists before claiming
        paper = db.query(Paper).filter(Paper.id == job.paper_id).first()
        if not paper:
            # Paper was deleted; delete orphaned job
            db.delete(job)
            db.commit()
            return None

        token = str(uuid.uuid4())
        now = utcnow_iso()

        job.status = "running"
        job.worker_id = self.worker_id
        job.claim_token = token
        job.claimed_at = now
        job.heartbeat_at = now
        if not job.started_at:
            job.started_at = now

        db.commit()

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

    def _send_heartbeat(self, job_id: str, claim_token: str) -> bool:
        """Update heartbeat timestamp if claim token is still valid. Returns False if lost claim."""
        factory = get_session_factory()
        db: Session = factory()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if not job or job.claim_token != claim_token or job.status != "running":
                return False
            job.heartbeat_at = utcnow_iso()
            db.commit()
            return True
        except Exception as exc:
            logger.warning(f"Failed to update heartbeat for {job_id}: {exc}")
            return False
        finally:
            db.close()

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

        validation_error: str | None = None
        pdf_file = self.settings.BASE_DIR / storage_path if not os.path.isabs(storage_path) else storage_path
        pdf_path = os.fspath(pdf_file)

        if not os.path.exists(pdf_path):
            validation_error = f"PDF file not found at storage path: {storage_path}"
        else:
            actual_size = os.path.getsize(pdf_path)
            if actual_size != expected_size:
                validation_error = f"File size mismatch: expected {expected_size}, got {actual_size}"
            else:
                try:
                    import hashlib

                    hasher = hashlib.sha256()
                    with open(pdf_path, "rb") as f:
                        header = f.read(5)
                        if header != b"%PDF-":
                            validation_error = "File header missing %PDF- magic bytes."
                        else:
                            hasher.update(header)
                            while chunk := f.read(65536):
                                hasher.update(chunk)
                            actual_sha = hasher.hexdigest()
                            if actual_sha != expected_sha256:
                                validation_error = f"File hash mismatch: expected {expected_sha256}, got {actual_sha}"
                except Exception as exc:
                    validation_error = f"Error reading PDF: {exc}"

        # Publish validation outcome
        factory = get_session_factory()
        db: Session = factory()
        try:
            # Verify paper still exists
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                logger.info(f"Paper {paper_id} deleted during validation; discarding job.")
                return

            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if not job or job.claim_token != token or job.status != "running":
                logger.warning(f"Validation job {job_id} claim token expired or superseded.")
                return

            now = utcnow_iso()
            if validation_error:
                job.status = "failed"
                job.error_message = validation_error
                job.finished_at = now
                paper.status = "failed"
                paper.updated_at = now
            else:
                job.status = "succeeded"
                job.finished_at = now
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
        storage_path = info["storage_path"]

        pdf_file = self.settings.BASE_DIR / storage_path if not os.path.isabs(storage_path) else storage_path
        pdf_path = os.fspath(pdf_file)

        # Heartbeat check before heavy extraction
        if not self._send_heartbeat(job_id, token):
            logger.warning(f"Lost lease before extraction start on job {job_id}.")
            return

        extraction_result: extraction_service.ExtractionResult | None = None
        extraction_error: str | None = None

        try:
            extraction_result = extraction_service.extract_pdf(pdf_path)
        except extraction_service.UnsupportedTextError as ute:
            extraction_error = str(ute)
        except Exception as exc:
            extraction_error = f"Extraction failure: {exc}"

        # Heartbeat check after extraction
        if not self._send_heartbeat(job_id, token):
            logger.warning(f"Lost lease after extraction on job {job_id}; discarding result.")
            return

        # Atomically publish extraction results
        factory = get_session_factory()
        db: Session = factory()
        try:
            # 1. Verify paper exists (deletion safety)
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                logger.info(f"Paper {paper_id} deleted during extraction; discarding output.")
                return

            # 2. Verify claim token matches (fencing safety)
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if not job or job.claim_token != token or job.status != "running":
                logger.warning(f"Extraction job {job_id} claim token expired or superseded.")
                return

            now = utcnow_iso()

            if extraction_error:
                job.status = "failed"
                job.error_message = extraction_error
                job.finished_at = now
                paper.status = "failed"
                paper.updated_at = now
            elif extraction_result:
                # Generation-consistent replacement: purge old pages for this paper
                db.query(Page).filter(Page.paper_id == paper_id).delete()

                # Insert new extracted pages
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
                if meta.title and paper.title in (None, "", paper.original_filename):
                    paper.title = meta.title
                if meta.authors:
                    paper.authors_json = json.dumps(meta.authors)
                if meta.publication_year:
                    paper.publication_year = meta.publication_year
                if meta.keywords:
                    paper.keywords_json = json.dumps(meta.keywords)
                if meta.sources:
                    paper.metadata_source_json = json.dumps(meta.sources)

                paper.page_count = extraction_result.page_count
                paper.quality_json = json.dumps(extraction_result.quality.to_dict())
                # Phase 3 boundary: remain processing (awaiting Phase 4 sectioning)
                paper.status = "processing"
                paper.updated_at = now

                job.status = "succeeded"
                job.finished_at = now
                job.versions_json = json.dumps(extraction_result.versions)

            db.commit()
            logger.info(f"Published extraction output for paper {paper_id} (job {job_id}).")
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to publish extraction results for paper {paper_id}: {exc}", exc_info=True)
            raise
        finally:
            db.close()
