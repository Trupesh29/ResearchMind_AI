import io
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.errors import ErrorCode
from tests.backend.test_papers_api import create_minimal_pdf


def test_request_size_limit_middleware_bounds_content_length(client: TestClient):
    """Finding 2: Headers with Content-Length exceeding MAX_REQUEST_BODY_BYTES are rejected with 413."""
    ws_res = client.post("/api/workspaces", json={"name": "Size Limit WS"})
    ws_id = ws_res.json()["id"]

    # Provide a Content-Length header exceeding 250 MB
    huge_length = str(300 * 1024 * 1024)
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        content=b"dummy",
        headers={"Content-Length": huge_length, "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert res.status_code == 413
    data = res.json()
    assert data["error"]["code"] == ErrorCode.FILE_TOO_LARGE.value
    assert "exceeds maximum allowed size" in data["error"]["message"]


def test_streaming_request_size_limit_chunked_no_content_length(client: TestClient):
    """Finding 3: Multi-chunk streaming request without Content-Length exceeding limit returns 413 FILE_TOO_LARGE with request_id."""
    from backend.app.core.config import get_settings

    ws_res = client.post("/api/workspaces", json={"name": "Stream WS"})
    ws_id = ws_res.json()["id"]

    settings = get_settings()
    orig_limit = settings.MAX_REQUEST_BODY_BYTES
    settings.MAX_REQUEST_BODY_BYTES = 256
    if hasattr(client.app.state, "settings") and client.app.state.settings:
        client.app.state.settings.MAX_REQUEST_BODY_BYTES = 256

    try:

        def chunk_gen():
            yield b'------WebKitFormBoundaryABC123\r\nContent-Disposition: form-data; name="files"; filename="test.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
            yield b"A" * 150
            yield b"B" * 200
            yield b"\r\n------WebKitFormBoundaryABC123--\r\n"

        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            content=chunk_gen(),
            headers={
                "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryABC123",
                "X-Request-ID": "custom-req-id-123",
            },
        )
        print("DEBUG RESULT:", res.status_code, res.text)
        assert res.status_code == 413

        assert res.headers.get("x-request-id") == "custom-req-id-123"
        data = res.json()
        assert data["error"]["code"] == ErrorCode.FILE_TOO_LARGE.value
        assert data["error"]["request_id"] == "custom-req-id-123"
        assert "Streamed request body exceeds maximum allowed size" in data["error"]["message"]
    finally:
        settings.MAX_REQUEST_BODY_BYTES = orig_limit


