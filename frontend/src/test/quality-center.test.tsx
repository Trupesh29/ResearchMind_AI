import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QualityCenterModal } from "../components/library/QualityCenterModal";
import * as client from "../api/client";
import {
  PaperItem,
  PaperStatusResponse,
  ChunkItem,
  SectionItem,
  PageSummaryItem,
} from "../api/types";

const mockPaper: PaperItem = {
  id: "paper-123",
  workspace_id: "ws-1",
  original_filename: "sample_paper.pdf",
  title: "Neural Attention Mechanism in Transformer Architectures",
  authors: ["Ashish Vaswani", "Noam Shazeer"],
  publication_year: 2017,
  keywords: ["transformers", "attention"],
  metadata_source: { title: "grobid" },
  page_count: 5,
  size_bytes: 1048576,
  status: "processing",
  quality: {
    total_pages: 5,
    has_text: true,
    scanned_pages: [],
    low_char_pages: [],
    warning_flags: [],
  },
  created_at: "2026-10-18T10:00:00Z",
};

const mockStatus: PaperStatusResponse = {
  status: "processing",
  stage: "chunking",
  substate: "awaiting_indexing",
  progress: 1.0,
  attempt: 1,
  error: null,
  stages: [
    {
      stage: "validating",
      status: "succeeded",
      attempt: 1,
      started_at: "2026-10-18T10:00:01Z",
      finished_at: "2026-10-18T10:00:02Z",
      error: null,
    },
    {
      stage: "extracting",
      status: "succeeded",
      attempt: 1,
      started_at: "2026-10-18T10:00:02Z",
      finished_at: "2026-10-18T10:00:05Z",
      error: null,
    },
    {
      stage: "sectioning",
      status: "succeeded",
      attempt: 1,
      started_at: "2026-10-18T10:00:05Z",
      finished_at: "2026-10-18T10:00:06Z",
      error: null,
    },
    {
      stage: "chunking",
      status: "succeeded",
      attempt: 1,
      started_at: "2026-10-18T10:00:06Z",
      finished_at: "2026-10-18T10:00:07Z",
      error: null,
    },
  ],
  run_id: "run-gen-1",
  current_run_id: "run-gen-1",
  published_run_id: "run-gen-1",
  is_stale: false,
};

const mockChunks: ChunkItem[] = [
  {
    id: "chunk-1",
    paper_id: "paper-123",
    run_id: "run-gen-1",
    chunk_index: 0,
    section: "1. Introduction",
    page_start: 1,
    page_end: 1,
    block_ids: ["b1"],
    text: "Recurrent neural networks have been firmly established as state of the art approaches in sequence modeling.",
    token_count: 185,
    is_excluded: false,
    created_at: "2026-10-18T10:00:07Z",
  },
  {
    id: "chunk-2",
    paper_id: "paper-123",
    run_id: "run-gen-1",
    chunk_index: 1,
    section: "References",
    page_start: 5,
    page_end: 5,
    block_ids: ["b2"],
    text: "[1] Vaswani et al. Attention Is All You Need. NeurIPS 2017.",
    token_count: 75,
    is_excluded: true,
    created_at: "2026-10-18T10:00:07Z",
  },
];

const mockSections: SectionItem[] = [
  {
    id: "sec-1",
    paper_id: "paper-123",
    run_id: "run-gen-1",
    section_index: 0,
    section: "1. Introduction",
    heading: "Introduction",
    page_start: 1,
    page_end: 2,
    block_ids: ["b1"],
    created_at: "2026-10-18T10:00:06Z",
  },
  {
    id: "sec-2",
    paper_id: "paper-123",
    run_id: "run-gen-1",
    section_index: 1,
    section: "References",
    heading: "References",
    page_start: 5,
    page_end: 5,
    block_ids: ["b2"],
    created_at: "2026-10-18T10:00:06Z",
  },
];

const mockPages: PageSummaryItem[] = [
  {
    page_number: 1,
    char_count: 1500,
    extraction_status: "ok",
    flags: [],
  },
  {
    page_number: 5,
    char_count: 600,
    extraction_status: "ok",
    flags: ["references"],
  },
];

describe("QualityCenterModal Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(client.api, "getPaperStatus").mockResolvedValue(mockStatus);
    vi.spyOn(client.api, "getPaperChunks").mockResolvedValue({
      items: mockChunks,
      total: 2,
      run_id: "run-gen-1",
      next_cursor: null,
      is_stale: false,
    });
    vi.spyOn(client.api, "getPaperSections").mockResolvedValue({
      items: mockSections,
      total: 2,
      run_id: "run-gen-1",
      is_stale: false,
    });
    vi.spyOn(client.api, "getPaperPages").mockResolvedValue({
      items: mockPages,
      total_pages: 2,
      run_id: "run-gen-1",
      is_stale: false,
    });
  });

  it("renders modal with paper details and token metrics", async () => {
    render(
      <QualityCenterModal
        paper={mockPaper}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("Quality Center")).toBeInTheDocument();
    expect(screen.getByText(mockPaper.title!)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("1. Introduction")).toBeInTheDocument();
      expect(screen.getByText("185")).toBeInTheDocument();
      expect(screen.getByText("75")).toBeInTheDocument();
    });
  });

  it("navigates tabs and displays stage history in pipeline tab", async () => {
    render(
      <QualityCenterModal
        paper={mockPaper}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    // Wait for initial load to settle
    await waitFor(() => {
      expect(screen.getByText("1. Introduction")).toBeInTheDocument();
    });

    const stageTab = screen.getByRole("button", { name: /stage history/i });
    fireEvent.click(stageTab);

    await waitFor(() => {
      expect(screen.getByText("Ingestion Generation Pipeline")).toBeInTheDocument();
      expect(screen.getAllByText("validating").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("extracting").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("sectioning").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("chunking").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("triggers jump to PDF page callback", async () => {
    const onOpenPdfPage = vi.fn();
    render(
      <QualityCenterModal
        paper={mockPaper}
        isOpen={true}
        onClose={vi.fn()}
        onOpenPdfPage={onOpenPdfPage}
      />
    );

    const viewButtons = await screen.findAllByText("View Page");
    expect(viewButtons.length).toBeGreaterThan(0);
    fireEvent.click(viewButtons[0]);

    expect(onOpenPdfPage).toHaveBeenCalledWith(mockPaper, 1);
  });

  it("handles reprocess 409 conflict gracefully", async () => {
    const error409 = new client.ApiClientError(
      {
        code: "CONFLICT",
        message: "Paper has an active processing job in progress.",
        details: {},
      },
      409
    );
    vi.spyOn(client.api, "reprocessPaper").mockRejectedValue(error409);

    render(
      <QualityCenterModal
        paper={mockPaper}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reprocess document/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /reprocess document/i }));

    await waitFor(() => {
      expect(screen.getByText(/Paper has an active processing job in progress/i)).toBeInTheDocument();
    });
  });

  it("calls onClose when Close button or Escape is pressed", async () => {
    const onClose = vi.fn();
    render(
      <QualityCenterModal
        paper={mockPaper}
        isOpen={true}
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Quality Center")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("Close modal"));
    expect(onClose).toHaveBeenCalled();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
