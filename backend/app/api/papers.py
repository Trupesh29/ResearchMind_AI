import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.paper import (
    PaperListResponse,
    PaperResponse,
    PaperStatusResponse,
    PaperUploadBatchResponse,
)
from backend.app.services import paper_service

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.post("", response_model=PaperUploadBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_papers(
    workspace_id: str | None = Form(default=None, description="ID of target workspace"),
    workspace_id_query: str | None = Query(default=None, alias="workspace_id"),
    files: list[UploadFile] = File(..., description="One or more PDF files to upload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PaperUploadBatchResponse:
    effective_ws_id = workspace_id or workspace_id_query
    if not effective_ws_id:
        raise AppException(
            code=ErrorCode.INVALID_REQUEST,
            message="workspace_id is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return await paper_service.process_paper_upload(
        db=db,
        user_id=current_user.id,
        workspace_id=effective_ws_id,
        files=files,
        settings=settings,
    )


@router.get("", response_model=PaperListResponse)
def list_papers(
    workspace_id: str = Query(..., description="Required workspace ID"),
    status: str | None = Query(default=None, description="Optional status filter"),
    q: str | None = Query(default=None, description="Optional search term across title, filename, authors"),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperListResponse:
    return paper_service.list_papers(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        status=status,
        q=q,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperResponse:
    paper = paper_service.get_paper_or_404(db, current_user.id, paper_id)
    return PaperResponse.model_validate(paper)


@router.get("/{paper_id}/status", response_model=PaperStatusResponse)
def get_paper_status(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperStatusResponse:
    paper = paper_service.get_paper_or_404(db, current_user.id, paper_id)
    return PaperStatusResponse(
        status=paper.status,
        stage="validating" if paper.status == "uploaded" else "ready",
        progress=1.0 if paper.status == "ready" else 0.0,
        attempt=1,
        error=None,
    )


@router.get("/{paper_id}/file")
def get_paper_file(
    paper_id: str,
    request: Request,
    range: str | None = Header(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    paper = paper_service.get_paper_or_404(db, current_user.id, paper_id)

    file_path = Path(paper.storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Backing document file not found on server.",
            status_code=404,
            details={"paper_id": paper_id},
        )

    file_size = file_path.stat().st_size
    safe_filename = paper_service.sanitize_filename(paper.original_filename)

    # Handle HTTP Range requests
    if range and range.strip():
        range_match = re.match(r"^bytes=(\d*)-(\d*)$", range.strip())
        if not range_match:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        start_str, end_str = range_match.groups()

        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str:
            start = int(start_str)
            end = file_size - 1
        elif end_str:
            # Suffix range
            suffix_len = int(end_str)
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        if start >= file_size or end >= file_size or start > end or start < 0:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        chunk_length = end - start + 1

        def iter_range_bytes():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = chunk_length
                while bytes_left > 0:
                    read_size = min(bytes_left, 64 * 1024)
                    data = f.read(read_size)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_length),
            "Content-Type": "application/pdf",
            "Content-Disposition": f'inline; filename="{safe_filename}"',
        }
        return StreamingResponse(
            iter_range_bytes(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers,
        )

    # Standard full response
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{safe_filename}"',
    }
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_filename,
        headers=headers,
    )


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    paper_service.delete_paper(db, current_user.id, paper_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
