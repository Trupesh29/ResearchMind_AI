import json
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PaperResponse(BaseModel):
    id: str
    workspace_id: str
    original_filename: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    keywords: list[str] = Field(default_factory=list)
    metadata_source: dict[str, str] | None = None
    page_count: int | None = None
    size_bytes: int
    status: str
    quality: dict[str, Any] | None = None
    created_at: str

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


class PaperStatusResponse(BaseModel):
    status: str
    stage: str = "validating"
    progress: float = 0.0
    attempt: int = 1
    error: str | None = None
