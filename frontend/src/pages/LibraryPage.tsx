import React, { useState, useEffect, useCallback, useRef } from "react";
import { Folder, Plus, AlertCircle, RefreshCw } from "lucide-react";
import { api, ApiClientError } from "../api/client";
import {
  WorkspaceItem,
  PaperItem,
  PaperUploadBatchResponse,
} from "../api/types";
import { WorkspaceSelector } from "../components/workspace/WorkspaceSelector";
import { WorkspaceModal } from "../components/workspace/WorkspaceModal";
import { UploadDropzone } from "../components/library/UploadDropzone";
import { PaperList } from "../components/library/PaperList";
import { PdfViewerModal } from "../components/library/PdfViewerModal";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Button } from "../components/ui/Button";

const STORAGE_KEY_SELECTED_WS = "researchmind_selected_workspace_id";

export const LibraryPage: React.FC = () => {
  // Workspaces state
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] =
    useState<WorkspaceItem | null>(null);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(true);

  // Papers state
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [totalPaperCount, setTotalPaperCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoadingPapers, setIsLoadingPapers] = useState(false);

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [lastBatchResult, setLastBatchResult] =
    useState<PaperUploadBatchResponse | null>(null);

  // Modals & Dialogs state
  const [isWsModalOpen, setIsWsModalOpen] = useState(false);
  const [wsModalMode, setWsModalMode] = useState<"create" | "edit">("create");
  const [viewingPaper, setViewingPaper] = useState<PaperItem | null>(null);
  const [deletingPaper, setDeletingPaper] = useState<PaperItem | null>(null);
  const [isDeletingWs, setIsDeletingWs] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Pagination state
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Error banners
  const [pageError, setPageError] = useState<string | null>(null);

  // Track active request ID, selected workspace ref, and search query ref to prevent race conditions
  const activePaperReqRef = useRef<number>(0);
  const activePaginationReqRef = useRef<number>(0);
  const selectedWorkspaceRef = useRef<WorkspaceItem | null>(null);
  const searchQueryRef = useRef<string>("");

  // Sync refs with state
  useEffect(() => {
    selectedWorkspaceRef.current = selectedWorkspace;
  }, [selectedWorkspace]);

  useEffect(() => {
    searchQueryRef.current = searchQuery;
  }, [searchQuery]);

  // 1. Fetch Workspaces
  const loadWorkspaces = useCallback(async (selectIdAfter?: string) => {
    setIsLoadingWorkspaces(true);
    setPageError(null);
    try {
      const items = await api.listAllWorkspaces();
      setWorkspaces(items);

      if (items.length === 0) {
        setSelectedWorkspace(null);
        selectedWorkspaceRef.current = null;
        localStorage.removeItem(STORAGE_KEY_SELECTED_WS);
        return;
      }

      // Determine active workspace: priority is selectIdAfter (explicit switch), then current selection ref, then storage, then first item
      const currentSelectedId = selectedWorkspaceRef.current?.id;
      const targetId =
        selectIdAfter ||
        currentSelectedId ||
        localStorage.getItem(STORAGE_KEY_SELECTED_WS);
      const matched = items.find((w) => w.id === targetId);
      const active = matched || items[0];
      setSelectedWorkspace(active);
      selectedWorkspaceRef.current = active;
      localStorage.setItem(STORAGE_KEY_SELECTED_WS, active.id);
    } catch (err: any) {
      setPageError(err?.message || "Failed to load research workspaces.");
    } finally {
      setIsLoadingWorkspaces(false);
    }
  }, []);

  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  // 2. Fetch Papers for selected workspace & search query
  const loadPapers = useCallback(
    async (workspaceId: string, query: string = "") => {
      const reqId = ++activePaperReqRef.current;
      // Reset pagination loading ownership when generation changes
      activePaginationReqRef.current = 0;
      setIsLoadingMore(false);
      setIsLoadingPapers(true);
      setPageError(null);
      try {
        const res = await api.listPapers(workspaceId, { q: query, limit: 25 });
        if (
          reqId === activePaperReqRef.current &&
          selectedWorkspaceRef.current?.id === workspaceId &&
          searchQueryRef.current === query
        ) {
          setPapers(res.items);
          setNextCursor(res.next_cursor);
          setTotalPaperCount(res.total_count);
        }
      } catch (err: any) {
        if (
          reqId === activePaperReqRef.current &&
          selectedWorkspaceRef.current?.id === workspaceId &&
          searchQueryRef.current === query
        ) {
          setPageError(err?.message || "Failed to load workspace documents.");
        }
      } finally {
        if (reqId === activePaperReqRef.current) {
          setIsLoadingPapers(false);
        }
      }
    },
    [],
  );

  // Load more papers (pagination)
  const loadMorePapers = useCallback(async () => {
    if (!selectedWorkspaceRef.current || !nextCursor || isLoadingMore) return;
    const currentWsId = selectedWorkspaceRef.current.id;
    const currentQuery = searchQueryRef.current;
    const currentCursor = nextCursor;
    const currentPaperGen = activePaperReqRef.current;
    const paginationReqId = ++activePaginationReqRef.current;
    setIsLoadingMore(true);
    try {
      const res = await api.listPapers(currentWsId, {
        q: currentQuery,
        cursor: currentCursor,
        limit: 25,
      });
      if (
        currentPaperGen === activePaperReqRef.current &&
        paginationReqId === activePaginationReqRef.current &&
        selectedWorkspaceRef.current?.id === currentWsId &&
        searchQueryRef.current === currentQuery
      ) {
        setPapers((prev) => [...prev, ...res.items]);
        setNextCursor(res.next_cursor);
        setTotalPaperCount(res.total_count);
      }
    } catch (err: any) {
      if (
        currentPaperGen === activePaperReqRef.current &&
        paginationReqId === activePaginationReqRef.current &&
        selectedWorkspaceRef.current?.id === currentWsId &&
        searchQueryRef.current === currentQuery
      ) {
        setPageError(err?.message || "Failed to load additional documents.");
      }
    } finally {
      // Stale completion must not clear a newer pagination request's loading state
      if (
        currentPaperGen === activePaperReqRef.current &&
        paginationReqId === activePaginationReqRef.current
      ) {
        setIsLoadingMore(false);
      }
    }
  }, [nextCursor, isLoadingMore]);

  useEffect(() => {
    if (selectedWorkspace) {
      loadPapers(selectedWorkspace.id, searchQuery);
    } else {
      activePaginationReqRef.current = 0;
      setIsLoadingMore(false);
      setPapers([]);
      setNextCursor(null);
      setTotalPaperCount(0);
    }
  }, [selectedWorkspace, searchQuery, loadPapers]);

  // Workspace Actions
  const handleSelectWorkspace = (ws: WorkspaceItem) => {
    activePaginationReqRef.current = 0;
    setIsLoadingMore(false);
    setSelectedWorkspace(ws);
    selectedWorkspaceRef.current = ws;
    localStorage.setItem(STORAGE_KEY_SELECTED_WS, ws.id);
    setSearchQuery("");
    setLastBatchResult(null);
  };

  const handleSaveWorkspace = async (name: string, description: string) => {
    if (wsModalMode === "create") {
      const created = await api.createWorkspace({ name, description });
      await loadWorkspaces(created.id);
    } else if (selectedWorkspaceRef.current) {
      const updated = await api.updateWorkspace(
        selectedWorkspaceRef.current.id,
        {
          name,
          description,
        },
      );
      await loadWorkspaces(updated.id);
    }
  };

  const handleDeleteWorkspace = async () => {
    if (!selectedWorkspaceRef.current) return;
    const wsIdToDelete = selectedWorkspaceRef.current.id;
    setIsActionLoading(true);
    try {
      await api.deleteWorkspace(wsIdToDelete);
      setIsDeletingWs(false);
      await loadWorkspaces();
    } catch (err: any) {
      setPageError(err?.message || "Failed to delete workspace.");
    } finally {
      setIsActionLoading(false);
    }
  };

  // Upload Action
  const handleUploadFiles = async (files: File[]) => {
    if (!selectedWorkspaceRef.current) return;
    const targetWsId = selectedWorkspaceRef.current.id;
    setIsUploading(true);
    setPageError(null);
    try {
      const batchResult = await api.uploadPapers(targetWsId, files);
      // Only refresh papers if user is still on the target workspace
      if (selectedWorkspaceRef.current?.id === targetWsId) {
        setLastBatchResult(batchResult);
        await loadPapers(targetWsId, searchQueryRef.current);
      }
      // Refresh workspace counts preserving the active workspace at resolution time
      await loadWorkspaces();
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setPageError(`${err.code}: ${err.message}`);
      } else {
        setPageError(err?.message || "An error occurred during file upload.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  // Delete Paper Action
  const handleConfirmDeletePaper = async () => {
    if (!deletingPaper || !selectedWorkspaceRef.current) return;
    const targetWsId = selectedWorkspaceRef.current.id;
    const paperToDeleteId = deletingPaper.id;
    setIsActionLoading(true);
    try {
      await api.deletePaper(paperToDeleteId);
      setDeletingPaper(null);
      if (selectedWorkspaceRef.current?.id === targetWsId) {
        await loadPapers(targetWsId, searchQueryRef.current);
      }
      await loadWorkspaces();
    } catch (err: any) {
      setPageError(err?.message || "Failed to delete paper.");
    } finally {
      setIsActionLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Top Header & Workspace Selector Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <h1
            style={{ fontSize: "26px", fontWeight: 700, margin: "0 0 6px 0" }}
          >
            Research Paper Library
          </h1>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: "14px",
              margin: 0,
            }}
          >
            Upload, manage, and inspect scientific literature within dedicated
            workspaces.
          </p>
        </div>

        {/* Workspace Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            flexWrap: "wrap",
          }}
        >
          {workspaces.length > 0 ? (
            <WorkspaceSelector
              workspaces={workspaces}
              selectedWorkspace={selectedWorkspace}
              onSelect={handleSelectWorkspace}
              onCreateNew={() => {
                setWsModalMode("create");
                setIsWsModalOpen(true);
              }}
              onEditCurrent={() => {
                setWsModalMode("edit");
                setIsWsModalOpen(true);
              }}
              onDeleteCurrent={() => setIsDeletingWs(true)}
              isLoading={isLoadingWorkspaces}
            />
          ) : (
            <Button
              variant="ink"
              onClick={() => {
                setWsModalMode("create");
                setIsWsModalOpen(true);
              }}
            >
              <Plus size={16} />
              <span>Create Workspace</span>
            </Button>
          )}
        </div>
      </div>

      {/* Global Error Banner */}
      {pageError && (
        <div
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
          role="alert"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <AlertCircle size={18} color="var(--red-strong)" />
            <span>{pageError}</span>
          </div>
          <Button
            variant="soft"
            size="sm"
            onClick={() => {
              setPageError(null);
              if (selectedWorkspace)
                loadPapers(selectedWorkspace.id, searchQuery);
            }}
          >
            <RefreshCw size={12} />
            <span>Retry</span>
          </Button>
        </div>
      )}

      {/* No Workspace State */}
      {!isLoadingWorkspaces && workspaces.length === 0 ? (
        <div
          style={{
            padding: "64px 24px",
            textAlign: "center",
            background: "var(--surface)",
            border: "1px solid var(--border-control)",
            borderRadius: "var(--r-2xl)",
            boxShadow: "var(--raise-1)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "16px",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "var(--surface-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--blue-action)",
            }}
          >
            <Folder size={28} />
          </div>
          <div>
            <h2
              style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 8px 0" }}
            >
              No Research Workspaces Yet
            </h2>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                maxWidth: "420px",
                margin: "0 auto",
                lineHeight: 1.5,
              }}
            >
              Workspaces isolate research domains and maintain document
              deduplication boundaries. Create your first workspace to start
              uploading papers.
            </p>
          </div>
          <Button
            variant="ink"
            onClick={() => {
              setWsModalMode("create");
              setIsWsModalOpen(true);
            }}
          >
            <Plus size={16} />
            <span>Create Workspace</span>
          </Button>
        </div>
      ) : (
        <>
          {/* Upload Dropzone Area */}
          <UploadDropzone
            isUploading={isUploading}
            lastBatchResult={lastBatchResult}
            onClearBatchResult={() => setLastBatchResult(null)}
            onUpload={handleUploadFiles}
            disabled={!selectedWorkspace}
          />

          {/* Paper List and Search */}
          <PaperList
            papers={papers}
            totalCount={totalPaperCount}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onViewPaper={setViewingPaper}
            onDeletePaper={setDeletingPaper}
            isLoading={isLoadingPapers}
            nextCursor={nextCursor}
            onLoadMore={loadMorePapers}
            isLoadingMore={isLoadingMore}
          />
        </>
      )}

      {/* Workspace Modal */}
      <WorkspaceModal
        isOpen={isWsModalOpen}
        mode={wsModalMode}
        initialName={wsModalMode === "edit" ? selectedWorkspace?.name : ""}
        initialDescription={
          wsModalMode === "edit" ? selectedWorkspace?.description || "" : ""
        }
        onSave={handleSaveWorkspace}
        onClose={() => setIsWsModalOpen(false)}
      />

      {/* Delete Workspace Confirmation */}
      <ConfirmDialog
        isOpen={isDeletingWs}
        title="Delete Workspace"
        description={`Are you sure you want to delete "${selectedWorkspace?.name}"? All associated papers and disk files in this workspace will be permanently removed.`}
        confirmLabel="Delete Workspace"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={isActionLoading}
        onConfirm={handleDeleteWorkspace}
        onCancel={() => setIsDeletingWs(false)}
      />

      {/* Delete Paper Confirmation */}
      <ConfirmDialog
        isOpen={!!deletingPaper}
        title="Delete Research Paper"
        description={`Are you sure you want to delete "${deletingPaper?.title || deletingPaper?.original_filename}"? This action removes the document record and cleans up the stored file from disk.`}
        confirmLabel="Delete Paper"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={isActionLoading}
        onConfirm={handleConfirmDeletePaper}
        onCancel={() => setDeletingPaper(null)}
      />

      {/* PDF Viewer Modal */}
      <PdfViewerModal
        isOpen={!!viewingPaper}
        paper={viewingPaper}
        onClose={() => setViewingPaper(null)}
      />
    </div>
  );
};
