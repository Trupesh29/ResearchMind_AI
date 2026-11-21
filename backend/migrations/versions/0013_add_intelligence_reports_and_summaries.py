"""add_intelligence_reports_and_summaries

Revision ID: 0013_add_intelligence_reports_and_summaries
Revises: 0012_add_assistant_conversations_and_messages
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_add_intelligence_reports_and_summaries"
down_revision: str | None = "0012_add_assistant_conversations_and_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create reports table
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary_style", sa.String(length=64), server_default="technical", nullable=False),
        sa.Column("paper_ids_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="completed", nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'generating', 'completed', 'failed')",
            name="ck_reports_status",
        ),
    )
    op.create_index("idx_reports_workspace", "reports", ["workspace_id"])
    op.create_index("idx_reports_created_at", "reports", ["created_at"])

    # 2. Create paper_summaries table
    op.create_table(
        "paper_summaries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "paper_id",
            sa.String(length=36),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("style", sa.String(length=32), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("paper_id", "style", name="uq_paper_summaries_paper_style"),
    )
    op.create_index("idx_paper_summaries_paper", "paper_summaries", ["paper_id"])


def downgrade() -> None:
    op.drop_index("idx_paper_summaries_paper", table_name="paper_summaries")
    op.drop_table("paper_summaries")
    op.drop_index("idx_reports_created_at", table_name="reports")
    op.drop_index("idx_reports_workspace", table_name="reports")
    op.drop_table("reports")
