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
        UniqueConstraint("paper_id", "page_number", name="uq_pages_paper_page_number"),
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
