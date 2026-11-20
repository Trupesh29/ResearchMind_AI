import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AlertTriangle,
  Eye,
  RefreshCw,
  BookOpen,
  AlertCircle,
  FileText,
  ArrowRight,
} from "lucide-react";
import { api, ApiClientError } from "../api/client";
import {
  WorkspaceItem,
  PaperItem,
  PaperStatusResponse,
  ChunkItem,
  SectionItem,
} from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PdfViewerModal } from "../components/library/PdfViewerModal";

const STORAGE_KEY_SELECTED_WS = "researchmind_selected_workspace_id";

const PIPELINE_STAGES = [
  {
    id: "validating",
    label: "Validating",
    desc: "Magic bytes, file integrity & openability",
  },
  {
    id: "extracting",
    label: "Extracting",
    desc: "Text, dimensions, bounding boxes & metadata",
  },
  {
    id: "sectioning",
    label: "Sectioning",
    desc: "Structural sections & reference zones",
  },
  {
    id: "chunking",
    label: "Chunking",
    desc: "Semantic units & token bounding",
  },
  {
    id: "embedding",
    label: "Embedding",
    desc: "all-MiniLM-L6-v2 dense vectors (384-d)",
  },
  {
    id: "indexing",
    label: "Indexing",
    desc: "Paired FAISS & BM25 workspace publication",
  },
];

interface QualityCenterPageProps {
  onNavigate?: (path: string) => void;
}

