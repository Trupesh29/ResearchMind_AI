import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def utcnow_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def generate_uuid() -> str:
    """Return new UUID4 string."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    # Relationships
    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_workspaces_user_name"),)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workspaces")
    papers: Mapped[list["Paper"]] = relationship("Paper", back_populates="workspace", cascade="all, delete-orphan")
    indexes: Mapped[list["EmbeddingIndex"]] = relationship(
        "EmbeddingIndex", back_populates="workspace", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} name={self.name}>"


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_source_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", server_default="uploaded", nullable=False)
    current_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso, nullable=False)

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_papers_workspace_sha256"),
        Index("idx_papers_workspace_status", "workspace_id", "status"),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="ck_papers_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_papers_size_bytes"),
        CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_papers_page_count",
        ),
        CheckConstraint(
            "publication_year IS NULL OR (publication_year >= 1900 AND publication_year <= 2100)",
            name="ck_papers_publication_year",
        ),
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="papers")
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="paper", cascade="all, delete-orphan"
    )
    pages: Mapped[list["Page"]] = relationship("Page", back_populates="paper", cascade="all, delete-orphan")
    sections: Mapped[list["Section"]] = relationship("Section", back_populates="paper", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="paper", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Paper id={self.id} filename={self.original_filename} status={self.status}>"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default=generate_uuid)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    claimed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    heartbeat_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    versions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    __table_args__ = (
        Index("idx_jobs_paper_run", "paper_id", "run_id"),
        Index("idx_jobs_status_stage", "status", "stage"),
        Index("idx_jobs_heartbeat", "status", "heartbeat_at"),
        Index(
            "uq_active_job_per_paper",
            "paper_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "stage IN ('validating', 'extracting', 'sectioning', 'chunking', 'embedding', 'indexing', 'ready')",
            name="ck_jobs_stage",
        ),
        CheckConstraint("attempt >= 1", name="ck_jobs_attempt"),
    )

    paper: Mapped["Paper"] = relationship("Paper", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<ProcessingJob id={self.id} paper_id={self.paper_id} stage={self.stage} status={self.status}>"


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(16), default="ok", server_default="ok", nullable=False)
    flags_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]", nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    __table_args__ = (
        UniqueConstraint("paper_id", "run_id", "page_number", name="uq_pages_paper_run_page"),
        CheckConstraint("page_number >= 1", name="ck_pages_page_number"),
        CheckConstraint("char_count >= 0", name="ck_pages_char_count"),
        CheckConstraint(
            "extraction_status IN ('ok', 'partial', 'failed')",
            name="ck_pages_extraction_status",
        ),
    )

    paper: Mapped["Paper"] = relationship("Paper", back_populates="pages")

    def __repr__(self) -> str:
        return f"<Page id={self.id} paper_id={self.paper_id} page={self.page_number} status={self.extraction_status}>"


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(100), default="unknown", server_default="unknown", nullable=False)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_spans_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    __table_args__ = (
        UniqueConstraint("paper_id", "run_id", "section_index", name="uq_sections_paper_run_index"),
        Index("idx_sections_paper_run", "paper_id", "run_id"),
        CheckConstraint("section_index >= 0", name="ck_sections_section_index"),
        CheckConstraint("page_start >= 1 AND page_end >= page_start", name="ck_sections_page_range"),
    )

    paper: Mapped["Paper"] = relationship("Paper", back_populates="sections")

    def __repr__(self) -> str:
        return f"<Section id={self.id} paper_id={self.paper_id} section={self.section} index={self.section_index}>"


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(100), default="unknown", server_default="unknown", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    block_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_excluded: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    embedding_index_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    faiss_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    tokenizer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tokenizer_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    __table_args__ = (
        UniqueConstraint("paper_id", "run_id", "chunk_index", name="uq_chunks_paper_run_index"),
        Index("idx_chunks_paper_run", "paper_id", "run_id"),
        Index("idx_chunks_paper_section", "paper_id", "section"),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index"),
        CheckConstraint("page_start >= 1 AND page_end >= page_start", name="ck_chunks_page_range"),
        CheckConstraint("token_count > 0", name="ck_chunks_token_count"),
    )

    paper: Mapped["Paper"] = relationship("Paper", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk id={self.id} paper_id={self.paper_id} index={self.chunk_index} tokens={self.token_count}>"


class EmbeddingIndex(Base):
    __tablename__ = "embedding_indexes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization: Mapped[str] = mapped_column(String(32), default="l2", server_default="l2", nullable=False)
    chunk_params_json: Mapped[str] = mapped_column(Text, nullable=False)
    faiss_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bm25_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    index_checksums_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="building", server_default="building", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "version", name="uq_embedding_indexes_workspace_version"),
        Index("idx_embedding_indexes_workspace", "workspace_id"),
        Index("idx_embedding_indexes_workspace_status", "workspace_id", "status"),
        Index(
            "uq_embedding_active_per_workspace",
            "workspace_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
        CheckConstraint(
            "status IN ('building', 'active', 'retired', 'failed')",
            name="ck_embedding_indexes_status",
        ),
        CheckConstraint("version >= 1", name="ck_embedding_indexes_version"),
        CheckConstraint("dimension > 0", name="ck_embedding_indexes_dimension"),
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="indexes")
    chunks: Mapped[list["IndexChunk"]] = relationship(
        "IndexChunk", back_populates="index", cascade="all, delete-orphan"
    )

    @property
    def chunk_count(self) -> int:
        if self.chunk_params_json:
            try:
                data = json.loads(self.chunk_params_json)
                if isinstance(data, dict):
                    return int(data.get("chunk_count", 0))
            except Exception:
                pass
        return len(self.chunks) if self.chunks else 0

    def __repr__(self) -> str:
        return f"<EmbeddingIndex id={self.id} workspace_id={self.workspace_id} v={self.version} status={self.status}>"


class IndexChunk(Base):
    __tablename__ = "index_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    index_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("embedding_indexes.id", ondelete="CASCADE"),
        nullable=False,
    )
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    faiss_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, nullable=False)

    __table_args__ = (
        UniqueConstraint("index_id", "chunk_id", name="uq_index_chunks_index_chunk"),
        UniqueConstraint("index_id", "faiss_id", name="uq_index_chunks_index_faiss_id"),
        Index("idx_index_chunks_index", "index_id"),
        Index("idx_index_chunks_paper", "paper_id"),
        Index("idx_index_chunks_run", "run_id"),
        Index("idx_index_chunks_chunk", "chunk_id"),
        Index("idx_index_chunks_index_paper", "index_id", "paper_id"),
        CheckConstraint("faiss_id >= 0", name="ck_index_chunks_faiss_id"),
    )

    index: Mapped["EmbeddingIndex"] = relationship("EmbeddingIndex", back_populates="chunks")
    paper: Mapped["Paper"] = relationship("Paper")
    chunk: Mapped["Chunk"] = relationship("Chunk")

    def __repr__(self) -> str:
        return f"<IndexChunk id={self.id} index_id={self.index_id} chunk_id={self.chunk_id} faiss_id={self.faiss_id}>"
