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
