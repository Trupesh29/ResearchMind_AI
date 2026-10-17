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
