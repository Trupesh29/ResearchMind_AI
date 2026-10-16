import io

import fitz  # PyMuPDF
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import User
from backend.app.main import app


def create_minimal_pdf(text: str = "Test Research Paper") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_upload_single_and_batch_papers(client: TestClient):
    # 1. Create workspace
    ws_res = client.post("/api/workspaces", json={"name": "AI Library"})
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    pdf1 = create_minimal_pdf("Paper 1 on Transformers")
    pdf2 = create_minimal_pdf("Paper 2 on Attention Mechanisms")

    # 2. Upload two valid PDFs in one batch
    files = [
        ("files", ("paper1.pdf", io.BytesIO(pdf1), "application/pdf")),
        ("files", ("paper2.pdf", io.BytesIO(pdf2), "application/pdf")),
    ]
    res = client.post(f"/api/papers?workspace_id={ws_id}", files=files)
    assert res.status_code == 202
    data = res.json()

    assert len(data["papers"]) == 2
    assert len(data["duplicates"]) == 0
    assert len(data["rejected"]) == 0

    p1 = data["papers"][0]
    p2 = data["papers"][1]
    assert p1["original_filename"] == "paper1.pdf"
    assert p1["status"] == "uploaded"

    assert p2["original_filename"] == "paper2.pdf"
    assert p2["status"] == "uploaded"

    # Verify detail metadata & storage privacy
    detail_res = client.get(f"/api/papers/{p1['id']}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["original_filename"] == "paper1.pdf"
    assert detail["workspace_id"] == ws_id
    assert detail["page_count"] == 1
    assert detail["status"] == "uploaded"
    assert "storage_path" not in detail


def test_upload_magic_bytes_and_corruption_rejection(client: TestClient):
    ws_res = client.post("/api/workspaces", json={"name": "Rejection WS"})
    ws_id = ws_res.json()["id"]

    fake_pdf = b"NOT_A_PDF_CONTENT"
    corrupt_magic_pdf = b"%PDF-1.4\ncorrupted garbage that fitz cannot parse"

    files = [
        ("files", ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")),
        ("files", ("corrupt.pdf", io.BytesIO(corrupt_magic_pdf), "application/pdf")),
    ]
    res = client.post(f"/api/papers?workspace_id={ws_id}", files=files)
    assert res.status_code == 202
    data = res.json()

    assert len(data["papers"]) == 0
    assert len(data["rejected"]) == 2
    filenames = [r["original_filename"] for r in data["rejected"]]
    assert "fake.pdf" in filenames
    assert "corrupt.pdf" in filenames


def test_upload_duplicate_detection(client: TestClient):
    ws_res = client.post("/api/workspaces", json={"name": "Dup WS"})
    ws_id = ws_res.json()["id"]

    pdf_content = create_minimal_pdf("Unique Content For Hash Verification")

    # 1. Batch internal duplicate: same content uploaded twice in same batch
    files = [
        ("files", ("original.pdf", io.BytesIO(pdf_content), "application/pdf")),
        ("files", ("copy.pdf", io.BytesIO(pdf_content), "application/pdf")),
    ]
    res = client.post(f"/api/papers?workspace_id={ws_id}", files=files)
    assert res.status_code == 202
    data = res.json()
    assert len(data["papers"]) == 1
    assert len(data["duplicates"]) == 1
    assert data["duplicates"][0]["original_filename"] == "copy.pdf"

    # 2. Workspace duplicate: second request with same content
    res2 = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("second_try.pdf", io.BytesIO(pdf_content), "application/pdf"))],
    )
    assert res2.status_code == 202
    data2 = res2.json()
    assert len(data2["papers"]) == 0
    assert len(data2["duplicates"]) == 1
    assert data2["duplicates"][0]["original_filename"] == "second_try.pdf"


def test_list_and_search_papers(client: TestClient):
    ws_res = client.post("/api/workspaces", json={"name": "Search WS"})
    ws_id = ws_res.json()["id"]

    for i in range(4):
        pdf = create_minimal_pdf(f"Unique body {i} Neural Networks")
        name = f"neural_paper_{i}.pdf"
        client.post(f"/api/papers?workspace_id={ws_id}", files=[("files", (name, io.BytesIO(pdf), "application/pdf"))])

    # Another paper with different name
    other_pdf = create_minimal_pdf("Quantum entanglement")
    client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("quantum.pdf", io.BytesIO(other_pdf), "application/pdf"))],
    )

    # List all
    res = client.get(f"/api/papers?workspace_id={ws_id}")
    assert res.status_code == 200
    assert res.json()["total_count"] == 5

    # Search with q
    search_res = client.get(f"/api/papers?workspace_id={ws_id}&q=neural")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_count"] == 4
    for p in search_data["items"]:
        assert "neural" in p["original_filename"].lower() or "neural" in (p["title"] or "").lower()


