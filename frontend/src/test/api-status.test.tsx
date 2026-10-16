import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { App } from "../app/App";
import * as client from "../api/client";

describe("Frontend API Loading, Status, and Error Handling", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, "", "/dashboard");
  });

  it("renders operational state when ready and config return successfully", async () => {
    vi.spyOn(client.api, "getReady").mockResolvedValue({
      status: "ready",
      checks: {
        database: {
          status: "healthy",
          message: "Connected and schema verified",
        },
        storage: { status: "healthy", message: "Storage directory writable" },
        ml_environment: {
          torch_installed: true,
          sentence_transformers_installed: true,
          faiss_installed: true,
          runtime_status: "unverified",
          model_loaded: false,
        },
        generator: {
          provider: "mock",
          model: "gpt-4o-mini",
          configured: true,
          connectivity: "unverified",
          status: "mock_configured_unverified",
          message: "Mock provider configured",
        },
      },
    });
    vi.spyOn(client.api, "getPublicConfig").mockResolvedValue({
      project_name: "ResearchMind AI",
      api_version: "0.1.0",
      environment: "development",
      max_upload_mb: 25,
      auth_enabled: false,
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
      generator_provider: "mock",
      default_user: {
        email: "local@researchmind.ai",
        display_name: "Local Researcher",
      },
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/System Operational/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Local Researcher Workspace/i),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Operational & Schema Verified/i),
      ).toBeInTheDocument();
      expect(screen.getByText(/Writable \(Verified\)/i)).toBeInTheDocument();
    });
  });

  it("handles degraded status when readiness check fails", async () => {
    vi.spyOn(client.api, "getReady").mockResolvedValue({
      status: "degraded",
      checks: {
        database: {
          status: "unhealthy",
          message: "Database schema not initialized or migration pending",
        },
        storage: { status: "healthy", message: "Storage directory writable" },
        ml_environment: {
          torch_installed: true,
          sentence_transformers_installed: true,
          faiss_installed: true,
          runtime_status: "unverified",
          model_loaded: false,
        },
        generator: {
          provider: "mock",
          model: "gpt-4o-mini",
          configured: true,
          connectivity: "unverified",
          status: "mock_configured_unverified",
          message: "Mock provider configured",
        },
      },
    });
    vi.spyOn(client.api, "getPublicConfig").mockResolvedValue({
      project_name: "ResearchMind AI",
      api_version: "0.1.0",
      environment: "development",
      max_upload_mb: 25,
      auth_enabled: false,
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
      generator_provider: "mock",
      default_user: {
        email: "local@researchmind.ai",
        display_name: "Local Researcher",
      },
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Offline \/ Degraded/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Database schema not initialized/i),
      ).toBeInTheDocument();
    });
  });

  it("displays offline error banner on network failure and allows retry", async () => {
    const getReadyMock = vi
      .spyOn(client.api, "getReady")
      .mockRejectedValueOnce(
        new client.ApiClientError({
          code: "NETWORK_ERROR",
          message: "Unable to connect to the ResearchMind API server.",
        }),
      )
      .mockResolvedValueOnce({
        status: "ready",
        checks: {
          database: { status: "healthy", message: "Connected" },
          storage: { status: "healthy", message: "Writable" },
          ml_environment: {
            torch_installed: true,
            sentence_transformers_installed: true,
            faiss_installed: true,
            runtime_status: "unverified",
            model_loaded: false,
          },
          generator: {
            provider: "mock",
            model: "gpt-4o-mini",
            configured: true,
            connectivity: "unverified",
            status: "mock_configured_unverified",
            message: "Mock provider configured",
          },
        },
      });

    vi.spyOn(client.api, "getPublicConfig").mockResolvedValue({
      project_name: "ResearchMind AI",
      api_version: "0.1.0",
      environment: "development",
      max_upload_mb: 25,
      auth_enabled: false,
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
      generator_provider: "mock",
      default_user: {
        email: "local@researchmind.ai",
        display_name: "Local Researcher",
      },
    });

    render(<App />);

    // Expect alert banner
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Backend Connection Error/i)).toBeInTheDocument();
    });

    // Click retry
    const retryBtn = screen.getByRole("button", { name: /Retry Connection/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.getByText(/System Operational/i)).toBeInTheDocument();
    });

    expect(getReadyMock).toHaveBeenCalledTimes(2);
  });
});
