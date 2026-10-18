"""add_block_spans_to_sections

Revision ID: 0008_add_block_spans_to_sections
Revises: 0007_add_sections_and_chunks
Create Date: 2026-10-19 01:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_block_spans_to_sections"
down_revision: str | None = "0007_add_sections_and_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add block_spans_json column to sections table using batch alter for SQLite compatibility
    with op.batch_alter_table("sections") as batch_op:
        batch_op.add_column(sa.Column("block_spans_json", sa.Text(), nullable=True))

    # 2. Forward data-preserving reconciliation: reconstruct exact block_spans_json
    # for existing section records where raw page blocks are available in the pages table
    conn = op.get_bind()
    sections = conn.execute(
        sa.text(
            "SELECT id, paper_id, run_id, text, block_ids_json, page_start, page_end "
            "FROM sections WHERE block_ids_json IS NOT NULL"
        )
    ).fetchall()

    for row in sections:
        sec_id = row[0]
        paper_id = row[1]
        run_id = row[2]
        sec_text = row[3] or ""
        block_ids_raw = row[4]
        p_start = row[5]
        p_end = row[6]

        try:
            target_block_ids = json.loads(block_ids_raw) if block_ids_raw else []
        except Exception:
            target_block_ids = []

        if not target_block_ids or not sec_text:
            continue

        # Fetch pages for this paper and run
        pages = conn.execute(
            sa.text(
                "SELECT page_number, blocks_json FROM pages "
                "WHERE paper_id = :pid AND run_id = :rid AND page_number >= :p_start AND page_number <= :p_end "
                "ORDER BY page_number ASC"
            ),
            {"pid": paper_id, "rid": run_id, "p_start": p_start, "p_end": p_end},
        ).fetchall()

        # Build map of block_id -> (page_num, text)
        page_blocks: dict[str, tuple[int, str]] = {}
        for p_row in pages:
            p_num = p_row[0]
            b_json = p_row[1]
            if not b_json:
                continue
            try:
                b_list = json.loads(b_json)
                for b in b_list:
                    b_id = b.get("id")
                    if b_id and b_id in target_block_ids:
                        page_blocks[b_id] = (p_num, b.get("text", "").strip())
            except Exception:
                continue

        # Reconstruct exact spans by matching block texts within section text in order
        reconstructed_spans: list[list] = []
        search_offset = 0
        all_matched = True

        for b_id in target_block_ids:
            if b_id not in page_blocks:
                all_matched = False
                break
            p_num, b_text = page_blocks[b_id]
            if not b_text:
                continue
            idx = sec_text.find(b_text, search_offset)
            if idx == -1:
                # Try finding without dehyphenation or substring
                idx = sec_text.find(b_text[: min(len(b_text), 30)], search_offset)
            if idx != -1:
                s_c = idx
                e_c = idx + len(b_text)
                reconstructed_spans.append([b_id, p_num, s_c, e_c])
                search_offset = e_c
            else:
                all_matched = False
                break

        if all_matched and reconstructed_spans:
            conn.execute(
                sa.text("UPDATE sections SET block_spans_json = :spans WHERE id = :id"),
                {"spans": json.dumps(reconstructed_spans), "id": sec_id},
            )


def downgrade() -> None:
    with op.batch_alter_table("sections") as batch_op:
        batch_op.drop_column("block_spans_json")
