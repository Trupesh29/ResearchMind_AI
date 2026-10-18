"""add_generation_and_fencing_controls

Revision ID: 0004_add_generation_and_fencing_controls
Revises: 0003_add_processing_jobs_and_pages
Create Date: 2026-10-18 12:00:00.000000

"""

import datetime
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_generation_and_fencing_controls"
down_revision: str | None = "0003_add_processing_jobs_and_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Update papers table with generation columns
    papers_cols = {c["name"] for c in inspector.get_columns("papers")}
    if "current_run_id" not in papers_cols:
        op.add_column("papers", sa.Column("current_run_id", sa.String(length=36), nullable=True))
    if "published_run_id" not in papers_cols:
        op.add_column("papers", sa.Column("published_run_id", sa.String(length=36), nullable=True))

    # 2. Update pages table with run_id column if missing
    pages_cols = {c["name"] for c in inspector.get_columns("pages")}
    if "run_id" not in pages_cols:
        op.add_column("pages", sa.Column("run_id", sa.String(length=36), nullable=True))

    # 3. Backfill paper generations and page run_ids
    papers = conn.execute(sa.text("SELECT id, status, current_run_id, published_run_id FROM papers")).fetchall()
    for row in papers:
        p_id = row[0]
        p_status = row[1]
        p_cur = row[2]
        p_pub = row[3]

        job_row = conn.execute(
            sa.text("SELECT run_id FROM processing_jobs WHERE paper_id = :pid ORDER BY created_at DESC LIMIT 1"),
            {"pid": p_id},
        ).fetchone()

        assigned_run = job_row[0] if job_row else str(uuid.uuid4())
        cur_run = p_cur or assigned_run
        pub_run = p_pub

        if pub_run is None:
            has_pages = conn.execute(
                sa.text("SELECT 1 FROM pages WHERE paper_id = :pid LIMIT 1"),
                {"pid": p_id},
            ).fetchone()
            if has_pages or p_status == "ready":
                pub_run = cur_run

        conn.execute(
            sa.text("UPDATE papers SET current_run_id = :cur, published_run_id = :pub WHERE id = :pid"),
            {"cur": cur_run, "pub": pub_run, "pid": p_id},
        )

        page_run = pub_run or cur_run
        conn.execute(
            sa.text("UPDATE pages SET run_id = :rid WHERE paper_id = :pid AND (run_id IS NULL OR run_id = '')"),
            {"rid": page_run, "pid": p_id},
        )

    # Any remaining orphan pages
    orphan_pages = conn.execute(sa.text("SELECT id FROM pages WHERE run_id IS NULL OR run_id = ''")).fetchall()
    for (pg_id,) in orphan_pages:
        conn.execute(
            sa.text("UPDATE pages SET run_id = :rid WHERE id = :pg_id"),
            {"rid": str(uuid.uuid4()), "pg_id": pg_id},
        )

    # 4. Enforce pages constraints and index
    inspector = sa.inspect(conn)
    page_uqs = {uq["name"] for uq in inspector.get_unique_constraints("pages")}
    with op.batch_alter_table("pages") as batch_op:
        if "uq_pages_paper_page_number" in page_uqs:
            batch_op.drop_constraint("uq_pages_paper_page_number", type_="unique")
        batch_op.alter_column("run_id", existing_type=sa.String(length=36), nullable=False)
        if "uq_pages_paper_run_page" not in page_uqs:
            batch_op.create_unique_constraint("uq_pages_paper_run_page", ["paper_id", "run_id", "page_number"])

    page_indexes = {idx["name"] for idx in inspector.get_indexes("pages")}
    if "ix_pages_run_id" not in page_indexes:
        op.create_index("ix_pages_run_id", "pages", ["run_id"], unique=False)

    # 5. Reconcile duplicate active processing jobs before enforcing uniqueness
    active_jobs = conn.execute(
        sa.text(
            """
            SELECT id, paper_id, created_at, attempt
            FROM processing_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY paper_id, created_at DESC, attempt DESC
            """
        )
    ).fetchall()

    seen_papers = set()
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for j_id, p_id, _c_at, _att in active_jobs:
        if p_id in seen_papers:
            # Reconcile duplicate active run
            conn.execute(
                sa.text(
                    """
                    UPDATE processing_jobs
                    SET status = 'failed',
                        finished_at = :now,
                        error_message = 'Worker processing superseded by newer generation or lease owner.'
                    WHERE id = :jid
                    """
                ),
                {"now": now_str, "jid": j_id},
            )
        else:
            seen_papers.add(p_id)

    # 6. Add partial unique index on processing_jobs
    job_indexes = {idx["name"] for idx in inspector.get_indexes("processing_jobs")}
    if "uq_active_job_per_paper" not in job_indexes:
        op.create_index(
            "uq_active_job_per_paper",
            "processing_jobs",
            ["paper_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('queued', 'running')"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    job_indexes = {idx["name"] for idx in inspector.get_indexes("processing_jobs")}
    if "uq_active_job_per_paper" in job_indexes:
        op.drop_index("uq_active_job_per_paper", table_name="processing_jobs")

    page_indexes = {idx["name"] for idx in inspector.get_indexes("pages")}
    if "ix_pages_run_id" in page_indexes:
        op.drop_index("ix_pages_run_id", table_name="pages")

    page_uqs = {uq["name"] for uq in inspector.get_unique_constraints("pages")}
    with op.batch_alter_table("pages") as batch_op:
        if "uq_pages_paper_run_page" in page_uqs:
            batch_op.drop_constraint("uq_pages_paper_run_page", type_="unique")
        batch_op.create_unique_constraint("uq_pages_paper_page_number", ["paper_id", "page_number"])
        batch_op.drop_column("run_id")

    with op.batch_alter_table("papers") as batch_op:
        batch_op.drop_column("published_run_id")
        batch_op.drop_column("current_run_id")
