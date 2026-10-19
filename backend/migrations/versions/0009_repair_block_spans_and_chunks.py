"""repair_block_spans_and_chunks

Revision ID: 0009_repair_block_spans_and_chunks
Revises: 0008_add_block_spans_to_sections
Create Date: 2026-10-19 14:00:00.000000

"""

import json
import logging
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision: str = "0009_repair_block_spans_and_chunks"
down_revision: str | None = "0008_add_block_spans_to_sections"
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

        sep_offset = search_offset
        while sep_offset < len(sec_text) and sec_text[sep_offset] in ("\n", "\r", " ", "\t"):
            sep_offset += 1

        if sec_text[sep_offset : sep_offset + len(cleaned_b_text)] == cleaned_b_text:
            s_c = sep_offset
            e_c = s_c + len(cleaned_b_text)
        else:
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
    conn = op.get_bind()

    # 1. Forward repair for section spans:
    # Re-reconcile all sections where block_ids_json is not null to ensure character spans
    # reflect exact dehyphenated endpoints and never exceed cleaned text length.
    sections = conn.execute(
        sa.text(
            "SELECT id, paper_id, run_id, section, text, block_ids_json, page_start, page_end, block_spans_json "
            "FROM sections WHERE block_ids_json IS NOT NULL"
        )
    ).fetchall()

    # Cache section reconstructed spans by sec_id
    section_spans_map: dict[str, list[list]] = {}
    # Map (paper_id, run_id, section_name) -> list of (sec_id, sec_text, reconstructed_spans, p_start, p_end)
    section_lookup: dict[tuple[str, str, str], list] = {}

    for row in sections:
        sec_id = row[0]
        paper_id = row[1]
        run_id = row[2]
        sec_name = row[3]
        sec_text = row[4] or ""
        block_ids_raw = row[5]
        p_start = row[6]
        p_end = row[7]
        existing_spans_raw = row[8]

        try:
            target_block_ids = json.loads(block_ids_raw) if block_ids_raw else []
        except Exception as err:
            logger.warning("Invalid block_ids_json in section %s: %s", sec_id, err)
            target_block_ids = []

        if not target_block_ids or not sec_text:
            if existing_spans_raw is not None:
                conn.execute(
                    sa.text("UPDATE sections SET block_spans_json = NULL WHERE id = :id"),
                    {"id": sec_id},
                )
            continue

        pages = conn.execute(
            sa.text(
                "SELECT page_number, blocks_json FROM pages "
                "WHERE paper_id = :pid AND run_id = :rid AND page_number >= :p_start AND page_number <= :p_end "
                "ORDER BY page_number ASC"
            ),
            {"pid": paper_id, "rid": run_id, "p_start": p_start, "p_end": p_end},
        ).fetchall()

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
            except Exception as err:
                logger.warning("Error reading page blocks for section %s: %s", sec_id, err)
                continue

        reconstructed_spans = reconcile_section_spans(sec_text, target_block_ids, page_blocks)

        if reconstructed_spans:
            section_spans_map[sec_id] = reconstructed_spans
            key = (paper_id, run_id, sec_name)
            section_lookup.setdefault(key, []).append((sec_id, sec_text, reconstructed_spans, p_start, p_end))
            conn.execute(
                sa.text("UPDATE sections SET block_spans_json = :spans WHERE id = :id"),
                {"spans": json.dumps(reconstructed_spans), "id": sec_id},
            )
        else:
            # Explicit None when exact reconciliation is impossible
            conn.execute(
                sa.text("UPDATE sections SET block_spans_json = NULL WHERE id = :id"),
                {"id": sec_id},
            )

    # 2. Historical chunk reconciliation (L2):
    # - NEVER infer chunk occurrence using first matching text or section label alone.
    # - If chunk has proven block identity in block_ids_json that exists in reconstructed section spans, PRESERVE IT!
    # - If chunk block_ids_json is missing/obsolete, ONLY reconcile if text occurrence is UNIQUE (count == 1)
    #   and section is unambiguous. If ambiguous (count > 1 or multiple sections), mark unresolved (NULL).
    try:
        chunks = conn.execute(
            sa.text(
                "SELECT id, paper_id, run_id, chunk_index, page_start, page_end, section, text, block_ids_json "
                "FROM chunks"
            )
        ).fetchall()

        for ch in chunks:
            ch_id = ch[0]
            paper_id = ch[1]
            run_id = ch[2]
            ch_sec_name = ch[6]
            ch_text = ch[7] or ""
            ch_bids_raw = ch[8]

            try:
                existing_bids = json.loads(ch_bids_raw) if ch_bids_raw else []
            except Exception as err:
                logger.warning("Invalid block_ids_json for chunk %s: %s", ch_id, err)
                existing_bids = []

            key = (paper_id, run_id, ch_sec_name)
            matching_sections = section_lookup.get(key, [])

            if not matching_sections or not ch_text:
                # Without reconstructable section or chunk text, provenance cannot be verified
                if existing_bids:
                    conn.execute(
                        sa.text("UPDATE chunks SET block_ids_json = NULL WHERE id = :cid"),
                        {"cid": ch_id},
                    )
                continue

            # Gather all candidate text occurrences across matching sections
            candidate_occurrences = []
            for sec_id, sec_text, rec_spans, p_start, p_end in matching_sections:
                if not sec_text:
                    continue
                matches = list(re.finditer(re.escape(ch_text), sec_text))
                if not matches and ch_text.strip() and ch_text.strip() != ch_text:
                    matches = list(re.finditer(re.escape(ch_text.strip()), sec_text))

                for m in matches:
                    occ_start = m.start()
                    occ_end = m.end()
                    occ_blocks = []
                    occ_pages = []
                    for b_id, p_num, b_s, b_e in rec_spans:
                        if max(occ_start, b_s) < min(occ_end, b_e):
                            occ_blocks.append(b_id)
                            occ_pages.append(p_num)
                    if occ_blocks and occ_pages:
                        distinct_blocks = list(dict.fromkeys(occ_blocks))
                        candidate_occurrences.append((sec_id, occ_start, distinct_blocks, occ_pages))

            # 1. Proven correspondence: check if existing_bids matches any candidate occurrence exactly
            proven_candidate = None
            if existing_bids:
                for cand in candidate_occurrences:
                    _, _, distinct_blocks, _ = cand
                    if existing_bids == distinct_blocks:
                        proven_candidate = cand
                        break

            if proven_candidate is not None:
                # Real text correspondence verified; preserve existing blocks and update page bounds
                _, _, _, occ_pages = proven_candidate
                conn.execute(
                    sa.text("UPDATE chunks SET page_start = :ps, page_end = :pe WHERE id = :cid"),
                    {"ps": min(occ_pages), "pe": max(occ_pages), "cid": ch_id},
                )
                continue

            # 2. Unique demonstrable match: repair if chunk appears exactly once across matching sections
            if len(candidate_occurrences) == 1:
                sec_id, occ_start, distinct_blocks, occ_pages = candidate_occurrences[0]
                conn.execute(
                    sa.text(
                        "UPDATE chunks SET block_ids_json = :bids, page_start = :ps, page_end = :pe WHERE id = :cid"
                    ),
                    {
                        "bids": json.dumps(distinct_blocks),
                        "ps": min(occ_pages),
                        "pe": max(occ_pages),
                        "cid": ch_id,
                    },
                )
                continue

            # 3. Unresolved ambiguity or missing correspondence: mark block_ids_json NULL
            if existing_bids:
                conn.execute(
                    sa.text("UPDATE chunks SET block_ids_json = NULL WHERE id = :cid"),
                    {"cid": ch_id},
                )
    except Exception as err:
        logger.error("Failed during historical chunk reconciliation: %s", err, exc_info=True)
        raise


def downgrade() -> None:
    pass
