"""
ResearchMind AI — Schemas for Grounded Research Assistant
Defines request and response structures for assistant queries, citations,
claim verification, calibrated abstention, and conversation history.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.retrieval import RetrievalPassage


class CitationItem(BaseModel):
    citation_id: str = Field(description="Display citation tag, e.g. [1]")
    passage_id: str = Field(description="ID of the retrieved passage chunk")
    paper_id: str = Field(description="UUID of the cited paper")
    paper_title: str = Field(description="Title of the cited paper")
    page_number: int = Field(description="Physical PDF page number where evidence appears")
    section_title: Optional[str] = Field(default=None, description="Section header of the passage")
    exact_quote: str = Field(description="Exact evidence quote from the source chunk")
    score: float = Field(description="Retrieval relevance score (RRF)")


class ResearchQueryRequest(BaseModel):
    workspace_id: str = Field(description="Workspace owning the requested papers")
    query: str = Field(min_length=1, max_length=2000, description="User research question")
    selected_paper_ids: List[str] = Field(min_length=1, description="Explicitly selected ready paper IDs")
    mode: Literal["concise", "detailed", "comparison"] = Field(
        default="concise",
        description="Response depth: concise overview, detailed analysis, or cross-paper comparison",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional existing conversation ID to continue a thread",
    )

    @model_validator(mode="after")
    def validate_non_empty_papers(self) -> "ResearchQueryRequest":
        clean_ids = [pid.strip() for pid in self.selected_paper_ids if pid and pid.strip()]
        if not clean_ids:
            raise ValueError("selected_paper_ids must contain at least one non-empty paper ID")
        self.selected_paper_ids = list(dict.fromkeys(clean_ids))
        self.query = self.query.strip()
        if not self.query:
            raise ValueError("query cannot be blank or whitespace-only")
        return self


class ResearchAssistantResponse(BaseModel):
    conversation_id: str
    message_id: str
    query: str
    rewritten_query: Optional[str] = None
    answer: str
    is_abstention: bool = Field(
        default=False,
        description="True if the assistant honestly abstained due to insufficient evidence",
    )
    citations: List[CitationItem] = Field(default_factory=list)
    retrieved_passages: List[RetrievalPassage] = Field(default_factory=list)
    selected_paper_ids: List[str]
    mode: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    is_abstention: bool = False
    citations: List[CitationItem] = Field(default_factory=list)
    selected_paper_ids: List[str] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    workspace_id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    workspace_id: str
    title: str
    messages: List[MessageResponse]
    created_at: str
    updated_at: str
