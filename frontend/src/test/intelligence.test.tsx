import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ResearchExplorerPage } from "../pages/ResearchExplorerPage";
import { ModelLabPage } from "../pages/ModelLabPage";
import * as client from "../api/client";

const mockPaper = {
  id: "paper-test-1",
  workspace_id: "ws-test-1",
  original_filename: "transformer.pdf",
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

const mockSummary = {
  paper_id: "paper-test-1",
  paper_title: "Attention Is All You Need",
  style: "simple" as const,
  overview: "High-level executive overview of Attention Is All You Need.",
  points: [
    {
      point_id: 1,
      heading: "Key Finding 1",
      content: "The Transformer relies entirely on self-attention.",
      citations: [
        {
          citation_id: 1,
          paper_id: "paper-test-1",
          paper_title: "Attention Is All You Need",
          page_number: 1,
          section_title: "Introduction",
          quote: "The Transformer relies entirely on self-attention.",
        },
      ],
    },
  ],
  cached: false,
  generated_at: "2026-10-22T00:00:00Z",
};

const mockSections = {
  paper_id: "paper-test-1",
  paper_title: "Attention Is All You Need",
  total_sections: 1,
  sections: [
    {
      section_index: 0,
      section_title: "Introduction",
      heading: "Introduction",
      page_start: 1,
      page_end: 2,
      chunk_count: 5,
      quality_status: "complete" as const,
      preview_text: "The Transformer relies entirely on self-attention.",
    },
  ],
};

const mockModelLabReports = {
  readiness: {
    splits: { train: { count: 8243 }, dev: { count: 916 }, test: { count: 1861 } },
  },
  baselines: {
    majority_baseline: { metrics: { accuracy: 0.5873 } },
    tfidf_baseline: { metrics: { accuracy: 0.8264 } },
  },
  distilbert_trial: { status: "resumed_step_15" },
  test_evaluation: {
    accuracy: 0.8162,
    macro_f1: 0.7977,
    micro_f1: 0.8162,
    weighted_f1: 0.819,
    classes: ["background", "method", "result"],
    confusion_matrix: [
      [800, 92, 105],
      [84, 495, 26],
      [27, 8, 224],
    ],
    per_class: {
      background: { precision: 0.8782, recall: 0.8024, f1_score: 0.8386, support: 997 },
      method: { precision: 0.8319, recall: 0.8182, f1_score: 0.825, support: 605 },
      result: { precision: 0.631, recall: 0.8649, f1_score: 0.7296, support: 259 },
    },
  },
};

describe("Week 5 Research Intelligence UI Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client.api, "listPapers").mockResolvedValue({
      items: [mockPaper],
      next_cursor: null,
      total_count: 1,
    });
    vi.spyOn(client.intelligenceApi, "getSummary").mockResolvedValue(mockSummary);
    vi.spyOn(client.intelligenceApi, "getSections").mockResolvedValue(mockSections);
    vi.spyOn(client.intelligenceApi, "getModelLabReports").mockResolvedValue(mockModelLabReports);
  });

  it("renders ResearchExplorerPage and switches to multi-style summaries tab", async () => {
    render(<ResearchExplorerPage onNavigate={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Research Explorer/i);
    expect(screen.getByText(/Planned · Phase 5/i)).toBeInTheDocument();

    const summariesBtn = screen.getByRole("button", { name: /Multi-Style Summaries/i });
    fireEvent.click(summariesBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Generate Summary/i })).toBeInTheDocument();
    });

    const generateBtn = screen.getByRole("button", { name: /Generate Summary/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(screen.getByText(/High-level executive overview/i)).toBeInTheDocument();
      expect(screen.getByText(/Key Finding 1/i)).toBeInTheDocument();
      expect(screen.getByText(/Document Sections \(1\)/i)).toBeInTheDocument();
    });
  });

  it("renders ModelLabPage with live held-out test evaluation metrics and confusion matrix", async () => {
    render(<ModelLabPage onNavigate={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Model Lab/i);
    expect(screen.getByText(/Planned · Phase 6/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("81.62%")).toBeInTheDocument();
      expect(screen.getByText("0.7977")).toBeInTheDocument();
      expect(screen.getByText(/Test Split Confusion Matrix/i)).toBeInTheDocument();
      expect(screen.getByText(/Step 15 Resumed/i)).toBeInTheDocument();
    });
  });
});