def test_paper_status_polling(client: TestClient):
    ws_res = client.post("/api/workspaces", json={"name": "Status WS"})
    ws_id = ws_res.json()["id"]

    pdf = create_minimal_pdf("Status check paper")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}", files=[("files", ("status.pdf", io.BytesIO(pdf), "application/pdf"))]
    )
    paper_id = res.json()["papers"][0]["id"]

    status_res = client.get(f"/api/papers/{paper_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "uploaded"
    assert status_data["error"] is None


def test_stream_pdf_range_requests(client: TestClient):
    ws_res = client.post("/api/workspaces", json={"name": "Streaming WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Testing PDF Streaming Range Requests" * 50)
    res = client.post(
        f"/api/papers?workspace_id={ws_id}", files=[("files", ("stream.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    )
    paper_id = res.json()["papers"][0]["id"]
    total_length = len(pdf_bytes)

    # 1. Full content request (200 OK)
    full_res = client.get(f"/api/papers/{paper_id}/file")
    assert full_res.status_code == 200
    assert full_res.headers["Accept-Ranges"] == "bytes"
    assert full_res.headers["Content-Type"] == "application/pdf"
    assert int(full_res.headers["Content-Length"]) == total_length
    assert full_res.content == pdf_bytes

    # 2. Byte range request (206 Partial Content)
    range_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": "bytes=0-99"})
    assert range_res.status_code == 206
    assert range_res.headers["Content-Range"] == f"bytes 0-99/{total_length}"
    assert int(range_res.headers["Content-Length"]) == 100
    assert range_res.content == pdf_bytes[0:100]

    # Suffix range
    suffix_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": "bytes=-50"})
    assert suffix_res.status_code == 206
    assert suffix_res.headers["Content-Range"] == f"bytes {total_length - 50}-{total_length - 1}/{total_length}"
    assert int(suffix_res.headers["Content-Length"]) == 50
    assert suffix_res.content == pdf_bytes[-50:]

    # 3. Unsatisfiable range (416 Range Not Satisfiable)
    invalid_res = client.get(f"/api/papers/{paper_id}/file", headers={"Range": "bytes=999999-9999999"})
    assert invalid_res.status_code == 416
    assert invalid_res.headers["Content-Range"] == f"bytes */{total_length}"


def test_delete_paper_cleans_up_disk(client: TestClient, isolated_env: dict):
    ws_res = client.post("/api/workspaces", json={"name": "Delete Paper WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Paper to delete")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("delete_me.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]

    # Verify physical file exists in isolated_env data_dir
    data_dir = isolated_env["data_dir"]
    pdf_path = data_dir / "pdfs" / f"{paper_id}.pdf"
    assert pdf_path.exists()
    assert pdf_path.is_file()

    # Delete paper
    del_res = client.delete(f"/api/papers/{paper_id}")
    assert del_res.status_code == 204

    # Verify physical file is cleaned up
    assert not pdf_path.exists()

    # Subsequent GET returns 404
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_foreign_user_paper_isolation(client: TestClient, db_session: Session):
    ws_res = client.post("/api/workspaces", json={"name": "Isolation WS"})
    ws_id = ws_res.json()["id"]

    pdf_bytes = create_minimal_pdf("Private research paper")
    res = client.post(
        f"/api/papers?workspace_id={ws_id}",
        files=[("files", ("private.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    paper_id = res.json()["papers"][0]["id"]

    # Switch to foreign user
    foreign_user = User(
        id="foreign-paper-user",
        email="hacker@researchmind.local",
        password_hash="mock_hash_value",
        display_name="Hacker",
    )
    db_session.add(foreign_user)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: foreign_user
    try:
        # Cannot get metadata -> 404
        assert client.get(f"/api/papers/{paper_id}").status_code == 404
        # Cannot get file -> 404
        assert client.get(f"/api/papers/{paper_id}/file").status_code == 404
        # Cannot delete -> 404
        assert client.delete(f"/api/papers/{paper_id}").status_code == 404
        # Cannot list
        list_res = client.get(f"/api/papers?workspace_id={ws_id}")
        assert list_res.status_code == 404  # Workspace itself is not found for foreign user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
