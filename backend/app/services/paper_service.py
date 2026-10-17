import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import urllib.parse
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import Paper, Workspace
from backend.app.schemas.paper import (
    PaperListResponse,
    PaperResponse,
    PaperUploadBatchResponse,
    PaperUploadDuplicateItem,
    PaperUploadRejectedItem,
    PaperUploadSuccessItem,
)
from backend.app.services.workspace_service import decode_cursor, encode_cursor, get_workspace_or_404

logger = logging.getLogger("researchmind.paper_service")

# Chunk size for streaming file uploads (64 KB)
STREAM_CHUNK_SIZE = 64 * 1024


def sanitize_filename(name: str) -> str:
    """Sanitizes user-provided filename to prevent path traversal and control character attacks."""
    if not name:
        return "unnamed_document.pdf"
    # Strip directory components (Windows and POSIX)
    cleaned = os.path.basename(name.replace("\\", "/"))
    # Remove null bytes and control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
    # Strip leading dots or slashes
    cleaned = cleaned.strip(". /\\")
    if not cleaned:
        cleaned = "unnamed_document.pdf"
    return cleaned[:255]


def format_content_disposition(name: str, disposition_type: str = "inline") -> str:
    """Formats an RFC 6266 / RFC 5987 compliant Content-Disposition header with safe ASCII fallback and UTF-8 encoding."""
    cleaned = sanitize_filename(name)
    # ASCII fallback replaces non-ASCII with underscore and escapes quotes/backslashes
    ascii_name = re.sub(r"[^\x20-\x7e]", "_", cleaned)
    ascii_escaped = ascii_name.replace("\\", "\\\\").replace('"', '\\"')
    if not ascii_escaped.strip(" _."):
        ascii_escaped = "document.pdf"
    encoded_utf8 = urllib.parse.quote(cleaned, encoding="utf-8")
    return f"{disposition_type}; filename=\"{ascii_escaped}\"; filename*=UTF-8''{encoded_utf8}"


def get_paper_or_404(db: Session, user_id: str, paper_id: str) -> Paper:
    paper = (
        db.query(Paper)
        .join(Workspace, Paper.workspace_id == Workspace.id)
        .filter(Paper.id == paper_id, Workspace.user_id == user_id)
        .first()
    )
    if not paper:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Paper not found or access denied.",
            status_code=404,
            details={"paper_id": paper_id},
        )
    return paper


