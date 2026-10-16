import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { App } from "../app/App";
import * as client from "../api/client";

describe("App Shell Navigation and History", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, "", "/");
    vi.spyOn(client.api, "getReady").mockResolvedValue({
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
  });

  it("renders landing page on root / and navigates to dashboard", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Evidence-First/i,
    );

    const openWorkspaceBtn = screen.getByRole("button", {
      name: /Open Workspace/i,
    });
    fireEvent.click(openWorkspaceBtn);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/dashboard");
      expect(screen.getByText(/Workspace Dashboard/i)).toBeInTheDocument();
    });
  });

  it("navigates to library and responds to popstate back/forward", async () => {
    render(<App />);

    // Click Library nav in desktop sidebar
    const libraryButtons = screen.getAllByRole("button", { name: /Library/i });
    fireEvent.click(libraryButtons[0]);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/library");
      expect(screen.getByText(/Research Paper Library/i)).toBeInTheDocument();
    });

    // Simulate browser back button
    window.history.pushState({}, "", "/dashboard");
    fireEvent(window, new PopStateEvent("popstate"));

    await waitFor(() => {
      expect(screen.getByText(/Workspace Dashboard/i)).toBeInTheDocument();
    });
  });

  it("renders 404 page for unknown route with go home recovery", async () => {
    window.history.pushState({}, "", "/unknown-test-path");
    render(<App />);

    expect(screen.getByText(/Page Not Found/i)).toBeInTheDocument();
    const returnBtn = screen.getByRole("button", {
      name: /Return to Dashboard/i,
    });
    fireEvent.click(returnBtn);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/dashboard");
      expect(screen.getByText(/Workspace Dashboard/i)).toBeInTheDocument();
    });
  });
});
