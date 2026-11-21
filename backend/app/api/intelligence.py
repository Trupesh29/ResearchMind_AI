from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import Settings, get_settings
from backend.app.db.models import Report, User, Workspace
from backend.app.db.session import get_db
from backend.app.schemas.intelligence import (
    ComparisonMatrixRequest,
    ComparisonMatrixResponse,
    ExperimentExtractRequest,
    ExperimentExtractResponse,
    ModelLabReportsResponse,
    PaperSectionsResponse,
    PaperSummaryResponse,
    ReportGenerateRequest,
    ReportStatusResponse,
    SummaryRequest,
)
from backend.app.services.intelligence_service import (
    compare_papers,
    download_docx_report,
    extract_experiments,
    generate_docx_report,
    generate_paper_summary,
    get_model_lab_reports,
    get_paper_sections,
)

router = APIRouter(tags=["intelligence"])


@router.get("/explorer/papers/{paper_id}/sections", response_model=PaperSectionsResponse)
def get_sections(
    paper_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve extracted sections with chunk counts, quality status, and page coordinates."""
    return get_paper_sections(db, paper_id, user.id)


@router.post("/explorer/summaries", response_model=PaperSummaryResponse)
def get_summary(
    req: SummaryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate or retrieve cached structured summary across simple, technical, methodology, or results styles."""
    return generate_paper_summary(db, req.paper_id, req.style, user.id)


@router.post("/comparison/matrix", response_model=ComparisonMatrixResponse)
def get_comparison(
    req: ComparisonMatrixRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Construct a four-dimensional comparative matrix between two papers with explicit citations."""
    return compare_papers(db, req.workspace_id, req.paper_a_id, req.paper_b_id, user.id)


@router.post("/experiments/extract", response_model=ExperimentExtractResponse)
def get_experiments(
    req: ExperimentExtractRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Extract structured experimental protocols, conditions, metrics, and page-level provenance."""
    return extract_experiments(db, req.paper_id, user.id)


@router.post("/reports/generate", response_model=ReportStatusResponse)
def create_report(
    req: ReportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Generate a server-side DOCX research intelligence report."""
    return generate_docx_report(
        db,
        workspace_id=req.workspace_id,
        title=req.title,
        paper_ids=req.paper_ids,
        summary_style=req.summary_style,
        include_comparison=req.include_comparison,
        include_experiments=req.include_experiments,
        user_id=user.id,
        data_dir=settings.DATA_DIR,
    )


@router.get("/reports/{report_id}", response_model=ReportStatusResponse)
def get_report_status(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check report generation status and metadata."""
    stmt = (
        select(Report)
        .join(Workspace, Report.workspace_id == Workspace.id)
        .where(Report.id == report_id, Workspace.user_id == user.id)
    )
    report = db.scalar(stmt)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportStatusResponse(
        report_id=report.id,
        workspace_id=report.workspace_id,
        title=report.title,
        summary_style=report.summary_style,
        status=report.status,  # type: ignore
        file_size_bytes=report.file_size_bytes,
        created_at=report.created_at,
        download_url=f"/api/reports/{report.id}/download",
    )


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Download generated research report in DOCX format with traversal protection."""
    return download_docx_report(db, report_id, user.id, data_dir=settings.DATA_DIR)


@router.get("/model-lab/reports", response_model=ModelLabReportsResponse)
def get_model_lab_data():
    """Retrieve persisted SciCite classification experiment reports, metrics, and curves."""
    return get_model_lab_reports()