async def process_paper_upload(
    db: Session,
    user_id: str,
    workspace_id: str,
    files: list[UploadFile],
    settings: Settings,
) -> PaperUploadBatchResponse:
    # 1. Validate workspace existence and ownership
    get_workspace_or_404(db, user_id, workspace_id)

    if not files:
        raise AppException(
            code=ErrorCode.INVALID_REQUEST,
            message="At least one PDF file must be provided in the upload batch.",
            status_code=400,
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    storage_dir = settings.DATA_DIR / "pdfs"
    storage_dir.mkdir(parents=True, exist_ok=True)

    success_items: list[PaperUploadSuccessItem] = []
    duplicate_items: list[PaperUploadDuplicateItem] = []
    rejected_items: list[PaperUploadRejectedItem] = []

    # Track seen SHA-256 within the current batch to prevent same-batch duplicates
    batch_seen_hashes: dict[str, str] = {}

    for upload in files:
        raw_name = upload.filename or "document.pdf"
        display_name = sanitize_filename(raw_name)

        # Create temporary file for streaming and verification
        temp_fd, temp_path_str = tempfile.mkstemp(prefix="upload_", suffix=".pdf")
        os.close(temp_fd)
        temp_path = Path(temp_path_str)

        try:
            hasher = hashlib.sha256()
            total_bytes = 0
            magic_bytes = b""

            while chunk := await upload.read(STREAM_CHUNK_SIZE):
                total_bytes += len(chunk)
                if len(magic_bytes) < 5:
                    magic_bytes += chunk[: 5 - len(magic_bytes)]

                if total_bytes > max_bytes:
                    rejected_items.append(
                        PaperUploadRejectedItem(
                            original_filename=display_name,
                            code=ErrorCode.FILE_TOO_LARGE.value,
                            message=f"File exceeds maximum upload limit of {settings.MAX_UPLOAD_MB} MB.",
                        )
                    )
                    break

                hasher.update(chunk)
                with open(temp_path, "ab") as f:
                    f.write(chunk)
            else:
                # 2. Check Magic Bytes
                if not magic_bytes.startswith(b"%PDF-"):
                    rejected_items.append(
                        PaperUploadRejectedItem(
                            original_filename=display_name,
                            code=ErrorCode.INVALID_FILE_TYPE.value,
                            message="Only valid PDF documents are accepted.",
                        )
                    )
                    continue

                if total_bytes == 0:
                    rejected_items.append(
                        PaperUploadRejectedItem(
                            original_filename=display_name,
                            code=ErrorCode.PDF_UNREADABLE.value,
                            message="PDF file is empty (0 bytes).",
                        )
                    )
                    continue

                computed_hash = hasher.hexdigest()

                # 3. Check duplicate in same batch
                if computed_hash in batch_seen_hashes:
                    duplicate_items.append(
                        PaperUploadDuplicateItem(
                            original_filename=display_name,
                            existing_paper_id=batch_seen_hashes[computed_hash],
                        )
                    )
                    continue

                # 4. Check duplicate in workspace in database
                existing_paper = (
                    db.query(Paper)
                    .filter(
                        Paper.workspace_id == workspace_id,
                        Paper.sha256 == computed_hash,
                    )
                    .first()
                )
                if existing_paper:
                    duplicate_items.append(
                        PaperUploadDuplicateItem(
                            original_filename=display_name,
                            existing_paper_id=existing_paper.id,
                        )
                    )
                    batch_seen_hashes[computed_hash] = existing_paper.id
                    continue

                # 5. Check PDF openability and page count with PyMuPDF
                doc = None
                try:
                    doc = fitz.open(str(temp_path))
                    if doc.is_encrypted:
                        rejected_items.append(
                            PaperUploadRejectedItem(
                                original_filename=display_name,
                                code=ErrorCode.PDF_UNREADABLE.value,
                                message="PDF is encrypted or password-protected and cannot be opened.",
                            )
                        )
                        continue

                    page_count = doc.page_count
                    if page_count <= 0:
                        rejected_items.append(
                            PaperUploadRejectedItem(
                                original_filename=display_name,
                                code=ErrorCode.PDF_UNREADABLE.value,
                                message="PDF contains no readable pages.",
                            )
                        )
                        continue

                    # Extract basic document metadata
                    meta = doc.metadata or {}
                    extracted_title = meta.get("title")
                    cleaned_title = extracted_title.strip() if extracted_title and extracted_title.strip() else None

                    author_str = meta.get("author")
                    authors_list = [a.strip() for a in author_str.split(",") if a.strip()] if author_str else []

                except Exception as exc:
                    rejected_items.append(
                        PaperUploadRejectedItem(
                            original_filename=display_name,
                            code=ErrorCode.PDF_UNREADABLE.value,
                            message=f"PDF structure is corrupt or unreadable: {exc}",
                        )
                    )
                    continue
                finally:
                    if doc:
                        doc.close()

                # 6. Publish file and persist to database
                paper_id = str(uuid.uuid4())
                final_storage_path = storage_dir / f"{paper_id}.pdf"
                shutil.move(str(temp_path), str(final_storage_path))

                new_paper = Paper(
                    id=paper_id,
                    workspace_id=workspace_id,
                    original_filename=display_name,
                    storage_path=str(final_storage_path),
                    sha256=computed_hash,
                    size_bytes=total_bytes,
                    page_count=page_count,
                    title=cleaned_title or display_name,
                    authors_json=json.dumps(authors_list) if authors_list else None,
                    status="uploaded",
                )

                committed = False
                try:
                    db.add(new_paper)
                    db.commit()
                    committed = True
                except IntegrityError:
                    db.rollback()
                    final_storage_path.unlink(missing_ok=True)
                    # Look up winning duplicate
                    winner = (
                        db.query(Paper)
                        .filter(
                            Paper.workspace_id == workspace_id,
                            Paper.sha256 == computed_hash,
                        )
                        .first()
                    )
                    if winner:
                        duplicate_items.append(
                            PaperUploadDuplicateItem(
                                original_filename=display_name,
                                existing_paper_id=winner.id,
                            )
                        )
                    else:
                        rejected_items.append(
                            PaperUploadRejectedItem(
                                original_filename=display_name,
                                code=ErrorCode.DATABASE_ERROR.value,
                                message="Database integrity error during paper persistence.",
                            )
                        )
                    continue
                except Exception as exc:
                    db.rollback()
                    if not committed:
                        final_storage_path.unlink(missing_ok=True)
                    logger.error(f"Database error persisting paper {paper_id}: {exc}")
                    rejected_items.append(
                        PaperUploadRejectedItem(
                            original_filename=display_name,
                            code=ErrorCode.DATABASE_ERROR.value,
                            message="Database error during document persistence. Please try again.",
                        )
                    )
                    continue

                # Refresh attributes; if refresh fails, the row is already committed so do NOT unlink
                try:
                    db.refresh(new_paper)
                except Exception as exc:
                    logger.warning(f"Refresh failed for paper {paper_id} after commit: {exc}")

                batch_seen_hashes[computed_hash] = new_paper.id
                success_items.append(
                    PaperUploadSuccessItem(
                        id=new_paper.id,
                        original_filename=new_paper.original_filename,
                        status=new_paper.status,
                    )
                )

        finally:
            # Clean temporary file if still exists
            temp_path.unlink(missing_ok=True)
            await upload.close()

    return PaperUploadBatchResponse(
        papers=success_items,
        duplicates=duplicate_items,
        rejected=rejected_items,
    )


def list_papers(
    db: Session,
    user_id: str,
    workspace_id: str,
    status: str | None = None,
    q: str | None = None,
    limit: int = 25,
    cursor: str | None = None,
) -> PaperListResponse:
    # Verify workspace ownership
    get_workspace_or_404(db, user_id, workspace_id)

    limit = min(max(1, limit), 100)
    query = (
        db.query(Paper).filter(Paper.workspace_id == workspace_id).order_by(Paper.created_at.desc(), Paper.id.desc())
    )

    if status:
        query = query.filter(Paper.status == status)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Paper.title.ilike(term),
                Paper.original_filename.ilike(term),
                Paper.authors_json.ilike(term),
            )
        )

    total_count = query.count()

    if cursor:
        cur_created_at, cur_id = decode_cursor(cursor)
        query = query.filter(
            (Paper.created_at < cur_created_at) | ((Paper.created_at == cur_created_at) & (Paper.id < cur_id))
        )

    rows = query.limit(limit + 1).all()
    has_next = len(rows) > limit
    selected_rows = rows[:limit]

    items = [PaperResponse.model_validate(p) for p in selected_rows]

    next_cursor = None
    if has_next and selected_rows:
        last_item = selected_rows[-1]
        next_cursor = encode_cursor(last_item.created_at, last_item.id)

    return PaperListResponse(items=items, next_cursor=next_cursor, total_count=total_count)


