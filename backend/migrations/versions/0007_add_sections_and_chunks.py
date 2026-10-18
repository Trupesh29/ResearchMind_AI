"""add_sections_and_chunks

Revision ID: 0007_add_sections_and_chunks
Revises: 0006_preserve_multirun_page_generations
Create Date: 2026-10-18 21:00:00.000000

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_sections_and_chunks"
down_revision: str | None = "0006_preserve_multirun_page_generations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def upgrade() -> None:
    # 1. Create sections table
    op.create_table(
        "sections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=100), server_default="unknown", nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("block_ids_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "run_id", "section_index", name="uq_sections_paper_run_index"),
        sa.CheckConstraint("section_index >= 0", name="ck_sections_section_index"),
        sa.CheckConstraint("page_start >= 1 AND page_end >= page_start", name="ck_sections_page_range"),
    )
    op.create_index("ix_sections_paper_id", "sections", ["paper_id"], unique=False)
    op.create_index("ix_sections_run_id", "sections", ["run_id"], unique=False)
    op.create_index("idx_sections_paper_run", "sections", ["paper_id", "run_id"], unique=False)

    # 2. Create chunks table
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=100), server_default="unknown", nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("block_ids_json", sa.Text(), nullable=True),
        sa.Column("is_excluded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_index_id", sa.String(length=36), nullable=True),
        sa.Column("faiss_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokenizer_name", sa.String(length=255), nullable=True),
        sa.Column("tokenizer_revision", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "run_id", "chunk_index", name="uq_chunks_paper_run_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index"),
        sa.CheckConstraint("page_start >= 1 AND page_end >= page_start", name="ck_chunks_page_range"),
        sa.CheckConstraint("token_count > 0", name="ck_chunks_token_count"),
    )
    op.create_index("ix_chunks_paper_id", "chunks", ["paper_id"], unique=False)
    op.create_index("ix_chunks_run_id", "chunks", ["run_id"], unique=False)
    op.create_index("idx_chunks_paper_run", "chunks", ["paper_id", "run_id"], unique=False)
    op.create_index("idx_chunks_paper_section", "chunks", ["paper_id", "section"], unique=False)

    # 3. Data transition: Advance already-extracted Phase 3 papers into sectioning without duplicate jobs or re-extracting PDF
    conn = op.get_bind()
    papers = conn.execute(sa.text("SELECT id, status, current_run_id, published_run_id FROM papers")).fetchall()

    now = utcnow_iso()
    for row in papers:
        p_id = row[0]
        p_cur = row[2]
        p_pub = row[3]
        target_run = p_cur or p_pub
        if not target_run:
            continue

        # Check if pages exist for target_run
        has_pages = (
            conn.execute(
                sa.text("SELECT 1 FROM pages WHERE paper_id = :pid AND run_id = :rid LIMIT 1"),
                {"pid": p_id, "rid": target_run},
            ).fetchone()
            is not None
        )

        if not has_pages:
            continue

        # Check if active job already exists
        active_job = (
            conn.execute(
                sa.text(
                    "SELECT 1 FROM processing_jobs WHERE paper_id = :pid AND status IN ('queued', 'running') LIMIT 1"
                ),
                {"pid": p_id},
            ).fetchone()
            is not None
        )

        if active_job:
            continue

        # Check if sectioning or chunking already recorded
        has_sec_or_chk = (
            conn.execute(
                sa.text(
                    "SELECT 1 FROM processing_jobs WHERE paper_id = :pid AND run_id = :rid AND stage IN ('sectioning', 'chunking') LIMIT 1"
                ),
                {"pid": p_id, "rid": target_run},
            ).fetchone()
            is not None
        )

        if not has_sec_or_chk:
            # Enqueue sectioning job
            conn.execute(
                sa.text(
                    "INSERT INTO processing_jobs (id, paper_id, run_id, stage, status, attempt, created_at) "
                    "VALUES (:jid, :pid, :rid, 'sectioning', 'queued', 1, :now)"
                ),
                {"jid": str(uuid.uuid4()), "pid": p_id, "rid": target_run, "now": now},
            )


def downgrade() -> None:
    op.drop_index("idx_chunks_paper_section", table_name="chunks")
    op.drop_index("idx_chunks_paper_run", table_name="chunks")
    op.drop_index("ix_chunks_run_id", table_name="chunks")
    op.drop_index("ix_chunks_paper_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("idx_sections_paper_run", table_name="sections")
    op.drop_index("ix_sections_run_id", table_name="sections")
    op.drop_index("ix_sections_paper_id", table_name="sections")
    op.drop_table("sections")
