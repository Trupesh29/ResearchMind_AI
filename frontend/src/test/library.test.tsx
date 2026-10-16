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

  it("renders empty state when no workspaces exist", async () => {
    vi.spyOn(client.api, "listWorkspaces").mockResolvedValue({
      items: [],
      next_cursor: null,
      total_count: 0,
    });

    render(<LibraryPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No Research Workspaces Yet/i),
      ).toBeInTheDocument();
    });
  });
});
