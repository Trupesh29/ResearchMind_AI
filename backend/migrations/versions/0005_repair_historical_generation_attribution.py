"""repair_historical_generation_attribution

Revision ID: 0005_repair_historical_generation_attribution
Revises: 0004_add_generation_and_fencing_controls
Create Date: 2026-10-18 16:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_repair_historical_generation_attribution"
down_revision: str | None = "0004_add_generation_and_fencing_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    papers = conn.execute(sa.text("SELECT id, status, current_run_id, published_run_id FROM papers")).fetchall()
    for row in papers:
        p_id = row[0]
        p_status = row[1]
        p_cur = row[2]
        p_pub = row[3]

        has_pages = (
            conn.execute(
                sa.text("SELECT 1 FROM pages WHERE paper_id = :pid LIMIT 1"),
                {"pid": p_id},
            ).fetchone()
            is not None
        )

        active_job = conn.execute(
            sa.text(
                "SELECT run_id FROM processing_jobs WHERE paper_id = :pid AND status IN ('queued', 'running') "
                "ORDER BY created_at DESC, attempt DESC LIMIT 1"
            ),
            {"pid": p_id},
        ).fetchone()

        latest_job = conn.execute(
            sa.text(
                "SELECT run_id FROM processing_jobs WHERE paper_id = :pid "
                "ORDER BY created_at DESC, attempt DESC LIMIT 1"
            ),
            {"pid": p_id},
        ).fetchone()

        expected_cur = p_cur
        if active_job:
            expected_cur = active_job[0]
        elif latest_job and not p_cur:
            expected_cur = latest_job[0]

        if not has_pages:
            if p_status != "ready" and p_pub is not None:
                conn.execute(
                    sa.text("UPDATE papers SET published_run_id = NULL WHERE id = :pid"),
                    {"pid": p_id},
                )
            if expected_cur != p_cur:
                conn.execute(
                    sa.text("UPDATE papers SET current_run_id = :cur WHERE id = :pid"),
                    {"cur": expected_cur, "pid": p_id},
                )
            continue

        # Pages exist: check if there was a successful extracting job
        succ_job = conn.execute(
            sa.text(
                "SELECT run_id FROM processing_jobs WHERE paper_id = :pid "
                "AND stage = 'extracting' AND status = 'succeeded' "
                "ORDER BY created_at DESC, attempt DESC LIMIT 1"
            ),
            {"pid": p_id},
        ).fetchone()

        # Find all valid successful extraction runs for this paper
        succ_runs_rows = conn.execute(
            sa.text(
                "SELECT DISTINCT run_id FROM processing_jobs WHERE paper_id = :pid "
                "AND stage = 'extracting' AND status = 'succeeded'"
            ),
            {"pid": p_id},
        ).fetchall()
        valid_succ_runs = {r[0] for r in succ_runs_rows if r[0]}

        if succ_job:
            real_pub_run = succ_job[0]
        else:
            # Ambiguous: check if published_run_id was mistakenly assigned to a failed or queued job
            is_bad_attribution = False
            if p_pub and latest_job and p_pub == latest_job[0]:
                bad_job = conn.execute(
                    sa.text(
                        "SELECT status FROM processing_jobs WHERE paper_id = :pid AND run_id = :rid "
                        "AND status IN ('failed', 'queued', 'running')"
                    ),
                    {"pid": p_id, "rid": p_pub},
                ).fetchone()
                if bad_job:
                    is_bad_attribution = True

            if is_bad_attribution:
                real_pub_run = f"legacy-{uuid.uuid4()}"
            else:
                real_pub_run = p_pub or f"legacy-{uuid.uuid4()}"

        # If published_run_id was attributed to a failed/running job when a successful job existed,
        # or was unassigned:
        if p_pub != real_pub_run:
            conn.execute(
                sa.text("UPDATE papers SET published_run_id = :pub WHERE id = :pid"),
                {"pub": real_pub_run, "pid": p_id},
            )

        # Inspect pages for this paper and preserve valid multi-generation page attribution:
        paper_pages = conn.execute(
            sa.text("SELECT id, page_number, run_id FROM pages WHERE paper_id = :pid ORDER BY page_number ASC"),
            {"pid": p_id},
        ).fetchall()

        existing_page_nums_in_pub_run = {pg[1] for pg in paper_pages if pg[2] == real_pub_run}

        for pg_id, pg_num, pg_run in paper_pages:
            # If the page already has a run_id belonging to a valid successful extraction run,
            # preserve it! Never collapse or relabel valid historical generations.
            if pg_run in valid_succ_runs:
                continue

            # If no successful extraction runs exist (ambiguous paper) and page is already
            # attached to real_pub_run, preserve it.
            if not valid_succ_runs and pg_run == real_pub_run:
                continue

            # Page has invalid or misattributed run_id (e.g. assigned to failed/queued/running job, or NULL).
            # Attempt to reassign to real_pub_run if no page with that number exists yet.
            if pg_num not in existing_page_nums_in_pub_run:
                conn.execute(
                    sa.text("UPDATE pages SET run_id = :pub WHERE id = :pg_id"),
                    {"pub": real_pub_run, "pg_id": pg_id},
                )
                existing_page_nums_in_pub_run.add(pg_num)
            else:
                # Collision: real_pub_run already has a page for this page_number!
                # Preserve the orphan/duplicate under an isolated legacy run ID to prevent constraint violation.
                orphan_legacy = f"legacy-{uuid.uuid4()}"
                conn.execute(
                    sa.text("UPDATE pages SET run_id = :rid WHERE id = :pg_id"),
                    {"rid": orphan_legacy, "pg_id": pg_id},
                )

        if expected_cur != p_cur:
            conn.execute(
                sa.text("UPDATE papers SET current_run_id = :cur WHERE id = :pid"),
                {"cur": expected_cur, "pid": p_id},
            )

    # Any remaining orphan pages across the database
    orphan_pages = conn.execute(sa.text("SELECT id FROM pages WHERE run_id IS NULL OR run_id = ''")).fetchall()
    for (pg_id,) in orphan_pages:
        conn.execute(
            sa.text("UPDATE pages SET run_id = :rid WHERE id = :pg_id"),
            {"rid": f"legacy-{uuid.uuid4()}", "pg_id": pg_id},
        )


def downgrade() -> None:
    pass
