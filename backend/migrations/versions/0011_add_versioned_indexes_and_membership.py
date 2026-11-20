"""add_versioned_indexes_and_membership

Revision ID: 0011_add_versioned_indexes_and_membership
Revises: 0010_repair_chunk_provenance
Create Date: 2026-10-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_add_versioned_indexes_and_membership"
down_revision: str | None = "0010_repair_chunk_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create embedding_indexes table
    op.create_table(
        "embedding_indexes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_revision", sa.String(length=64), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalization", sa.String(length=32), server_default="l2", nullable=False),
        sa.Column("chunk_params_json", sa.Text(), nullable=False),
        sa.Column("faiss_path", sa.String(length=500), nullable=True),
        sa.Column("bm25_path", sa.String(length=500), nullable=True),
        sa.Column("manifest_path", sa.String(length=500), nullable=True),
        sa.Column("index_checksums_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="building", nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("workspace_id", "version", name="uq_embedding_indexes_workspace_version"),
        sa.CheckConstraint(
            "status IN ('building', 'active', 'retired', 'failed')",
            name="ck_embedding_indexes_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_embedding_indexes_version"),
        sa.CheckConstraint("dimension > 0", name="ck_embedding_indexes_dimension"),
    )
    op.create_index("idx_embedding_indexes_workspace", "embedding_indexes", ["workspace_id"])
    op.create_index("idx_embedding_indexes_workspace_status", "embedding_indexes", ["workspace_id", "status"])
    op.create_index(
        "uq_embedding_active_per_workspace",
        "embedding_indexes",
        ["workspace_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )

    # 2. Create index_chunks table
    op.create_table(
        "index_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "index_id",
            sa.String(length=36),
            sa.ForeignKey("embedding_indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paper_id",
            sa.String(length=36),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "chunk_id",
            sa.String(length=36),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("faiss_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("index_id", "chunk_id", name="uq_index_chunks_index_chunk"),
        sa.UniqueConstraint("index_id", "faiss_id", name="uq_index_chunks_index_faiss_id"),
        sa.CheckConstraint("faiss_id >= 0", name="ck_index_chunks_faiss_id"),
    )
    op.create_index("idx_index_chunks_index", "index_chunks", ["index_id"])
    op.create_index("idx_index_chunks_paper", "index_chunks", ["paper_id"])
    op.create_index("idx_index_chunks_run", "index_chunks", ["run_id"])
    op.create_index("idx_index_chunks_chunk", "index_chunks", ["chunk_id"])
    op.create_index("idx_index_chunks_index_paper", "index_chunks", ["index_id", "paper_id"])


def downgrade() -> None:
    op.drop_table("index_chunks")
    op.drop_table("embedding_indexes")
