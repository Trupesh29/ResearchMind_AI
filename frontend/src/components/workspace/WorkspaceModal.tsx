import React, { useState, useEffect, useRef } from "react";
import { X, FolderPlus, Edit3 } from "lucide-react";
import { Button } from "../ui/Button";

interface WorkspaceModalProps {
  isOpen: boolean;
  mode: "create" | "edit";
  initialName?: string;
  initialDescription?: string;
  onSave: (name: string, description: string) => Promise<void>;
  onClose: () => void;
}

export const WorkspaceModal: React.FC<WorkspaceModalProps> = ({
  isOpen,
  mode,
  initialName = "",
  initialDescription = "",
  onSave,
  onClose,
}) => {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;
      setName(initialName);
      setDescription(initialDescription);
      setError(null);
      setIsSubmitting(false);

      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape" && !isSubmitting) {
          e.preventDefault();
          onClose();
        }

        // Trap focus inside modal
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
  }, [isOpen, initialName, initialDescription, isSubmitting, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Workspace name is required.");
      inputRef.current?.focus();
      return;
    }
    if (trimmed.length > 100) {
      setError("Workspace name cannot exceed 100 characters.");
      inputRef.current?.focus();
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await onSave(trimmed, description.trim());
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save workspace.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(10, 15, 29, 0.7)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "16px",
      }}
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-modal-title"
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "var(--surface)",
          border: "1px solid var(--border-control)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--raise-4)",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {mode === "create" ? (
              <FolderPlus size={20} color="var(--blue-action)" />
            ) : (
              <Edit3 size={20} color="var(--blue-action)" />
            )}
            <h2
              id="workspace-modal-title"
              style={{ fontSize: "18px", fontWeight: 700 }}
            >
              {mode === "create" ? "Create New Workspace" : "Rename Workspace"}
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close dialog"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "var(--r-sm)",
            }}
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: "16px" }}
        >
          {error && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: "var(--r-md)",
                background: "var(--red-surface)",
                border: "1px solid rgba(255, 59, 48, 0.3)",
                color: "var(--red-text)",
                fontSize: "13px",
              }}
              role="alert"
            >
              {error}
            </div>
          )}

          <div>
            <label
              htmlFor="workspace-name-input"
              style={{
                display: "block",
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-primary)",
                marginBottom: "6px",
              }}
            >
              Workspace Name{" "}
              <span style={{ color: "var(--red-strong)" }}>*</span>
            </label>
            <input
              id="workspace-name-input"
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Neuroscience & Cognitive ML"
              maxLength={100}
              disabled={isSubmitting}
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--border-control)",
                background: "var(--surface-soft)",
                color: "var(--text-primary)",
                fontSize: "14px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="workspace-desc-input"
              style={{
                display: "block",
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-primary)",
                marginBottom: "6px",
              }}
            >
              Description (Optional)
            </label>
            <textarea
              id="workspace-desc-input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief context or topic scope for this research workspace..."
              maxLength={2000}
              rows={3}
              disabled={isSubmitting}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--border-control)",
                background: "var(--surface-soft)",
                color: "var(--text-primary)",
                fontSize: "14px",
                outline: "none",
                boxSizing: "border-box",
                resize: "vertical",
              }}
            />
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "10px",
              marginTop: "8px",
            }}
          >
            <Button
              variant="soft"
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button variant="ink" type="submit" isLoading={isSubmitting}>
              {mode === "create" ? "Create Workspace" : "Save Changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
