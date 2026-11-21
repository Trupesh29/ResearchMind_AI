export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, any>;
  request_id?: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export interface HealthResponse {
  status: string;
}

export interface CheckStatus {
  status: "healthy" | "unhealthy" | "unknown";
  message: string;
}

export interface ReadyResponse {
  status: "ready" | "degraded";
  checks: {
    database: CheckStatus;
    storage: CheckStatus;
    ml_environment: {
      torch_installed: boolean;
      sentence_transformers_installed: boolean;
      faiss_installed: boolean;
      runtime_status: string;
      model_loaded: boolean;
    };
    generator: {
      provider: string;
      model: string;
      configured: boolean;
      connectivity: string;
      status: string;
      message: string;
    };
  };
}

export interface PublicConfigResponse {
  project_name: string;
  api_version: string;
  environment: string;
  max_upload_mb: number;
  auth_enabled: boolean;
  embedding_model: string;
  generator_provider: string;
  default_user: {
    email: string;
    display_name: string;
  };
}

export interface WorkspaceItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  paper_count: number;
  ready_count: number;
}

export interface WorkspaceDetail extends WorkspaceItem {
  active_index?: {
    model_name: string;
    version: number;
  } | null;
}

export interface WorkspaceListResponse {
  items: WorkspaceItem[];
  next_cursor: string | null;
  total_count: number;
}

export interface WorkspaceCreatePayload {
  name: string;
  description?: string;
}

export interface WorkspaceUpdatePayload {
  name?: string;
  description?: string;
}

export interface ProvenanceDetail {
  source: string;
  file_property?: string;
  page_number?: number;
  block_id?: string;
  evidence?: string;
}

export interface PaperItem {
  id: string;
  workspace_id: string;
  original_filename: string;
  title: string | null;
  authors: string[];
  publication_year: number | null;
  keywords: string[];
  metadata_source: Record<string, ProvenanceDetail | string> | null;
  page_count: number | null;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  quality: Record<string, any> | null;
  created_at: string;
  current_run_id?: string | null;
  published_run_id?: string | null;
}

export interface PaperListResponse {
  items: PaperItem[];
  next_cursor: string | null;
  total_count: number;
}

export interface PaperUploadSuccessItem {
  id: string;
  original_filename: string;
  status: string;
}

export interface PaperUploadDuplicateItem {
  original_filename: string;
  existing_paper_id: string;
}

export interface PaperUploadRejectedItem {
  original_filename: string;
  code: string;
  message: string;
}

export interface PaperUploadBatchResponse {
  papers: PaperUploadSuccessItem[];
  duplicates: PaperUploadDuplicateItem[];
  rejected: PaperUploadRejectedItem[];
}

export interface PaperStageDetail {
  stage: string;
  status: string;
  attempt: number;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
}

export interface PaperStatusResponse {
  status: string;
  stage: string;
  substate?: string | null;
  progress: number;
  attempt: number;
  error?: string | null;
  stages?: PaperStageDetail[];
  run_id?: string | null;
  current_run_id?: string | null;
  published_run_id?: string | null;
  is_stale?: boolean;
}

export interface PageSummaryItem {
  page_number: number;
  char_count: number;
  extraction_status: string;
  flags: string[];
}

export interface PagesListResponse {
  items: PageSummaryItem[];
  total_pages: number;
  run_id?: string | null;
  is_stale?: boolean;
}

export interface PageBlockItem {
  id: string;
  bbox: [number, number, number, number];
  text: string;
  text_hash: string;
}

export interface PageBlocksResponse {
  page_number: number;
  width?: number | null;
  height?: number | null;
  rotation?: number | null;
  blocks: PageBlockItem[];
  run_id?: string | null;
  is_stale?: boolean;
}

export interface ChunkItem {
  id: string;
  paper_id: string;
  run_id: string;
  chunk_index: number;
  page_start: number;
  page_end: number;
  section: string;
  text: string;
  token_count: number;
  block_ids: string[];
  is_excluded: boolean;
  tokenizer_name?: string | null;
  tokenizer_revision?: string | null;
  created_at: string;
}

export interface ChunksListResponse {
  items: ChunkItem[];
  total: number;
  run_id?: string | null;
  is_stale?: boolean;
  next_cursor?: string | null;
}

export interface SectionItem {
  id: string;
  paper_id: string;
  run_id: string;
  section_index: number;
  section: string;
  heading?: string | null;
  page_start: number;
  page_end: number;
  text?: string | null;
  block_ids: string[];
  created_at: string;
}

export interface SectionsListResponse {
  items: SectionItem[];
  total: number;
  run_id?: string | null;
  is_stale?: boolean;
}


