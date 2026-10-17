import base64
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException, ErrorCode
from backend.app.db.models import Paper, Workspace
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from backend.app.services import quarantine_service

logger = logging.getLogger("researchmind.workspace_service")


def encode_cursor(created_at: str, item_id: str) -> str:
    token = f"{created_at}|{item_id}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> tuple[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        created_at, item_id = decoded.split("|", 1)
        return created_at, item_id
    except Exception:
        raise AppException(
            code=ErrorCode.INVALID_REQUEST,
            message="Invalid pagination cursor format.",
            status_code=400,
        )


def get_workspace_or_404(db: Session, user_id: str, workspace_id: str) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user_id).first()
    if not workspace:
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Workspace not found or access denied.",
            status_code=404,
            details={"workspace_id": workspace_id},
        )
    return workspace


def create_workspace(db: Session, user_id: str, data: WorkspaceCreate) -> Workspace:
    # Check duplicate name
    existing = db.query(Workspace).filter(Workspace.user_id == user_id, Workspace.name == data.name).first()
    if existing:
        raise AppException(
            code=ErrorCode.NAME_CONFLICT,
            message=f"A workspace named '{data.name}' already exists.",
            status_code=409,
            details={"name": data.name},
        )

    workspace = Workspace(
        user_id=user_id,
        name=data.name,
        description=data.description,
    )
    try:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace
    except IntegrityError:
        db.rollback()
        raise AppException(
            code=ErrorCode.NAME_CONFLICT,
            message=f"A workspace named '{data.name}' already exists.",
            status_code=409,
            details={"name": data.name},
        )


def list_workspaces(
    db: Session,
    user_id: str,
    limit: int = 25,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, int]:
    limit = min(max(1, limit), 100)

    total_count = db.query(func.count(Workspace.id)).filter(Workspace.user_id == user_id).scalar() or 0

    # Aggregated counts query
    query = (
        db.query(
            Workspace,
            func.count(Paper.id).label("paper_count"),
            func.count(case((Paper.status == "ready", Paper.id))).label("ready_count"),
        )
        .outerjoin(Paper, Paper.workspace_id == Workspace.id)
        .filter(Workspace.user_id == user_id)
        .group_by(Workspace.id)
        .order_by(Workspace.created_at.desc(), Workspace.id.desc())
    )

    if cursor:
        cur_created_at, cur_id = decode_cursor(cursor)
        query = query.filter(
            (Workspace.created_at < cur_created_at)
            | ((Workspace.created_at == cur_created_at) & (Workspace.id < cur_id))
        )

    rows = query.limit(limit + 1).all()

    items = []
    has_next = len(rows) > limit
    selected_rows = rows[:limit]

    for ws, paper_count, ready_count in selected_rows:
        items.append(
            {
                "id": ws.id,
                "name": ws.name,
                "description": ws.description,
                "created_at": ws.created_at,
                "paper_count": paper_count,
                "ready_count": ready_count,
            }
        )

    next_cursor = None
    if has_next and selected_rows:
        last_ws = selected_rows[-1][0]
        next_cursor = encode_cursor(last_ws.created_at, last_ws.id)

    return items, next_cursor, total_count


def get_workspace_detail(db: Session, user_id: str, workspace_id: str) -> dict[str, Any]:
    ws = get_workspace_or_404(db, user_id, workspace_id)

    counts = (
        db.query(
            func.count(Paper.id).label("paper_count"),
            func.count(case((Paper.status == "ready", Paper.id))).label("ready_count"),
        )
        .filter(Paper.workspace_id == ws.id)
        .one()
    )

    return {
        "id": ws.id,
        "name": ws.name,
        "description": ws.description,
        "created_at": ws.created_at,
        "paper_count": counts.paper_count,
        "ready_count": counts.ready_count,
        "active_index": None,
    }


def update_workspace(
    db: Session,
    user_id: str,
    workspace_id: str,
    data: WorkspaceUpdate,
) -> dict[str, Any]:
    ws = get_workspace_or_404(db, user_id, workspace_id)

    if data.name is not None and data.name != ws.name:
        conflict = (
            db.query(Workspace)
            .filter(
                Workspace.user_id == user_id,
                Workspace.name == data.name,
                Workspace.id != ws.id,
            )
            .first()
        )
        if conflict:
            raise AppException(
                code=ErrorCode.NAME_CONFLICT,
                message=f"A workspace named '{data.name}' already exists.",
                status_code=409,
                details={"name": data.name},
            )
        ws.name = data.name

    if data.description is not None:
        ws.description = data.description

    try:
        db.commit()
        db.refresh(ws)
    except IntegrityError:
        db.rollback()
        raise AppException(
            code=ErrorCode.NAME_CONFLICT,
            message=f"A workspace named '{data.name}' already exists.",
            status_code=409,
            details={"name": data.name},
        )

    return get_workspace_detail(db, user_id, ws.id)


