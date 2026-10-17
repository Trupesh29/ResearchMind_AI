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
    """Finding 4: When physical file cannot be deleted (e.g. locked), DB row is preserved and 500 is returned."""
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

    # Simulate locked file during unlink
    with patch.object(
        Path, "unlink", side_effect=OSError("The process cannot access the file because it is being used")
    ):
        del_res = client.delete(f"/api/papers/{paper_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value
        assert "Failed to delete paper file from storage" in err["error"]["message"]

    # Crucial assertion: Paper still exists in database and on disk!
    assert client.get(f"/api/papers/{paper_id}").status_code == 200
    assert pdf_path.exists()

    # Now retry without lock: it must succeed and clean up!
    retry_res = client.delete(f"/api/papers/{paper_id}")
    assert retry_res.status_code == 204
    assert not pdf_path.exists()
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_delete_workspace_partial_lock_failure_preserves_state(client: TestClient, isolated_env: dict):
    """Finding 4: If a file fails to delete during workspace deletion, the workspace and failed file's row are preserved for retry."""
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

    original_unlink = Path.unlink

    def selective_unlink(self, *args, **kwargs):
        if self.name == f"{p2_id}.pdf":
            raise OSError("Simulated Windows file lock on paper 2")
        return original_unlink(self, *args, **kwargs)

    with patch.object(Path, "unlink", selective_unlink):
        del_res = client.delete(f"/api/workspaces/{ws_id}")
        assert del_res.status_code == 500
        err = del_res.json()
        assert err["error"]["code"] == ErrorCode.DATABASE_ERROR.value

    # Paper 1 file was deleted and row removed
    assert not p1_path.exists()
    # Paper 2 file was locked so it and workspace are preserved in DB!
    assert p2_path.exists()
    ws_get = client.get(f"/api/workspaces/{ws_id}")
    assert ws_get.status_code == 200
    p2_get = client.get(f"/api/papers/{p2_id}")
    assert p2_get.status_code == 200

    # Retry deleting workspace now that lock is removed
    del_retry = client.delete(f"/api/workspaces/{ws_id}")
    assert del_retry.status_code == 204
    assert not p2_path.exists()
    assert client.get(f"/api/workspaces/{ws_id}").status_code == 404


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
