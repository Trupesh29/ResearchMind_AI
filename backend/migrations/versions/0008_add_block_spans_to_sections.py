"""add_block_spans_to_sections

Revision ID: 0008_add_block_spans_to_sections
Revises: 0007_add_sections_and_chunks
Create Date: 2026-10-19 01:00:00.000000

"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_block_spans_to_sections"
down_revision: str | None = "0007_add_sections_and_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def dehyphenate_text(text: str) -> str:
    """Line-wrap dehyphenation matching sectioning_service."""
    if not text:
        return text
    return re.sub(r"(\b[A-Za-z]+)-\s*\n\s*([a-z]+)", r"\1\2", text)


def reconcile_section_spans(
    sec_text: str,
    target_block_ids: list[str],
    page_blocks: dict[str, tuple[int, str]],
) -> list[list] | None:
    """Exact reconciliation of raw page blocks to cleaned section text.

    Returns list of [block_id, page_number, start_char, end_char] with exact equality,
    or None if exact full-text correspondence cannot be established. Never guesses.
    """
    if not target_block_ids or not sec_text:
        return None

    reconstructed_spans: list[list] = []
    search_offset = 0

    for b_id in target_block_ids:
        if b_id not in page_blocks:
            return None
        p_num, raw_b_text = page_blocks[b_id]
        if not raw_b_text:
            continue

        cleaned_b_text = dehyphenate_text(raw_b_text)
        if not cleaned_b_text:
            continue

        # Look for cleaned_b_text starting from search_offset
        # First check right after any whitespace/newlines
        sep_offset = search_offset
        while sep_offset < len(sec_text) and sec_text[sep_offset] in ("\n", "\r", " ", "\t"):
            sep_offset += 1

        if sec_text[sep_offset : sep_offset + len(cleaned_b_text)] == cleaned_b_text:
            s_c = sep_offset
            e_c = s_c + len(cleaned_b_text)
        else:
            # Strict forward find from search_offset
            idx = sec_text.find(cleaned_b_text, search_offset)
            if idx == -1:
                return None
            s_c = idx
            e_c = s_c + len(cleaned_b_text)

        # Validate bounds and text identity strictly
        if s_c < 0 or e_c > len(sec_text) or s_c >= e_c:
            return None
        if sec_text[s_c:e_c] != cleaned_b_text:
            return None

        reconstructed_spans.append([b_id, p_num, s_c, e_c])
        search_offset = e_c

    # Validate complete sequence: non-empty and monotonically non-overlapping
    if not reconstructed_spans:
        return None

    for i in range(len(reconstructed_spans)):
        b_id, p_num, s_c, e_c = reconstructed_spans[i]
        if s_c >= e_c or e_c > len(sec_text):
            return None
        if i > 0 and s_c < reconstructed_spans[i - 1][3]:
            return None

    return reconstructed_spans


def upgrade() -> None:
    # 1. Add block_spans_json column to sections table using batch alter for SQLite compatibility
    with op.batch_alter_table("sections") as batch_op:
        batch_op.add_column(sa.Column("block_spans_json", sa.Text(), nullable=True))

    # 2. Forward data-preserving reconciliation: reconstruct exact block_spans_json
    # for existing section records where raw page blocks are available in the pages table
    conn = op.get_bind()
    sections = conn.execute(
        sa.text(
            "SELECT id, paper_id, run_id, section, text, block_ids_json, page_start, page_end "
            "FROM sections WHERE block_ids_json IS NOT NULL"
        )
    ).fetchall()

    for row in sections:
        sec_id = row[0]
        paper_id = row[1]
        run_id = row[2]
        sec_name = row[3]
        sec_text = row[4] or ""
        block_ids_raw = row[5]
        p_start = row[6]
        p_end = row[7]

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

        reconstructed_spans = reconcile_section_spans(sec_text, target_block_ids, page_blocks)

        if reconstructed_spans:
            conn.execute(
                sa.text("UPDATE sections SET block_spans_json = :spans WHERE id = :id"),
                {"spans": json.dumps(reconstructed_spans), "id": sec_id},
            )

            # Forward repair for historical chunks associated with this section:
            # If chunks exist and their text matches within sec_text, update block_ids_json and page bounds
            # with exact reconciled provenance. Historical chunks that cannot be resolved remain intact.
            try:
                chunks = conn.execute(
                    sa.text(
                        "SELECT id, text FROM chunks WHERE paper_id = :pid AND run_id = :rid AND section = :sec_name"
                    ),
                    {"pid": paper_id, "rid": run_id, "sec_name": sec_name},
                ).fetchall()

                for ch_row in chunks:
                    ch_id, ch_text = ch_row[0], ch_row[1]
                    if not ch_text:
                        continue
                    ch_idx = sec_text.find(ch_text)
                    if ch_idx != -1:
                        ch_start = ch_idx
                        ch_end = ch_idx + len(ch_text)
                        overlapping_blocks = []
                        overlapping_pages = []
                        for b_id, p_num, b_s, b_e in reconstructed_spans:
                            if max(ch_start, b_s) < min(ch_end, b_e):
                                overlapping_blocks.append(b_id)
                                overlapping_pages.append(p_num)
                        if overlapping_blocks and overlapping_pages:
                            distinct_blocks = list(dict.fromkeys(overlapping_blocks))
                            conn.execute(
                                sa.text(
                                    "UPDATE chunks SET block_ids_json = :bids, page_start = :p_start, page_end = :p_end "
                                    "WHERE id = :cid"
                                ),
                                {
                                    "bids": json.dumps(distinct_blocks),
                                    "p_start": min(overlapping_pages),
                                    "p_end": max(overlapping_pages),
                                    "cid": ch_id,
                                },
                            )
            except Exception:
                # Chunks table may be unpopulated in tests or historical databases; preserve safety
                pass


def downgrade() -> None:
    with op.batch_alter_table("sections") as batch_op:
        batch_op.drop_column("block_spans_json")
