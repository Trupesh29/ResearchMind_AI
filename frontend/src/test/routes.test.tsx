import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { App } from "../app/App";
import * as client from "../api/client";

const mockWorkspace = {
  id: "ws-test-1",
  name: "Machine Learning Research",
  description: "NLP and Transformers",
  paper_count: 2,
  ready_count: 2,
  created_at: "2026-10-15T00:00:00Z",
};

const mockPaper = {
  id: "paper-test-1",
  workspace_id: "ws-test-1",
  original_filename: "attention_is_all_you_need.pdf",
  title: "Attention Is All You Need",
  authors: ["Vaswani et al."],
  publication_year: 2017,
  keywords: ["transformer", "attention"],
  metadata_source: null,
  page_count: 15,
  size_bytes: 2048000,
  status: "ready" as const,
  quality: null,
  created_at: "2026-10-15T00:00:00Z",
  current_run_id: "run-test-1",
  published_run_id: "run-test-1",
};

describe("Role-Specific Route and Page Separation Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
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
          runtime_status: "verified",
          model_loaded: true,
        },
        generator: {
          provider: "mock",
          model: "gpt-4o-mini",
          configured: true,
          connectivity: "verified",
          status: "ready",
          message: "Ready",
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

    vi.spyOn(client.api, "listAllWorkspaces").mockResolvedValue([
      mockWorkspace,
    ]);
    vi.spyOn(client.api, "listPapers").mockResolvedValue({
      items: [mockPaper],
      next_cursor: null,
      total_count: 1,
    });
    vi.spyOn(client.api, "getPaperStatus").mockResolvedValue({
      status: "ready",
      stage: "indexing",
      progress: 1.0,
      attempt: 1,
      run_id: "run-test-1",
      current_run_id: "run-test-1",
      published_run_id: "run-test-1",
      stages: [
        { stage: "validating", status: "completed", attempt: 1 },
        { stage: "extracting", status: "completed", attempt: 1 },
        { stage: "sectioning", status: "completed", attempt: 1 },
        { stage: "chunking", status: "completed", attempt: 1 },
        { stage: "embedding", status: "completed", attempt: 1 },
        { stage: "indexing", status: "completed", attempt: 1 },
      ],
    });
    vi.spyOn(client.api, "getPaperChunks").mockResolvedValue({
      items: [
        {
          id: "chunk-1",
          paper_id: "paper-test-1",
          run_id: "run-test-1",
          chunk_index: 0,
          page_start: 1,
          page_end: 1,
          section: "Abstract",
          text: "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
          token_count: 24,
          block_ids: ["b1"],
          is_excluded: false,
          created_at: "2026-10-15T00:00:00Z",
        },
      ],
      total: 1,
      run_id: "run-test-1",
    });
    vi.spyOn(client.api, "getPaperSections").mockResolvedValue({
      items: [
        {
          id: "sec-1",
          paper_id: "paper-test-1",
          run_id: "run-test-1",
          section_index: 0,
          section: "Abstract",
          page_start: 1,
          page_end: 1,
          block_ids: ["b1"],
          created_at: "2026-10-15T00:00:00Z",
        },
      ],
      total: 1,
      run_id: "run-test-1",
    });
    vi.spyOn(client.api, "getPaperPages").mockResolvedValue({
      items: [
        {
          page_number: 1,
          char_count: 1500,
          extraction_status: "success",
          flags: [],
        },
      ],
      total_pages: 1,
      run_id: "run-test-1",
    });
  });

  it("renders LandingPage on / with product introduction and no upload controls or QC banner", async () => {
    window.history.pushState({}, "", "/");
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Evidence-First/i,
    );
    expect(
      screen.getByText(/Traceable\. Grounded\. Verified\./i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Select PDF Files/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(/Quality Center Inspection Guidance/i),
    ).not.toBeInTheDocument();
  });

  it("renders DashboardPage on /dashboard with workspace overview counts and no dropzone", async () => {
    window.history.pushState({}, "", "/dashboard");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Workspace Dashboard/i,
      );
    });
    expect(
      screen.getByText(/Overview of uploaded research documents/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Open Library/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Select PDF Files/i }),
    ).not.toBeInTheDocument();
  });

  it("renders LibraryPage on /library with upload dropzone and paper list, with no initialQualityMode banner", async () => {
    window.history.pushState({}, "", "/library");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Research Paper Library/i,
      );
    });
    expect(
      screen.getByRole("button", { name: /Select PDF Files/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText(/Quality Center Inspection Guidance/i),
    ).not.toBeInTheDocument();
  });

  it("navigates from LibraryPage to QualityCenterPage with ?paper= when Quality action is clicked", async () => {
    window.history.pushState({}, "", "/library");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    });

    const qualityBtn = screen.getByRole("button", {
      name: /Quality Center for attention_is_all_you_need\.pdf/i,
    });
    fireEvent.click(qualityBtn);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/quality");
      expect(window.location.search).toBe("?paper=paper-test-1");
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Quality Center/i,
      );
    });
  });

  it("renders QualityCenterPage on /quality with 6-stage pipeline, paper selector, and no upload dropzone", async () => {
    window.history.pushState({}, "", "/quality");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Quality Center/i,
      );
    });

    expect(screen.getByText(/6-stage ingestion pipeline/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Select PDF Files/i }),
    ).not.toBeInTheDocument();

    // Select paper from dropdown
    await waitFor(() => {
      expect(
        screen.getByLabelText(/Select Research Paper/i),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Select Research Paper/i), {
      target: { value: "paper-test-1" },
    });

    await waitFor(() => {
      expect(
        screen.getByText(/6-Stage Processing Pipeline/i),
      ).toBeInTheDocument();
      expect(screen.getByText("Validating")).toBeInTheDocument();
      expect(screen.getByText("Extracting")).toBeInTheDocument();
      expect(screen.getByText("Sectioning")).toBeInTheDocument();
      expect(screen.getByText("Chunking")).toBeInTheDocument();
      expect(screen.getByText("Embedding")).toBeInTheDocument();
      expect(screen.getByText("Indexing")).toBeInTheDocument();
    });
  });

  it("deep-links directly into QualityCenterPage with ?paper= query parameter", async () => {
    window.history.pushState({}, "", "/quality?paper=paper-test-1");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Quality Center/i,
      );
      expect(
        screen.getByText(/6-Stage Processing Pipeline/i),
      ).toBeInTheDocument();
      expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    });
  });

  it("displays honest error state when deep-linked paper does not exist", async () => {
    window.history.pushState({}, "", "/quality?paper=non-existent-id");
    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByText(/Deep-Linked Paper Not Found/i),
      ).toBeInTheDocument();
      expect(screen.getByText(/non-existent-id/i)).toBeInTheDocument();
    });
  });

  it("renders ResearchExplorerPage on /explorer with Planned Phase 5 badge and capabilities", async () => {
    window.history.pushState({}, "", "/explorer");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Research Explorer/i,
      );
      expect(
        screen.getAllByText(/Planned · Phase 5/i).length,
      ).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Two-Paper Comparison/i)).toBeInTheDocument();
      expect(screen.getByText(/Hybrid Index Retrieval/i)).toBeInTheDocument();
    });
  });

  it("renders ResearchAssistantPage on /assistant with Planned Phase 4 badge and capabilities", async () => {
    window.history.pushState({}, "", "/assistant");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Research Assistant/i,
      );
      expect(
        screen.getAllByText(/Planned · Phase 4/i).length,
      ).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Conversational Grounding/i)).toBeInTheDocument();
      expect(screen.getByText(/Explicit Abstention/i)).toBeInTheDocument();
    });
  });

  it("renders ModelLabPage on /model-lab with Planned Phase 6 badge and CLI reproducibility", async () => {
    window.history.pushState({}, "", "/model-lab");
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Model Lab/i,
      );
      expect(
        screen.getAllByText(/Planned · Phase 6/i).length,
      ).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/SciCite Intent Taxonomy/i)).toBeInTheDocument();
      expect(
        screen.getByText(/CLI-Driven Training & Reproducibility/i),
      ).toBeInTheDocument();
    });
  });

  it("displays truthful sidebar badges and highlights single active item", async () => {
    window.history.pushState({}, "", "/quality?paper=paper-test-1");
    render(<App />);

    // Verify badges in sidebar
    expect(
      screen.getAllByText(/Active · Phase 2/i).length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/Planned · Phase 4/i).length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/Planned · Phase 5/i).length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/Planned · Phase 6/i).length,
    ).toBeGreaterThanOrEqual(1);

    // Verify Quality Center is the single active nav button
    const qualityNavBtns = screen.getAllByRole("button", {
      name: /Quality Center/i,
    });
    expect(qualityNavBtns[0]).toHaveStyle({ color: "var(--blue-action)" });

    const libraryNavBtns = screen.getAllByRole("button", {
      name: /Paper Library/i,
    });
    expect(libraryNavBtns[0]).toHaveStyle({ color: "var(--text-secondary)" });
  });

  describe("Quality Center Workspace Request Fencing (P5-F3)", () => {
    it("fences workspace requests and discards late responses from previous workspace", async () => {
      const wsA = {
        id: "ws-a",
        name: "Workspace A",
        description: "Old Workspace",
        paper_count: 1,
        ready_count: 1,
        created_at: "2026-10-15T00:00:00Z",
      };
      const wsB = {
        id: "ws-b",
        name: "Workspace B",
        description: "New Workspace",
        paper_count: 1,
        ready_count: 1,
        created_at: "2026-10-15T00:00:00Z",
      };

      const paperA = {
        ...mockPaper,
        id: "paper-a",
        workspace_id: "ws-a",
        title: "Paper from Stale Workspace A",
      };
      const paperB = {
        ...mockPaper,
        id: "paper-b",
        workspace_id: "ws-b",
        title: "Paper from Fresh Workspace B",
      };

      vi.spyOn(client.api, "listAllWorkspaces").mockResolvedValue([wsA, wsB]);

      let resolveWsA: (value: any) => void = () => {};
      const pendingPromiseA = new Promise((resolve) => {
        resolveWsA = resolve;
      });

      vi.spyOn(client.api, "listPapers").mockImplementation(
        (wsId: string, _options?: any) => {
          if (wsId === "ws-a") {
            return pendingPromiseA as any;
          }
          if (wsId === "ws-b") {
            return Promise.resolve({
              items: [paperB],
              next_cursor: null,
              total_count: 1,
            });
          }
          return Promise.resolve({
            items: [],
            next_cursor: null,
            total_count: 0,
          });
        },
      );

      window.history.pushState({}, "", "/quality");
      render(<App />);

      // Workspace selector should be present
      await waitFor(() => {
        expect(screen.getByLabelText("Select Workspace")).toBeInTheDocument();
      });

      // Switch to Workspace B while A is still pending
      const wsSelect = screen.getByLabelText("Select Workspace");
      fireEvent.change(wsSelect, { target: { value: "ws-b" } });

      // Workspace B resolves and displays Paper B
      await waitFor(() => {
        expect(
          screen.getByText(/Paper from Fresh Workspace B/i),
        ).toBeInTheDocument();
      });

      // Now resolve the delayed Workspace A request
      resolveWsA({
        items: [paperA],
        next_cursor: null,
        total_count: 1,
      });

      // Wait a moment and confirm Paper A NEVER overwrites Paper B
      await new Promise((r) => setTimeout(r, 50));
      expect(
        screen.queryByText(/Paper from Stale Workspace A/i),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/Paper from Fresh Workspace B/i),
      ).toBeInTheDocument();
    });

    it("ignores errors from superseded workspace requests without displaying error banner", async () => {
      const wsA = {
        id: "ws-a",
        name: "Workspace A",
        description: "Old Workspace",
        paper_count: 1,
        ready_count: 1,
        created_at: "2026-10-15T00:00:00Z",
      };
      const wsB = {
        id: "ws-b",
        name: "Workspace B",
        description: "New Workspace",
        paper_count: 1,
        ready_count: 1,
        created_at: "2026-10-15T00:00:00Z",
      };

      const paperB = {
        ...mockPaper,
        id: "paper-b",
        workspace_id: "ws-b",
        title: "Paper from Fresh Workspace B",
      };

      vi.spyOn(client.api, "listAllWorkspaces").mockResolvedValue([wsA, wsB]);

      let rejectWsA: (reason?: any) => void = () => {};
      const pendingPromiseA = new Promise((_, reject) => {
        rejectWsA = reject;
      });

      vi.spyOn(client.api, "listPapers").mockImplementation((wsId: string) => {
        if (wsId === "ws-a") {
          return pendingPromiseA as any;
        }
        if (wsId === "ws-b") {
          return Promise.resolve({
            items: [paperB],
            next_cursor: null,
            total_count: 1,
          });
        }
        return Promise.resolve({
          items: [],
          next_cursor: null,
          total_count: 0,
        });
      });

      window.history.pushState({}, "", "/quality");
      render(<App />);

      await waitFor(() => {
        expect(screen.getByLabelText("Select Workspace")).toBeInTheDocument();
      });

      // Switch to Workspace B
      const wsSelect = screen.getByLabelText("Select Workspace");
      fireEvent.change(wsSelect, { target: { value: "ws-b" } });

      await waitFor(() => {
        expect(
          screen.getByText(/Paper from Fresh Workspace B/i),
        ).toBeInTheDocument();
      });

      // Reject A with network error
      rejectWsA(new Error("Workspace A connection dropped"));

      await new Promise((r) => setTimeout(r, 50));
      // No error banner should be displayed
      expect(
        screen.queryByText(/Workspace A connection dropped/i),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Failed to load papers for workspace/i),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/Paper from Fresh Workspace B/i),
      ).toBeInTheDocument();
    });

    it("clears inspection data, selection and URL paper param on workspace switch", async () => {
      const wsA = {
        id: "ws-a",
        name: "Workspace A",
        description: "Old Workspace",
        paper_count: 1,
        ready_count: 1,
        created_at: "2026-10-15T00:00:00Z",
      };
      const wsB = {
        id: "ws-b",
        name: "Workspace B",
        description: "New Workspace",
        paper_count: 0,
        ready_count: 0,
        created_at: "2026-10-15T00:00:00Z",
      };

      vi.spyOn(client.api, "listAllWorkspaces").mockResolvedValue([wsA, wsB]);
      vi.spyOn(client.api, "listPapers").mockImplementation((wsId: string) => {
        if (wsId === "ws-a") {
          return Promise.resolve({
            items: [mockPaper],
            next_cursor: null,
            total_count: 1,
          });
        }
        return Promise.resolve({
          items: [],
          next_cursor: null,
          total_count: 0,
        });
      });

      window.history.pushState({}, "", "/quality?paper=paper-test-1");
      render(<App />);

      // Initially paper is loaded and selected
      await waitFor(() => {
        expect(
          screen.getByText("Attention Is All You Need"),
        ).toBeInTheDocument();
      });

      // Switch workspace to B
      const wsSelect = screen.getByLabelText("Select Workspace");
      fireEvent.change(wsSelect, { target: { value: "ws-b" } });

      // Invariant: ?paper= is removed from URL and old paper is not shown
      await waitFor(() => {
        expect(window.location.search).not.toContain("paper=");
        expect(
          screen.queryByText("Attention Is All You Need"),
        ).not.toBeInTheDocument();
      });
    });
  });
});
