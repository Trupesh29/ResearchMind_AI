"""add_paper_check_constraints

Revision ID: 0002_add_paper_check_constraints
Revises: 0001_initial_core_schema
Create Date: 2026-10-15 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_add_paper_check_constraints"
down_revision: str | None = "0001_initial_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("papers", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_papers_status",
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
        )
        batch_op.create_check_constraint(
            "ck_papers_size_bytes",
            "size_bytes > 0",
        )
        batch_op.create_check_constraint(
            "ck_papers_page_count",
            "page_count IS NULL OR page_count > 0",
        )
        batch_op.create_check_constraint(
            "ck_papers_publication_year",
            "publication_year IS NULL OR (publication_year >= 1900 AND publication_year <= 2100)",
        )


def downgrade() -> None:
    with op.batch_alter_table("papers", schema=None) as batch_op:
        batch_op.drop_constraint("ck_papers_publication_year", type_="check")
        batch_op.drop_constraint("ck_papers_page_count", type_="check")
        batch_op.drop_constraint("ck_papers_size_bytes", type_="check")
        batch_op.drop_constraint("ck_papers_status", type_="check")
