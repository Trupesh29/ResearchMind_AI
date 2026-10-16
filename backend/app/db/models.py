import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
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

    def __repr__(self) -> str:
        return f"<Paper id={self.id} filename={self.original_filename} status={self.status}>"
