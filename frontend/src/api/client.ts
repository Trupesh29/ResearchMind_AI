import { ApiErrorDetail, HealthResponse, ReadyResponse, PublicConfigResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiClientError extends Error {
  public code: string;
  public details: Record<string, any>;
  public requestId?: string;
  public statusCode?: number;

  constructor(error: ApiErrorDetail, statusCode?: number) {
    super(error.message);
    this.name = 'ApiClientError';
    this.code = error.code;
    this.details = error.details || {};
    this.requestId = error.request_id;
    this.statusCode = statusCode;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errorData: any = null;
      try {
        errorData = await res.json();
      } catch {
        // Response was not JSON
      }

      if (errorData && errorData.error) {
        throw new ApiClientError(errorData.error, res.status);
      }

      throw new ApiClientError(
        {
          code: `HTTP_${res.status}`,
          message: res.statusText || 'An error occurred during the request.',
        },
        res.status
      );
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiClientError) {
      throw err;
    }
    // Network or client-side connection error
    throw new ApiClientError({
      code: 'NETWORK_ERROR',
      message: 'Unable to connect to the ResearchMind API server. Please ensure the backend is running.',
      details: { original_error: err?.message || String(err) },
    });
  }
}

export const api = {
  getHealth: () => request<HealthResponse>('/health'),
  getReady: () => request<ReadyResponse>('/ready'),
  getPublicConfig: () => request<PublicConfigResponse>('/config/public'),
};
