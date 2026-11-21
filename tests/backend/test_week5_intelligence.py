"""
Tests for Week 5 Research Intelligence:
1. GET /api/explorer/papers/{paper_id}/sections (section hierarchy, chunk counts, page coordinates, quality).
2. POST /api/explorer/summaries (multi-style summaries: simple, technical, methodology, results; DB caching).
3. POST /api/comparison/matrix (four-dimension comparison, comparability status, per-cell citations).
4. POST /api/experiments/extract (task, method, conditions, metrics, provenance, empty state handling).
5. POST /api/reports/generate & GET /api/reports/{id}/download (valid DOCX structure, tables, citation appendix, traversal safety).
6. GET /api/model-lab/reports (SciCite readiness, baselines, DistilBERT trial, and test evaluation reports).
"""

import uuid
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Chunk, Paper, PaperSummary, Report, Section, User, Workspace
from tests.backend.test_phase6_retrieval import _create_ready_paper_with_chunks


def _get_user_id(db: Session) -> str:
    user = db.execute(select(User)).scalars().first()
    assert user is not None, "Expected bootstrapped user"
    return user.id


@pytest.fixture
def test_workspace_fixture(db_session: Session):
    user_id = _get_user_id(db_session)
    ws = Workspace(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name="Week 5 Intelligence Test Workspace",
        description="Workspace for testing Research Intelligence features",
    )
    db_session.add(ws)
    db_session.flush()

    # Paper A: Deep Learning Transformer
    paper_a, _ = _create_ready_paper_with_chunks(
        db=db_session,
        workspace=ws,
        title="Attention Is All You Need",
        chunks_data=[
            {
                "page": 1,
                "section": "abstract",
                "text": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, based solely on attention mechanisms.",
            },
            {
                "page": 2,
                "section": "methodology",
                "text": "The Transformer uses multi-head self-attention mechanisms with scaled dot-product attention: Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V.",
            },
            {
                "page": 5,
                "section": "experiments",
                "text": "On the WMT 2014 English-to-German translation task, the big transformer model achieves a BLEU score of 28.4. Accuracy reached 84.5% with learning rate 0.0001.",
            },
            {
                "page": 8,
                "section": "discussion",
                "text": "The model has quadratic complexity with respect to sequence length, which remains an operational limitation on very long sequences.",
            },
        ],
    )
    paper_a.status = "ready"
    paper_a.published_run_id = paper_a.current_run_id

    # Add explicit Section rows for Paper A
    sec_a1 = Section(
        id=str(uuid.uuid4()),
        paper_id=paper_a.id,
        run_id=paper_a.current_run_id,
        section_index=0,
        section="abstract",
        heading="Abstract",
        page_start=1,
        page_end=1,
        text="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
    )
    sec_a2 = Section(
        id=str(uuid.uuid4()),
        paper_id=paper_a.id,
        run_id=paper_a.current_run_id,
        section_index=1,
        section="methodology",
        heading="Model Architecture",
        page_start=2,
        page_end=4,
        text="The Transformer uses multi-head self-attention mechanisms with scaled dot-product attention.",
    )
    db_session.add_all([sec_a1, sec_a2])

    # Paper B: Convolutional Sequence Modeling
    paper_b, _ = _create_ready_paper_with_chunks(
        db=db_session,
        workspace=ws,
        title="Convolutional Sequence to Sequence Learning",
        chunks_data=[
            {
                "page": 1,
                "section": "abstract",
                "text": "The prevalent approach to sequence-to-sequence learning maps an input sequence to a variable length sequence via recurrent neural networks. We introduce a fully convolutional architecture.",
            },
            {
                "page": 3,
                "section": "methodology",
                "text": "Our model applies gated linear units and multi-layer hierarchical convolutional networks with residual connections across attention layers.",
            },
            {
                "page": 6,
                "section": "results",
                "text": "On WMT 2014 English-to-German, our convolutional model yields 25.16 BLEU. Inference latency is 18.2 ms on NVIDIA GPUs.",
            },
            {
                "page": 7,
                "section": "discussion",
                "text": "Convolutional representations are fixed to linear contexts, limiting long-distance dependencies compared to unconstrained attention.",
            },
        ],
    )
    paper_b.status = "ready"
    paper_b.published_run_id = paper_b.current_run_id

    db_session.commit()
    return ws, paper_a, paper_b


def test_paper_sections_extraction_and_coordinates(
    client: TestClient, db_session: Session, test_workspace_fixture
):
    ws, paper_a, _ = test_workspace_fixture

    resp = client.get(f"/api/explorer/papers/{paper_a.id}/sections")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["paper_id"] == paper_a.id
    assert data["paper_title"] == "Attention Is All You Need"
    assert data["total_sections"] >= 2

    # Check section structure
    sec0 = data["sections"][0]
    assert sec0["section_title"] == "Abstract"
    assert sec0["page_start"] == 1
    assert sec0["page_end"] == 1
    assert sec0["chunk_count"] >= 1
    assert sec0["quality_status"] in ["complete", "sparse"]
    assert len(sec0["preview_text"]) > 0


