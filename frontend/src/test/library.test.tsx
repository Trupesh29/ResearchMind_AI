import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LibraryPage } from "../pages/LibraryPage";
import * as client from "../api/client";
import {
  WorkspaceItem,
  PaperItem,
  PaperUploadBatchResponse,
} from "../api/types";

const mockWorkspaces: WorkspaceItem[] = [
  {
    id: "ws-1",
    name: "Quantum Computing",
    description: "Quantum algorithms and physics",
    created_at: "2026-10-16T12:00:00Z",
    paper_count: 2,
    ready_count: 0,
  },
  {
    id: "ws-2",
    name: "Neural Networks",
    description: "Deep learning research",
    created_at: "2026-10-15T12:00:00Z",
    paper_count: 0,
    ready_count: 0,
  },
];

const mockPapers: PaperItem[] = [
  {
    id: "paper-1",
    workspace_id: "ws-1",
    original_filename: "quantum_supremacy.pdf",
    title: "Quantum Supremacy Experiment",
    authors: ["John Preskill"],
    publication_year: 2024,
    keywords: ["quantum", "algorithms"],
    metadata_source: null,
    page_count: 12,
    size_bytes: 1048576,
    status: "uploaded",
    quality: null,
    created_at: "2026-10-16T12:30:00Z",
  },
  {
    id: "paper-2",
    workspace_id: "ws-1",
    original_filename: "error_mitigation.pdf",
    title: "Quantum Error Mitigation",
    authors: ["Alice Bob"],
    publication_year: 2025,
    keywords: ["error", "mitigation"],
    metadata_source: null,
    page_count: 8,
    size_bytes: 524288,
    status: "uploaded",
    quality: null,
    created_at: "2026-10-16T13:00:00Z",
  },
];