export interface RetrievalPassage {
  chunk_id: string;
  paper_id: string;
  paper_title?: string | null;
  section: string;
  heading?: string | null;
  page_start: number;
  page_end: number;
  text: string;
  score: number;
  rank: number;
  dense_rank?: number | null;
  dense_score?: number | null;
  sparse_rank?: number | null;
  sparse_score?: number | null;
  index_version: number;
  model_name: string;
  model_revision: string;
}

export interface RetrievalDiagnostics {
  total_eligible_chunks: number;
  dense_candidate_count: number;
  sparse_candidate_count: number;
  fused_count: number;
  timings: {
    dense_ms: number;
    sparse_ms: number;
    fusion_ms: number;
    total_ms: number;
  };
  index_version: number;
  index_id: string;
  mode: string;
  score_explanation: string;
}

export interface RetrievalQueryData {
  query: string;
  workspace_id: string;
  selected_paper_ids: string[];
  passages: RetrievalPassage[];
  diagnostics: RetrievalDiagnostics;
}

export interface RetrievalQueryResponse {
  data: RetrievalQueryData;
  error?: ApiErrorDetail | null;
}

export interface CitationItem {
  citation_id: string;
  passage_id: string;
  paper_id: string;
  paper_title: string;
  page_number: number;
  section_title?: string | null;
  exact_quote: string;
  score: number;
}

export interface ResearchQueryRequest {
  workspace_id: string;
  query: string;
  selected_paper_ids: string[];
  mode?: "concise" | "detailed" | "comparison";
  conversation_id?: string | null;
}

export interface ResearchAssistantResponse {
  conversation_id: string;
  message_id: string;
  query: string;
  rewritten_query?: string | null;
  answer: string;
  is_abstention: boolean;
  citations: CitationItem[];
  retrieved_passages: RetrievalPassage[];
  timings: {
    retrieval_ms: number;
    generation_ms: number;
    total_ms: number;
  };
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  is_abstention: boolean;
  citations: CitationItem[];
  selected_paper_ids: string[];
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  workspace_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  workspace_id: string;
  title: string;
  messages: MessageResponse[];
  created_at: string;
  updated_at: string;
}

export interface ExplorerSectionItem {
  section_index: number;
  section_title: string;
  heading?: string | null;
  page_start: number;
  page_end: number;
  chunk_count: number;
  quality_status: "complete" | "sparse" | "empty";
  preview_text: string;
}

export interface PaperSectionsResponse {
  paper_id: string;
  paper_title: string;
  total_sections: number;
  sections: ExplorerSectionItem[];
}

export interface SummaryCitation {
  citation_id: number;
  paper_id: string;
  paper_title: string;
  page_number: number;
  section_title: string;
  quote: string;
}

export interface SummaryPoint {
  point_id: number;
  heading: string;
  content: string;
  citations: SummaryCitation[];
}

export type SummaryStyle = "simple" | "technical" | "methodology" | "results";

export interface PaperSummaryResponse {
  paper_id: string;
  paper_title: string;
  style: SummaryStyle;
  overview: string;
  points: SummaryPoint[];
  cached: boolean;
  generated_at: string;
}

export interface ComparisonDimensionCell {
  dimension_id: string;
  dimension_name: string;
  paper_a_claim: string;
  paper_b_claim: string;
  paper_a_citations: SummaryCitation[];
  paper_b_citations: SummaryCitation[];
  comparable_status: "comparable" | "partially_comparable" | "non_comparable";
  synthesis_notes: string;
}

export interface ComparisonMatrixResponse {
  workspace_id: string;
  paper_a_id: string;
  paper_a_title: string;
  paper_b_id: string;
  paper_b_title: string;
  dimensions: ComparisonDimensionCell[];
  overall_synthesis: string;
  comparability_summary: string;
}

export interface ExperimentMetric {
  metric_name: string;
  value: string;
  unit?: string | null;
  raw_excerpt: string;
}

export interface ExperimentRecord {
  experiment_id: string;
  paper_id: string;
  task: string;
  method: string;
  conditions: Record<string, string>;
  metrics: ExperimentMetric[];
  limitations: string;
  provenance?: SummaryCitation | null;
}

export interface ExperimentExtractResponse {
  paper_id: string;
  paper_title: string;
  status: "experiments_extracted" | "no_experiments_detected";
  experiments: ExperimentRecord[];
}

export interface ReportStatusResponse {
  report_id: string;
  workspace_id: string;
  title: string;
  summary_style: string;
  status: "queued" | "generating" | "completed" | "failed";
  file_size_bytes?: number | null;
  created_at: string;
  download_url: string;
}

export interface ModelLabReportsResponse {
  readiness?: Record<string, any> | null;
  baselines?: Record<string, any> | null;
  distilbert_trial?: Record<string, any> | null;
  test_evaluation?: Record<string, any> | null;
}
