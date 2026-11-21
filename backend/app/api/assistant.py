"""
ResearchMind AI — Research Assistant API Router
Handles grounded QA queries, claim verification, honest abstention,
and conversation lifecycle.
"""

from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.schemas.assistant import (
    ConversationDetail,
    ConversationSummary,
    ResearchAssistantResponse,
    ResearchQueryRequest,
)
from backend.app.services.assistant_service import AssistantService

router = APIRouter(prefix="/research", tags=["assistant"])


@router.post(
    "/query",
    response_model=ResearchAssistantResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit research query with citations and honest abstention",
)
def query_research_assistant(
    req: ResearchQueryRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ResearchAssistantResponse:
    return AssistantService.execute_research_query(db=db, req=req, settings=settings)


@router.get(
    "/conversations",
    response_model=List[ConversationSummary],
    status_code=status.HTTP_200_OK,
    summary="List conversations in a workspace",
)
def list_conversations(
    workspace_id: str = Query(..., description="Workspace ID"),
    db: Session = Depends(get_db),
) -> List[ConversationSummary]:
    return AssistantService.list_conversations(db=db, workspace_id=workspace_id)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail and message history",
)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> ConversationDetail:
    return AssistantService.get_conversation_detail(db=db, conversation_id=conversation_id)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> None:
    AssistantService.delete_conversation(db=db, conversation_id=conversation_id)