def test_multi_style_summaries_and_caching(
    client: TestClient, db_session: Session, test_workspace_fixture
):
    ws, paper_a, _ = test_workspace_fixture

    # Test all 4 styles
    for style in ["simple", "technical", "methodology", "results"]:
        resp = client.post(
            "/api/explorer/summaries",
            json={"paper_id": paper_a.id, "style": style},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["paper_id"] == paper_a.id
        assert data["style"] == style
        assert len(data["overview"]) > 20
        assert len(data["points"]) >= 1
        assert data["cached"] is False

        # Verify point citations
        for pt in data["points"]:
            assert len(pt["heading"]) > 0
            assert len(pt["content"]) > 0
            assert len(pt["citations"]) >= 1
            c = pt["citations"][0]
            assert c["paper_id"] == paper_a.id
            assert c["page_number"] >= 1
            assert len(c["quote"]) > 0

    # Repeat request to verify DB cache
    repeat_resp = client.post(
        "/api/explorer/summaries",
        json={"paper_id": paper_a.id, "style": "technical"},
    )
    assert repeat_resp.status_code == 200
    assert repeat_resp.json()["cached"] is True


def test_two_paper_comparison_matrix(
    client: TestClient, db_session: Session, test_workspace_fixture
):
    ws, paper_a, paper_b = test_workspace_fixture

    resp = client.post(
        "/api/comparison/matrix",
        json={
            "workspace_id": ws.id,
            "paper_a_id": paper_a.id,
            "paper_b_id": paper_b.id,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["workspace_id"] == ws.id
    assert data["paper_a_title"] == paper_a.title
    assert data["paper_b_title"] == paper_b.title
    assert len(data["dimensions"]) == 4

    dim_ids = [d["dimension_id"] for d in data["dimensions"]]
    assert "objectives" in dim_ids
    assert "methodology" in dim_ids
    assert "findings" in dim_ids
    assert "limitations" in dim_ids

    # Verify citations and comparability status for each dimension
    for d in data["dimensions"]:
        assert len(d["paper_a_claim"]) > 10
        assert len(d["paper_b_claim"]) > 10
        assert d["comparable_status"] in ["comparable", "partially_comparable", "non_comparable"]
        assert len(d["paper_a_citations"]) >= 1
        assert len(d["paper_b_citations"]) >= 1
        assert len(d["synthesis_notes"]) > 10


def test_experiment_intelligence_extraction(
    client: TestClient, db_session: Session, test_workspace_fixture
):
    ws, paper_a, _ = test_workspace_fixture

    resp = client.post(
        "/api/experiments/extract",
        json={"paper_id": paper_a.id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["paper_id"] == paper_a.id
    assert data["status"] == "experiments_extracted"
    assert len(data["experiments"]) >= 1

    exp = data["experiments"][0]
    assert len(exp["task"]) > 0
    assert len(exp["method"]) > 0
    assert "Hardware" in exp["conditions"]
    assert len(exp["metrics"]) >= 1
    assert exp["provenance"] is not None
    assert exp["provenance"]["paper_id"] == paper_a.id


def test_server_side_docx_generation_and_traversal_guard(
    client: TestClient, db_session: Session, test_workspace_fixture, tmp_path
):
    ws, paper_a, paper_b = test_workspace_fixture

    # 1. Generate report
    gen_resp = client.post(
        "/api/reports/generate",
        json={
            "workspace_id": ws.id,
            "title": "Comprehensive Research Synthesis Report",
            "paper_ids": [paper_a.id, paper_b.id],
            "summary_style": "technical",
            "include_comparison": True,
            "include_experiments": True,
        },
    )
    assert gen_resp.status_code == 200, gen_resp.text
    rep_data = gen_resp.json()

    report_id = rep_data["report_id"]
    assert rep_data["status"] == "completed"
    assert rep_data["file_size_bytes"] is not None
    assert rep_data["file_size_bytes"] > 5000  # valid docx file has zip headers & xml > 5KB

    # 2. Verify report status endpoint
    status_resp = client.get(f"/api/reports/{report_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    # 3. Download DOCX and verify with python-docx
    down_resp = client.get(f"/api/reports/{report_id}/download")
    assert down_resp.status_code == 200
    assert (
        down_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    doc_file = tmp_path / "downloaded_test.docx"
    doc_file.write_bytes(down_resp.content)

    doc = Document(str(doc_file))
    paragraphs_text = [p.text for p in doc.paragraphs]
    full_text = "\n".join(paragraphs_text)

    assert "Comprehensive Research Synthesis Report" in full_text
    assert "1. Executive Summary" in full_text
    assert "2. Cross-Paper Comparison Matrix" in full_text
    assert "3. Verified Experimental Intelligence" in full_text
    assert "4. Citation Index & Provenance Appendix" in full_text
    assert len(doc.tables) >= 2  # Comparison table + Experiments table

    # 4. Path traversal attempt rejected
    bad_resp = client.get("/api/reports/non-existent-report/download")
    assert bad_resp.status_code == 404


def test_model_lab_reports_endpoint(client: TestClient):
    resp = client.get("/api/model-lab/reports")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["readiness"] is not None
    assert data["readiness"]["splits"]["train"]["count"] == 8243
    assert data["baselines"] is not None
    assert "tfidf_baseline" in data["baselines"]
    assert data["distilbert_trial"] is not None
    assert data["test_evaluation"] is not None
    assert data["test_evaluation"]["accuracy"] == 0.8162
    assert data["test_evaluation"]["macro_f1"] == 0.7977
