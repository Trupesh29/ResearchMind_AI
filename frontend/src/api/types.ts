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

export interface ReadyResponse {
  status: 'ready' | 'degraded';
  checks: {
    database: string;
    storage: string;
    ml_environment: {
      torch_version?: string;
      cuda_available?: boolean;
      sentence_transformers_available?: boolean;
      faiss_available?: boolean;
      available?: boolean;
      detail?: string;
    } | string;
    generator: {
      provider: string;
      model: string;
      configured: boolean;
      status: string;
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
