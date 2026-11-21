import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ResearchAssistantPage } from "../pages/ResearchAssistantPage";
import * as client from "../api/client";

const mockWorkspace = {
  id: "ws-test-1",
  name: "Machine Learning Research",
  description: "NLP and Transformers",
  paper_count: 2,
  ready_count: 2,
  created_at: "2026-10-15T00:00:00Z",
};

const mockPaper1 = {
  id: "paper-1",
  workspace_id: "ws-test-1",
  original_filename: "attention.pdf",
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
  current_run_id: "run-1",
  published_run_id: "run-1",
};

const mockPaper2 = {
  id: "paper-2",
  workspace_id: "ws-test-1",
  original_filename: "gnn.pdf",
  title: "Graph Neural Networks in Molecular Discovery",
  authors: ["Stokes et al."],
  publication_year: 2020,
  keywords: ["gnn", "molecules"],
  metadata_source: null,
  page_count: 10,
  size_bytes: 1024000,
  status: "ready" as const,
  quality: null,
  created_at: "2026-10-15T00:00:00Z",
  current_run_id: "run-2",
  published_run_id: "run-2",
};

describe("ResearchAssistantPage Split Workspace & Grounded Chat", () => {
  const onNavigateMock = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("selected_workspace_id", "ws-test-1");

    vi.spyOn(client.api, "listAllWorkspaces").mockResolvedValue([mockWorkspace]);
    vi.spyOn(client.api, "listPapers").mockResolvedValue({
      items: [mockPaper1, mockPaper2],
      next_cursor: null,
      total_count: 2,
    });
    vi.spyOn(client.api, "getPaperFileUrl").mockImplementation(
      (id: string) => `/api/papers/${id}/file`,
    );

    vi.spyOn(client.assistantApi, "listConversations").mockResolvedValue([
      {
        id: "conv-1",
        workspace_id: "ws-test-1",
        title: "Transformer Attention Analysis",
        message_count: 2,
        created_at: "2026-10-16T10:00:00Z",
        updated_at: "2026-10-16T10:05:00Z",
      },
    ]);

    vi.spyOn(client.assistantApi, "getConversation").mockResolvedValue({
      id: "conv-1",
      workspace_id: "ws-test-1",
      title: "Transformer Attention Analysis",
      messages: [
        {
          id: "msg-1",
          conversation_id: "conv-1",
          role: "user",
          content: "What is self-attention?",
          is_abstention: false,
          citations: [],
          selected_paper_ids: ["paper-1"],
          created_at: "2026-10-16T10:00:00Z",
        },
        {
          id: "msg-2",
          conversation_id: "conv-1",
          role: "assistant",
          content: "Self-attention computes representations without recurrence [1].",
          is_abstention: false,
          citations: [
            {
              citation_id: "[1]",
              passage_id: "chunk-1",
              paper_id: "paper-1",
              paper_title: "Attention Is All You Need",
              page_number: 3,
              exact_quote: "The Transformer relies entirely on self-attention mechanisms.",
              score: 0.035,
            },
          ],
          selected_paper_ids: ["paper-1"],
          created_at: "2026-10-16T10:01:00Z",
        },
      ],
      created_at: "2026-10-16T10:00:00Z",
      updated_at: "2026-10-16T10:05:00Z",
    });
  });

  it("renders split workspace with evidence viewer and grounded chat panes", async () => {
    render(<ResearchAssistantPage onNavigate={onNavigateMock} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /Research Assistant/i,
      );
      expect(screen.getByText(/Grounded Research Chat/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Attention Is All You Need/i).length).toBeGreaterThan(0);
    });
  });

  it("submits research query and displays grounded response with citation pills", async () => {
    vi.spyOn(client.assistantApi, "query").mockResolvedValue({
      conversation_id: "conv-new-1",
      message_id: "msg-new-2",
      query: "How does GNN predict antibacterial activity?",
      rewritten_query: null,
      answer: "Halicin was discovered using a deep graph neural network [1].",
      is_abstention: false,
      citations: [
        {
          citation_id: "[1]",
          passage_id: "chunk-2",
          paper_id: "paper-2",
          paper_title: "Graph Neural Networks in Molecular Discovery",
          page_number: 2,
          exact_quote: "Halicin was discovered using a deep graph neural network.",
          score: 0.04,
        },
      ],
      retrieved_passages: [],
      timings: { retrieval_ms: 15.2, generation_ms: 45.1, total_ms: 60.3 },
    });

    render(<ResearchAssistantPage onNavigate={onNavigateMock} />);

    await waitFor(() => {
      expect(screen.getAllByText(/Attention Is All You Need/i).length).toBeGreaterThan(0);
      expect(screen.getByPlaceholderText(/Ask a grounded question across selected papers/i)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Ask a grounded question across selected papers/i);
    fireEvent.change(input, { target: { value: "How does GNN predict antibacterial activity?" } });

    const askButton = screen.getByRole("button", { name: /Ask/i });
    expect(askButton).toBeEnabled();
    fireEvent.click(askButton);

    await waitFor(() => {
      expect(screen.getByText(/Halicin was discovered using a deep graph neural network/i)).toBeInTheDocument();
      expect(screen.getAllByText(/\[1\]/i).length).toBeGreaterThan(0);
    });
  });

  it("displays honest abstention banner when answer has insufficient evidence", async () => {
    vi.spyOn(client.assistantApi, "query").mockResolvedValue({
      conversation_id: "conv-abstain",
      message_id: "msg-abstain-1",
      query: "What is the capital of Mars?",
      rewritten_query: null,
      answer: "Based on the provided research papers, there is insufficient evidence to answer your query.",
      is_abstention: true,
      citations: [],
      retrieved_passages: [],
      timings: { retrieval_ms: 12.0, generation_ms: 20.0, total_ms: 32.0 },
    });

    render(<ResearchAssistantPage onNavigate={onNavigateMock} />);

    await waitFor(() => {
      expect(screen.getAllByText(/Attention Is All You Need/i).length).toBeGreaterThan(0);
      expect(screen.getByPlaceholderText(/Ask a grounded question across selected papers/i)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Ask a grounded question across selected papers/i);
    fireEvent.change(input, { target: { value: "What is the capital of Mars?" } });

    const askButton = screen.getByRole("button", { name: /Ask/i });
    expect(askButton).toBeEnabled();
    fireEvent.click(askButton);

    await waitFor(() => {
      expect(screen.getByText(/Honest Abstention: Evidence is insufficient/i)).toBeInTheDocument();
    });
  });
});
