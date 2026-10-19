import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  X,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
  Hash,
  Filter,
  Eye,
  Info,
} from "lucide-react";
import {
  PaperItem,
  PaperStatusResponse,
  ChunkItem,
  SectionItem,
  PageSummaryItem,
} from "../../api/types";
import { api, ApiClientError } from "../../api/client";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface QualityCenterModalProps {
  paper: PaperItem | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenPdfPage?: (paper: PaperItem, pageNumber: number) => void;
}

export const QualityCenterModal: React.FC<QualityCenterModalProps> = ({
  paper,
  isOpen,
  onClose,
  onOpenPdfPage,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<
    "pipeline" | "chunks" | "metadata"
  >("chunks");

  // Inspection Data
  const [statusData, setStatusData] = useState<PaperStatusResponse | null>(
    null,
  );
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [nextChunkCursor, setNextChunkCursor] = useState<string | null>(null);
  const [isLoadingMoreChunks, setIsLoadingMoreChunks] =
    useState<boolean>(false);
  const [sections, setSections] = useState<SectionItem[]>([]);
  const [pages, setPages] = useState<PageSummaryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters for Chunks
  const [sectionFilter, setSectionFilter] = useState<string>("");
  const [pageFilter, setPageFilter] = useState<string>("");
  const [searchFilter, setSearchFilter] = useState<string>("");

  // Action state
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);
  const [reprocessMsg, setReprocessMsg] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Request & Polling guards
  const activeReqRef = useRef<number>(0);
  const activeActionTokenRef = useRef<number>(0);
  const currentPaperIdRef = useRef<string | null>(paper?.id ?? null);
  const currentWorkspaceIdRef = useRef<string | null>(
    paper?.workspace_id ?? null,
  );
  const isOpenRef = useRef<boolean>(isOpen);
  const filtersRef = useRef<{ section: string; page: string }>({
    section: sectionFilter,
    page: pageFilter,
  });
  const currentRunIdRef = useRef<string | null>(null);
  const pollTimerRef = useRef<any>(null);
  const retryCountRef = useRef<number>(0);
  const generationConflictCountRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const statusDataRef = useRef<PaperStatusResponse | null>(null);

  // Synchronously update current identity refs on every render
  currentPaperIdRef.current = paper?.id ?? null;
  currentWorkspaceIdRef.current = paper?.workspace_id ?? null;
  isOpenRef.current = isOpen;
  filtersRef.current = { section: sectionFilter, page: pageFilter };
  statusDataRef.current = statusData;
  currentRunIdRef.current =
    statusData?.published_run_id || statusData?.run_id || null;

  // Invalidate and reset state when active paper or workspace changes
  useEffect(() => {
    activeActionTokenRef.current += 1;
    activeReqRef.current += 1;
    generationConflictCountRef.current = 0;
    retryCountRef.current = 0;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    setStatusData(null);
    statusDataRef.current = null;
    currentRunIdRef.current = null;
    setChunks([]);
    setTotalChunks(0);
    setSections([]);
    setPages([]);
    setNextChunkCursor(null);
    setErrorMsg(null);
    setReprocessMsg(null);
    setSectionFilter("");
    setPageFilter("");
    setSearchFilter("");
    setIsReprocessing(false);
    setIsLoadingMoreChunks(false);
  }, [paper?.id, paper?.workspace_id]);

  // Invalidate active actions, loads, and timers on modal close
  useEffect(() => {
    if (!isOpen) {
      activeActionTokenRef.current += 1;
      activeReqRef.current += 1;
      generationConflictCountRef.current = 0;
      retryCountRef.current = 0;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }

      setIsReprocessing(false);
      setIsLoadingMoreChunks(false);
    }
  }, [isOpen]);

  // Invalidate pagination and load more actions when filters change
  useEffect(() => {
    activeActionTokenRef.current += 1;
    setNextChunkCursor(null);
    setIsLoadingMoreChunks(false);
  }, [sectionFilter, pageFilter]);

  // Focus trap & Escape key
  useEffect(() => {
    if (isOpen && paper) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;

      const timer = setTimeout(() => {
        const closeBtn = modalRef.current?.querySelector<HTMLButtonElement>(
          '[data-action="close"]',
        );
        closeBtn?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        }
        if (e.key === "Tab" && modalRef.current) {
          const focusable = modalRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          );
          if (focusable.length === 0) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (e.shiftKey) {
            if (document.activeElement === first) {
              e.preventDefault();
              last.focus();
            }
          } else {
            if (document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
        }
      };

      document.addEventListener("keydown", handleKeyDown);
      return () => {
        clearTimeout(timer);
        document.removeEventListener("keydown", handleKeyDown);
        if (previouslyFocusedElement.current) {
          previouslyFocusedElement.current.focus();
        }
      };
    }
  }, [isOpen, paper, onClose]);

  // Load All Quality Data (enforces generation agreement on initial, filter, and polling loads)
  const loadData = useCallback(
    async (isPolling: boolean = false) => {
      if (!paper) return;
      const targetPaperId = paper.id;
      const targetWorkspaceId = paper.workspace_id;
      const targetSection = sectionFilter;
      const targetPage = pageFilter;
      const reqId = ++activeReqRef.current;

      if (!isPolling) {
        setIsLoading(true);
        setErrorMsg(null);
      }

      // Cancel in-flight request if present
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortCtrl = new AbortController();
      abortControllerRef.current = abortCtrl;

      try {
        const [statusRes, chunksRes, sectionsRes, pagesRes] = await Promise.all(
          [
            api.getPaperStatus(targetPaperId, abortCtrl.signal),
            api.getPaperChunks(targetPaperId, {
              section: targetSection || undefined,
              page: targetPage ? parseInt(targetPage, 10) : undefined,
              limit: 100,
              signal: abortCtrl.signal,
            }),
            api.getPaperSections(targetPaperId, abortCtrl.signal),
            api.getPaperPages(targetPaperId, abortCtrl.signal),
          ],
        );

        // Current identity validation against mutable refs (K1)
        const isRequestStillValid =
          reqId === activeReqRef.current &&
          isOpenRef.current &&
          currentPaperIdRef.current === targetPaperId &&
          currentWorkspaceIdRef.current === targetWorkspaceId &&
          filtersRef.current.section === targetSection &&
          filtersRef.current.page === targetPage;

        if (!isRequestStillValid) {
          return;
        }

        // Multi-resource generation agreement check (K2)
        const targetPublishedRunId =
          statusRes.published_run_id || statusRes.run_id;
        const gens = [
          chunksRes.run_id,
          sectionsRes.run_id,
          pagesRes.run_id,
        ].filter(Boolean);

        const anyStale = Boolean(
          statusRes.is_stale ||
          chunksRes.is_stale ||
          sectionsRes.is_stale ||
          pagesRes.is_stale,
        );

        const distinctGens = Array.from(new Set(gens));
        const hasConflict =
          anyStale ||
          (targetPublishedRunId
            ? gens.some((g) => g !== targetPublishedRunId)
            : distinctGens.length > 1);

        if (hasConflict) {
          generationConflictCountRef.current += 1;
          const MAX_GENERATION_RETRIES = 3;

          // Invalidate active actions because generation is inconsistent or publishing
          activeActionTokenRef.current += 1;

          if (generationConflictCountRef.current > MAX_GENERATION_RETRIES) {
            // Explicit unavailable state when generation agreement cannot be reached after bounded retries
            setErrorMsg(
              "Document artifacts are updating across pipeline runs. Generation agreement could not be reached. Retrying...",
            );
            setIsLoading(false);
          }

          // Schedule bounded retry to reach generation agreement
          const delay = Math.min(
            1500 *
              Math.pow(1.5, Math.min(generationConflictCountRef.current, 4)),
            8000,
          );
          if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
          pollTimerRef.current = setTimeout(() => {
            loadData(true);
          }, delay);
          // Never publish mixed snapshots
          return;
        }

        // Generation agreement verified: publish atomic snapshot
        generationConflictCountRef.current = 0;
        retryCountRef.current = 0;
        setErrorMsg(null);
        setIsLoading(false);

        // Check if generation changed from previous snapshot; if so, invalidate action tokens
        const newRunId = targetPublishedRunId || null;
        if (
          currentRunIdRef.current &&
          newRunId &&
          currentRunIdRef.current !== newRunId
        ) {
          activeActionTokenRef.current += 1;
        }
        currentRunIdRef.current = newRunId;
        statusDataRef.current = statusRes;

        setStatusData(statusRes);
        setChunks(chunksRes.items);
        setTotalChunks(chunksRes.total ?? chunksRes.items.length);
        setNextChunkCursor(chunksRes.next_cursor ?? null);
        setSections(sectionsRes.items);
        setPages(pagesRes.items);
      } catch (err: any) {
        if (abortCtrl.signal.aborted) return;

        const isRequestStillValid =
          reqId === activeReqRef.current &&
          isOpenRef.current &&
          currentPaperIdRef.current === targetPaperId &&
          currentWorkspaceIdRef.current === targetWorkspaceId;

        if (!isRequestStillValid) return;

        if (!isPolling) {
          setErrorMsg(err?.message || "Failed to load quality metrics.");
        } else {
          // Transient polling failure: record retry attempt and explicitly schedule next poll
          retryCountRef.current += 1;
          const currentStatus = statusDataRef.current?.status || paper.status;
          const currentSubstate = statusDataRef.current?.substate;
          const hasConflict = generationConflictCountRef.current > 0;
          const shouldPoll =
            currentStatus === "uploaded" ||
            (currentStatus === "processing" &&
              (currentSubstate !== "awaiting_indexing" || hasConflict)) ||
            hasConflict;

          if (shouldPoll) {
            const delay = Math.min(
              2000 * Math.pow(1.5, retryCountRef.current),
              8000,
            );
            if (pollTimerRef.current) {
              clearTimeout(pollTimerRef.current);
            }
            pollTimerRef.current = setTimeout(() => {
              loadData(true);
            }, delay);
          }
        }
      } finally {
        const isRequestStillValid =
          reqId === activeReqRef.current &&
          isOpenRef.current &&
          currentPaperIdRef.current === targetPaperId &&
          currentWorkspaceIdRef.current === targetWorkspaceId;

        if (isRequestStillValid && generationConflictCountRef.current === 0) {
          setIsLoading(false);
        }
      }
    },
    [paper, sectionFilter, pageFilter],
  );

  // Initial load and filter change trigger
  useEffect(() => {
    if (isOpen && paper) {
      loadData(false);
    }
  }, [isOpen, paper, loadData]);

  // Adaptive polling: poll while queued (uploaded), actively processing, or while generation conflict persists
  useEffect(() => {
    if (!isOpen || !paper) return;

    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    const currentStatus = statusData?.status || paper.status;
    const currentSubstate = statusData?.substate;
    const hasConflict = generationConflictCountRef.current > 0;

    // Continue polling if uploaded (queued), actively processing, or if generation agreement is pending
    const shouldPoll =
      currentStatus === "uploaded" ||
      (currentStatus === "processing" &&
        (currentSubstate !== "awaiting_indexing" || hasConflict)) ||
      hasConflict;

    if (shouldPoll) {
      const delay = Math.min(
        2000 *
          Math.pow(
            1.5,
            Math.max(retryCountRef.current, generationConflictCountRef.current),
          ),
        8000,
      );
      pollTimerRef.current = setTimeout(() => {
        loadData(true);
      }, delay);
    }

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isOpen, paper, statusData, loadData]);

  // Load More Chunks handler for pagination beyond 100 (guarded against closure & identity changes)
  const handleLoadMoreChunks = async () => {
    if (!paper || !nextChunkCursor || isLoadingMoreChunks) return;
    const targetPaperId = paper.id;
    const targetWorkspaceId = paper.workspace_id;
    const targetCursor = nextChunkCursor;
    const targetSection = sectionFilter;
    const targetPage = pageFilter;
    const targetRunId = currentRunIdRef.current;
    const actionToken = ++activeActionTokenRef.current;

    setIsLoadingMoreChunks(true);

    const isActionStillValid = () => {
      return (
        actionToken === activeActionTokenRef.current &&
        isOpenRef.current &&
        currentPaperIdRef.current === targetPaperId &&
        currentWorkspaceIdRef.current === targetWorkspaceId &&
        filtersRef.current.section === targetSection &&
        filtersRef.current.page === targetPage &&
        currentRunIdRef.current === targetRunId
      );
    };

    try {
      const res = await api.getPaperChunks(targetPaperId, {
        section: targetSection || undefined,
        page: targetPage ? parseInt(targetPage, 10) : undefined,
        cursor: targetCursor,
        limit: 100,
      });

      if (!isActionStillValid()) return;

      // Invalidate if res generation conflicts with current generation
      if (res.run_id && targetRunId && res.run_id !== targetRunId) {
        return;
      }

      setChunks((prev) => [...prev, ...res.items]);
      setNextChunkCursor(res.next_cursor ?? null);
      if (res.total !== undefined) {
        setTotalChunks(res.total);
      }
    } catch (err: any) {
      if (!isActionStillValid()) return;
      setErrorMsg(err?.message || "Failed to load more chunks.");
    } finally {
      if (isActionStillValid()) {
        setIsLoadingMoreChunks(false);
      }
    }
  };

  // Reprocess Handler (guarded against closure, paper change, close, and stale reload triggers)
  const handleReprocess = async () => {
    if (!paper || isReprocessing) return;
    const targetPaperId = paper.id;
    const targetWorkspaceId = paper.workspace_id;
    const actionToken = ++activeActionTokenRef.current;

    setIsReprocessing(true);
    setReprocessMsg(null);

    const isActionStillValid = () => {
      return (
        actionToken === activeActionTokenRef.current &&
        isOpenRef.current &&
        currentPaperIdRef.current === targetPaperId &&
        currentWorkspaceIdRef.current === targetWorkspaceId
      );
    };

    try {
      const res = await api.reprocessPaper(targetPaperId);
      if (!isActionStillValid()) return;

      setStatusData(res);
      statusDataRef.current = res;
      currentRunIdRef.current = res.published_run_id || res.run_id || null;
      setReprocessMsg({
        type: "success",
        text: "Reprocessing job enqueued successfully. Pipeline restarted.",
      });

      // Guard reprocess-triggered reload: only reload if action remains valid for this paper
      if (isActionStillValid()) {
        loadData(true);
      }
    } catch (err: any) {
      if (!isActionStillValid()) return;

      if (err instanceof ApiClientError && err.statusCode === 409) {
        setReprocessMsg({
          type: "error",
          text:
            err.message ||
            "A processing job is already running for this document.",
        });
      } else {
        setReprocessMsg({
          type: "error",
          text: err?.message || "Failed to trigger reprocess.",
        });
      }
    } finally {
      if (isActionStillValid()) {
        setIsReprocessing(false);
      }
    }
  };

  if (!isOpen || !paper) return null;

  // Filtered Chunks for Local Text Search
  const displayChunks = chunks.filter((c) => {
    if (!searchFilter.trim()) return true;
    return (
      c.text.toLowerCase().includes(searchFilter.toLowerCase()) ||
      c.section.toLowerCase().includes(searchFilter.toLowerCase())
    );
  });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(10, 15, 29, 0.75)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "16px",
      }}
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Quality Center: ${paper.title || paper.original_filename}`}
        style={{
          width: "100%",
          maxWidth: "1100px",
          maxHeight: "92vh",
          backgroundColor: "var(--surface)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--float-2)",
          border: "1px solid var(--border-control)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid var(--hairline)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--surface-alt)",
            gap: "16px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              minWidth: 0,
            }}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--r-md)",
                background: "var(--blue-surface)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--blue)",
                flexShrink: 0,
              }}
            >
              <Layers size={20} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <h2
                  style={{
                    fontSize: "17px",
                    fontWeight: 700,
                    margin: 0,
                    color: "var(--text-primary)",
                  }}
                >
                  Quality Center
                </h2>
                {statusData?.is_stale && (
                  <Badge variant="warning">
                    Reprocessing in Progress (Old Bundle Shown)
                  </Badge>
                )}
              </div>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-muted)",
                  margin: "2px 0 0",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={paper.title || paper.original_filename}
              >
                {paper.title || paper.original_filename}
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Button
              variant="soft"
              size="sm"
              onClick={handleReprocess}
              disabled={isReprocessing}
              aria-label="Reprocess document"
              title="Trigger a fresh ingestion generation"
            >
              <RefreshCw
                size={14}
                className={isReprocessing ? "animate-spin" : ""}
              />
              <span>{isReprocessing ? "Enqueueing..." : "Reprocess"}</span>
            </Button>

            <button
              data-action="close"
              onClick={onClose}
              style={{
                padding: "8px",
                borderRadius: "var(--r-sm)",
                border: "none",
                background: "transparent",
                color: "var(--text-muted)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              aria-label="Close modal"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Feedback / Notification Banner */}
        {errorMsg && (
          <div
            style={{
              padding: "10px 24px",
              background: "var(--red-surface)",
              color: "var(--red-text)",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              borderBottom: "1px solid var(--hairline)",
            }}
          >
            <AlertTriangle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}

        {reprocessMsg && (
          <div
            style={{
              padding: "10px 24px",
              background:
                reprocessMsg.type === "success"
                  ? "var(--green-surface)"
                  : "var(--red-surface)",
              color:
                reprocessMsg.type === "success"
                  ? "var(--green-text)"
                  : "var(--red-text)",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              borderBottom: "1px solid var(--hairline)",
            }}
          >
            {reprocessMsg.type === "success" ? (
              <CheckCircle2 size={16} />
            ) : (
              <AlertTriangle size={16} />
            )}
            <span>{reprocessMsg.text}</span>
          </div>
        )}

        {/* Top Status Bar: Phase 4 Ingestion Summary */}
        <div
          style={{
            padding: "14px 24px",
            background: "var(--surface)",
            borderBottom: "1px solid var(--hairline)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Stage:
              </span>
              <Badge variant="info">{statusData?.stage || "validating"}</Badge>
            </div>

            {statusData?.substate === "awaiting_indexing" && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 10px",
                  background: "var(--blue-surface)",
                  borderRadius: "var(--r-pill)",
                  color: "var(--blue-text)",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                <CheckCircle2 size={14} />
                <span>Awaiting Semantic Indexing (Week 3)</span>
              </div>
            )}

            {statusData?.status === "failed" && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 10px",
                  background: "var(--red-surface)",
                  borderRadius: "var(--r-pill)",
                  color: "var(--red-text)",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                <AlertTriangle size={14} />
                <span>Processing Failed</span>
              </div>
            )}

            <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Progress:{" "}
              <strong>{Math.round((statusData?.progress || 0) * 100)}%</strong>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div
            role="tablist"
            aria-label="Quality Center Navigation"
            style={{ display: "flex", gap: "4px" }}
          >
            <button
              role="tab"
              id="tab-chunks"
              aria-selected={activeTab === "chunks"}
              aria-controls="tabpanel-chunks"
              onClick={() => setActiveTab("chunks")}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--r-sm)",
                border: "none",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: activeTab === "chunks" ? 600 : 400,
                background:
                  activeTab === "chunks"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "chunks"
                    ? "var(--blue)"
                    : "var(--text-secondary)",
                boxShadow: activeTab === "chunks" ? "var(--raise-1)" : "none",
              }}
            >
              Chunks ({totalChunks})
            </button>
            <button
              role="tab"
              id="tab-pipeline"
              aria-selected={activeTab === "pipeline"}
              aria-controls="tabpanel-pipeline"
              onClick={() => setActiveTab("pipeline")}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--r-sm)",
                border: "none",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: activeTab === "pipeline" ? 600 : 400,
                background:
                  activeTab === "pipeline"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "pipeline"
                    ? "var(--blue)"
                    : "var(--text-secondary)",
                boxShadow: activeTab === "pipeline" ? "var(--raise-1)" : "none",
              }}
            >
              Stage History
            </button>
            <button
              role="tab"
              id="tab-metadata"
              aria-selected={activeTab === "metadata"}
              aria-controls="tabpanel-metadata"
              onClick={() => setActiveTab("metadata")}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--r-sm)",
                border: "none",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: activeTab === "metadata" ? 600 : 400,
                background:
                  activeTab === "metadata"
                    ? "var(--surface-soft)"
                    : "transparent",
                color:
                  activeTab === "metadata"
                    ? "var(--blue)"
                    : "var(--text-secondary)",
                boxShadow: activeTab === "metadata" ? "var(--raise-1)" : "none",
              }}
            >
              Provenance & Pages
            </button>
          </div>
        </div>

        {/* Tab 1: Chunks & Section Inspector */}
        {activeTab === "chunks" && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Filter Bar */}
            <div
              style={{
                padding: "12px 24px",
                background: "var(--surface-alt)",
                borderBottom: "1px solid var(--hairline)",
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  flex: "1 1 200px",
                }}
              >
                <Filter size={14} style={{ color: "var(--text-muted)" }} />
                <input
                  type="text"
                  placeholder={
                    chunks.length < totalChunks
                      ? `Filter loaded chunks (${chunks.length} of ${totalChunks} loaded)...`
                      : "Search chunk text or section..."
                  }
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--r-xs)",
                    border: "1px solid var(--border-strong)",
                    background: "var(--surface)",
                    fontSize: "13px",
                  }}
                  aria-label="Filter chunk text"
                />
              </div>

              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <label style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  Section:
                </label>
                <select
                  value={sectionFilter}
                  onChange={(e) => setSectionFilter(e.target.value)}
                  style={{
                    padding: "6px 8px",
                    borderRadius: "var(--r-xs)",
                    border: "1px solid var(--border-strong)",
                    background: "var(--surface)",
                    fontSize: "12px",
                  }}
                  aria-label="Filter by section"
                >
                  <option value="">All Sections</option>
                  {sections.map((s) => (
                    <option key={s.id} value={s.section}>
                      {s.section} ({s.heading || `Page ${s.page_start}`})
                    </option>
                  ))}
                </select>
              </div>

              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <label style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  Page:
                </label>
                <input
                  type="number"
                  min={1}
                  placeholder="All"
                  value={pageFilter}
                  onChange={(e) => setPageFilter(e.target.value)}
                  style={{
                    width: "60px",
                    padding: "6px 8px",
                    borderRadius: "var(--r-xs)",
                    border: "1px solid var(--border-strong)",
                    background: "var(--surface)",
                    fontSize: "12px",
                  }}
                  aria-label="Filter by page"
                />
              </div>

              <span
                style={{
                  fontSize: "12px",
                  color: "var(--text-muted)",
                  marginLeft: "auto",
                }}
              >
                Loaded {chunks.length} of {totalChunks} chunks
                {searchFilter.trim() &&
                  ` (${displayChunks.length} match filter)`}
              </span>
            </div>

            {/* Chunk List Container */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "16px 24px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              {isLoading ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "40px",
                    color: "var(--text-muted)",
                  }}
                >
                  <RefreshCw
                    className="animate-spin"
                    size={24}
                    style={{ margin: "0 auto 12px" }}
                  />
                  <p>Loading document chunks and section bounds...</p>
                </div>
              ) : displayChunks.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "40px",
                    background: "var(--surface-soft)",
                    borderRadius: "var(--r-md)",
                    border: "1px dashed var(--border-control)",
                  }}
                >
                  <Info
                    size={28}
                    style={{ color: "var(--text-muted)", margin: "0 auto 8px" }}
                  />
                  <p
                    style={{
                      margin: 0,
                      fontWeight: 600,
                      color: "var(--text-primary)",
                    }}
                  >
                    No chunks available for this view
                  </p>
                  <p
                    style={{
                      margin: "4px 0 0",
                      fontSize: "13px",
                      color: "var(--text-muted)",
                    }}
                  >
                    {statusData?.stage !== "chunking"
                      ? "Ingestion is currently processing earlier stages."
                      : "Try clearing filters to display all chunks."}
                  </p>
                </div>
              ) : (
                displayChunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--hairline)",
                      borderRadius: "var(--r-md)",
                      padding: "14px 18px",
                      boxShadow: "var(--raise-1)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    {/* Chunk Meta Header */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: "8px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          flexWrap: "wrap",
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "12px",
                            fontWeight: 700,
                            padding: "2px 8px",
                            background: "var(--surface-sunken)",
                            borderRadius: "var(--r-xs)",
                            color: "var(--text-primary)",
                          }}
                        >
                          #{chunk.chunk_index}
                        </span>

                        <Badge variant="neutral">{chunk.section}</Badge>

                        {chunk.is_excluded && (
                          <Badge variant="warning">
                            Excluded from Retrieval (Reference)
                          </Badge>
                        )}

                        <span
                          style={{
                            fontSize: "12px",
                            color: "var(--text-muted)",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          <Hash size={12} />
                          <strong>{chunk.token_count}</strong> tokens (MiniLM
                          limit: 256)
                        </span>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "12px",
                            color: "var(--text-secondary)",
                          }}
                        >
                          Pages {chunk.page_start}–{chunk.page_end}
                        </span>

                        {onOpenPdfPage && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              onOpenPdfPage(paper, chunk.page_start)
                            }
                            title={`Jump to page ${chunk.page_start} in PDF viewer`}
                            style={{ padding: "4px 8px", fontSize: "12px" }}
                          >
                            <Eye size={12} />
                            <span>View Page</span>
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Chunk Text Content */}
                    <div
                      style={{
                        background: "var(--surface-sunken)",
                        padding: "12px 14px",
                        borderRadius: "var(--r-xs)",
                        fontSize: "13px",
                        lineHeight: 1.5,
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-sans)",
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {chunk.text}
                    </div>

                    {/* Block Provenance Tags */}
                    {chunk.block_ids && chunk.block_ids.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          flexWrap: "wrap",
                          fontSize: "11px",
                          color: "var(--text-muted)",
                        }}
                      >
                        <span>Blocks:</span>
                        {chunk.block_ids.slice(0, 8).map((bId) => (
                          <span
                            key={bId}
                            style={{
                              padding: "1px 6px",
                              background: "var(--surface-alt)",
                              borderRadius: "4px",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {bId}
                          </span>
                        ))}
                        {chunk.block_ids.length > 8 && (
                          <span>+{chunk.block_ids.length - 8} more</span>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}

              {/* Load More Button for pagination beyond 100 chunks */}
              {nextChunkCursor && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    padding: "16px 0",
                  }}
                >
                  <Button
                    variant="soft"
                    size="sm"
                    onClick={handleLoadMoreChunks}
                    isLoading={isLoadingMoreChunks}
                  >
                    <span>
                      Load More Chunks ({chunks.length} of {totalChunks} loaded)
                    </span>
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Stage & Attempt History */}
        {activeTab === "pipeline" && (
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "20px 24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <h3
              style={{
                fontSize: "15px",
                fontWeight: 700,
                margin: 0,
                color: "var(--text-primary)",
              }}
            >
              Ingestion Generation Pipeline
            </h3>

            {statusData?.stages && statusData.stages.length > 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                {statusData.stages.map((st, idx) => (
                  <div
                    key={`${st.stage}-${st.attempt}-${idx}`}
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--hairline)",
                      borderRadius: "var(--r-md)",
                      padding: "14px 18px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      boxShadow: "var(--raise-1)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                      }}
                    >
                      {st.status === "succeeded" && (
                        <CheckCircle2
                          size={18}
                          style={{ color: "var(--green-strong)" }}
                        />
                      )}
                      {st.status === "running" && (
                        <RefreshCw
                          size={18}
                          className="animate-spin"
                          style={{ color: "var(--blue)" }}
                        />
                      )}
                      {st.status === "failed" && (
                        <AlertTriangle
                          size={18}
                          style={{ color: "var(--red-strong)" }}
                        />
                      )}
                      {st.status === "queued" && (
                        <Clock
                          size={18}
                          style={{ color: "var(--orange-strong)" }}
                        />
                      )}

                      <div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <strong
                            style={{
                              fontSize: "14px",
                              textTransform: "capitalize",
                            }}
                          >
                            {st.stage}
                          </strong>
                          <span
                            style={{
                              fontSize: "12px",
                              color: "var(--text-muted)",
                            }}
                          >
                            Attempt #{st.attempt}
                          </span>
                        </div>
                        {st.error && (
                          <p
                            style={{
                              margin: "4px 0 0",
                              fontSize: "12px",
                              color: "var(--red-text)",
                            }}
                          >
                            {st.error}
                          </p>
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        textAlign: "right",
                        fontSize: "12px",
                        color: "var(--text-muted)",
                      }}
                    >
                      <div>
                        Status: <strong>{st.status}</strong>
                      </div>
                      {st.finished_at && (
                        <div>
                          Finished:{" "}
                          {new Date(st.finished_at).toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "20px",
                  color: "var(--text-muted)",
                  textAlign: "center",
                }}
              >
                No stage history recorded yet.
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Provenance & Page Flags */}
        {activeTab === "metadata" && (
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "20px 24px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            {/* Metadata Provenance */}
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--hairline)",
                borderRadius: "var(--r-md)",
                padding: "16px 20px",
                boxShadow: "var(--raise-1)",
              }}
            >
              <h4
                style={{
                  margin: "0 0 12px",
                  fontSize: "14px",
                  fontWeight: 700,
                }}
              >
                Metadata Provenance
              </h4>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "140px 1fr",
                  gap: "10px",
                  fontSize: "13px",
                }}
              >
                <span style={{ color: "var(--text-muted)" }}>Title:</span>
                <span>{paper.title || "Not extracted"}</span>

                <span style={{ color: "var(--text-muted)" }}>Authors:</span>
                <span>
                  {paper.authors && paper.authors.length > 0
                    ? paper.authors.join(", ")
                    : "None detected"}
                </span>

                <span style={{ color: "var(--text-muted)" }}>
                  Publication Year:
                </span>
                <span>{paper.publication_year || "Unknown"}</span>

                <span style={{ color: "var(--text-muted)" }}>Keywords:</span>
                <span>
                  {paper.keywords && paper.keywords.length > 0
                    ? paper.keywords.join(", ")
                    : "None"}
                </span>
              </div>
            </div>

            {/* Extracted Pages & Quality Flags */}
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--hairline)",
                borderRadius: "var(--r-md)",
                padding: "16px 20px",
                boxShadow: "var(--raise-1)",
              }}
            >
              <h4
                style={{
                  margin: "0 0 12px",
                  fontSize: "14px",
                  fontWeight: 700,
                }}
              >
                Page Extraction & Quality Flags ({pages.length} Pages)
              </h4>

              <div
                style={{ display: "flex", flexDirection: "column", gap: "8px" }}
              >
                {pages.map((p) => (
                  <div
                    key={p.page_number}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      background: "var(--surface-alt)",
                      borderRadius: "var(--r-xs)",
                      fontSize: "12px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>
                        Page {p.page_number}
                      </span>
                      <Badge
                        variant={
                          p.extraction_status === "ok" ? "success" : "warning"
                        }
                      >
                        {p.extraction_status}
                      </Badge>
                      <span style={{ color: "var(--text-muted)" }}>
                        {p.char_count} chars
                      </span>
                    </div>

                    <div style={{ display: "flex", gap: "6px" }}>
                      {p.flags && p.flags.length > 0 ? (
                        p.flags.map((f) => (
                          <Badge key={f} variant="warning">
                            {f}
                          </Badge>
                        ))
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>
                          No quality warnings
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
