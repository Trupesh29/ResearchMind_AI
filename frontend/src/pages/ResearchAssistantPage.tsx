import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  BookOpen,
  MessageSquare,
  ShieldCheck,
  AlertCircle,
  FileSearch,
  Search,
  Clock,
  Layers,
  ExternalLink,
  Send,
  RefreshCw,
  FileText,
  CheckCircle2,
  Columns,
  Maximize2,
  Trash2,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { api, retrievalApi, assistantApi, ApiClientError } from "../api/client";
import {
  PaperItem,
  WorkspaceItem,
  RetrievalPassage,
  RetrievalDiagnostics,
  CitationItem,
  ConversationSummary,
  ResearchAssistantResponse,
} from "../api/types";
import { PdfViewerModal } from "../components/library/PdfViewerModal";

interface ResearchAssistantPageProps {
  onNavigate: (path: string) => void;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  is_abstention?: boolean;
  citations?: CitationItem[];
  rewritten_query?: string | null;
  timings?: {
    retrieval_ms: number;
    generation_ms: number;
    total_ms: number;
  };
  created_at: string;
}

export const ResearchAssistantPage: React.FC<ResearchAssistantPageProps> = ({
  onNavigate,
}) => {
  // Navigation tab
  const [activeTab, setActiveTab] = useState<"assistant" | "retrieval">("assistant");

  // Workspaces and ready papers state
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>(
    () => localStorage.getItem("selected_workspace_id") || "",
  );
  const [readyPapers, setReadyPapers] = useState<PaperItem[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [isLoadingPapers, setIsLoadingPapers] = useState<boolean>(false);

  // Assistant Chat State
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [assistantQuery, setAssistantQuery] = useState<string>("");
  const [assistantMode, setAssistantMode] = useState<"concise" | "detailed" | "comparison">("concise");
  const [isSubmittingQuery, setIsSubmittingQuery] = useState<boolean>(false);
  const [assistantError, setAssistantError] = useState<string | null>(null);

  // Split Workspace: Left Pane Active Evidence / PDF state
  const [activeEvidencePaper, setActiveEvidencePaper] = useState<PaperItem | null>(null);
  const [activeEvidencePage, setActiveEvidencePage] = useState<number>(1);
  const [activeEvidenceQuote, setActiveEvidenceQuote] = useState<string | null>(null);
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);

  // Retrieval Inspection Mode state
  const [retrievalQuery, setRetrievalQuery] = useState<string>("");
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  const [isSearchingRetrieval, setIsSearchingRetrieval] = useState<boolean>(false);
  const [retrievalError, setRetrievalError] = useState<string | null>(null);
  const [passages, setPassages] = useState<RetrievalPassage[] | null>(null);
  const [diagnostics, setDiagnostics] = useState<RetrievalDiagnostics | null>(null);

  // PDF modal state (for full screen viewing)
  const [modalPaper, setModalPaper] = useState<PaperItem | null>(null);
  const [modalPage, setModalPage] = useState<number>(1);
  const [isPdfModalOpen, setIsPdfModalOpen] = useState<boolean>(false);

  // Race guard ref
  const activeReqIdRef = useRef<number>(0);
  const abortCtrlRef = useRef<AbortController | null>(null);

  // Load workspaces on mount
  useEffect(() => {
    let isMounted = true;
    api
      .listAllWorkspaces()
      .then((wsList) => {
        if (!isMounted) return;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          const initialWsId = localStorage.getItem("selected_workspace_id") || wsList[0].id;
          const found = wsList.find((w) => w.id === initialWsId) || wsList[0];
          setSelectedWorkspaceId(found.id);
        }
      })
      .catch((err) => {
        console.error("Failed to load workspaces", err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Load ready papers & conversations when workspace changes
  useEffect(() => {
    if (!selectedWorkspaceId) return;

    // Invalidate stale search results upon workspace switch
    setPassages(null);
    setDiagnostics(null);
    setRetrievalError(null);
    setAssistantError(null);
    setChatMessages([]);
    setActiveConversationId(null);
    setActiveEvidencePaper(null);
    setActiveEvidenceQuote(null);
    setActiveCitationId(null);

    let isMounted = true;
    setIsLoadingPapers(true);

    // Fetch papers
    api
      .listPapers(selectedWorkspaceId, { status: "ready", limit: 50 })
      .then((res) => {
        if (!isMounted) return;
        const papers = res.items || [];
        setReadyPapers(papers);
        setSelectedPaperIds(papers.map((p) => p.id));
        if (papers.length > 0) {
          setActiveEvidencePaper(papers[0]);
          setActiveEvidencePage(1);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Failed to load papers", err);
        setReadyPapers([]);
        setSelectedPaperIds([]);
      })
      .finally(() => {
        if (isMounted) setIsLoadingPapers(false);
      });

    // Fetch conversations
    assistantApi
      .listConversations(selectedWorkspaceId)
      .then((convs) => {
        if (!isMounted) return;
        setConversations(convs);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Failed to load conversations", err);
        setConversations([]);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedWorkspaceId]);

  // Load conversation details when activeConversationId changes
  useEffect(() => {
    if (!activeConversationId) return;
    let isMounted = true;
    assistantApi
      .getConversation(activeConversationId)
      .then((detail) => {
        if (!isMounted) return;
        const formatted: ChatMessage[] = detail.messages.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          is_abstention: m.is_abstention,
          citations: m.citations,
          created_at: m.created_at,
        }));
        setChatMessages(formatted);
      })
      .catch((err) => {
        console.error("Failed to load conversation messages", err);
      });
    return () => {
      isMounted = false;
    };
  }, [activeConversationId]);

  const handleTogglePaper = (paperId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((id) => id !== paperId) : [...prev, paperId],
    );
  };

  const handleSelectAll = () => {
    if (selectedPaperIds.length === readyPapers.length) {
      setSelectedPaperIds([]);
    } else {
      setSelectedPaperIds(readyPapers.map((p) => p.id));
    }
  };

  // Assistant QA Submission
  const handleSubmitAssistantQuery = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanQuery = assistantQuery.trim();
    if (!cleanQuery) return;
    if (selectedPaperIds.length === 0) {
      setAssistantError("Please select at least one ready paper to query.");
      return;
    }

    setAssistantError(null);
    setIsSubmittingQuery(true);

    // Optimistically show user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: cleanQuery,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, tempUserMsg]);
    setAssistantQuery("");

    try {
      const resp: ResearchAssistantResponse = await assistantApi.query({
        workspace_id: selectedWorkspaceId,
        query: cleanQuery,
        selected_paper_ids: selectedPaperIds,
        mode: assistantMode,
        conversation_id: activeConversationId || undefined,
      });

      if (!activeConversationId) {
        setActiveConversationId(resp.conversation_id);
        // Refresh conversations list
        assistantApi.listConversations(selectedWorkspaceId).then(setConversations);
      }

      const assistantMsg: ChatMessage = {
        id: resp.message_id,
        role: "assistant",
        content: resp.answer,
        is_abstention: resp.is_abstention,
        citations: resp.citations,
        rewritten_query: resp.rewritten_query,
        timings: resp.timings,
        created_at: new Date().toISOString(),
      };

      setChatMessages((prev) => [...prev, assistantMsg]);

      // If citations exist, activate first citation in the split viewer
      if (resp.citations && resp.citations.length > 0) {
        handleCitationClick(resp.citations[0]);
      }
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setAssistantError(`${err.code}: ${err.message}`);
      } else {
        setAssistantError(err?.message || "Failed to query research assistant.");
      }
    } finally {
      setIsSubmittingQuery(false);
    }
  };

  // Citation marker jump to split PDF viewer
  const handleCitationClick = (cit: CitationItem) => {
    setActiveCitationId(cit.citation_id);
    setActiveEvidenceQuote(cit.exact_quote);
    setActiveEvidencePage(cit.page_number);

    const paper = readyPapers.find((p) => p.id === cit.paper_id);
    if (paper) {
      setActiveEvidencePaper(paper);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation?")) return;
    try {
      await assistantApi.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        setActiveConversationId(null);
        setChatMessages([]);
      }
    } catch (err) {
      console.error("Failed to delete conversation", err);
    }
  };

  // Retrieval search handler
  const handleRetrievalSearch = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      const trimmedQuery = retrievalQuery.trim();
      if (!trimmedQuery) {
        setRetrievalError("Please enter a search query.");
        return;
      }
      if (selectedPaperIds.length === 0) {
        setRetrievalError("Please select at least one ready paper to search across.");
        return;
      }

      if (abortCtrlRef.current) abortCtrlRef.current.abort();
      const controller = new AbortController();
      abortCtrlRef.current = controller;

      const currentReqId = ++activeReqIdRef.current;
      setIsSearchingRetrieval(true);
      setRetrievalError(null);

      try {
        const response = await retrievalApi.query(
          {
            workspace_id: selectedWorkspaceId,
            query: trimmedQuery,
            selected_paper_ids: selectedPaperIds,
            mode: retrievalMode,
            top_k: 20,
          },
          controller.signal,
        );

        if (activeReqIdRef.current !== currentReqId) return;
        setPassages(response.data.passages);
        setDiagnostics(response.data.diagnostics);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        if (activeReqIdRef.current === currentReqId) {
          if (err instanceof ApiClientError) {
            setRetrievalError(`${err.code}: ${err.message}`);
          } else {
            setRetrievalError(err?.message || "An unexpected error occurred during retrieval.");
          }
          setPassages(null);
          setDiagnostics(null);
        }
      } finally {
        if (activeReqIdRef.current === currentReqId) {
          setIsSearchingRetrieval(false);
        }
      }
    },
    [retrievalQuery, selectedWorkspaceId, selectedPaperIds, retrievalMode],
  );

  const handleOpenPdfModal = (paper: PaperItem, pageNumber: number) => {
    setModalPaper(paper);
    setModalPage(pageNumber);
    setIsPdfModalOpen(true);
  };

  return (
    <div
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        padding: "16px 0 48px 0",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "8px",
            }}
          >
            <h1
              style={{
                fontSize: "28px",
                fontWeight: 700,
                margin: 0,
                color: "var(--text-primary)",
              }}
            >
              Research Assistant
            </h1>
            <Badge variant="neutral">Planned · Phase 4</Badge>
            <Badge variant="info">Week 4 Grounded Assistant</Badge>
          </div>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: "15px",
              margin: 0,
              maxWidth: "760px",
              lineHeight: 1.5,
            }}
          >
            Evidence-grounded conversational synthesis over selected research documents
            with split PDF viewing, verifiable claim citations, and calibrated honest abstention.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {/* Workspace select */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <label htmlFor="assistant-ws-select" style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-secondary)" }}>
              Workspace:
            </label>
            <select
              id="assistant-ws-select"
              value={selectedWorkspaceId}
              onChange={(e) => setSelectedWorkspaceId(e.target.value)}
              style={{
                fontSize: "13px",
                padding: "6px 12px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--hairline)",
                background: "var(--surface)",
                color: "var(--text-primary)",
              }}
            >
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name} ({ws.ready_count} ready)
                </option>
              ))}
            </select>
          </div>
          <Button variant="ink" onClick={() => onNavigate("/library")}>
            <BookOpen size={16} />
            <span>Paper Library</span>
          </Button>
        </div>
      </div>

      {/* Capabilities Grid (Preserved for compatibility and user overview) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        <Card elevation={1}>
          <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--r-md)",
                background: "var(--blue-surface)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--blue-action)",
                flexShrink: 0,
              }}
            >
              <MessageSquare size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Conversational Grounding
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Ask complex research questions with strict answer grounding. Every generated claim
                includes direct quotes from source chunks and explicit page references.
              </p>
            </div>
          </div>
        </Card>

        <Card elevation={1}>
          <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--r-md)",
                background: "var(--surface-soft)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-primary)",
                flexShrink: 0,
              }}
            >
              <FileSearch size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Split PDF & Evidence Drawer
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Side-by-side conversational interface with integrated PDF viewer, highlighting exact
                text spans and bounding boxes when clicking citation pills.
              </p>
            </div>
          </div>
        </Card>

        <Card elevation={1}>
          <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--r-md)",
                background: "var(--green-surface, rgba(52, 199, 89, 0.12))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--green-text, #248a3d)",
                flexShrink: 0,
              }}
            >
              <ShieldCheck size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Explicit Abstention
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Refuses hallucination. If a query cannot be answered with high confidence from ingested
                workspace literature, the assistant reports evidence gaps explicitly.
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Scope Selector Bar */}
      <div
        style={{
          padding: "12px 16px",
          background: "var(--surface-sunken)",
          borderRadius: "var(--r-lg)",
          border: "1px solid var(--hairline)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
            Selected Scope ({selectedPaperIds.length} of {readyPapers.length} ready papers):
          </span>
          {readyPapers.length > 0 && (
            <button
              type="button"
              onClick={handleSelectAll}
              style={{
                fontSize: "12px",
                color: "var(--blue-action)",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              {selectedPaperIds.length === readyPapers.length ? "Deselect All" : "Select All"}
            </button>
          )}
        </div>

        {isLoadingPapers ? (
          <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>Loading ready papers...</p>
        ) : readyPapers.length === 0 ? (
          <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
            No ready papers found in this workspace. Upload and process papers in the Library first.
          </p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {readyPapers.map((paper) => {
              const isChecked = selectedPaperIds.includes(paper.id);
              return (
                <label
                  key={paper.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 10px",
                    borderRadius: "var(--r-md)",
                    fontSize: "12px",
                    cursor: "pointer",
                    background: isChecked ? "var(--blue-surface)" : "var(--surface)",
                    border: `1px solid ${isChecked ? "var(--blue-action)" : "var(--hairline)"}`,
                    color: isChecked ? "var(--blue-action)" : "var(--text-primary)",
                    userSelect: "none",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleTogglePaper(paper.id)}
                    style={{ cursor: "pointer" }}
                  />
                  <span style={{ maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {paper.title || paper.original_filename}
                  </span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* Tabs Header */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--hairline)", paddingBottom: "8px" }}>
        <Button
          variant={activeTab === "assistant" ? "blue" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("assistant")}
        >
          <Columns size={16} />
          <span>Grounded Assistant Workspace</span>
        </Button>
        <Button
          variant={activeTab === "retrieval" ? "blue" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("retrieval")}
        >
          <Layers size={16} />
          <span>Retrieval Engine Inspection</span>
        </Button>
      </div>

      {/* TAB 1: Grounded Assistant Split Workspace */}
      {activeTab === "assistant" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(320px, 1fr) minmax(360px, 1.2fr)",
            gap: "20px",
            alignItems: "stretch",
          }}
        >
          {/* LEFT PANE: Split Evidence & PDF Viewer */}
          <Card
            elevation={2}
            style={{
              display: "flex",
              flexDirection: "column",
              height: "720px",
              overflow: "hidden",
              border: "1px solid var(--hairline-strong, #d1d5db)",
            }}
          >
            {/* Viewer Header */}
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--hairline)",
                background: "var(--surface-sunken)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                <FileText size={18} color="var(--blue-action)" />
                <span
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "240px",
                  }}
                >
                  {activeEvidencePaper ? (activeEvidencePaper.title || activeEvidencePaper.original_filename) : "Select Paper"}
                </span>
                {activeCitationId && <Badge variant="info">Active {activeCitationId}</Badge>}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                {activeEvidencePaper && (
                  <Button
                    variant="soft"
                    size="sm"
                    onClick={() => handleOpenPdfModal(activeEvidencePaper, activeEvidencePage)}
                    aria-label="Maximize viewer"
                  >
                    <Maximize2 size={13} />
                    <span>Popout</span>
                  </Button>
                )}
              </div>
            </div>

            {/* Paper & Page Selector */}
            <div
              style={{
                padding: "8px 16px",
                borderBottom: "1px solid var(--hairline)",
                background: "var(--surface)",
                display: "flex",
                gap: "10px",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <select
                value={activeEvidencePaper?.id || ""}
                onChange={(e) => {
                  const p = readyPapers.find((item) => item.id === e.target.value);
                  if (p) {
                    setActiveEvidencePaper(p);
                    setActiveEvidencePage(1);
                    setActiveEvidenceQuote(null);
                    setActiveCitationId(null);
                  }
                }}
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--hairline)",
                  background: "var(--surface)",
                  color: "var(--text-primary)",
                  maxWidth: "200px",
                }}
              >
                {readyPapers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title || p.original_filename}
                  </option>
                ))}
              </select>

              <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px" }}>
                <span>Page:</span>
                <input
                  type="number"
                  min={1}
                  max={activeEvidencePaper?.page_count || 100}
                  value={activeEvidencePage}
                  onChange={(e) => setActiveEvidencePage(Math.max(1, parseInt(e.target.value) || 1))}
                  style={{
                    width: "48px",
                    padding: "3px 6px",
                    fontSize: "12px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--hairline)",
                    textAlign: "center",
                  }}
                />
                {activeEvidencePaper?.page_count && (
                  <span style={{ color: "var(--text-muted)" }}>/ {activeEvidencePaper.page_count}</span>
                )}
              </div>
            </div>

            {/* Cited Quote Callout Banner (if citation clicked) */}
            {activeEvidenceQuote && (
              <div
                style={{
                  padding: "10px 16px",
                  background: "var(--blue-surface)",
                  borderBottom: "1px solid var(--hairline)",
                  fontSize: "12px",
                  color: "var(--text-primary)",
                  lineHeight: 1.5,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <CheckCircle2 size={14} color="var(--blue-action)" />
                  <strong style={{ color: "var(--blue-action)" }}>Supporting Citation Quote (Page {activeEvidencePage}):</strong>
                </div>
                <p style={{ margin: 0, fontStyle: "italic", fontFamily: "var(--font-mono, monospace)" }}>
                  "{activeEvidenceQuote}"
                </p>
              </div>
            )}

            {/* Embedded Iframe Preview */}
            <div style={{ flex: 1, position: "relative", background: "var(--surface-soft)" }}>
              {activeEvidencePaper ? (
                <iframe
                  key={`${activeEvidencePaper.id}-page-${activeEvidencePage}`}
                  src={`${api.getPaperFileUrl(activeEvidencePaper.id)}#page=${activeEvidencePage}`}
                  title={activeEvidencePaper.original_filename}
                  style={{
                    width: "100%",
                    height: "100%",
                    border: "none",
                  }}
                />
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)", fontSize: "13px" }}>
                  Select a paper above or click a citation marker in chat to inspect evidence.
                </div>
              )}
            </div>
          </Card>

          {/* RIGHT PANE: Conversational Research Chat */}
          <Card
            elevation={2}
            style={{
              display: "flex",
              flexDirection: "column",
              height: "720px",
              border: "1px solid var(--hairline-strong, #d1d5db)",
            }}
          >
            {/* Conversation Header & Threads */}
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--hairline)",
                background: "var(--surface-sunken)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <MessageSquare size={18} color="var(--blue-action)" />
                <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary)" }}>
                  Grounded Research Chat
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {conversations.length > 0 && (
                  <select
                    value={activeConversationId || ""}
                    onChange={(e) => setActiveConversationId(e.target.value || null)}
                    style={{
                      fontSize: "12px",
                      padding: "4px 8px",
                      borderRadius: "var(--r-md)",
                      border: "1px solid var(--hairline)",
                      background: "var(--surface)",
                      maxWidth: "180px",
                    }}
                  >
                    <option value="">New Conversation</option>
                    {conversations.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title}
                      </option>
                    ))}
                  </select>
                )}
                {activeConversationId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => handleDeleteConversation(activeConversationId, e)}
                    aria-label="Delete conversation"
                    style={{ padding: "4px" }}
                  >
                    <Trash2 size={14} color="var(--red-text, #d70015)" />
                  </Button>
                )}
              </div>
            </div>

            {/* Error Banner */}
            {assistantError && (
              <div
                style={{
                  margin: "12px 16px 0 16px",
                  padding: "10px 14px",
                  borderRadius: "var(--r-md)",
                  background: "rgba(255, 59, 48, 0.08)",
                  border: "1px solid var(--red-border, #ff3b30)",
                  color: "var(--red-text, #d70015)",
                  fontSize: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <AlertCircle size={15} />
                <span>{assistantError}</span>
              </div>
            )}

            {/* Messages Scroll Area */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              {chatMessages.length === 0 ? (
                <div style={{ textAlign: "center", padding: "48px 16px", color: "var(--text-secondary)" }}>
                  <MessageSquare size={32} style={{ margin: "0 auto 12px auto", opacity: 0.4 }} />
                  <h3 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 6px 0", color: "var(--text-primary)" }}>
                    Ask a Research Question
                  </h3>
                  <p style={{ fontSize: "13px", margin: 0, maxWidth: "340px", lineHeight: 1.5 }}>
                    Inquire about methodologies, findings, model architectures, or empirical results. Every answer is grounded in your selected papers with verifiable citations.
                  </p>
                </div>
              ) : (
                chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                      gap: "6px",
                    }}
                  >
                    {/* Role Header */}
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      {msg.role === "user" ? "You" : "ResearchMind AI"} • {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>

                    {/* Message Bubble */}
                    <div
                      style={{
                        maxWidth: "88%",
                        padding: "12px 16px",
                        borderRadius: "var(--r-lg)",
                        fontSize: "13px",
                        lineHeight: 1.6,
                        background: msg.role === "user" ? "var(--blue-action)" : "var(--surface)",
                        color: msg.role === "user" ? "#ffffff" : "var(--text-primary)",
                        border: msg.role === "user" ? "none" : "1px solid var(--hairline)",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      {/* Rewritten Query note if present */}
                      {msg.rewritten_query && (
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px", fontStyle: "italic" }}>
                          Expanded focus: "{msg.rewritten_query}"
                        </div>
                      )}

                      {/* Honest Abstention Banner */}
                      {msg.is_abstention && (
                        <div
                          style={{
                            marginBottom: "10px",
                            padding: "8px 12px",
                            borderRadius: "var(--r-md)",
                            background: "rgba(255, 149, 0, 0.12)",
                            border: "1px solid rgba(255, 149, 0, 0.4)",
                            color: "#b25000",
                            fontWeight: 600,
                            fontSize: "12px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <AlertCircle size={14} />
                          <span>Honest Abstention: Evidence is insufficient in the selected sources.</span>
                        </div>
                      )}

                      <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>

                      {/* Citations Row */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div
                          style={{
                            marginTop: "12px",
                            paddingTop: "10px",
                            borderTop: "1px solid var(--hairline)",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>
                            Citations & Evidence Links:
                          </span>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {msg.citations.map((c) => (
                              <button
                                key={c.citation_id}
                                type="button"
                                onClick={() => handleCitationClick(c)}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  padding: "3px 8px",
                                  fontSize: "11px",
                                  borderRadius: "var(--r-sm)",
                                  background: activeCitationId === c.citation_id ? "var(--blue-action)" : "var(--surface-soft)",
                                  color: activeCitationId === c.citation_id ? "#ffffff" : "var(--blue-action)",
                                  border: "1px solid var(--hairline)",
                                  cursor: "pointer",
                                }}
                              >
                                <strong>{c.citation_id}</strong>
                                <span>{c.paper_title || "Source"} (p.{c.page_number})</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              {isSubmittingQuery && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-secondary)", fontSize: "12px" }}>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Synthesizing grounded response with citation verification...</span>
                </div>
              )}
            </div>

            {/* Input Form */}
            <form
              onSubmit={handleSubmitAssistantQuery}
              style={{
                padding: "12px 16px",
                borderTop: "1px solid var(--hairline)",
                background: "var(--surface)",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Depth Mode:</span>
                {(["concise", "detailed", "comparison"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setAssistantMode(m)}
                    style={{
                      fontSize: "11px",
                      padding: "2px 8px",
                      borderRadius: "var(--r-sm)",
                      border: "1px solid var(--hairline)",
                      background: assistantMode === m ? "var(--blue-surface)" : "var(--surface)",
                      color: assistantMode === m ? "var(--blue-action)" : "var(--text-secondary)",
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  value={assistantQuery}
                  onChange={(e) => setAssistantQuery(e.target.value)}
                  placeholder="Ask a grounded question across selected papers..."
                  disabled={isSubmittingQuery || selectedPaperIds.length === 0}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    fontSize: "13px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--hairline)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                />
                <Button
                  variant="blue"
                  type="submit"
                  disabled={isSubmittingQuery || !assistantQuery.trim() || selectedPaperIds.length === 0}
                >
                  <Send size={15} />
                  <span>Ask</span>
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* TAB 2: Phase 6 Evidence Retrieval Inspector Slice */}
      {activeTab === "retrieval" && (
        <Card
          elevation={2}
          style={{
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            border: "1px solid var(--hairline-strong, #d1d5db)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <Layers size={18} color="var(--blue-action)" />
                <h3 style={{ fontSize: "17px", fontWeight: 600, margin: 0, color: "var(--text-primary)" }}>
                  Evidence Retrieval Inspection
                </h3>
                <Badge variant="info">Phase 6 Hybrid Engine</Badge>
              </div>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
                Search across selected ready documents using dense embeddings (FAISS FlatIP), sparse keywords (BM25), or reciprocal-rank fusion.
              </p>
            </div>
          </div>

          {/* Query Input Bar */}
          <form onSubmit={handleRetrievalSearch} style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 300px", position: "relative" }}>
              <input
                type="text"
                value={retrievalQuery}
                onChange={(e) => setRetrievalQuery(e.target.value)}
                placeholder="Search literature evidence (e.g. self-attention complexity, fault-tolerance threshold)..."
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  fontSize: "14px",
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--hairline)",
                  background: "var(--surface)",
                  color: "var(--text-primary)",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>

            {/* Mode Selector */}
            <select
              value={retrievalMode}
              onChange={(e) => setRetrievalMode(e.target.value as any)}
              style={{
                padding: "10px 12px",
                fontSize: "13px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--hairline)",
                background: "var(--surface)",
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              <option value="hybrid">Hybrid (RRF k=60)</option>
              <option value="dense">Dense Only (FAISS)</option>
              <option value="sparse">Sparse Only (BM25)</option>
            </select>

            <Button variant="blue" type="submit" disabled={isSearchingRetrieval || selectedPaperIds.length === 0}>
              <Search size={16} />
              <span>{isSearchingRetrieval ? "Searching..." : "Retrieve Evidence"}</span>
            </Button>
          </form>

          {/* Error Alert */}
          {retrievalError && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "var(--r-md)",
                background: "rgba(255, 59, 48, 0.08)",
                border: "1px solid var(--red-border, #ff3b30)",
                color: "var(--red-text, #d70015)",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <AlertCircle size={16} />
              <span>{retrievalError}</span>
            </div>
          )}

          {/* Diagnostics Bar */}
          {diagnostics && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "10px 16px",
                background: "var(--surface-soft)",
                borderRadius: "var(--r-md)",
                fontSize: "12px",
                color: "var(--text-secondary)",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                <span>
                  <strong>Mode:</strong> {diagnostics.mode.toUpperCase()}
                </span>
                <span>
                  <strong>Candidates:</strong> {diagnostics.fused_count} passages (from {diagnostics.total_eligible_chunks} eligible chunks)
                </span>
                <span>
                  <strong>Index Version:</strong> v{diagnostics.index_version}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Clock size={14} />
                <span>
                  Total: <strong>{diagnostics.timings.total_ms}ms</strong> (Dense: {diagnostics.timings.dense_ms}ms, Sparse: {diagnostics.timings.sparse_ms}ms, Fusion: {diagnostics.timings.fusion_ms}ms)
                </span>
              </div>
            </div>
          )}

          {/* Guidance Note */}
          {diagnostics && (
            <p style={{ fontSize: "11px", color: "var(--text-tertiary, #8e8e93)", margin: "-8px 0 0 0", fontStyle: "italic" }}>
              Note: {diagnostics.score_explanation}
            </p>
          )}

          {/* Passages Results List */}
          {passages !== null && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {passages.length === 0 ? (
                <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-secondary)" }}>
                  <p style={{ margin: 0, fontSize: "14px" }}>No matching evidence passages found in the selected paper(s).</p>
                </div>
              ) : (
                passages.map((p) => (
                  <div
                    key={`${p.chunk_id}-${p.rank}`}
                    style={{
                      padding: "16px",
                      borderRadius: "var(--r-lg)",
                      background: "var(--surface)",
                      border: "1px solid var(--hairline)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Badge variant="info">#{p.rank} · Score {p.score}</Badge>
                        <Badge variant="neutral">{p.paper_title || "Paper"}</Badge>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500 }}>
                          Section: {p.section} · p.{p.page_start}{p.page_end > p.page_start ? `–${p.page_end}` : ""}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {p.dense_rank && (
                          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #8e8e93)" }}>
                            Dense #{p.dense_rank} ({p.dense_score})
                          </span>
                        )}
                        {p.sparse_rank && (
                          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #8e8e93)" }}>
                            Sparse #{p.sparse_rank} ({p.sparse_score})
                          </span>
                        )}
                        <Button
                          variant="soft"
                          size="sm"
                          onClick={() => {
                            const found = readyPapers.find((item) => item.id === p.paper_id);
                            if (found) handleOpenPdfModal(found, p.page_start);
                          }}
                        >
                          <ExternalLink size={12} />
                          <span>View Page {p.page_start}</span>
                        </Button>
                      </div>
                    </div>

                    <p
                      style={{
                        fontSize: "13px",
                        lineHeight: 1.6,
                        color: "var(--text-primary)",
                        margin: 0,
                        background: "var(--surface-sunken)",
                        padding: "10px 12px",
                        borderRadius: "var(--r-md)",
                        fontFamily: "var(--font-mono, monospace)",
                      }}
                    >
                      {p.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </Card>
      )}

      {/* PDF Viewer Modal */}
      {modalPaper && (
        <PdfViewerModal
          isOpen={isPdfModalOpen}
          paper={modalPaper}
          initialPage={modalPage}
          onClose={() => {
            setIsPdfModalOpen(false);
            setModalPaper(null);
          }}
        />
      )}
    </div>
  );
};
