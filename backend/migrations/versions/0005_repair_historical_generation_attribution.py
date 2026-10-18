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

        # If published_run_id or pages was attributed to a failed job when a successful job existed:
        if p_pub != real_pub_run:
            conn.execute(
                sa.text("UPDATE papers SET published_run_id = :pub WHERE id = :pid"),
                {"pub": real_pub_run, "pid": p_id},
            )

        # Check if pages are attached to a run that differs from real_pub_run
        conn.execute(
            sa.text("UPDATE pages SET run_id = :pub WHERE paper_id = :pid AND (run_id IS NULL OR run_id != :pub)"),
            {"pub": real_pub_run, "pid": p_id},
        )

        if expected_cur != p_cur:
            conn.execute(
                sa.text("UPDATE papers SET current_run_id = :cur WHERE id = :pid"),
                {"cur": expected_cur, "pid": p_id},
            )


def downgrade() -> None:
    pass
