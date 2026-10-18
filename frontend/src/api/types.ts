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
  progress: number;
  attempt: number;
  error?: string | null;
  stages?: PaperStageDetail[];
  run_id?: string | null;
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
