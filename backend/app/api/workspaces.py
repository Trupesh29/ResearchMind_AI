from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from backend.app.services import workspace_service

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceResponse:
    workspace = workspace_service.create_workspace(db, current_user.id, data)
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceListResponse:
    items, next_cursor, total_count = workspace_service.list_workspaces(db, current_user.id, limit=limit, cursor=cursor)
    return WorkspaceListResponse(
        items=[WorkspaceResponse.model_validate(i) for i in items],
        next_cursor=next_cursor,
        total_count=total_count,
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetailResponse:
    detail = workspace_service.get_workspace_detail(db, current_user.id, workspace_id)
    return WorkspaceDetailResponse.model_validate(detail)


@router.patch("/{workspace_id}", response_model=WorkspaceDetailResponse)
def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceDetailResponse:
    detail = workspace_service.update_workspace(db, current_user.id, workspace_id, data)
    return WorkspaceDetailResponse.model_validate(detail)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    workspace_service.delete_workspace(db, current_user.id, workspace_id, settings.DATA_DIR)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
