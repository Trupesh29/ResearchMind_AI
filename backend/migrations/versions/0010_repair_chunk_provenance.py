"""repair_chunk_provenance

Revision ID: 0010_repair_chunk_provenance
Revises: 0009_repair_block_spans_and_chunks
Create Date: 2026-10-19 19:30:00.000000

"""

import json
import logging
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision: str = "0010_repair_chunk_provenance"
down_revision: str | None = "0009_repair_block_spans_and_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Load reconstructed section spans from 0009
    sections = conn.execute(
        sa.text(
            "SELECT id, paper_id, run_id, section, text, page_start, page_end, block_spans_json "
            "FROM sections WHERE block_spans_json IS NOT NULL"
        )
    ).fetchall()

    # Map (paper_id, run_id, section_name) -> list of (sec_id, sec_text, rec_spans, p_start, p_end)
    section_lookup: dict[tuple[str, str, str], list] = {}
    for row in sections:
        sec_id = row[0]
        paper_id = row[1]
        run_id = row[2]
        sec_name = row[3]
        sec_text = row[4] or ""
        p_start = row[5]
        p_end = row[6]
        spans_raw = row[7]

        try:
            rec_spans = json.loads(spans_raw) if spans_raw else []
        except Exception as err:
            logger.warning("Invalid block_spans_json in section %s: %s", sec_id, err)
            rec_spans = []

        if rec_spans and sec_text:
            key = (paper_id, run_id, sec_name)
            section_lookup.setdefault(key, []).append((sec_id, sec_text, rec_spans, p_start, p_end))

    # 2. Historical chunk reconciliation (M1):
    # - Validate exact text/offset correspondence before preserving existing references.
    # - Preserve valid repeated occurrences with real text evidence.
    # - If existing block IDs are unrelated or unproven, repair unique matches in reconstructable sections.
    # - Mark unresolved ambiguity (missing sections, multi-occurrence ambiguity, unresolvable references) honestly as NULL.
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
        logger.error("Failed during chunk provenance repair: %s", err, exc_info=True)
        raise


def downgrade() -> None:
    pass
