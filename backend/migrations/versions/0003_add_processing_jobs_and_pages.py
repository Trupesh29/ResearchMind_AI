"""add_processing_jobs_and_pages

Revision ID: 0003_add_processing_jobs_and_pages
Revises: 0002_add_paper_check_constraints
Create Date: 2026-10-17 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_processing_jobs_and_pages"
down_revision: str | None = "0002_add_paper_check_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update papers table with generation tracking
    op.add_column("papers", sa.Column("current_run_id", sa.String(length=36), nullable=True))
    op.add_column("papers", sa.Column("published_run_id", sa.String(length=36), nullable=True))

    # 2. processing_jobs table
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("claim_token", sa.String(length=36), nullable=True),
        sa.Column("claimed_at", sa.String(length=32), nullable=True),
        sa.Column("heartbeat_at", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(length=32), nullable=True),
        sa.Column("finished_at", sa.String(length=32), nullable=True),
        sa.Column("versions_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint(
            "stage IN ('validating', 'extracting', 'sectioning', 'chunking', 'embedding', 'indexing', 'ready')",
            name="ck_jobs_stage",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_jobs_attempt"),
    )
    op.create_index("ix_processing_jobs_paper_id", "processing_jobs", ["paper_id"], unique=False)
    op.create_index("ix_processing_jobs_run_id", "processing_jobs", ["run_id"], unique=False)
    op.create_index("idx_jobs_paper_run", "processing_jobs", ["paper_id", "run_id"], unique=False)
    op.create_index("idx_jobs_status_stage", "processing_jobs", ["status", "stage"], unique=False)
    op.create_index("idx_jobs_heartbeat", "processing_jobs", ["status", "heartbeat_at"], unique=False)
    op.create_index(
        "uq_active_job_per_paper",
        "processing_jobs",
        ["paper_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )

    # 3. pages table
    op.create_table(
        "pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("rotation", sa.Integer(), nullable=True),
        sa.Column("extraction_status", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("flags_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("blocks_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "run_id", "page_number", name="uq_pages_paper_run_page"),
        sa.CheckConstraint("page_number >= 1", name="ck_pages_page_number"),
        sa.CheckConstraint("char_count >= 0", name="ck_pages_char_count"),
        sa.CheckConstraint(
            "extraction_status IN ('ok', 'partial', 'failed')",
            name="ck_pages_extraction_status",
        ),
    )
    op.create_index("ix_pages_paper_id", "pages", ["paper_id"], unique=False)
    op.create_index("ix_pages_run_id", "pages", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pages_run_id", table_name="pages")
    op.drop_index("ix_pages_paper_id", table_name="pages")
    op.drop_table("pages")

    op.drop_index("uq_active_job_per_paper", table_name="processing_jobs")
    op.drop_index("idx_jobs_heartbeat", table_name="processing_jobs")
    op.drop_index("idx_jobs_status_stage", table_name="processing_jobs")
    op.drop_index("idx_jobs_paper_run", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_run_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_paper_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    with op.batch_alter_table("papers") as batch_op:
        batch_op.drop_column("published_run_id")
        batch_op.drop_column("current_run_id")
