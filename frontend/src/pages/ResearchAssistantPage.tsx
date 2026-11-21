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
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { api, retrievalApi, ApiClientError } from "../api/client";
import {
  PaperItem,
  WorkspaceItem,
  RetrievalPassage,
  RetrievalDiagnostics,
} from "../api/types";
import { PdfViewerModal } from "../components/library/PdfViewerModal";

interface ResearchAssistantPageProps {
  onNavigate: (path: string) => void;
}

export const ResearchAssistantPage: React.FC<ResearchAssistantPageProps> = ({
  onNavigate,
}) => {
  // Workspaces and ready papers state
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const [readyPapers, setReadyPapers] = useState<PaperItem[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [isLoadingPapers, setIsLoadingPapers] = useState<boolean>(false);

  // Search state
  const [query, setQuery] = useState<string>("");
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Results state
  const [passages, setPassages] = useState<RetrievalPassage[] | null>(null);
  const [diagnostics, setDiagnostics] = useState<RetrievalDiagnostics | null>(null);

  // PDF modal state
  const [viewingPaper, setViewingPaper] = useState<PaperItem | null>(null);
  const [viewingPage, setViewingPage] = useState<number>(1);
  const [isPdfModalOpen, setIsPdfModalOpen] = useState<boolean>(false);

  // Race guard ref
  const activeRequestIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

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

  // Load ready papers when workspace changes
  useEffect(() => {
    if (!selectedWorkspaceId) return;

    // Invalidate stale search results upon workspace switch
    setPassages(null);
    setDiagnostics(null);
    setSearchError(null);

    let isMounted = true;
    setIsLoadingPapers(true);
    api
      .listPapers(selectedWorkspaceId, { status: "ready", limit: 50 })
      .then((res) => {
        if (!isMounted) return;
        const papers = res.items || [];
        setReadyPapers(papers);
        // By default select all ready papers
        setSelectedPaperIds(papers.map((p) => p.id));
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

    return () => {
      isMounted = false;
    };
  }, [selectedWorkspaceId]);

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

  const handleSearch = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      const trimmedQuery = query.trim();
      if (!trimmedQuery) {
        setSearchError("Please enter a search query.");
        return;
      }
      if (selectedPaperIds.length === 0) {
        setSearchError("Please select at least one ready paper to search across.");
        return;
      }

      // Abort any ongoing search to prevent race conditions
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const currentReqId = ++activeRequestIdRef.current;
      setIsSearching(true);
      setSearchError(null);

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

        // Guard against late out-of-order responses
        if (activeRequestIdRef.current !== currentReqId) {
          return;
        }

        setPassages(response.data.passages);
        setDiagnostics(response.data.diagnostics);
      } catch (err: any) {
        if (err?.name === "AbortError") {
          return;
        }
        if (activeRequestIdRef.current === currentReqId) {
          if (err instanceof ApiClientError) {
            setSearchError(`${err.code}: ${err.message}`);
          } else {
            setSearchError(err?.message || "An unexpected error occurred during retrieval.");
          }
          setPassages(null);
          setDiagnostics(null);
        }
      } finally {
        if (activeRequestIdRef.current === currentReqId) {
          setIsSearching(false);
        }
      }
    },
    [query, selectedWorkspaceId, selectedPaperIds, retrievalMode],
  );

  const handleOpenPdf = (paperId: string, pageNumber: number) => {
    const paper = readyPapers.find((p) => p.id === paperId);
    if (paper) {
      setViewingPaper(paper);
      setViewingPage(pageNumber);
      setIsPdfModalOpen(true);
    }
  };

  return (
    <div
      style={{
        maxWidth: "1080px",
        margin: "0 auto",
        padding: "16px 0 48px 0",
        display: "flex",
        flexDirection: "column",
        gap: "28px",
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
          </div>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: "15px",
              margin: 0,
              maxWidth: "680px",
              lineHeight: 1.5,
            }}
          >
            Evidence-grounded conversational synthesis over selected research documents
            with split PDF viewing and verifiable citations.
          </p>
        </div>
        <Button variant="ink" onClick={() => onNavigate("/library")}>
          <BookOpen size={16} />
          <span>Paper Library</span>
        </Button>
      </div>

      {/* Capabilities Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "20px",
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

      {/* Phase 6 Evidence Retrieval Inspector Slice */}
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

          {/* Workspace select */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <label htmlFor="retrieval-ws-select" style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-secondary)" }}>
              Workspace:
            </label>
            <select
              id="retrieval-ws-select"
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
        </div>

        {/* Paper Selection Filter */}
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

        {/* Query Input Bar */}
        <form onSubmit={handleSearch} style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 300px", position: "relative" }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
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

          <Button variant="blue" type="submit" disabled={isSearching || selectedPaperIds.length === 0}>
            <Search size={16} />
            <span>{isSearching ? "Searching..." : "Retrieve Evidence"}</span>
          </Button>
        </form>

        {/* Error Alert */}
        {searchError && (
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
            <span>{searchError}</span>
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
                        onClick={() => handleOpenPdf(p.paper_id, p.page_start)}
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

      {/* Roadmap & Status Box */}
      <div
        style={{
          padding: "20px 24px",
          borderRadius: "var(--r-xl)",
          background: "var(--surface-sunken)",
          border: "1px solid var(--hairline)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "12px",
          }}
        >
          <AlertCircle size={18} color="var(--blue-action)" />
          <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
            Phase 4 Foundation
          </h3>
        </div>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-secondary)",
            lineHeight: 1.6,
            margin: "0 0 16px 0",
          }}
        >
          Document sectioning and semantic chunking with token bounding are complete. The assistant interactive interface will connect to the active FAISS/BM25 retrieval engine in the upcoming synthesis milestone.
        </p>
        <Button variant="soft" size="sm" onClick={() => onNavigate("/library")}>
          <BookOpen size={14} />
          <span>Prepare Papers in Library</span>
        </Button>
      </div>

      {/* PDF Viewer Modal */}
      {viewingPaper && (
        <PdfViewerModal
          isOpen={isPdfModalOpen}
          paper={viewingPaper}
          initialPage={viewingPage}
          onClose={() => {
            setIsPdfModalOpen(false);
            setViewingPaper(null);
          }}
        />
      )}
    </div>
  );
};