export const QualityCenterPage: React.FC<QualityCenterPageProps> = ({
  onNavigate,
}) => {
  // Navigation / Deep Linking
  const navigate =
    onNavigate ||
    ((path: string) => {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

  // Workspaces state
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState<boolean>(true);

  // Papers state
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<string>("");
  const [isLoadingPapers, setIsLoadingPapers] = useState<boolean>(false);
  const [paperNotFound, setPaperNotFound] = useState<string | null>(null);

  // Inspection Data state
  const [statusData, setStatusData] = useState<PaperStatusResponse | null>(
    null,
  );
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [nextChunkCursor, setNextChunkCursor] = useState<string | null>(null);
  const [isLoadingMoreChunks, setIsLoadingMoreChunks] =
    useState<boolean>(false);
  const [sections, setSections] = useState<SectionItem[]>([]);
  const [inspectionError, setInspectionError] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<
    "pipeline" | "chunks" | "metadata"
  >("pipeline");

  // Filters
  const [sectionFilter, setSectionFilter] = useState<string>("");
  const [pageFilter, setPageFilter] = useState<string>("");
  const [searchFilter, setSearchFilter] = useState<string>("");

  // Actions state
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);
  const [reprocessMsg, setReprocessMsg] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // PDF Viewer Modal
  const [isViewingPdf, setIsViewingPdf] = useState<boolean>(false);
  const [selectedViewerPage, setSelectedViewerPage] = useState<number>(1);

  // Request & Polling guards
  const activeReqRef = useRef<number>(0);
  const abortCtrlRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<any>(null);
  const paperListReqIdRef = useRef<number>(0);
  const paperListAbortCtrlRef = useRef<AbortController | null>(null);
  const selectedWorkspaceIdRef = useRef<string>(selectedWorkspaceId);
  const reprocessActionTokenRef = useRef<number>(0);
  const loadMoreActionTokenRef = useRef<number>(0);
  const currentPaperIdRef = useRef<string>("");

  useEffect(() => {
    selectedWorkspaceIdRef.current = selectedWorkspaceId;
  }, [selectedWorkspaceId]);

  useEffect(() => {
    currentPaperIdRef.current = selectedPaperId;
  }, [selectedPaperId]);

  // Handle workspace change with full state fencing & cancellation
  const handleSelectWorkspace = useCallback((newWs: string) => {
    selectedWorkspaceIdRef.current = newWs;

    // Invalidate and cancel previous paper list requests
    paperListReqIdRef.current += 1;
    if (paperListAbortCtrlRef.current) {
      paperListAbortCtrlRef.current.abort();
      paperListAbortCtrlRef.current = null;
    }

    // Invalidate and cancel any ongoing inspection or polling requests
    activeReqRef.current += 1;
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
      abortCtrlRef.current = null;
    }
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    // Reset action tokens
    reprocessActionTokenRef.current += 1;
    loadMoreActionTokenRef.current += 1;
    setIsReprocessing(false);
    setIsLoadingMoreChunks(false);

    // Immediately clear old workspace and paper state
    setPapers([]);
    setSelectedPaperId("");
    setPaperNotFound(null);
    setStatusData(null);
    setChunks([]);
    setTotalChunks(0);
    setNextChunkCursor(null);
    setSections([]);
    setInspectionError(null);
    setReprocessMsg(null);
    setSectionFilter("");
    setPageFilter("");
    setSearchFilter("");

    // Clean up URL query parameters
    const url = new URL(window.location.href);
    url.searchParams.delete("paper");
    window.history.pushState({}, "", url.pathname + url.search);

    // Set new workspace
    setSelectedWorkspaceId(newWs);
    localStorage.setItem(STORAGE_KEY_SELECTED_WS, newWs);
  }, []);

  // 1. Initial Workspace Load
  useEffect(() => {
    let isMounted = true;
    setIsLoadingWorkspaces(true);
    api
      .listAllWorkspaces()
      .then((items) => {
        if (!isMounted) return;
        setWorkspaces(items);
        if (items.length > 0) {
          const stored = localStorage.getItem(STORAGE_KEY_SELECTED_WS);
          const matched = items.find((w) => w.id === stored);
          const initialWsId = matched ? matched.id : items[0].id;
          setSelectedWorkspaceId(initialWsId);
          selectedWorkspaceIdRef.current = initialWsId;
          localStorage.setItem(STORAGE_KEY_SELECTED_WS, initialWsId);
        }
      })
      .catch((err: any) => {
        if (isMounted)
          setInspectionError(err?.message || "Failed to load workspaces.");
      })
      .finally(() => {
        if (isMounted) setIsLoadingWorkspaces(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch Papers when Workspace changes
  const loadPapers = useCallback(async (wsId: string) => {
    if (!wsId) {
      setPapers([]);
      setIsLoadingPapers(false);
      return;
    }

    const reqId = ++paperListReqIdRef.current;
    if (paperListAbortCtrlRef.current) {
      paperListAbortCtrlRef.current.abort();
    }
    const abortCtrl = new AbortController();
    paperListAbortCtrlRef.current = abortCtrl;

    setIsLoadingPapers(true);
    setPaperNotFound(null);

    try {
      const res = await api.listPapers(wsId, {
        limit: 100,
        signal: abortCtrl.signal,
      });

      // Request fence: check generation identity and workspace alignment
      if (
        reqId !== paperListReqIdRef.current ||
        wsId !== selectedWorkspaceIdRef.current
      ) {
        return;
      }

      setPapers(res.items);

      // Check URL search params for deep-linked paper
      const params = new URLSearchParams(window.location.search);
      const urlPaperId = params.get("paper");

      if (urlPaperId) {
        const found = res.items.find((p) => p.id === urlPaperId);
        if (found) {
          setSelectedPaperId(found.id);
          setPaperNotFound(null);
        } else {
          setSelectedPaperId("");
          setPaperNotFound(urlPaperId);
        }
      } else {
        setSelectedPaperId("");
        setPaperNotFound(null);
      }
    } catch (err: any) {
      if (err?.name === "AbortError" || abortCtrl.signal.aborted) {
        return;
      }
      if (
        reqId !== paperListReqIdRef.current ||
        wsId !== selectedWorkspaceIdRef.current
      ) {
        return;
      }
      setInspectionError(
        err?.message || "Failed to load papers for workspace.",
      );
    } finally {
      if (reqId === paperListReqIdRef.current) {
        setIsLoadingPapers(false);
      }
    }
  }, []);

  useEffect(() => {
    selectedWorkspaceIdRef.current = selectedWorkspaceId;
    if (selectedWorkspaceId) {
      loadPapers(selectedWorkspaceId);
    }
  }, [selectedWorkspaceId, loadPapers]);

  // 3. Listen to browser popstate to sync URL ?paper=
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const urlPaperId = params.get("paper");
      if (urlPaperId !== currentPaperIdRef.current) {
        reprocessActionTokenRef.current += 1;
        loadMoreActionTokenRef.current += 1;
        setIsReprocessing(false);
        setIsLoadingMoreChunks(false);
        setReprocessMsg(null);
      }
      if (urlPaperId) {
        const found = papers.find((p) => p.id === urlPaperId);
        if (found) {
          setSelectedPaperId(found.id);
          setPaperNotFound(null);
        } else {
          setSelectedPaperId("");
          setPaperNotFound(urlPaperId);
        }
      } else {
        setSelectedPaperId("");
        setPaperNotFound(null);
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [papers]);

  // 4. Handle paper selection change
  const handleSelectPaper = (paperId: string) => {
    reprocessActionTokenRef.current += 1;
    loadMoreActionTokenRef.current += 1;
    setIsReprocessing(false);
    setIsLoadingMoreChunks(false);
    setSelectedPaperId(paperId);
    setPaperNotFound(null);
    setReprocessMsg(null);
    setSectionFilter("");
    setPageFilter("");
    setSearchFilter("");

    const url = new URL(window.location.href);
    if (paperId) {
      url.searchParams.set("paper", paperId);
    } else {
      url.searchParams.delete("paper");
    }
    window.history.pushState({}, "", url.pathname + url.search);
  };

  // 5. Fetch Inspection Data for Selected Paper
  const loadInspectionData = useCallback(
    async (isPolling: boolean = false) => {
      if (!selectedPaperId) {
        setStatusData(null);
        setChunks([]);
        setSections([]);
        return;
      }

      const reqId = ++activeReqRef.current;
      if (!isPolling) {
        setInspectionError(null);
      }

      if (abortCtrlRef.current) {
        abortCtrlRef.current.abort();
      }
      const abortCtrl = new AbortController();
      abortCtrlRef.current = abortCtrl;

      try {
        const [statusRes, chunksRes, sectionsRes] = await Promise.all([
          api.getPaperStatus(selectedPaperId, abortCtrl.signal),
          api.getPaperChunks(selectedPaperId, {
            section: sectionFilter || undefined,
            page: pageFilter ? parseInt(pageFilter, 10) : undefined,
            limit: 100,
            signal: abortCtrl.signal,
          }),
          api.getPaperSections(selectedPaperId, abortCtrl.signal),
        ]);

        if (reqId !== activeReqRef.current) return;

        setInspectionError(null);
        setStatusData(statusRes);
        setChunks(chunksRes.items);
        setTotalChunks(chunksRes.total);
        setNextChunkCursor(chunksRes.next_cursor || null);
        setSections(sectionsRes.items);

        // Auto-poll if processing or uploaded
        if (
          statusRes.status === "processing" ||
          statusRes.status === "uploaded"
        ) {
          pollTimerRef.current = setTimeout(() => {
            loadInspectionData(true);
          }, 2000);
        }
      } catch (err: any) {
        if (err?.name === "AbortError" || err?.name === "CanceledError") return;
        if (reqId === activeReqRef.current) {
          if (
            err instanceof ApiClientError &&
            (err.statusCode === 404 || err.code === "NOT_FOUND")
          ) {
            setPaperNotFound(selectedPaperId);
            setSelectedPaperId("");
          } else {
            setInspectionError(
              err?.message || "Failed to inspect paper quality data.",
            );
            // Automatic retry on transient error
            pollTimerRef.current = setTimeout(() => {
              loadInspectionData(true);
            }, 2000);
          }
        }
      }
    },
    [selectedPaperId, sectionFilter, pageFilter],
  );

  useEffect(() => {
    loadInspectionData(false);
    return () => {
      if (abortCtrlRef.current) abortCtrlRef.current.abort();
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [loadInspectionData]);

  // Load More Chunks pagination
  const handleLoadMoreChunks = async () => {
    if (!selectedPaperId || !nextChunkCursor || isLoadingMoreChunks) return;
    const targetPaperId = selectedPaperId;
    const actionToken = ++loadMoreActionTokenRef.current;
    setIsLoadingMoreChunks(true);
    try {
      const res = await api.getPaperChunks(targetPaperId, {
        section: sectionFilter || undefined,
        page: pageFilter ? parseInt(pageFilter, 10) : undefined,
        cursor: nextChunkCursor,
        limit: 100,
      });
      if (
        actionToken !== loadMoreActionTokenRef.current ||
        targetPaperId !== currentPaperIdRef.current
      ) {
        return;
      }
      setChunks((prev) => [...prev, ...res.items]);
      setNextChunkCursor(res.next_cursor || null);
    } catch (err: any) {
      if (
        actionToken !== loadMoreActionTokenRef.current ||
        targetPaperId !== currentPaperIdRef.current
      ) {
        return;
      }
      setInspectionError(err?.message || "Failed to load more chunks.");
    } finally {
      if (
        actionToken === loadMoreActionTokenRef.current &&
        targetPaperId === currentPaperIdRef.current
      ) {
        setIsLoadingMoreChunks(false);
      }
    }
  };

  // Reprocess action
  const handleReprocess = async () => {
    if (!selectedPaperId || isReprocessing) return;
    const targetPaperId = selectedPaperId;
    const actionToken = ++reprocessActionTokenRef.current;
    setIsReprocessing(true);
    setReprocessMsg(null);
    try {
      await api.reprocessPaper(targetPaperId);
      if (
        actionToken !== reprocessActionTokenRef.current ||
        targetPaperId !== currentPaperIdRef.current
      ) {
        return;
      }
      setReprocessMsg({
        type: "success",
        text: "Reprocessing job dispatched to worker.",
      });
      await loadInspectionData(false);
      if (selectedWorkspaceId) await loadPapers(selectedWorkspaceId);
    } catch (err: any) {
      if (
        actionToken !== reprocessActionTokenRef.current ||
        targetPaperId !== currentPaperIdRef.current
      ) {
        return;
      }
      setReprocessMsg({
        type: "error",
        text: err?.message || "Failed to initiate document reprocessing.",
      });
    } finally {
      if (
        actionToken === reprocessActionTokenRef.current &&
        targetPaperId === currentPaperIdRef.current
      ) {
        setIsReprocessing(false);
      }
    }
  };

  const selectedPaper = papers.find((p) => p.id === selectedPaperId) || null;

  // Filter chunks by search term in memory if searchFilter is set
  const filteredChunks = searchFilter
    ? chunks.filter((c) =>
        c.text.toLowerCase().includes(searchFilter.toLowerCase()),
      )
    : chunks;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "28px",
        maxWidth: "1200px",
        margin: "0 auto",
        width: "100%",
      }}
    >
      {/* Inspection Guidance Region */}
      <div
        role="region"
        aria-label="Quality Center Inspection Guidance"
        style={{ display: "none" }}
      >
        Quality Center · Inspection Mode
      </div>

      {/* Page Header */}
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
              marginBottom: "6px",
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
              Quality Center
            </h1>
            <Badge variant="success">Active · Phase 2</Badge>
          </div>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: "14px",
              margin: 0,
              maxWidth: "720px",
              lineHeight: 1.5,
            }}
          >
            Inspect document processing stages, tokenization limits, chunk
            provenance, and vector index membership across the 6-stage ingestion
            pipeline.
          </p>
        </div>

        {/* Top Controls: Workspace & Paper Selectors */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          {/* Workspace Select */}
          {workspaces.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                }}
              >
                Workspace:
              </span>
              <select
                aria-label="Select Workspace"
                value={selectedWorkspaceId}
                onChange={(e) => {
                  handleSelectWorkspace(e.target.value);
                }}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--border-control)",
                  background: "var(--surface)",
                  color: "var(--text-primary)",
                  fontSize: "13px",
                  fontWeight: 500,
                  outline: "none",
                }}
              >
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.paper_count} papers)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Paper Select */}
          {papers.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                }}
              >
                Paper:
              </span>
              <select
                aria-label="Select Research Paper"
                value={selectedPaperId}
                onChange={(e) => handleSelectPaper(e.target.value)}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--border-control)",
                  background: "var(--surface)",
                  color: "var(--text-primary)",
                  fontSize: "13px",
                  fontWeight: 500,
                  maxWidth: "280px",
                  outline: "none",
                }}
              >
                <option value="">-- Choose Paper to Inspect --</option>
                {papers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title
                      ? `${p.title.substring(0, 35)}...`
                      : p.original_filename}{" "}
                    ({p.status})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Global Error Banner */}
      {inspectionError && (
        <div
          role="alert"
          style={{
            padding: "12px 18px",
            borderRadius: "var(--r-lg)",
            background: "var(--red-surface)",
            border: "1px solid rgba(255, 59, 48, 0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            color: "var(--red-text)",
            fontSize: "13px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <AlertCircle size={18} color="var(--red-strong)" />
            <span>{inspectionError}</span>
          </div>
          <Button
            variant="soft"
            size="sm"
            onClick={() => loadInspectionData(false)}
          >
            <RefreshCw size={12} />
            <span>Retry</span>
          </Button>
        </div>
      )}

      {/* Reprocess Feedback Message */}
      {reprocessMsg && (
        <div
          role="status"
          style={{
            padding: "10px 16px",
            borderRadius: "var(--r-md)",
            background:
              reprocessMsg.type === "success"
                ? "var(--green-surface, rgba(52, 199, 89, 0.12))"
                : "var(--red-surface)",
            border: `1px solid ${reprocessMsg.type === "success" ? "rgba(52, 199, 89, 0.3)" : "rgba(255, 59, 48, 0.3)"}`,
            color:
              reprocessMsg.type === "success"
                ? "var(--green-text, #248a3d)"
                : "var(--red-text)",
            fontSize: "13px",
          }}
        >
          {reprocessMsg.text}
        </div>
      )}

      {/* Honest Empty States */}
      {!isLoadingWorkspaces && workspaces.length === 0 && (
        <Card elevation={1}>
          <div
            style={{
              padding: "48px 24px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "14px",
            }}
          >
            <BookOpen size={36} color="var(--blue-action)" />
            <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
              No Research Workspaces Found
            </h2>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                maxWidth: "420px",
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              Workspaces isolate research literature. Create a workspace in
              Paper Library to upload documents and inspect quality.
            </p>
            <Button variant="ink" onClick={() => navigate("/library")}>
              <span>Open Paper Library</span>
              <ArrowRight size={14} />
            </Button>
          </div>
        </Card>
      )}

      {!isLoadingWorkspaces &&
        workspaces.length > 0 &&
        !isLoadingPapers &&
        papers.length === 0 && (
          <Card elevation={1}>
            <div
              style={{
                padding: "48px 24px",
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "14px",
              }}
            >
              <FileText size={36} color="var(--blue-action)" />
              <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
                No Papers in this Workspace
              </h2>
              <p
                style={{
                  fontSize: "14px",
                  color: "var(--text-secondary)",
                  maxWidth: "420px",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                This workspace does not have any research papers yet. Upload
                documents in the Paper Library to run the ingestion pipeline.
              </p>
              <Button variant="ink" onClick={() => navigate("/library")}>
                <span>Upload Papers in Library</span>
                <ArrowRight size={14} />
              </Button>
            </div>
          </Card>
        )}

      {paperNotFound && (
        <Card elevation={1}>
          <div
            style={{
              padding: "36px 24px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <AlertTriangle size={32} color="var(--orange-strong, #f5a623)" />
            <h2 style={{ fontSize: "17px", fontWeight: 700, margin: 0 }}>
              Deep-Linked Paper Not Found
            </h2>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-secondary)",
                maxWidth: "440px",
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              The paper with ID <code>{paperNotFound}</code> was not found in
              the selected workspace. It may have been deleted, moved, or
              belonging to another workspace.
            </p>
            <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
              <Button
                variant="soft"
                size="sm"
                onClick={() => handleSelectPaper("")}
              >
                <span>Clear Selection</span>
              </Button>
              <Button
                variant="ink"
                size="sm"
                onClick={() => navigate("/library")}
              >
                <span>Return to Library</span>
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!selectedPaperId && !paperNotFound && papers.length > 0 && (
        <Card elevation={1}>
          <div
            style={{
              padding: "48px 24px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "14px",
            }}
          >
            <Eye size={36} color="var(--blue-action)" />
            <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
              Select a Research Paper
            </h2>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                maxWidth: "480px",
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              Choose any document from the dropdown selector above to inspect
              its 6-stage ingestion pipeline, section spans, chunk token counts,
              and vector index membership.
            </p>
          </div>
        </Card>
      )}

      {/* Selected Paper Ingestion Inspection View */}
      {selectedPaper && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Paper Summary Card */}
          <Card elevation={1}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                flexWrap: "wrap",
                gap: "16px",
              }}
            >
              <div style={{ flex: 1, minWidth: "280px" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    marginBottom: "8px",
                  }}
                >
                  <h2
                    style={{
                      fontSize: "18px",
                      fontWeight: 700,
                      margin: 0,
                      color: "var(--text-primary)",
                    }}
                  >
                    {selectedPaper.title || selectedPaper.original_filename}
                  </h2>
                  <Badge
                    variant={
                      selectedPaper.status === "ready"
                        ? "success"
                        : selectedPaper.status === "failed"
                          ? "error"
                          : "warning"
                    }
                  >
                    {selectedPaper.status.toUpperCase()}
                  </Badge>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "16px",
                    flexWrap: "wrap",
                    fontSize: "12px",
                    color: "var(--text-muted)",
                  }}
                >
                  <span>
                    File: <strong>{selectedPaper.original_filename}</strong>
                  </span>
                  <span>
                    Size:{" "}
                    <strong>
                      {(selectedPaper.size_bytes / (1024 * 1024)).toFixed(2)} MB
                    </strong>
                  </span>
                  <span>
                    Pages:{" "}
                    <strong>{selectedPaper.page_count ?? "Unknown"}</strong>
                  </span>
                  {statusData?.published_run_id && (
                    <span>
                      Published Run:{" "}
                      <code style={{ fontSize: "11px" }}>
                        {statusData.published_run_id.substring(0, 8)}
                      </code>
                    </span>
                  )}
                  {statusData?.current_run_id &&
                    statusData?.current_run_id !==
                      statusData?.published_run_id && (
                      <span style={{ color: "var(--blue-action)" }}>
                        Active In-Flight Run:{" "}
                        <code style={{ fontSize: "11px" }}>
                          {statusData.current_run_id.substring(0, 8)}
                        </code>
                      </span>
                    )}
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <Button
                  variant="soft"
                  size="sm"
                  onClick={() => setIsViewingPdf(true)}
                >
                  <Eye size={14} />
                  <span>View Original PDF</span>
                </Button>
                <Button
                  variant="soft"
                  size="sm"
                  aria-label="Reprocess document"
                  onClick={handleReprocess}
                  isLoading={isReprocessing}
                  disabled={isReprocessing}
                >
                  <RefreshCw
                    size={14}
                    className={isReprocessing ? "animate-spin" : ""}
                  />
                  <span>{isReprocessing ? "Enqueueing..." : "Reprocess"}</span>
                </Button>
              </div>
            </div>
          </Card>

          {/* 6-Stage Timeline */}
          <Card elevation={1}>
            <div style={{ marginBottom: "16px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
                  6-Stage Processing Pipeline
                </h3>
                {statusData && (
                  <span
                    style={{ fontSize: "12px", color: "var(--text-muted)" }}
                  >
                    Progress:{" "}
                    <strong>
                      {Math.round((statusData.progress || 0) * 100)}%
                    </strong>
                  </span>
                )}
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: "12px",
              }}
            >
              {PIPELINE_STAGES.map((st, idx) => {
                const stageDetail = statusData?.stages?.find(
                  (s) => s.stage === st.id,
                );
                const isCurrent = statusData?.stage === st.id;
                const isFailed = statusData?.status === "failed" && isCurrent;
                const isDone =
                  selectedPaper.status === "ready" ||
                  (stageDetail && stageDetail.status === "completed") ||
                  (statusData?.progress !== undefined &&
                    statusData.progress > (idx + 1) / 6);

                let badgeVariant: "neutral" | "info" | "success" | "warning" =
                  "neutral";
                let statusLabel = "Pending";

                if (isFailed) {
                  badgeVariant = "warning";
                  statusLabel = "Failed";
                } else if (isDone) {
                  badgeVariant = "success";
                  statusLabel = "Completed";
                } else if (isCurrent) {
                  badgeVariant = "info";
                  statusLabel = "In Progress";
                }

                return (
                  <div
                    key={st.id}
                    style={{
                      padding: "14px 12px",
                      borderRadius: "var(--r-md)",
                      background: isCurrent
                        ? "var(--surface-soft)"
                        : "var(--surface-sunken)",
                      border: `1px solid ${isCurrent ? "var(--blue-action)" : "var(--hairline)"}`,
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "var(--text-muted)",
                        }}
                      >
                        0{idx + 1}
                      </span>
                      <Badge variant={badgeVariant}>{statusLabel}</Badge>
                    </div>
                    <div
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                      }}
                    >
                      {st.label}
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "var(--text-secondary)",
                        lineHeight: 1.4,
                      }}
                    >
                      {st.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Sub-view Navigation Tabs */}
          <div
            style={{
              display: "flex",
              gap: "8px",
              borderBottom: "1px solid var(--hairline)",
              paddingBottom: "8px",
            }}
          >
            <button
              role="tab"
              aria-selected={activeTab === "pipeline"}
              onClick={() => setActiveTab("pipeline")}
              style={{
                padding: "8px 14px",
                borderRadius: "var(--r-md)",
                border: "none",
                background:
                  activeTab === "pipeline"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "pipeline"
                    ? "var(--blue-action)"
                    : "var(--text-secondary)",
                fontWeight: activeTab === "pipeline" ? 600 : 500,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Stage History
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "chunks"}
              onClick={() => setActiveTab("chunks")}
              style={{
                padding: "8px 14px",
                borderRadius: "var(--r-md)",
                border: "none",
                background:
                  activeTab === "chunks"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "chunks"
                    ? "var(--blue-action)"
                    : "var(--text-secondary)",
                fontWeight: activeTab === "chunks" ? 600 : 500,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Chunks ({totalChunks})
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "metadata"}
              onClick={() => setActiveTab("metadata")}
              style={{
                padding: "8px 14px",
                borderRadius: "var(--r-md)",
                border: "none",
                background:
                  activeTab === "metadata"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "metadata"
                    ? "var(--blue-action)"
                    : "var(--text-secondary)",
                fontWeight: activeTab === "metadata" ? 600 : 500,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Index & Membership
            </button>
          </div>

          {/* Tab 1: Pipeline & History */}
          {activeTab === "pipeline" && (
            <Card elevation={1}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "16px",
                }}
              >
                <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
                  Execution State & Worker Telemetry
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "16px",
                    fontSize: "13px",
                  }}
                >
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Active Stage:
                    </span>
                    <strong>{statusData?.stage || "None"}</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Attempt:
                    </span>
                    <strong>{statusData?.attempt ?? 1} / 3</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Run ID:
                    </span>
                    <code style={{ fontSize: "12px" }}>
                      {statusData?.run_id || "None"}
                    </code>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Stale Worker Recovery:
                    </span>
                    <strong>
                      {statusData?.is_stale
                        ? "Detected & Reprocessing"
                        : "Nominal"}
                    </strong>
                  </div>
                </div>

                {statusData?.error && (
                  <div
                    style={{
                      padding: "12px",
                      borderRadius: "var(--r-md)",
                      background: "var(--red-surface)",
                      border: "1px solid rgba(255,59,48,0.3)",
                      color: "var(--red-text)",
                      fontSize: "13px",
                    }}
                  >
                    <strong>Pipeline Error:</strong> {statusData.error}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Tab 2: Extracted Chunks */}
          {activeTab === "chunks" && (
            <div
              style={{ display: "flex", flexDirection: "column", gap: "16px" }}
            >
              {/* Filter Bar */}
              <div
                style={{
                  display: "flex",
                  gap: "12px",
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    gap: "12px",
                    flexWrap: "wrap",
                    alignItems: "center",
                  }}
                >
                  {sections.length > 0 && (
                    <select
                      aria-label="Filter by section"
                      value={sectionFilter}
                      onChange={(e) => setSectionFilter(e.target.value)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: "var(--r-md)",
                        border: "1px solid var(--border-control)",
                        background: "var(--surface)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                        outline: "none",
                      }}
                    >
                      <option value="">All Sections</option>
                      {sections.map((s) => (
                        <option key={s.id} value={s.section}>
                          {s.section}
                        </option>
                      ))}
                    </select>
                  )}

                  <input
                    type="text"
                    placeholder="Filter chunk text..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "var(--r-md)",
                      border: "1px solid var(--border-control)",
                      background: "var(--surface)",
                      color: "var(--text-primary)",
                      fontSize: "13px",
                      minWidth: "220px",
                      outline: "none",
                    }}
                  />

                  {(sectionFilter || searchFilter) && (
                    <Button
                      variant="soft"
                      size="sm"
                      onClick={() => {
                        setSectionFilter("");
                        setSearchFilter("");
                      }}
                    >
                      Clear Filters
                    </Button>
                  )}
                </div>

                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  Loaded {chunks.length} of {totalChunks} chunks
                </span>
              </div>

              {/* Chunks List */}
              {filteredChunks.length === 0 ? (
                <Card elevation={1}>
                  <div
                    style={{
                      padding: "32px",
                      textAlign: "center",
                      color: "var(--text-muted)",
                      fontSize: "14px",
                    }}
                  >
                    No chunks found matching the filter criteria.
                  </div>
                </Card>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {filteredChunks.map((c) => (
                    <article
                      key={c.id}
                      className="chunk-card"
                      data-testid="chunk-card"
                    >
                      <Card elevation={1}>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "8px",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "8px",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <Badge variant="neutral">
                                Chunk #{c.chunk_index}
                              </Badge>
                              <span
                                style={{
                                  fontSize: "13px",
                                  fontWeight: 600,
                                  color: "var(--text-primary)",
                                }}
                              >
                                {c.section || "Body"}
                              </span>
                              <span
                                style={{
                                  fontSize: "12px",
                                  color: "var(--text-muted)",
                                }}
                              >
                                Page{" "}
                                {c.page_start === c.page_end
                                  ? c.page_start
                                  : `${c.page_start}–${c.page_end}`}
                              </span>
                            </div>

                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: "11px",
                                  color: "var(--text-muted)",
                                }}
                              >
                                <strong>{c.token_count}</strong> tokens (MiniLM
                                limit: 256)
                              </span>
                              {c.is_excluded && (
                                <Badge variant="warning">
                                  Reference Zone (Excluded)
                                </Badge>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                title={`Jump to page ${c.page_start} in PDF viewer`}
                                onClick={() => {
                                  setSelectedViewerPage(c.page_start);
                                  setIsViewingPdf(true);
                                }}
                                style={{ padding: "4px 8px", fontSize: "12px" }}
                              >
                                <Eye size={12} />
                                <span>View Page</span>
                              </Button>
                            </div>
                          </div>

                          <p
                            style={{
                              fontSize: "13px",
                              color: "var(--text-secondary)",
                              lineHeight: 1.6,
                              margin: 0,
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {c.text}
                          </p>
                        </div>
                      </Card>
                    </article>
                  ))}

                  {/* Load More Button */}
                  {nextChunkCursor && (
                    <div style={{ textAlign: "center", marginTop: "12px" }}>
                      <Button
                        variant="soft"
                        onClick={handleLoadMoreChunks}
                        isLoading={isLoadingMoreChunks}
                      >
                        <span>Load More Chunks</span>
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Index & Membership */}
          {activeTab === "metadata" && (
            <Card elevation={1}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "16px",
                }}
              >
                <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
                  Vector Embedding & Workspace Index Architecture
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                    gap: "16px",
                    fontSize: "13px",
                  }}
                >
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Embedding Model:
                    </span>
                    <strong>all-MiniLM-L6-v2 (sentence-transformers)</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Vector Dimension:
                    </span>
                    <strong>384 (float32)</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Normalization:
                    </span>
                    <strong>Unit L2 (tolerance 1e-3)</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Dense Index Engine:
                    </span>
                    <strong>FAISS FlatIP (Inner Product)</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Sparse Index Engine:
                    </span>
                    <strong>BM25 Okapi with exact term scoring</strong>
                  </div>
                  <div>
                    <span
                      style={{ color: "var(--text-muted)", display: "block" }}
                    >
                      Index Publication:
                    </span>
                    <strong>
                      Serialized Publication Slot + CAS Version Check
                    </strong>
                  </div>
                </div>

                <div
                  style={{
                    borderTop: "1px solid var(--hairline)",
                    paddingTop: "14px",
                    marginTop: "8px",
                  }}
                >
                  <h4
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      margin: "0 0 8px 0",
                    }}
                  >
                    Paired Artifact Verification
                  </h4>
                  <p
                    style={{
                      fontSize: "13px",
                      color: "var(--text-secondary)",
                      margin: 0,
                      lineHeight: 1.5,
                    }}
                  >
                    Indexes are published atomically to immutable versioned
                    directories (<code>v1</code>, <code>v2</code>, ...)
                    containing <code>index.faiss</code>, <code>bm25.json</code>,
                    and <code>manifest.json</code> protected by SHA-256
                    checksums and exact database membership matches.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* PDF Viewer Modal */}
          {selectedPaper && (
            <PdfViewerModal
              paper={selectedPaper}
              isOpen={isViewingPdf}
              initialPage={selectedViewerPage}
              onClose={() => setIsViewingPdf(false)}
            />
          )}
        </div>
      )}
    </div>
  );
};