def delete_workspace(
    db: Session,
    user_id: str,
    workspace_id: str,
    data_dir: Path,
) -> None:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user_id).first()
    if not ws:
        trash_dir = data_dir / "pdfs" / ".trash"
        pending = quarantine_service.find_pending_purges_by_workspace(trash_dir, workspace_id)
        if pending:
            all_purged = all(quarantine_service.purge_quarantined_file(stg, meta) for stg, meta in pending)
            if all_purged:
                return
            raise AppException(
                code=ErrorCode.DATABASE_ERROR,
                message="Quarantined files purge failed during workspace deletion. Cleanup remains pending.",
                status_code=500,
                details={"workspace_id": workspace_id, "status": "pending_purge"},
            )
        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Workspace not found.",
            status_code=404,
            details={"workspace_id": workspace_id},
        )

    # Collect backing files
    papers = db.query(Paper).filter(Paper.workspace_id == ws.id).all()

    # Identify unique files to stage that are NOT referenced by other workspaces
    files_to_stage: dict[str, list[Paper]] = {}
    for p in papers:
        if p.storage_path:
            p_file = Path(p.storage_path)
            if p_file.exists():
                other_ref = (
                    db.query(Paper).filter(Paper.workspace_id != ws.id, Paper.storage_path == p.storage_path).first()
                )
                if not other_ref:
                    files_to_stage.setdefault(p.storage_path, []).append(p)

    staged_entries: list[tuple[Path, Path, Path]] = []  # (original_path, staged_path, meta_path)
    # Stage each file into quarantine
    for path_str, associated_papers in files_to_stage.items():
        p_file = Path(path_str)
        try:
            staged_p, meta_p = quarantine_service.stage_file_for_deletion(
                original_path=p_file,
                entity_type="workspace",
                paper_id=associated_papers[0].id,
                workspace_id=ws.id,
            )
            staged_entries.append((p_file, staged_p, meta_p))
        except OSError as exc:
            logger.error(f"Error staging file {path_str} during workspace deletion: {exc}")
            # Restore any files already staged so far
            for orig_p, stg_p, meta_p in staged_entries:
                quarantine_service.restore_quarantined_file(stg_p, orig_p, meta_p)
            raise AppException(
                code=ErrorCode.DATABASE_ERROR,
                message="Failed to delete one or more backing files during workspace deletion. Workspace and papers preserved for retry.",
                status_code=500,
                details={"workspace_id": ws.id, "failed_paper_ids": [p.id for p in associated_papers]},
            )

    # Delete workspace from DB (FK cascade removes paper records)
    try:
        db.delete(ws)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error committing deletion for workspace {ws.id}: {exc}")
        all_restored = True
        for orig_p, stg_p, meta_p in staged_entries:
            if not quarantine_service.restore_quarantined_file(stg_p, orig_p, meta_p):
                all_restored = False
        if all_restored:
            raise AppException(
                code=ErrorCode.DATABASE_ERROR,
                message="Database error during workspace deletion. Workspace and backing files preserved for retry.",
                status_code=500,
                details={"workspace_id": ws.id},
            )
        else:
            raise AppException(
                code=ErrorCode.DATABASE_ERROR,
                message="Database error during workspace deletion and failed to restore one or more backing files. Files quarantined for recovery.",
                status_code=500,
                details={"workspace_id": ws.id, "status": "quarantined_for_recovery"},
            )

    # Database commit succeeded: permanently unlink all quarantined files
    all_purged = True
    for _, stg_p, meta_p in staged_entries:
        quarantine_service.mark_committed_deletion(meta_p)
        if not quarantine_service.purge_quarantined_file(stg_p, meta_p, max_retries=3):
            all_purged = False

    if not all_purged:
        raise AppException(
            code=ErrorCode.DATABASE_ERROR,
            message="Workspace deleted from database, but one or more quarantined files failed to purge. Cleanup remains pending.",
            status_code=500,
            details={"workspace_id": ws.id, "status": "pending_purge"},
        )
