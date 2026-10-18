import json
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProvenanceDetail(BaseModel):
    source: str
    file_property: str | None = None
    page_number: int | None = None
    block_id: str | None = None
    evidence: str | None = None

    model_config = {"from_attributes": True}


class PaperResponse(BaseModel):
    id: str
    workspace_id: str
    original_filename: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    keywords: list[str] = Field(default_factory=list)
    metadata_source: dict[str, ProvenanceDetail | str] | None = None
    page_count: int | None = None
    size_bytes: int
    status: str
    quality: dict[str, Any] | None = None
    created_at: str
    current_run_id: str | None = None
    published_run_id: str | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def parse_orm_json_fields(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            # Reading from SQLAlchemy ORM model
            raw_authors = getattr(data, "authors_json", None)
            authors = json.loads(raw_authors) if raw_authors else []

            raw_keywords = getattr(data, "keywords_json", None)
            keywords = json.loads(raw_keywords) if raw_keywords else []

            raw_meta = getattr(data, "metadata_source_json", None)
            metadata_source = json.loads(raw_meta) if raw_meta else None

            raw_quality = getattr(data, "quality_json", None)
            quality = json.loads(raw_quality) if raw_quality else None

            return {
                "id": data.id,
                "workspace_id": data.workspace_id,
                "original_filename": data.original_filename,
                "title": data.title,
                "authors": authors,
                "publication_year": data.publication_year,
                "keywords": keywords,
                "metadata_source": metadata_source,
                "page_count": data.page_count,
                "size_bytes": data.size_bytes,
                "status": data.status,
                "quality": quality,
                "created_at": data.created_at,
                "current_run_id": getattr(data, "current_run_id", None),
                "published_run_id": getattr(data, "published_run_id", None),
            }
        return data


class PaperUploadSuccessItem(BaseModel):
    id: str
    original_filename: str
    status: str


class PaperUploadDuplicateItem(BaseModel):
    original_filename: str
    existing_paper_id: str


class PaperUploadRejectedItem(BaseModel):
    original_filename: str
    code: str
    message: str


class PaperUploadBatchResponse(BaseModel):
    papers: list[PaperUploadSuccessItem] = Field(default_factory=list)
    duplicates: list[PaperUploadDuplicateItem] = Field(default_factory=list)
    rejected: list[PaperUploadRejectedItem] = Field(default_factory=list)


class PaperListResponse(BaseModel):
    items: list[PaperResponse]
    next_cursor: str | None = None
    total_count: int = 0


class PaperStageDetail(BaseModel):
    stage: str
    status: str
    attempt: int = 1
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class PaperStatusResponse(BaseModel):
    status: str
    stage: str = "validating"
    progress: float = 0.0
    attempt: int = 1
    error: str | None = None
    stages: list[PaperStageDetail] = Field(default_factory=list)
    run_id: str | None = None
    is_stale: bool = False


class PageSummaryItem(BaseModel):
    page_number: int
    char_count: int
    extraction_status: str
    flags: list[str] = Field(default_factory=list)


class PagesListResponse(BaseModel):
    items: list[PageSummaryItem]
    total_pages: int = 0
    run_id: str | None = None
    is_stale: bool = False


class PageBlockItem(BaseModel):
    id: str
    bbox: list[float]  # [x0, y0, x1, y1]
    text: str
    text_hash: str


class PageBlocksResponse(BaseModel):
    page_number: int
    width: float | None = None
    height: float | None = None
    rotation: int | None = None
    blocks: list[PageBlockItem] = Field(default_factory=list)
    run_id: str | None = None
    is_stale: bool = False
