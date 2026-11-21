"""ResearchMind AI — Retrieval Schemas (Phase 6).

Pydantic schemas for the hybrid retrieval endpoint, candidate passages,
diagnostics, and timing breakdowns.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RetrievalQueryRequest(BaseModel):
    """Request payload for scoped document retrieval."""

    workspace_id: str = Field(..., description="Target workspace ID")
    query: str = Field(..., min_length=1, max_length=1000, description="Search query string")
    selected_paper_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Explicit list of ready paper IDs within the workspace to search across",
    )
    top_k: int = Field(default=20, ge=1, le=50, description="Maximum number of fused passages to return")
    mode: Literal["hybrid", "dense", "sparse"] = Field(
        default="hybrid",
        description="Retrieval mode: hybrid (RRF k=60), dense (FAISS FlatIP), or sparse (BM25Okapi)",
    )


class RetrievalPassage(BaseModel):
    """Traceable passage retrieved from a ready paper chunk."""

    chunk_id: str
    paper_id: str
    paper_title: str | None = None
    section: str
    heading: str | None = None
    page_start: int
    page_end: int
    text: str
    score: float = Field(
        ...,
        description="Ranking score. Note: For hybrid mode, this is a reciprocal-rank fusion score (k=60), "
        "not a calibrated probability or confidence percentage.",
    )
    rank: int = Field(..., description="1-based output rank")
    dense_rank: int | None = Field(default=None, description="1-based rank in dense retrieval candidates")
    dense_score: float | None = Field(default=None, description="Cosine/Inner-product similarity score from dense search")
    sparse_rank: int | None = Field(default=None, description="1-based rank in BM25 sparse candidates")
    sparse_score: float | None = Field(default=None, description="BM25Okapi score from sparse search")
    index_version: int = Field(..., description="Version of the active embedding index used for retrieval")
    model_name: str
    model_revision: str

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "page_start" not in data and "page_number" in data:
                data["page_start"] = data["page_number"]
            if "page_end" not in data and "page_number" in data:
                data["page_end"] = data["page_number"]
            if "section" not in data and "section_title" in data:
                data["section"] = data["section_title"]
            if "rank" not in data:
                data["rank"] = 1
            if "index_version" not in data:
                data["index_version"] = 1
            if "model_name" not in data:
                data["model_name"] = "default"
            if "model_revision" not in data:
                data["model_revision"] = "default"
        return data

    @property
    def page_number(self) -> int:
        return self.page_start

    @property
    def section_title(self) -> str | None:
        return self.section


class RetrievalTimings(BaseModel):
    """Execution timing breakdown in milliseconds."""

    dense_ms: float = Field(default=0.0, description="Dense embedding and candidate search time in ms")
    sparse_ms: float = Field(default=0.0, description="Sparse BM25 candidate search time in ms")
    fusion_ms: float = Field(default=0.0, description="Reciprocal-rank fusion and deduplication time in ms")
    total_ms: float = Field(default=0.0, description="Total server processing time in ms")


class RetrievalDiagnostics(BaseModel):
    """Diagnostic metadata for retrieval inspection."""

    total_eligible_chunks: int = Field(..., description="Total chunks eligible for retrieval across selected papers")
    dense_candidate_count: int = Field(..., description="Number of candidate chunks evaluated from dense search")
    sparse_candidate_count: int = Field(..., description="Number of candidate chunks evaluated from sparse search")
    fused_count: int = Field(..., description="Final number of returned passages")
    timings: RetrievalTimings
    index_version: int
    index_id: str
    mode: str
    score_explanation: str = Field(
        default="RRF scores represent relative ranking fusion scores (k=60), not calibrated probabilities or confidence percentages.",
        description="Interpretation guidance for scores",
    )


class RetrievalQueryData(BaseModel):
    """Enclosed response data for retrieval query."""

    query: str
    workspace_id: str
    selected_paper_ids: list[str]
    passages: list[RetrievalPassage]
    diagnostics: RetrievalDiagnostics


class RetrievalQueryResponse(BaseModel):
    """Top-level API response envelope for retrieval."""

    data: RetrievalQueryData
    error: dict[str, Any] | None = None
