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

export interface PaperItem {
  id: string;
  workspace_id: string;
  original_filename: string;
  title: string | null;
  authors: string[];
  publication_year: number | null;
  keywords: string[];
  metadata_source: Record<string, string> | null;
  page_count: number | null;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  quality: Record<string, any> | null;
  created_at: string;
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

export interface PaperStatusResponse {
  status: string;
  stage: string;
  progress: number;
  attempt: number;
  error?: string | null;
}
