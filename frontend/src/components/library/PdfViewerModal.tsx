import React, { useEffect, useRef } from "react";
import { X, ExternalLink, Download, FileText } from "lucide-react";
import { PaperItem } from "../../api/types";
import { api } from "../../api/client";
import { Button } from "../ui/Button";

interface PdfViewerModalProps {
  paper: PaperItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  paper,
  isOpen,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

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
  }, [isOpen, paper, onClose]);

  if (!isOpen || !paper) return null;

  const fileUrl = api.getPaperFileUrl(paper.id);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(10, 15, 29, 0.8)",
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
        aria-label={`PDF Viewer: ${paper.title || paper.original_filename}`}
        style={{
          width: "100%",
          maxWidth: "1080px",
          height: "90vh",
          background: "var(--surface)",
          border: "1px solid var(--border-control)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--raise-4)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid var(--border-control)",
            background: "var(--surface-alt)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              minWidth: 0,
            }}
          >
            <FileText
              size={20}
              color="var(--blue-action)"
              style={{ flexShrink: 0 }}
            />
            <div style={{ minWidth: 0 }}>
              <h2
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  margin: 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {paper.title || paper.original_filename}
              </h2>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                {paper.original_filename} •{" "}
                {paper.page_count
                  ? `${paper.page_count} pages`
                  : "PDF document"}
              </span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexShrink: 0,
            }}
          >
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              download={paper.original_filename}
              style={{ textDecoration: "none" }}
            >
              <Button
                variant="soft"
                size="sm"
                aria-label="Download original PDF"
              >
                <Download size={14} />
                <span>Download</span>
              </Button>
            </a>
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: "none" }}
            >
              <Button variant="soft" size="sm" aria-label="Open in new window">
                <ExternalLink size={14} />
                <span>New Tab</span>
              </Button>
            </a>
            <Button
              variant="ghost"
              size="sm"
              data-action="close"
              onClick={onClose}
              aria-label="Close PDF viewer"
              style={{ padding: "6px" }}
            >
              <X size={18} />
            </Button>
          </div>
        </div>

        {/* Viewer Body */}
        <div
          style={{
            flex: 1,
            position: "relative",
            background: "var(--surface-soft)",
          }}
        >
          <iframe
            src={fileUrl}
            title={paper.original_filename}
            style={{
              width: "100%",
              height: "100%",
              border: "none",
            }}
          />
        </div>
      </div>
    </div>
  );
};