def delete_paper(db: Session, user_id: str, paper_id: str) -> None:
    paper = get_paper_or_404(db, user_id, paper_id)
    storage_path_str = paper.storage_path

    # Safely stage physical file if not referenced by another record
    staged_path: Path | None = None
    original_file: Path | None = None
    if storage_path_str:
        other_ref = db.query(Paper).filter(Paper.id != paper.id, Paper.storage_path == storage_path_str).first()
        if not other_ref:
            p_file = Path(storage_path_str)
            if p_file.exists():
                original_file = p_file
                trash_dir = p_file.parent / ".trash"
                try:
                    trash_dir.mkdir(parents=True, exist_ok=True)
                    staged_path = trash_dir / f"del_{paper.id}_{uuid.uuid4().hex[:8]}.tmp"
                    p_file.rename(staged_path)
                except OSError as exc:
                    logger.error(f"Failed to stage backing file {storage_path_str} for deletion: {exc}")
                    raise AppException(
                        code=ErrorCode.DATABASE_ERROR,
                        message="Failed to delete paper file from storage. Deletion aborted to preserve retryable state.",
                        status_code=500,
                        details={"paper_id": paper_id},
                    )

    try:
        db.delete(paper)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error committing deletion for paper {paper_id}: {exc}")
        # Recover: restore staged file back to original location
        if staged_path and original_file and staged_path.exists():
            try:
                staged_path.rename(original_file)
            except Exception as restore_exc:
                logger.error(f"Failed to restore staged file {staged_path} back to {original_file}: {restore_exc}")
        raise AppException(
            code=ErrorCode.DATABASE_ERROR,
            message="Database error during paper deletion. Deletion aborted and original file preserved.",
            status_code=500,
            details={"paper_id": paper_id},
        )

    # Database commit succeeded: permanently unlink quarantined file
    if staged_path and staged_path.exists():
        try:
            staged_path.unlink()
        except OSError as exc:
            logger.warning(f"Failed to permanently remove staged file {staged_path}: {exc}")
