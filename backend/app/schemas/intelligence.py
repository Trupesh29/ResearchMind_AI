from typing import Literal
from pydantic import BaseModel, Field


class SectionItem(BaseModel):
    section_index: int
    section_title: str
    heading: str | None = None
    page_start: int
    page_end: int
    chunk_count: int
    quality_status: Literal["complete", "sparse", "empty"] = "complete"
    preview_text: str = ""


class PaperSectionsResponse(BaseModel):
    paper_id: str
    paper_title: str
    total_sections: int
    sections: list[SectionItem]


class SummaryCitation(BaseModel):
    citation_id: int
    paper_id: str
    paper_title: str
    page_number: int
    section_title: str
    quote: str


class SummaryPoint(BaseModel):
    point_id: int
    heading: str
    content: str
    citations: list[SummaryCitation] = Field(default_factory=list)


SummaryStyle = Literal["simple", "technical", "methodology", "results"]


class SummaryRequest(BaseModel):
    paper_id: str
    style: SummaryStyle = "simple"


class PaperSummaryResponse(BaseModel):
    paper_id: str
    paper_title: str
    style: SummaryStyle
    overview: str
    points: list[SummaryPoint]
    cached: bool = False
    generated_at: str


class ComparisonDimensionCell(BaseModel):
    dimension_id: str
    dimension_name: str
    paper_a_claim: str
    paper_b_claim: str
    paper_a_citations: list[SummaryCitation] = Field(default_factory=list)
    paper_b_citations: list[SummaryCitation] = Field(default_factory=list)
    comparable_status: Literal["comparable", "partially_comparable", "non_comparable"] = "comparable"
    synthesis_notes: str


class ComparisonMatrixRequest(BaseModel):
    workspace_id: str
    paper_a_id: str
    paper_b_id: str


class ComparisonMatrixResponse(BaseModel):
    workspace_id: str
    paper_a_id: str
    paper_a_title: str
    paper_b_id: str
    paper_b_title: str
    dimensions: list[ComparisonDimensionCell]
    overall_synthesis: str
    comparability_summary: str


class ExperimentMetric(BaseModel):
    metric_name: str
    value: str
    unit: str | None = None
    raw_excerpt: str


class ExperimentRecord(BaseModel):
    experiment_id: str
    paper_id: str
    task: str
    method: str
    conditions: dict[str, str] = Field(default_factory=dict)
    metrics: list[ExperimentMetric] = Field(default_factory=list)
    limitations: str
    provenance: SummaryCitation | None = None


class ExperimentExtractRequest(BaseModel):
    paper_id: str


class ExperimentExtractResponse(BaseModel):
    paper_id: str
    paper_title: str
    status: Literal["experiments_extracted", "no_experiments_detected"]
    experiments: list[ExperimentRecord] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    workspace_id: str
    title: str = "Research Intelligence Synthesis Report"
    paper_ids: list[str]
    summary_style: SummaryStyle = "technical"
    include_comparison: bool = True
    include_experiments: bool = True


class ReportStatusResponse(BaseModel):
    report_id: str
    workspace_id: str
    title: str
    summary_style: str
    status: Literal["queued", "generating", "completed", "failed"]
    file_size_bytes: int | None = None
    created_at: str
    download_url: str


class ModelLabReportsResponse(BaseModel):
    readiness: dict | None = None
    baselines: dict | None = None
    distilbert_trial: dict | None = None
    test_evaluation: dict | None = None
