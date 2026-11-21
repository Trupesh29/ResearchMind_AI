"""add_assistant_conversations_and_messages

Revision ID: 0012_add_assistant_conversations_and_messages
Revises: 0011_add_versioned_indexes_and_membership
Create Date: 2026-10-21 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_add_assistant_conversations_and_messages"
down_revision: str | None = "0011_add_versioned_indexes_and_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )
    op.create_index("idx_conversations_workspace", "conversations", ["workspace_id"])
    op.create_index("idx_conversations_updated_at", "conversations", ["updated_at"])

    # 2. Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("selected_paper_ids_json", sa.Text(), nullable=True),
        sa.Column("retrieved_passages_json", sa.Text(), nullable=True),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("is_abstention", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        sa.CheckConstraint("is_abstention IN (0, 1)", name="ck_messages_is_abstention"),
    )
    op.create_index("idx_messages_conversation", "messages", ["conversation_id"])
    op.create_index("idx_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
