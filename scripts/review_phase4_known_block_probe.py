"""Show that migration preserves a known block ID unrelated to chunk text."""

import json
import tempfile
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    cfg = Config(str(root / "backend/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "backend/migrations"))
    url = "sqlite:///" + (Path(temporary) / "probe.db").as_posix()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0007_add_sections_and_chunks")
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    metadata.reflect(engine)
    stamp = "2026-10-19T00:00:00+00:00"
    raw = "Repeated evidence."
    cleaned = raw + "\nOther unrelated evidence."
    with engine.begin() as conn:
        conn.execute(
            metadata.tables["users"].insert(), dict(id="u", email="probe@test.org", password_hash="x", created_at=stamp)
        )
        conn.execute(metadata.tables["workspaces"].insert(), dict(id="w", user_id="u", name="Probe", created_at=stamp))
        conn.execute(
            metadata.tables["papers"].insert(),
            dict(
                id="p",
                workspace_id="w",
                original_filename="p.pdf",
                storage_path="p.pdf",
                sha256="a" * 64,
                size_bytes=10,
                status="processing",
                created_at=stamp,
                updated_at=stamp,
                current_run_id="r",
                published_run_id="r",
            ),
        )
        conn.execute(
            metadata.tables["pages"].insert(),
            dict(
                id="pg",
                paper_id="p",
                run_id="r",
                page_number=1,
                char_count=len(raw),
                extraction_status="ok",
                flags_json="[]",
                raw_text=raw,
                blocks_json=json.dumps([{"id": "b", "text": raw}, {"id": "c", "text": "Other unrelated evidence."}]),
                created_at=stamp,
            ),
        )
        conn.execute(
            metadata.tables["sections"].insert(),
            dict(
                id="s",
                paper_id="p",
                run_id="r",
                section_index=0,
                section="unknown",
                page_start=1,
                page_end=1,
                text=cleaned,
                block_ids_json='["b","c"]',
                created_at=stamp,
            ),
        )
    with engine.begin() as conn:
        conn.execute(
            metadata.tables["chunks"].insert(),
            dict(
                id="ch",
                paper_id="p",
                run_id="r",
                chunk_index=1,
                section="unknown",
                text=raw,
                page_start=1,
                page_end=1,
                token_count=5,
                block_ids_json='["c"]',
                is_excluded=0,
                tokenizer_name="test",
                tokenizer_revision="test",
                created_at=stamp,
            ),
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        spans = json.loads(conn.execute(sa.text("SELECT block_spans_json FROM sections WHERE id='s'")).scalar())
        print("CLEANED_TEXT_LENGTH", len(cleaned))
        print("MIGRATED_SPANS", spans)
        print("SPAN_EXCEEDS_TEXT", spans[0][3] > len(cleaned))
    with engine.connect() as conn:
        print(
            "UNRELATED_BLOCK_RETAINED",
            conn.execute(sa.text("SELECT block_ids_json FROM chunks WHERE id='ch'")).scalar(),
        )
    engine.dispose()
