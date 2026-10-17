import React, { useState, useEffect } from "react";
import {
  Search,
  Eye,
  Trash2,
  FileText,
  Calendar,
  Layers,
  ChevronDown,
} from "lucide-react";
import { PaperItem } from "../../api/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface PaperListProps {
  papers: PaperItem[];
  totalCount: number;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onViewPaper: (paper: PaperItem) => void;
  onDeletePaper: (paper: PaperItem) => void;
  isLoading: boolean;
  nextCursor?: string | null;
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

export const PaperList: React.FC<PaperListProps> = ({
  papers,
  totalCount,
  searchQuery,
  onSearchChange,
  onViewPaper,
  onDeletePaper,
  isLoading,
  nextCursor,
  onLoadMore,
  isLoadingMore,
}) => {
  const [searchTerm, setSearchTerm] = useState(searchQuery);

  // Sync with prop when external query changes
  useEffect(() => {
    setSearchTerm(searchQuery);
  }, [searchQuery]);

  // 250ms debounce for search input
  useEffect(() => {
    const handler = setTimeout(() => {
      if (searchTerm !== searchQuery) {
        onSearchChange(searchTerm);
      }
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm, searchQuery, onSearchChange]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        background: "var(--surface)",
        border: "1px solid var(--border-control)",
        borderRadius: "var(--r-xl)",
        overflow: "hidden",
        boxShadow: "var(--raise-1)",
      }}
    >
      {/* Search Header */}
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--hairline)",
          background: "var(--surface-alt)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <strong style={{ fontSize: "15px", color: "var(--text-primary)" }}>
            Documents in Workspace
          </strong>
          <span
            style={{
              fontSize: "12px",
              padding: "2px 8px",
              background: "var(--surface-soft)",
              borderRadius: "var(--r-full)",
              color: "var(--text-muted)",
              fontWeight: 600,
            }}
          >
            {totalCount}
          </span>
        </div>

        {/* Search Field */}
        <div style={{ position: "relative", minWidth: "260px" }}>
          <Search
            size={16}
            color="var(--text-muted)"
            style={{
              position: "absolute",
              left: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
            }}
          />
          <input
            id="paper-search-input"
            type="search"
            placeholder="Search papers by title or filename..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px 8px 36px",
              borderRadius: "var(--r-md)",
              border: "1px solid var(--border-control)",
              background: "var(--surface)",
              color: "var(--text-primary)",
              fontSize: "13px",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>
      </div>

      {/* List content */}
      {isLoading ? (
        <div
          style={{
            padding: "48px 20px",
            textAlign: "center",
            color: "var(--text-muted)",
          }}
        >
          Loading documents...
        </div>
      ) : papers.length === 0 ? (
        <div style={{ padding: "48px 24px", textAlign: "center" }}>
          <FileText
            size={36}
            color="var(--text-disabled)"
            style={{ marginBottom: "12px" }}
          />
          <p
            style={{
              fontSize: "14px",
              color: "var(--text-secondary)",
              margin: "0 0 6px 0",
              fontWeight: 600,
            }}
          >
            {searchQuery.trim()
              ? "No matching documents found"
              : "No documents in this workspace"}
          </p>
          <p
            style={{ fontSize: "13px", color: "var(--text-muted)", margin: 0 }}
          >
            {searchQuery.trim()
              ? `No papers match the search term "${searchQuery}".`
              : "Upload PDF research papers above to begin building your library."}
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {papers.map((paper, idx) => (
            <div
              key={paper.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "16px 20px",
                borderBottom:
                  idx === papers.length - 1
                    ? "none"
                    : "1px solid var(--hairline)",
                gap: "16px",
                transition: "background 100ms ease",
              }}
              className="paper-row"
            >
              {/* Paper Information */}
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  minWidth: 0,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "var(--r-md)",
                    background: "var(--surface-soft)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--blue-action)",
                    flexShrink: 0,
                    marginTop: "2px",
                  }}
                >
                  <FileText size={18} />
                </div>

                <div style={{ minWidth: 0, flex: 1 }}>
                  <h3
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      margin: "0 0 4px 0",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                    title={paper.title || paper.original_filename}
                  >
                    {paper.title || paper.original_filename}
                  </h3>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "12px",
                      fontSize: "12px",
                      color: "var(--text-muted)",
                    }}
                  >
                    <span>{paper.original_filename}</span>
                    <span>•</span>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <Layers size={12} />
                      {paper.page_count
                        ? `${paper.page_count} pages`
                        : "Unknown pages"}
                    </span>
                    <span>•</span>
                    <span>{formatBytes(paper.size_bytes)}</span>
                    <span>•</span>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <Calendar size={12} />
                      {formatDate(paper.created_at)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status and Action Buttons */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  flexShrink: 0,
                }}
              >
                <Badge variant={paper.status === "ready" ? "success" : "info"}>
                  {paper.status}
                </Badge>

                <Button
                  variant="soft"
                  size="sm"
                  onClick={() => onViewPaper(paper)}
                  aria-label={`View ${paper.original_filename}`}
                  title="View original PDF document"
                >
                  <Eye size={14} />
                  <span>View</span>
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDeletePaper(paper)}
                  aria-label={`Delete ${paper.original_filename}`}
                  title="Delete paper from library"
                  style={{ color: "var(--red-strong)", padding: "6px" }}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Footer */}
      {!isLoading && papers.length > 0 && (
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--hairline)",
            background: "var(--surface-alt)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
            Showing {papers.length} of {totalCount} document
            {totalCount === 1 ? "" : "s"}
          </span>

          {nextCursor && onLoadMore && (
            <Button
              variant="soft"
              size="sm"
              onClick={onLoadMore}
              disabled={isLoadingMore}
              aria-label="Load more documents"
            >
              <ChevronDown size={14} />
              <span>
                {isLoadingMore ? "Loading more..." : "Load more documents"}
              </span>
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
