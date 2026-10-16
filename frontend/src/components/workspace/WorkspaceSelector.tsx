import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Plus, Edit2, Trash2, Folder, Check } from "lucide-react";
import { WorkspaceItem } from "../../api/types";
import { Button } from "../ui/Button";

interface WorkspaceSelectorProps {
  workspaces: WorkspaceItem[];
  selectedWorkspace: WorkspaceItem | null;
  onSelect: (workspace: WorkspaceItem) => void;
  onCreateNew: () => void;
  onEditCurrent: () => void;
  onDeleteCurrent: () => void;
  isLoading?: boolean;
}

export const WorkspaceSelector: React.FC<WorkspaceSelectorProps> = ({
  workspaces,
  selectedWorkspace,
  onSelect,
  onCreateNew,
  onEditCurrent,
  onDeleteCurrent,
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
      }}
    >
      <button
        id="workspace-selector-btn"
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "8px 14px",
          borderRadius: "var(--r-md)",
          border: "1px solid var(--border-control)",
          background: "var(--surface)",
          color: "var(--text-primary)",
          fontSize: "14px",
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: "var(--raise-1)",
          transition: "var(--transition-fast)",
        }}
      >
        <Folder size={18} color="var(--blue-action)" />
        <span
          style={{
            maxWidth: "200px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {selectedWorkspace ? selectedWorkspace.name : "Select Workspace"}
        </span>
        <ChevronDown
          size={16}
          color="var(--text-muted)"
          style={{
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 150ms ease",
          }}
        />
      </button>

      {/* Action buttons for active workspace */}
      {selectedWorkspace && (
        <div style={{ display: "inline-flex", gap: "4px" }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={onEditCurrent}
            aria-label="Rename workspace"
            title="Rename workspace"
            style={{ padding: "8px" }}
          >
            <Edit2 size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDeleteCurrent}
            aria-label="Delete workspace"
            title="Delete workspace"
            style={{ padding: "8px", color: "var(--red-strong)" }}
          >
            <Trash2 size={16} />
          </Button>
        </div>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="listbox"
          aria-label="Workspaces"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            width: "280px",
            maxHeight: "340px",
            overflowY: "auto",
            background: "var(--surface)",
            border: "1px solid var(--border-control)",
            borderRadius: "var(--r-lg)",
            boxShadow: "var(--raise-3)",
            zIndex: 1000,
            padding: "6px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          <div
            style={{
              padding: "6px 10px",
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              color: "var(--text-muted)",
              borderBottom: "1px solid var(--hairline)",
              marginBottom: "4px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>Your Workspaces</span>
            <span>{workspaces.length}</span>
          </div>

          {workspaces.length === 0 ? (
            <div
              style={{
                padding: "16px 12px",
                textAlign: "center",
                fontSize: "13px",
                color: "var(--text-muted)",
              }}
            >
              No workspaces created yet.
            </div>
          ) : (
            workspaces.map((ws) => {
              const isSelected = selectedWorkspace?.id === ws.id;
              return (
                <button
                  key={ws.id}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onSelect(ws);
                    setIsOpen(false);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 10px",
                    borderRadius: "var(--r-md)",
                    background: isSelected
                      ? "var(--surface-soft)"
                      : "transparent",
                    border: "none",
                    color: "var(--text-primary)",
                    fontSize: "13px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "background 100ms ease",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      overflow: "hidden",
                    }}
                  >
                    <Folder
                      size={14}
                      color={
                        isSelected ? "var(--blue-action)" : "var(--text-muted)"
                      }
                    />
                    <span
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        maxWidth: "170px",
                        fontWeight: isSelected ? 600 : 400,
                      }}
                    >
                      {ws.name}
                    </span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11px",
                        color: "var(--text-muted)",
                        background: "var(--surface-alt)",
                        padding: "2px 6px",
                        borderRadius: "var(--r-sm)",
                      }}
                    >
                      {ws.paper_count}
                    </span>
                    {isSelected && (
                      <Check size={14} color="var(--blue-action)" />
                    )}
                  </div>
                </button>
              );
            })
          )}

          <div
            style={{
              borderTop: "1px solid var(--hairline)",
              marginTop: "4px",
              paddingTop: "4px",
            }}
          >
            <button
              type="button"
              id="new-workspace-btn"
              onClick={() => {
                setIsOpen(false);
                onCreateNew();
              }}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 10px",
                borderRadius: "var(--r-md)",
                background: "transparent",
                border: "none",
                color: "var(--blue-action)",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <Plus size={16} />
              <span>Create New Workspace</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
