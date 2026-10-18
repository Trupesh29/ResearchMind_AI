"""Disposable historical-generation and overlay diagnostics for 3c7743d."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile

import fitz
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from backend.app.services.extraction_service import extract_pdf
from backend.app.services.processing_service import get_paper_pages

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    database = Path(temporary) / "migration.db"
    url = "sqlite:///" + database.as_posix()
    config = Config(str(root / "backend/alembic.ini"))
    config.set_main_option("script_location", str(root / "backend/migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0003_add_processing_jobs_and_pages")
    engine = sa.create_engine(url)
    tables = sa.MetaData()
    tables.reflect(engine)
    old_time = "2026-01-01T00:00:00+00:00"
    new_time = "2026-02-01T00:00:00+00:00"
    with engine.begin() as conn:
        conn.execute(
            tables.tables["users"].insert(),
            dict(id="u", email="probe@example.test", password_hash="unused", created_at=old_time),
        )
        conn.execute(tables.tables["workspaces"].insert(), dict(id="w", user_id="u", name="Probe", created_at=old_time))
        conn.execute(
            tables.tables["papers"].insert(),
            dict(
                id="p",
                workspace_id="w",
                original_filename="probe.pdf",
                storage_path="probe.pdf",
                sha256="a" * 64,
                size_bytes=10,
                status="failed",
                created_at=old_time,
                updated_at=new_time,
            ),
        )
        conn.execute(
            tables.tables["processing_jobs"].insert(),
            [
                dict(
                    id="old",
                    paper_id="p",
                    run_id="run-old",
                    stage="extracting",
                    status="succeeded",
                    attempt=1,
                    created_at=old_time,
                ),
                dict(
                    id="new",
                    paper_id="p",
                    run_id="run-new",
                    stage="extracting",
                    status="failed",
                    attempt=1,
                    created_at=new_time,
                ),
            ],
        )
        conn.execute(
            tables.tables["pages"].insert(),
            dict(
                id="page",
                paper_id="p",
                page_number=1,
                char_count=19,
                extraction_status="ok",
                flags_json="[]",
                raw_text="Old generation text",
                created_at=old_time,
            ),
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        print(
            "BACKFILLED_GENERATIONS",
            tuple(conn.execute(sa.text("SELECT current_run_id, published_run_id FROM papers WHERE id='p'")).one()),
        )
        print("PAGE_ASSIGNED_RUN", conn.execute(sa.text("SELECT run_id FROM pages WHERE id='page'")).scalar())
    with sessionmaker(bind=engine)() as session:
        result = get_paper_pages(session, "u", "p")
        print("RETAINED_OLD_PAGES_IS_STALE", result.is_stale)
    engine.dispose()

out = root / "artifacts/review_phase3_geometry"
out.mkdir(parents=True, exist_ok=True)
pdf = out / "rotation90.pdf"
with fitz.open() as document:
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 700), "Rotated page test 90")
    page.set_rotation(90)
    document.save(pdf)
result = extract_pdf(str(pdf))
with fitz.open(pdf) as document:
    page = document[0]
    shape = page.new_shape()
    for block in result.pages[0].blocks:
        # Convert visual coordinates back through page.derotation_matrix for PDF shape drawing
        shape.draw_rect(fitz.Rect(block.bbox) * page.derotation_matrix)
    shape.finish(color=(1, 0, 0), width=1.5)
    shape.commit()
    page.get_pixmap().save(out / "test_overlay_rotation90.png")
print("OVERLAY", out / "test_overlay_rotation90.png")
