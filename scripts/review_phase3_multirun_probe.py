"""Reproduce 0005 failure on retained pages from two successful generations."""

import tempfile
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    url = "sqlite:///" + (Path(temporary) / "probe.db").as_posix()
    cfg = Config(str(ROOT / "backend/alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0004_add_generation_and_fencing_controls")
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    metadata.reflect(engine)
    stamp = "2026-10-18T10:00:00+00:00"
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
                current_run_id="B",
                published_run_id="B",
            ),
        )
        for run, time in [("A", stamp), ("B", "2026-10-18T11:00:00+00:00")]:
            conn.execute(
                metadata.tables["processing_jobs"].insert(),
                dict(
                    id="job-" + run,
                    paper_id="p",
                    run_id=run,
                    stage="extracting",
                    status="succeeded",
                    attempt=1,
                    created_at=time,
                ),
            )
            conn.execute(
                metadata.tables["pages"].insert(),
                dict(
                    id="page-" + run,
                    paper_id="p",
                    run_id=run,
                    page_number=1,
                    char_count=1,
                    extraction_status="ok",
                    flags_json="[]",
                    raw_text=run,
                    created_at=time,
                ),
            )
    try:
        command.upgrade(cfg, "head")
    except sa.exc.IntegrityError as exc:
        print("MULTIRUN_UPGRADE_FAILED", str(exc.orig))
    else:
        print("MULTIRUN_UPGRADE_SUCCEEDED")
    with engine.connect() as conn:
        print("PAGES", conn.execute(sa.text("SELECT id, run_id, raw_text FROM pages ORDER BY id")).fetchall())
        print("REVISION", conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar())
    engine.dispose()