def test_upload_batch_file_count_limit(client: TestClient):
    """Finding 2: Batches exceeding MAX_BATCH_FILES are rejected with 400 before parsing all files."""
    ws_res = client.post("/api/workspaces", json={"name": "Batch Limit WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Batch limit test")
    # 21 files (limit is 20)
    files = [("files", (f"paper_{i}.pdf", io.BytesIO(pdf_bytes), "application/pdf")) for i in range(21)]

    res = client.post(f"/api/papers?workspace_id={ws_id}", files=files)
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == ErrorCode.INVALID_REQUEST.value
    assert "exceeds maximum limit" in data["error"]["message"]


def test_failed_database_commit_unlinks_published_pdf(client: TestClient, isolated_env: dict):
    """Finding 3: If db.commit fails during paper upload, final PDF is unlinked to avoid orphan files."""
    ws_res = client.post("/api/workspaces", json={"name": "Orphan Test WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Orphan cleanup test")
    data_dir = isolated_env["data_dir"]
    pdf_dir = data_dir / "pdfs"

    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB commit error")):
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files=[("files", ("orphan_test.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
        )
        assert res.status_code == 202
        data = res.json()
        assert len(data["rejected"]) == 1
        assert data["rejected"][0]["code"] == ErrorCode.DATABASE_ERROR.value

    # Verify no orphan PDFs remain in data_dir/pdfs
    remaining_files = list(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    assert len(remaining_files) == 0


def test_commit_success_refresh_failure_preserves_row_and_file(client: TestClient, isolated_env: dict):
    """Finding 3: If commit succeeds but refresh fails, row is preserved and file is NOT unlinked."""
    ws_res = client.post("/api/workspaces", json={"name": "Refresh WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Refresh failure test")
    data_dir = isolated_env["data_dir"]
    pdf_dir = data_dir / "pdfs"

    with patch.object(Session, "refresh", side_effect=RuntimeError("Simulated refresh failure")):
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files=[("files", ("refresh_test.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
        )
        assert res.status_code == 202
        data = res.json()
        assert len(data["papers"]) == 1
        paper_id = data["papers"][0]["id"]

    # File must exist
    pdf_path = pdf_dir / f"{paper_id}.pdf"
    assert pdf_path.exists()

    # Detail must be retrievable
    detail = client.get(f"/api/papers/{paper_id}")
    assert detail.status_code == 200


def test_delete_paper_lock_failure_preserves_row_for_retry(client: TestClient, isolated_env: dict):
    """Finding 1 & 4: When physical file cannot be staged (e.g. locked), DB row is preserved and 500 is returned."""
    ws_res = client.post("/api/workspaces", json={"name": "Lock Paper WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Locked paper test")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("locked.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"
    assert pdf_path.exists()

    # Simulate locked file during rename/staging
    with patch.object(
        Path, "rename", side_effect=OSError("The process cannot access the file because it is being used")
    ):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "Failed to delete paper file from storage" in err["error"]["message"]
        # Sanitation check: no internal paths or raw OS error text exposed
        assert str(pdf_path) not in err["error"]["message"]
        assert "storage_path" not in err["error"]["details"]

    # Crucial assertion: Paper still exists in database and on disk!
    assert client.get(f"/api/papers/{paper_id}").status_code == 200
    assert pdf_path.exists()

    # Now retry without lock: it must succeed and clean up!
    retry_res = client.delete(f"/api/papers/{paper_id}")
    assert retry_res.status_code == 204
    assert not pdf_path.exists()
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_delete_paper_db_commit_failure_preserves_file_and_row(client: TestClient, isolated_env: dict):
    """Finding 1: If database commit fails during paper deletion, staged file is restored and row is preserved."""
    ws_res = client.post("/api/workspaces", json={"name": "Commit Fail Paper WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Commit fail paper test")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("commit_fail.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"
    assert pdf_path.exists()

    # Force Session.commit to fail during deletion
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB commit error on delete")):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "Database error during paper deletion" in err["error"]["message"]
        assert "original file preserved" in err["error"]["message"]

    # Both DB row and original file must be preserved and downloadable
    assert client.get(f"/api/papers/{paper_id}").status_code == 200
    assert pdf_path.exists()
    file_res = client.get(f"/api/papers/{paper_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == pdf_bytes

    # Retry without DB error: succeeds cleanly
    retry_res = client.delete(f"/api/papers/{paper_id}")
    assert retry_res.status_code == 204
    assert not pdf_path.exists()
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_delete_workspace_partial_lock_failure_preserves_state(client: TestClient, isolated_env: dict):
    """Finding 1 & 4: If a file fails to stage during workspace deletion, all files and workspace are preserved."""
    ws_res = client.post("/api/workspaces", json={"name": "Partial Lock WS"})
    ws_id = ws_res.json()["id"]

    pdf1 = create_minimal_pdf("Paper 1")
    pdf2 = create_minimal_pdf("Paper 2")

    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[
            ("files", ("paper1.pdf", io.BytesIO(pdf1), "application/pdf")),
            ("files", ("paper2.pdf", io.BytesIO(pdf2), "application/pdf")),
        ],
    )
    p1_id = res.json()["papers"][0]["id"]
    p2_id = res.json()["papers"][1]["id"]
    data_dir = isolated_env["data_dir"]
    p1_path = data_dir / "pdfs" / f"{p1_id}.pdf"
    p2_path = data_dir / "pdfs" / f"{p2_id}.pdf"

    original_rename = Path.rename

    def selective_rename(self, target, *args, **kwargs):
        if self.name == f"{p2_id}.pdf":
            raise OSError("Simulated Windows file lock on paper 2")
        return original_rename(self, target, *args, **kwargs)

    with patch.object(Path, "rename", selective_rename):
        del_res = client.delete(f"/api/workspaces/{ws_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        # Verify sanitized error (no raw paths)
        assert str(p2_path) not in str(err)

    # Both files must still exist on disk (p1 was restored after p2 failed staging)
    assert p1_path.exists()
    assert p2_path.exists()
    ws_get = client.get(f"/api/workspaces/{ws_id}")
    assert ws_get.status_code == 200
    p1_get = client.get(f"/api/papers/{p1_id}")
    assert p1_get.status_code == 200
    p2_get = client.get(f"/api/papers/{p2_id}")
    assert p2_get.status_code == 200

    # Retry deleting workspace now that lock is removed
    del_retry = client.delete(f"/api/workspaces/{ws_id}")
    assert del_retry.status_code == 204
    assert not p1_path.exists()
    assert not p2_path.exists()
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404


def test_delete_workspace_db_commit_failure_preserves_files_and_workspace(client: TestClient, isolated_env: dict):
    """Finding 1: If database commit fails during workspace deletion, all files and workspace are restored."""
    ws_res = client.post("/api/workspaces", json={"name": "WS Commit Fail"})
    ws_id = ws_res.json()["id"]

    pdf1 = create_minimal_pdf("WS Paper 1")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("wsp1.pdf", io.BytesIO(pdf1), "application/pdf"))],
    )
    p1_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    p1_path = data_dir / "pdfs" / f"{p1_id}.pdf"
    assert p1_path.exists()

    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB commit error on workspace delete")):
        del_res = client.delete(f"/api/workspaces/{ws_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value

    # File and workspace preserved
    assert p1_path.exists()
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 200
    assert client.get(f"/api/papers/{p1_id}").status_code == 200

    # Retry succeeds
    del_retry = client.delete(f"/api/workspaces/{ws_id}")
    assert del_retry.status_code == 204
    assert not p1_path.exists()
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404


def test_public_error_sanitization_no_private_paths_or_sql_exposed(client: TestClient, isolated_env: dict):
    """Finding 4: Error responses never expose storage paths or raw SQL exceptions."""
    ws_res = client.post("/api/workspaces", json={"name": "Sanitize WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Sanitize test")
    data_dir = isolated_env["data_dir"]

    # 1. Upload DB error: no raw SQL trace or private path
    sentinel_error = "SELECT * FROM secret_table WHERE private_data = 'leak'"
    with patch.object(Session, "commit", side_effect=RuntimeError(sentinel_error)):
        res = client.post(
            f"/api/papers?workspace_id={ws_id}",
            files=[("files", ("leak_test.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
        )
        assert res.status_code == 202
        body_text = res.text
        assert "secret_table" not in body_text
        assert str(data_dir) not in body_text
        assert res.json()["rejected"][0]["message"] == "Database error during document persistence. Please try again."


def test_unicode_and_quoted_filename_content_disposition(client: TestClient):
    """Finding 5: Original Unicode and quoted filenames can be retrieved via GET /file without 500 error."""
    ws_res = client.post("/api/workspaces", json={"name": "Unicode WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Unicode Paper Content")
    unicode_name = "研究論文_2026.pdf"

    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", (unicode_name, io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    assert res.status_code == 202
    paper_id = res.json()["papers"][0]["id"]

    # GET file (full)
    file_res = client.get(f"/api/papers/{paper_id}/file")
    assert file_res.status_code == 200
    disposition = file_res.headers.get("Content-Disposition", "")
    assert "filename*=" in disposition
    assert "UTF-8''" in disposition
    assert file_res.content == pdf_bytes

    # GET file (range)
    range_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": "bytes=0-49"})
    assert range_res.status_code == 206
    range_disp = range_res.headers.get("Content-Disposition", "")
    assert "filename*=" in range_disp
    assert "UTF-8''" in range_disp


def test_range_request_clipping_past_eof(client: TestClient):
    """Finding 6: Range requests with end >= file_size are clipped to file_size - 1 per RFC 9110."""
    ws_res = client.post("/api/workspaces", json={"name": "Range WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Range testing content")
    file_size = len(pdf_bytes)

    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("range.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]

    # Range extending past EOF
    overshoot_end = file_size + 500
    range_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": f"bytes=0-{overshoot_end}"})
    assert range_res.status_code == 206
    assert range_res.headers["Content-Range"] == f"bytes 0-{file_size - 1}/{file_size}"
    assert int(range_res.headers["Content-Length"]) == file_size
    assert range_res.content == pdf_bytes

    # Open-ended range from byte 10 to EOF
    open_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": "bytes=10-"})
    assert open_res.status_code == 206
    assert open_res.headers["Content-Range"] == f"bytes 10-{file_size - 1}/{file_size}"
    assert range_res.content[10:] == open_res.content


# ==============================================================================
# R1 Tests: Durable Quarantine Ledger, Truthful Semantics, & Reconciliation
# ==============================================================================


def test_r1_staging_failure_aborts_deletion_preserves_row_and_file(client: TestClient, isolated_env: dict):
    """R1: If staging file into .trash fails with OSError, paper deletion is aborted, row and file preserved."""
    ws_res = client.post("/api/workspaces", json={"name": "R1 Staging Fail WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("R1 Staging Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("staging_test.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"
    assert pdf_path.exists()

    with patch(
        "backend.app.services.quarantine_service.stage_file_for_deletion", side_effect=OSError("Disk write lock")
    ):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        data = del_res.json()
        assert data["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "Failed to delete paper file from storage" in data["error"]["message"]

    # Original file and database record remain intact
    assert pdf_path.exists()
    assert client.get(f"/api/papers/{paper_id}").status_code == 200


def test_r1_rollback_restoration_failure_truthful_semantics_and_recovery_route(client: TestClient, isolated_env: dict):
    """R1: If commit fails AND rollback rename fails, reports truthful 500 and provides live recovery route."""
    ws_res = client.post("/api/workspaces", json={"name": "R1 Truthful Semantics WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("R1 Recovery Route Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("recovery_route.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"

    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB failure")):
        with patch("backend.app.services.quarantine_service.restore_quarantined_file", return_value=False):
            del_res = client.delete(f"/api/papers/{paper_id}")
            assert del_res.status_code == 500
            data = del_res.json()
            assert data["error"]["code"] == ErrorCode.DATABASE_ERROR.value
            # Truthful semantics: does NOT promise file was restored
            assert "failed to restore file. File quarantined for recovery." in data["error"]["message"]
            assert data["error"]["details"].get("status") == "quarantined_for_recovery"

    # Row is still live in DB
    paper_res = client.get(f"/api/papers/{paper_id}")
    assert paper_res.status_code == 200

    # Original file is NOT at pdf_path because rollback rename failed
    assert not pdf_path.exists()

    # BUT live paper document CAN STILL BE ACCESSED via quarantine fallback!
    file_res = client.get(f"/api/papers/{paper_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == pdf_bytes


def test_r1_final_unlink_failure_truthful_pending_purge_and_retry_204(client: TestClient, isolated_env: dict):
    """R1: If final unlink fails, returns 500 pending_purge; retry purges quarantined file and returns 204."""
    ws_res = client.post("/api/workspaces", json={"name": "R1 Unlink Fail WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("R1 Unlink Failure Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("unlink_fail.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # Simulate PermissionError on purge_quarantined_file
    with patch("backend.app.services.quarantine_service.purge_quarantined_file", return_value=False):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        data = del_res.json()
        assert data["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "quarantined file purge failed. Deletion remains pending." in data["error"]["message"]
        assert data["error"]["details"].get("status") == "pending_purge"

    # Paper row is deleted from DB
    assert client.get(f"/api/papers/{paper_id}").status_code == 404

    # File and ledger still exist in .trash in committed_pending_purge state
    meta_files = list(trash_dir.glob("*.meta.json"))
    assert len(meta_files) >= 1

    # Retry DELETE /api/papers/{paper_id}: purge succeeds now, returning 204!
    retry_del = client.delete(f"/api/papers/{paper_id}")
    assert retry_del.status_code == 204

    # Now quarantine files for this paper are gone
    remaining = [m for m in trash_dir.glob("*.meta.json") if paper_id in m.name]
    assert len(remaining) == 0


def test_r1_reconciliation_surviving_restart_preserves_unrelated_files(client: TestClient, isolated_env: dict):
    """R1: Quarantine reconciliation restores live records, purges committed deletions, preserves foreign files."""
    from backend.app.services.quarantine_service import (
        mark_committed_deletion,
        reconcile_quarantine,
        stage_file_for_deletion,
    )

    data_dir = isolated_env["data_dir"]
    pdf_dir = data_dir / "pdfs"
    trash_dir = pdf_dir / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)

    # 1. Foreign / unrelated file without .meta.json: MUST BE PRESERVED
    foreign_file = trash_dir / "unrelated_foreign_backup.dat"
    foreign_file.write_text("critical external data", encoding="utf-8")

    # 2. Live paper: create paper in DB, move its file to trash with staged state
    ws_res = client.post("/api/workspaces", json={"name": "Reconciliation Live WS"})
    ws_id = ws_res.json()["id"]
    pdf_bytes = create_minimal_pdf("Live paper needing restart restoration")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("live_reconcile.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    live_paper_id = res.json()["papers"][0]["id"]
    live_path = pdf_dir / f"{live_paper_id}.pdf"
    assert live_path.exists()
    staged_live, live_meta = stage_file_for_deletion(live_path, "paper", live_paper_id, ws_id)
    assert not live_path.exists()

    # 3. Committed deletion (paper id not in DB)
    dead_paper_id = "00000000-0000-0000-0000-000000000099"
    dead_dummy = pdf_dir / f"{dead_paper_id}.pdf"
    dead_dummy.write_text("dead paper content", encoding="utf-8")
    staged_dead, dead_meta = stage_file_for_deletion(dead_dummy, "paper", dead_paper_id, ws_id)
    mark_committed_deletion(dead_meta)

    # Run reconciliation
    with isolated_env["session_factory"]() as db:
        stats = reconcile_quarantine(trash_dir, db)

    # Assert outcomes
    assert stats["restored"] == 1
    assert stats["purged"] == 1
    assert foreign_file.exists()  # Foreign file strictly preserved!
    assert foreign_file.read_text(encoding="utf-8") == "critical external data"
    assert live_path.exists()  # Live paper restored to original path!
    assert not staged_dead.exists()  # Committed deletion purged!
    assert not dead_meta.exists()


def test_r1_workspace_delete_unlink_failure_pending_purge_and_retry(client: TestClient, isolated_env: dict):
    """R1: If workspace deletion commits but unlinking staged files fails, returns 500 pending_purge; retry purges and returns 204."""
    ws_res = client.post("/api/workspaces", json={"name": "WS Unlink Fail WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Workspace Unlink Fail Paper")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("ws_unlink.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # Simulate PermissionError on purge_quarantined_file during workspace deletion
    with patch("backend.app.services.quarantine_service.purge_quarantined_file", return_value=False):
        del_res = client.delete(f"/api/workspaces/{ws_id}")
        assert del_res.status_code == 500
        data = del_res.json()
        assert data["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "quarantined files failed to purge. Cleanup remains pending." in data["error"]["message"]
        assert data["error"]["details"].get("status") == "pending_purge"

    # Workspace is deleted from DB
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404

    # Retry DELETE /api/workspaces/{ws_id}: purge succeeds now, returning 204!
    retry_del = client.delete(f"/api/workspaces/{ws_id}")
    assert retry_del.status_code == 204

    # Quarantined files are purged
    remaining = [m for m in trash_dir.glob("*.meta.json") if paper_id in m.name]
    assert len(remaining) == 0


def test_q1_paper_pending_purge_foreign_and_ownerless_rejection(
    client: TestClient, isolated_env: dict, db_session: Session
):
    """Q1: Pending-purge retries enforce resource ownership; foreign/ownerless requests receive 404 without file mutation."""
    import json

    from backend.app.api.deps import get_current_user
    from backend.app.db.models import User
    from backend.app.main import app

    # Create foreign user
    foreign_user = User(
        id="user_foreign_q1_paper",
        email="foreign_p@example.com",
        password_hash="mock_hash",
        display_name="Foreign Paper User",
    )
    db_session.add(foreign_user)
    db_session.commit()

    ws_res = client.post("/api/workspaces", json={"name": "Q1 Paper Owner WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Q1 Paper Pending Purge Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("q1_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # 1. Trigger deletion with purge failure so row is deleted and ledger has committed_pending_purge
    with patch("backend.app.services.quarantine_service.purge_quarantined_file", return_value=False):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        assert del_res.json()["error"]["details"].get("status") == "pending_purge"

    # Confirm paper row deleted
    assert client.get(f"/api/papers/{paper_id}").status_code == 404

    # Verify ledger file exists and has user_id set to genuine owner
    matching_metas = [m for m in trash_dir.glob("*.meta.json") if paper_id in m.name]
    assert len(matching_metas) == 1
    meta_p = matching_metas[0]
    meta_data = json.loads(meta_p.read_text(encoding="utf-8"))
    staged_p = Path(meta_data["staged_path"])
    assert staged_p.exists()
    owner_id = meta_data["user_id"]
    assert bool(owner_id)
    assert owner_id != foreign_user.id

    # 2. Foreign user tries to delete: MUST return 404 and leave file & ledger untouched
    app.dependency_overrides[get_current_user] = lambda: foreign_user
    try:
        foreign_del = client.delete(f"/api/papers/{paper_id}")
        assert foreign_del.status_code == 404
        assert foreign_del.json()["error"]["code"] == ErrorCode.NOT_FOUND.value
        # File and ledger strictly untouched
        assert staged_p.exists()
        assert meta_p.exists()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Ownerless/legacy record: simulate missing/None user_id in ledger
    meta_data["user_id"] = None
    meta_p.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

    # Even owner call must be rejected conservatively (no unauthorized purge merely from ID)
    owner_ownerless_del = client.delete(f"/api/papers/{paper_id}")
    assert owner_ownerless_del.status_code == 404
    assert staged_p.exists()
    assert meta_p.exists()

    # 4. Restore genuine owner ID on ledger: genuine owner retry succeeds with 204
    meta_data["user_id"] = owner_id
    meta_p.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

    retry_del = client.delete(f"/api/papers/{paper_id}")
    assert retry_del.status_code == 204
    assert not staged_p.exists()
    assert not meta_p.exists()


def test_q1_workspace_pending_purge_foreign_and_ownerless_rejection(
    client: TestClient, isolated_env: dict, db_session: Session
):
    """Q1: Workspace pending-purge retries enforce ownership; foreign users cannot purge retained files."""
    import json

    from backend.app.api.deps import get_current_user
    from backend.app.db.models import User
    from backend.app.main import app

    # Create foreign user
    foreign_user = User(
        id="user_foreign_q1_ws",
        email="foreign_ws@example.com",
        password_hash="mock_hash",
        display_name="Foreign WS User",
    )
    db_session.add(foreign_user)
    db_session.commit()

    ws_res = client.post("/api/workspaces", json={"name": "Q1 WS Owner WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Q1 WS Pending Purge Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("q1_ws_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # 1. Trigger workspace deletion with purge failure
    with patch("backend.app.services.quarantine_service.purge_quarantined_file", return_value=False):
        del_res = client.delete(f"/api/workspaces/{ws_id}")
        assert del_res.status_code == 500
        assert del_res.json()["error"]["details"].get("status") == "pending_purge"

    # Confirm workspace row deleted
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404

    # Ledger exists in trash
    matching_metas = [m for m in trash_dir.glob("*.meta.json") if paper_id in m.name]
    assert len(matching_metas) == 1
    meta_p = matching_metas[0]
    meta_data = json.loads(meta_p.read_text(encoding="utf-8"))
    staged_p = Path(meta_data["staged_path"])
    assert staged_p.exists()
    owner_id = meta_data["user_id"]
    assert bool(owner_id)
    assert owner_id != foreign_user.id

    # 2. Foreign user tries to delete workspace: 404, file and ledger untouched
    app.dependency_overrides[get_current_user] = lambda: foreign_user
    try:
        foreign_del = client.delete(f"/api/workspaces/{ws_id}")
        assert foreign_del.status_code == 404
        assert staged_p.exists()
        assert meta_p.exists()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Ownerless record test
    meta_data["user_id"] = None
    meta_p.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")
    owner_ownerless_del = client.delete(f"/api/workspaces/{ws_id}")
    assert owner_ownerless_del.status_code == 404
    assert staged_p.exists()

    # 4. Genuine owner retry
    meta_data["user_id"] = owner_id
    meta_p.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")
    retry_del = client.delete(f"/api/workspaces/{ws_id}")
    assert retry_del.status_code == 204
    assert not staged_p.exists()
    assert not meta_p.exists()


def test_q2_paper_already_in_quarantine_adopted_and_purged(client: TestClient, isolated_env: dict):
    """Q2: Live paper with file already staged in quarantine is adopted on DELETE, purged completely on commit."""
    ws_res = client.post("/api/workspaces", json={"name": "Q2 Adopted Paper WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Q2 Live Paper Quarantined Bytes")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("q2_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # 1. Force commit failure + restoration failure so paper remains alive in DB but bytes reside in .trash
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated commit error")):
        with patch("backend.app.services.quarantine_service.restore_quarantined_file", return_value=False):
            del_res = client.delete(f"/api/papers/{paper_id}")
            assert del_res.status_code == 500
            assert del_res.json()["error"]["details"]["status"] == "quarantined_for_recovery"

    # Paper is alive in DB and accessible via fallback route
    assert client.get(f"/api/papers/{paper_id}").status_code == 200
    file_res = client.get(f"/api/papers/{paper_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == pdf_bytes

    # Original storage_path file does not exist (bytes are in .trash)
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"
    assert not pdf_path.exists()

    # 2. Retry DELETE /api/papers/{paper_id} without errors:
    # Must adopt the quarantined file, commit deletion, and purge it!
    retry_del = client.delete(f"/api/papers/{paper_id}")
    assert retry_del.status_code == 204

    # Paper row is deleted
    assert client.get(f"/api/papers/{paper_id}").status_code == 404

    # Quarantined file and metadata are completely purged from .trash!
    remaining = [m for m in trash_dir.glob("*.meta.json") if paper_id in m.name]
    assert len(remaining) == 0
    remaining_tmp = [t for t in trash_dir.glob("*.tmp") if paper_id in t.name]
    assert len(remaining_tmp) == 0

    # Subsequent delete returns 404
    subsequent_del = client.delete(f"/api/papers/{paper_id}")
    assert subsequent_del.status_code == 404


def test_q2_paper_already_in_quarantine_purge_failure_then_owner_retry(client: TestClient, isolated_env: dict):
    """Q2: Live paper with file in quarantine adopted on DELETE; purge failure marks committed_pending_purge; retry succeeds."""
    ws_res = client.post("/api/workspaces", json={"name": "Q2 Purge Fail WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Q2 Purge Failure Retry Content")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("q2_purge_fail.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]
    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # Incur commit failure + restoration failure
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated commit error")):
        with patch("backend.app.services.quarantine_service.restore_quarantined_file", return_value=False):
            del_res = client.delete(f"/api/papers/{paper_id}")
            assert del_res.status_code == 500

    # Now retry DELETE, but purge_quarantined_file fails
    with patch("backend.app.services.quarantine_service.purge_quarantined_file", return_value=False):
        retry_fail = client.delete(f"/api/papers/{paper_id}")
        assert retry_fail.status_code == 500
        assert retry_fail.json()["error"]["details"]["status"] == "pending_purge"

    # Paper row is gone from DB
    assert client.get(f"/api/papers/{paper_id}").status_code == 404

    # Subsequent owner retry: purge succeeds!
    final_del = client.delete(f"/api/papers/{paper_id}")
    assert final_del.status_code == 204
    assert len(list(trash_dir.glob(f"*{paper_id}*"))) == 0


def test_q2_workspace_cascade_mixed_normal_and_quarantined_files(client: TestClient, isolated_env: dict):
    """Q2: Workspace deletion cascade correctly adopts already-quarantined files along with normal files."""
    ws_res = client.post("/api/workspaces", json={"name": "Q2 Mixed WS"})
    ws_id = ws_res.json()["id"]

    # Upload Paper 1 (normal)
    pdf1_bytes = create_minimal_pdf("Paper 1 Normal Content")
    res1 = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("p1_normal.pdf", io.BytesIO(pdf1_bytes), "application/pdf"))],
    )
    p1_id = res1.json()["papers"][0]["id"]

    # Upload Paper 2 (will be put into quarantine via failed restoration)
    pdf2_bytes = create_minimal_pdf("Paper 2 Quarantined Content")
    res2 = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("p2_quarantine.pdf", io.BytesIO(pdf2_bytes), "application/pdf"))],
    )
    p2_id = res2.json()["papers"][0]["id"]

    data_dir = isolated_env["data_dir"]
    trash_dir = data_dir / "pdfs" / ".trash"

    # Put Paper 2 into quarantine
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated commit error")):
        with patch("backend.app.services.quarantine_service.restore_quarantined_file", return_value=False):
            client.delete(f"/api/papers/{p2_id}")

    # Verify state: Paper 1 has normal file, Paper 2 has quarantined file
    p1_file = data_dir / "pdfs" / f"{p1_id}.pdf"
    p2_file = data_dir / "pdfs" / f"{p2_id}.pdf"
    assert p1_file.exists()
    assert not p2_file.exists()

    # Now delete workspace: cascade must stage Paper 1 and adopt Paper 2, then purge both!
    del_ws = client.delete(f"/api/workspaces/{ws_id}")
    assert del_ws.status_code == 204

    # Both papers and workspace are gone from DB
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404
    assert client.get(f"/api/papers/{p1_id}").status_code == 404
    assert client.get(f"/api/papers/{p2_id}").status_code == 404

    # Both files are purged from disk and trash
    assert not p1_file.exists()
    assert len([m for m in trash_dir.glob("*.meta.json") if p1_id in m.name or p2_id in m.name]) == 0
    assert len([t for t in trash_dir.glob("*.tmp") if p1_id in t.name or p2_id in t.name]) == 0
