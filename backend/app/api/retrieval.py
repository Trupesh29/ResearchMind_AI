"""ResearchMind AI — Retrieval API Router (Phase 6).

Exposes `POST /api/retrieval/query` for scoped hybrid candidate retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.retrieval import RetrievalQueryRequest, RetrievalQueryResponse
from backend.app.services import retrieval_service

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post("/query", response_model=RetrievalQueryResponse, status_code=status.HTTP_200_OK)
def query_retrieval(
    request: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetrievalQueryResponse:
    """Retrieve ranked evidence passages matching the query across selected workspace papers."""
    data = retrieval_service.retrieve_passages(db=db, user_id=current_user.id, request=request)
    return RetrievalQueryResponse(data=data, error=None)
