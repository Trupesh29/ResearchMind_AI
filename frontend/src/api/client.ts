import {
  ApiErrorDetail,
  HealthResponse,
  PaperItem,
  PaperListResponse,
  PaperStatusResponse,
  PaperUploadBatchResponse,
  PublicConfigResponse,
  ReadyResponse,
  WorkspaceCreatePayload,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceListResponse,
  WorkspaceUpdatePayload,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiClientError extends Error {
  public code: string;
  public details: Record<string, any>;
  public requestId?: string;
  public statusCode?: number;

  constructor(error: ApiErrorDetail, statusCode?: number) {
    super(error.message);
    this.name = "ApiClientError";
    this.code = error.code;
    this.details = error.details || {};
    this.requestId = error.request_id;
    this.statusCode = statusCode;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  // Handle JSON vs FormData Content-Type
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!isFormData && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
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
          message: res.statusText || "An error occurred during the request.",
        },
        res.status,
      );
    }

    // Support empty 204 No Content responses safely
    if (res.status === 204) {
      return null as T;
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiClientError) {
      throw err;
    }
    // Network or client-side connection error
    throw new ApiClientError({
      code: "NETWORK_ERROR",
      message:
        "Unable to connect to the ResearchMind API server. Please ensure the backend is running.",
      details: { original_error: err?.message || String(err) },
    });
  }
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getReady: () => request<ReadyResponse>("/ready"),
  getPublicConfig: () => request<PublicConfigResponse>("/config/public"),

  // Workspaces
  listWorkspaces: (cursor?: string | null, limit: number = 50) => {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString();
    return request<WorkspaceListResponse>(`/workspaces${qs ? `?${qs}` : ""}`);
  },
  listAllWorkspaces: async (): Promise<WorkspaceItem[]> => {
    let all: WorkspaceItem[] = [];
    let cursor: string | null = null;
    do {
      const res = await api.listWorkspaces(cursor, 100);
      all = all.concat(res.items);
      cursor = res.next_cursor;
    } while (cursor);
    return all;
  },
  getWorkspace: (id: string) => request<WorkspaceDetail>(`/workspaces/${id}`),
  createWorkspace: (data: WorkspaceCreatePayload) =>
    request<WorkspaceItem>("/workspaces", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateWorkspace: (id: string, data: WorkspaceUpdatePayload) =>
    request<WorkspaceItem>(`/workspaces/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteWorkspace: (id: string) =>
    request<void>(`/workspaces/${id}`, {
      method: "DELETE",
    }),

  // Papers
  uploadPapers: (workspaceId: string, files: File[]) => {
    const formData = new FormData();
    formData.append("workspace_id", workspaceId);
    for (const file of files) {
      formData.append("files", file);
    }
    return request<PaperUploadBatchResponse>("/papers", {
      method: "POST",
      body: formData,
    });
  },
  listPapers: (
    workspaceId: string,
    options: {
      status?: string;
      q?: string;
      cursor?: string | null;
      limit?: number;
    } = {},
  ) => {
    const params = new URLSearchParams();
    params.set("workspace_id", workspaceId);
    if (options.status) params.set("status", options.status);
    if (options.q && options.q.trim()) params.set("q", options.q.trim());
    if (options.cursor) params.set("cursor", options.cursor);
    if (options.limit) params.set("limit", String(options.limit));
    return request<PaperListResponse>(`/papers?${params.toString()}`);
  },
  getPaper: (id: string) => request<PaperItem>(`/papers/${id}`),
  getPaperStatus: (id: string) =>
    request<PaperStatusResponse>(`/papers/${id}/status`),
  getPaperFileUrl: (id: string) => `${API_BASE}/papers/${id}/file`,
  deletePaper: (id: string) =>
    request<void>(`/papers/${id}`, {
      method: "DELETE",
    }),
};