describe("LibraryPage Integration and Component Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();

    vi.spyOn(client.api, "listWorkspaces").mockResolvedValue({
      items: mockWorkspaces,
      next_cursor: null,
      total_count: 2,
    });

    vi.spyOn(client.api, "listPapers").mockResolvedValue({
      items: mockPapers,
      next_cursor: null,
      total_count: 2,
    });
  });

  it("renders workspace selector and document list", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Quantum Computing")).toBeInTheDocument();
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(screen.getByText("Quantum Error Mitigation")).toBeInTheDocument();
    });
  });

  it("filters documents when searching", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search papers/i);
    fireEvent.change(searchInput, { target: { value: "error" } });

    await waitFor(() => {
      expect(client.api.listPapers).toHaveBeenCalledWith(
        "ws-1",
        expect.objectContaining({ q: "error" }),
      );
    });
  });

  it("displays empty results state when search query matches no documents", async () => {
    vi.spyOn(client.api, "listPapers").mockResolvedValue({
      items: [],
      next_cursor: null,
      total_count: 0,
    });

    render(<LibraryPage />);

    const searchInput = screen.getByPlaceholderText(/Search papers/i);
    fireEvent.change(searchInput, {
      target: { value: "nonexistent_query_xyz" },
    });

    await waitFor(() => {
      expect(
        screen.getByText("No matching documents found"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /No papers match the search term "nonexistent_query_xyz"/i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("restores all documents when search query is cleared", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search papers/i);
    fireEvent.change(searchInput, { target: { value: "error" } });

    await waitFor(() => {
      expect(client.api.listPapers).toHaveBeenCalledWith(
        "ws-1",
        expect.objectContaining({ q: "error" }),
      );
    });

    // Clear search query
    fireEvent.change(searchInput, { target: { value: "" } });

    await waitFor(() => {
      expect(client.api.listPapers).toHaveBeenCalledWith(
        "ws-1",
        expect.objectContaining({ q: "" }),
      );
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(screen.getByText("Quantum Error Mitigation")).toBeInTheDocument();
    });
  });

  it("opens PDF viewer modal when View button is clicked", async () => {
    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    const viewButton = screen.getByRole("button", {
      name: `View ${mockPapers[0].original_filename}`,
    });
    fireEvent.click(viewButton);

    await waitFor(() => {
      expect(
        screen.getByRole("dialog", { name: /PDF Viewer/i }),
      ).toBeInTheDocument();
      expect(screen.getAllByText(/12 pages/i).length).toBeGreaterThanOrEqual(2);
    });

    // Close viewer via Escape
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", { name: /PDF Viewer/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("prompts for delete confirmation and calls deletePaper API upon confirm", async () => {
    const deleteSpy = vi
      .spyOn(client.api, "deletePaper")
      .mockResolvedValue(undefined);

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole("button", {
      name: `Delete ${mockPapers[0].original_filename}`,
    });
    fireEvent.click(deleteBtn);

    // Check alertdialog is opened
    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
      expect(
        screen.getByText(/Are you sure you want to delete/i),
      ).toBeInTheDocument();
    });

    // Confirm deletion
    const confirmBtn = screen.getByRole("button", { name: "Delete Paper" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith("paper-1");
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
  });

  it("cancels paper deletion without calling deletePaper", async () => {
    const deleteSpy = vi
      .spyOn(client.api, "deletePaper")
      .mockResolvedValue(undefined);

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole("button", {
      name: `Delete ${mockPapers[0].original_filename}`,
    });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(deleteSpy).not.toHaveBeenCalled();
    });
  });

  it("handles multi-file upload and displays batch feedback summary", async () => {
    const batchResponse: PaperUploadBatchResponse = {
      papers: [
        { id: "new-p1", original_filename: "valid.pdf", status: "uploaded" },
      ],
      duplicates: [
        { original_filename: "dup.pdf", existing_paper_id: "paper-1" },
      ],
      rejected: [
        {
          original_filename: "corrupt.pdf",
          code: "PDF_UNREADABLE",
          message: "PDF is corrupt.",
        },
      ],
    };

    const uploadSpy = vi
      .spyOn(client.api, "uploadPapers")
      .mockResolvedValue(batchResponse);

    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Quantum Computing")).toBeInTheDocument();
    });

    const fileInput = document.getElementById(
      "pdf-upload-input",
    ) as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();

    const file1 = new File(["dummy pdf 1"], "valid.pdf", {
      type: "application/pdf",
    });
    const file2 = new File(["dummy pdf 2"], "dup.pdf", {
      type: "application/pdf",
    });
    const file3 = new File(["dummy pdf 3"], "corrupt.pdf", {
      type: "application/pdf",
    });

    fireEvent.change(fileInput, { target: { files: [file1, file2, file3] } });

    await waitFor(() => {
      expect(uploadSpy).toHaveBeenCalledWith("ws-1", [file1, file2, file3]);
      expect(screen.getByText(/1 Accepted/i)).toBeInTheDocument();
      expect(screen.getByText(/1 Duplicate/i)).toBeInTheDocument();
      expect(screen.getByText(/1 Rejected/i)).toBeInTheDocument();
      expect(screen.getByText(/PDF is corrupt/i)).toBeInTheDocument();
    });
  });

  it("supports document pagination and loading more documents", async () => {
    const page1Papers = [mockPapers[0]];
    const page2Papers = [mockPapers[1]];

    vi.spyOn(client.api, "listPapers")
      .mockResolvedValueOnce({
        items: page1Papers,
        next_cursor: "cursor-page-2",
        total_count: 2,
      })
      .mockResolvedValueOnce({
        items: page2Papers,
        next_cursor: null,
        total_count: 2,
      });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(screen.getByText("Showing 1 of 2 documents")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Load more documents" }),
      ).toBeInTheDocument();
    });

    const loadMoreBtn = screen.getByRole("button", {
      name: "Load more documents",
    });
    fireEvent.click(loadMoreBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(screen.getByText("Quantum Error Mitigation")).toBeInTheDocument();
      expect(screen.getByText("Showing 2 of 2 documents")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Load more documents" }),
      ).not.toBeInTheDocument();
    });
  });

  it("does not force selection back to old workspace if user switches workspace during upload (race condition guard)", async () => {
    let resolveUpload: (val: any) => void = () => {};
    const deferredUploadPromise = new Promise((resolve) => {
      resolveUpload = resolve;
    });

    vi.spyOn(client.api, "uploadPapers").mockImplementation(
      () => deferredUploadPromise as any,
    );

    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Quantum Computing")).toBeInTheDocument();
    });

    // 1. Start upload in ws-1
    const fileInput = document.getElementById(
      "pdf-upload-input",
    ) as HTMLInputElement;
    const file = new File(["dummy"], "slow.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // 2. While upload is in flight, user opens selector dropdown and switches to ws-2 ("Neural Networks")
    const selectorBtn = document.getElementById(
      "workspace-selector-btn",
    ) as HTMLElement;
    fireEvent.click(selectorBtn);

    await waitFor(() => {
      expect(screen.getByText("Neural Networks")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Neural Networks"));

    // 3. Resolve upload for ws-1
    resolveUpload({
      papers: [
        { id: "slow-p1", original_filename: "slow.pdf", status: "uploaded" },
      ],
      duplicates: [],
      rejected: [],
    });

    await waitFor(() => {
      // Neural Networks must REMAIN active in the selector button!
      expect(selectorBtn).toHaveTextContent("Neural Networks");
    });
  });

  it("discards pagination results if search query changed while request was in-flight (query generation guard)", async () => {
    let resolvePage2: (val: any) => void = () => {};
    const deferredPage2Promise = new Promise((resolve) => {
      resolvePage2 = resolve;
    });

    vi.spyOn(client.api, "listPapers")
      .mockResolvedValueOnce({
        items: [mockPapers[0]],
        next_cursor: "cursor-p2",
        total_count: 2,
      })
      .mockImplementationOnce(() => deferredPage2Promise as any)
      .mockResolvedValueOnce({
        items: [],
        next_cursor: null,
        total_count: 0,
      });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Load more documents" }),
      ).toBeInTheDocument();
    });

    // Click load more (triggers deferred second request)
    fireEvent.click(
      screen.getByRole("button", { name: "Load more documents" }),
    );

    // User types in search input while pagination request is in flight
    const searchInput = screen.getByPlaceholderText(
      /search papers by title or filename/i,
    );
    fireEvent.change(searchInput, { target: { value: "nonexistent query" } });

    // Resolve pagination request (should be ignored because query changed)
    resolvePage2({
      items: [mockPapers[1]],
      next_cursor: null,
      total_count: 2,
    });

    await waitFor(() => {
      // Outdated page 2 paper must NOT be appended to results!
      expect(
        screen.queryByText("Quantum Error Mitigation"),
      ).not.toBeInTheDocument();
    });
  });

  it("discards pagination results if workspace changed while request was in-flight (workspace generation guard)", async () => {
    let resolvePage2: (val: any) => void = () => {};
    const deferredPage2Promise = new Promise((resolve) => {
      resolvePage2 = resolve;
    });

    vi.spyOn(client.api, "listPapers")
      .mockResolvedValueOnce({
        items: [mockPapers[0]],
        next_cursor: "cursor-p2",
        total_count: 2,
      })
      .mockImplementationOnce(() => deferredPage2Promise as any)
      .mockResolvedValueOnce({
        items: [],
        next_cursor: null,
        total_count: 0,
      });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Load more documents" }),
      ).toBeInTheDocument();
    });

    // Click load more
    fireEvent.click(
      screen.getByRole("button", { name: "Load more documents" }),
    );

    // Switch workspace while pagination request is in flight
    const selectorBtn = document.getElementById(
      "workspace-selector-btn",
    ) as HTMLElement;
    fireEvent.click(selectorBtn);
    await waitFor(() => {
      expect(screen.getByText("Neural Networks")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Neural Networks"));

    // Resolve pagination request for old workspace
    resolvePage2({
      items: [mockPapers[1]],
      next_cursor: null,
      total_count: 2,
    });

    await waitFor(() => {
      // Old paper must NOT be rendered into new workspace
      expect(
        screen.queryByText("Quantum Error Mitigation"),
      ).not.toBeInTheDocument();
    });
  });

  it("does not force selection back to old workspace if user switches workspace during paper deletion", async () => {
    let resolveDelete: (val: any) => void = () => {};
    const deferredDeletePromise = new Promise((resolve) => {
      resolveDelete = resolve;
    });

    vi.spyOn(client.api, "deletePaper").mockImplementation(
      () => deferredDeletePromise as any,
    );

    render(<LibraryPage />);

    await waitFor(() => {
      expect(screen.getByText("Quantum Computing")).toBeInTheDocument();
      expect(
        screen.getByText("Quantum Supremacy Experiment"),
      ).toBeInTheDocument();
    });

    // Trigger delete dialog for paper-1
    const delBtn = screen.getByRole("button", {
      name: `Delete ${mockPapers[0].original_filename}`,
    });
    fireEvent.click(delBtn);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Delete Paper" }),
      ).toBeInTheDocument();
    });

    // Click confirm delete (starts deletePaper in flight)
    fireEvent.click(screen.getByRole("button", { name: "Delete Paper" }));

    // While deletion is in flight, user switches to workspace 2
    const selectorBtn = document.getElementById(
      "workspace-selector-btn",
    ) as HTMLElement;
    fireEvent.click(selectorBtn);
    await waitFor(() => {
      expect(screen.getByText("Neural Networks")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Neural Networks"));

    // Resolve deletion
    resolveDelete({ success: true });

    await waitFor(() => {
      expect(selectorBtn).toHaveTextContent("Neural Networks");
    });
  });

  // ============================================================================
  // R2 Tests: Pagination Loading Ownership & Superseded Request Handling
  // ============================================================================

  it("R2: superseded pagination resolution leaves replacement Load more button enabled and appends correct page", async () => {
    let resolveStalePage2: (val: any) => void = () => {};
    const deferredStalePage2 = new Promise((resolve) => {
      resolveStalePage2 = resolve;
    });

    let resolvePhysicsPage2: (val: any) => void = () => {};
    const deferredPhysicsPage2 = new Promise((resolve) => {
      resolvePhysicsPage2 = resolve;
    });

    const listPapersSpy = vi.spyOn(client.api, "listPapers");

    listPapersSpy.mockImplementation((_wsId, params) => {
      // Initial load: 1 paper with next_cursor
      if (params?.q === "" && !params?.cursor) {
        return Promise.resolve({
          items: [mockPapers[0]],
          next_cursor: "cursor-initial-page1",
          total_count: 2,
        });
      }
      // Initial query pagination (deferred)
      if (params?.q === "" && params?.cursor === "cursor-initial-page1") {
        return deferredStalePage2 as any;
      }
      // New search query "physics": page 1 with next_cursor
      if (params?.q === "physics" && !params?.cursor) {
        return Promise.resolve({
          items: [
            {
              ...mockPapers[0],
              id: "physics-1",
              title: "Physics Paper 1",
            },
          ],
          next_cursor: "physics-cursor-1",
          total_count: 2,
        });
      }
      // New search query "physics": page 2 (deferred)
      if (params?.q === "physics" && params?.cursor === "physics-cursor-1") {
        return deferredPhysicsPage2 as any;
      }
      return Promise.resolve({ items: [], next_cursor: null, total_count: 0 });
    });

    render(<LibraryPage />);

    // 1. Initial page 1 loads with next_cursor
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more documents/i }),
      ).toBeEnabled();
    });

    // 2. Start page 2 pagination for initial query
    fireEvent.click(
      screen.getByRole("button", { name: "Load more documents" }),
    );
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toHaveTextContent(/loading more/i);

    // 3. User changes search to "physics" while pagination is in flight
    const searchInput = screen.getByPlaceholderText(/search papers/i);
    fireEvent.change(searchInput, { target: { value: "physics" } });

    // 4. Wait for replacement query page 1 to load
    await waitFor(() => {
      expect(screen.getByText("Physics Paper 1")).toBeInTheDocument();
      // Load more button must be ENABLED for the replacement query!
      expect(
        screen.getByRole("button", { name: "Load more documents" }),
      ).toBeEnabled();
    });

    // 5. Resolve the stale page 2 request with old document
    resolveStalePage2({
      items: [
        {
          ...mockPapers[1],
          id: "stale-paper-2",
          title: "Stale Quantum Error Paper",
        },
      ],
      next_cursor: "stale-next-cursor",
      total_count: 2,
    });

    // Give microtasks time to run
    await new Promise((r) => setTimeout(r, 50));

    // Stale row must NOT be rendered, no error, and button remains enabled
    expect(
      screen.queryByText("Stale Quantum Error Paper"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toBeEnabled();

    // 6. Click Load more for the current "physics" query!
    fireEvent.click(
      screen.getByRole("button", { name: "Load more documents" }),
    );
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toHaveTextContent(/loading more/i);

    // Resolve current query's page 2
    resolvePhysicsPage2({
      items: [
        {
          ...mockPapers[1],
          id: "physics-2",
          title: "Physics Paper 2 Appended",
        },
      ],
      next_cursor: null,
      total_count: 2,
    });

    // 7. Verify correct next page was appended
    await waitFor(() => {
      expect(screen.getByText("Physics Paper 2 Appended")).toBeInTheDocument();
    });
  });

  it("R2: stale rejected pagination does not display error and leaves replacement query enabled", async () => {
    let rejectStalePage2: (err: any) => void = () => {};
    const deferredStalePage2 = new Promise((_, reject) => {
      rejectStalePage2 = reject;
    });

    const listPapersSpy = vi.spyOn(client.api, "listPapers");

    listPapersSpy.mockImplementation((_wsId, params) => {
      if (params?.q === "" && !params?.cursor) {
        return Promise.resolve({
          items: [mockPapers[0]],
          next_cursor: "cur-1",
          total_count: 2,
        });
      }
      if (params?.q === "" && params?.cursor === "cur-1") {
        return deferredStalePage2 as any;
      }
      if (params?.q === "ai") {
        return Promise.resolve({
          items: [{ ...mockPapers[0], id: "ai-1", title: "AI Research" }],
          next_cursor: "ai-cur-2",
          total_count: 2,
        });
      }
      return Promise.resolve({ items: [], next_cursor: null, total_count: 0 });
    });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more documents/i }),
      ).toBeEnabled();
    });

    // Start pagination
    fireEvent.click(
      screen.getByRole("button", { name: /load more documents/i }),
    );

    // Switch query to "ai"
    const searchInput = screen.getByPlaceholderText(/search papers/i);
    fireEvent.change(searchInput, { target: { value: "ai" } });

    await waitFor(() => {
      expect(screen.getByText("AI Research")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /load more documents/i }),
      ).toBeEnabled();
    });

    // Reject stale request
    rejectStalePage2(new Error("Stale network timeout"));

    await new Promise((r) => setTimeout(r, 50));

    // Stale error must NOT be shown
    expect(
      screen.queryByText(/stale network timeout/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /load more documents/i }),
    ).toBeEnabled();
  });

  it("R2: stale completion does not clear loading state of a concurrent new pagination request", async () => {
    let resolveStalePage: (val: any) => void = () => {};
    const deferredStale = new Promise((resolve) => {
      resolveStalePage = resolve;
    });

    let resolveNewPage: (val: any) => void = () => {};
    const deferredNew = new Promise((resolve) => {
      resolveNewPage = resolve;
    });

    const listPapersSpy = vi.spyOn(client.api, "listPapers");

    listPapersSpy.mockImplementation((_wsId, params) => {
      if (params?.q === "" && !params?.cursor) {
        return Promise.resolve({
          items: [mockPapers[0]],
          next_cursor: "cur-1",
          total_count: 2,
        });
      }
      if (params?.q === "" && params?.cursor === "cur-1") {
        return deferredStale as any;
      }
      if (params?.q === "deep" && !params?.cursor) {
        return Promise.resolve({
          items: [{ ...mockPapers[0], id: "deep-1", title: "Deep Learning" }],
          next_cursor: "deep-cur-2",
          total_count: 2,
        });
      }
      if (params?.q === "deep" && params?.cursor === "deep-cur-2") {
        return deferredNew as any;
      }
      return Promise.resolve({ items: [], next_cursor: null, total_count: 0 });
    });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more documents/i }),
      ).toBeEnabled();
    });

    // Start pagination for query A
    fireEvent.click(
      screen.getByRole("button", { name: /load more documents/i }),
    );

    // Switch to query "deep"
    const searchInput = screen.getByPlaceholderText(/search papers/i);
    fireEvent.change(searchInput, { target: { value: "deep" } });

    await waitFor(() => {
      expect(screen.getByText("Deep Learning")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Load more documents" }),
      ).toBeEnabled();
    });

    // Start pagination for query B
    fireEvent.click(
      screen.getByRole("button", { name: "Load more documents" }),
    );
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toHaveTextContent(/loading more/i);

    // Now resolve the stale request from query A
    resolveStalePage({
      items: [mockPapers[1]],
      next_cursor: null,
      total_count: 2,
    });

    await new Promise((r) => setTimeout(r, 50));

    // Button must STILL be loading query B (stale request completion must not clear its loading state!)
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Load more documents" }),
    ).toHaveTextContent(/loading more/i);

    // Resolve query B pagination
    resolveNewPage({
      items: [
        { ...mockPapers[1], id: "deep-2", title: "Deep Learning Part 2" },
      ],
      next_cursor: null,
      total_count: 2,
    });

    await waitFor(() => {
      expect(screen.getByText("Deep Learning Part 2")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Load more documents" }),
      ).not.toBeInTheDocument();
    });
  });
});
