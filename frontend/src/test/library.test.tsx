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
});
