import React, { useState, useRef } from "react";
import {
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  X,
} from "lucide-react";
import { PaperUploadBatchResponse } from "../../api/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface UploadDropzoneProps {
  maxUploadMb?: number;
  isUploading: boolean;
  lastBatchResult: PaperUploadBatchResponse | null;
  onClearBatchResult: () => void;
  onUpload: (files: File[]) => void;
  disabled?: boolean;
}

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({
  maxUploadMb = 25,
  isUploading,
  lastBatchResult,
  onClearBatchResult,
  onUpload,
  disabled = false,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (disabled || isUploading) return;
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled || isUploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selectedFiles = Array.from(e.dataTransfer.files);
      onUpload(selectedFiles);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      onUpload(selectedFiles);
      e.target.value = "";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Dropzone Card */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          border: isDragOver
            ? "2px dashed var(--blue-action)"
            : "2px dashed var(--border-control)",
          borderRadius: "var(--r-2xl)",
          padding: "40px 24px",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "14px",
          background: isDragOver ? "rgba(0, 113, 227, 0.04)" : "var(--surface)",
          boxShadow: isDragOver ? "var(--raise-2)" : "var(--raise-1)",
          transition: "all 150ms ease",
          opacity: disabled ? 0.6 : 1,
          pointerEvents: disabled ? "none" : "auto",
        }}
      >
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "var(--surface-soft)",
            boxShadow: "var(--raise-2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--blue-action)",
          }}
        >
          <UploadCloud size={28} />
        </div>

        <div>
          <h2
            style={{ fontSize: "17px", fontWeight: 700, margin: "0 0 6px 0" }}
          >
            Upload Research Papers
          </h2>
          <p
            style={{
              fontSize: "13px",
              color: "var(--text-secondary)",
              maxWidth: "460px",
              margin: "0 auto",
              lineHeight: 1.5,
            }}
          >
            Drag and drop academic PDFs or browse your device. Files are
            validated by binary magic bytes and deduplicated by SHA-256 hash.
          </p>
        </div>

        <input
          id="pdf-upload-input"
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,application/pdf"
          onChange={handleFileInputChange}
          style={{ display: "none" }}
          disabled={disabled || isUploading}
        />

        <div
          style={{
            display: "flex",
            gap: "12px",
            alignItems: "center",
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          <Button
            variant="ink"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isUploading}
            isLoading={isUploading}
          >
            {isUploading ? "Uploading & Validating..." : "Select PDF Files"}
          </Button>
          <Badge variant="neutral">Max {maxUploadMb} MB per document</Badge>
        </div>
      </div>

      {/* Batch Feedback Banner */}
      {lastBatchResult && (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-control)",
            borderRadius: "var(--r-xl)",
            padding: "16px 20px",
            boxShadow: "var(--raise-2)",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
          role="region"
          aria-label="Upload results summary"
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <strong style={{ fontSize: "14px", color: "var(--text-primary)" }}>
              Batch Ingestion Results
            </strong>
            <button
              onClick={onClearBatchResult}
              aria-label="Dismiss results"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                padding: "4px",
              }}
            >
              <X size={16} />
            </button>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {lastBatchResult.papers.length > 0 && (
              <Badge variant="success">
                <CheckCircle2 size={13} style={{ marginRight: "4px" }} />
                {lastBatchResult.papers.length} Accepted
              </Badge>
            )}
            {lastBatchResult.duplicates.length > 0 && (
              <Badge variant="warning">
                <AlertTriangle size={13} style={{ marginRight: "4px" }} />
                {lastBatchResult.duplicates.length} Duplicate
              </Badge>
            )}
            {lastBatchResult.rejected.length > 0 && (
              <Badge variant="error">
                <XCircle size={13} style={{ marginRight: "4px" }} />
                {lastBatchResult.rejected.length} Rejected
              </Badge>
            )}
          </div>

          {/* Detailed item list if any duplicates or rejections occurred */}
          {(lastBatchResult.duplicates.length > 0 ||
            lastBatchResult.rejected.length > 0) && (
            <div
              style={{
                fontSize: "12px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                background: "var(--surface-soft)",
                padding: "10px 14px",
                borderRadius: "var(--r-md)",
              }}
            >
              {lastBatchResult.duplicates.map((dup, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--orange-text)",
                  }}
                >
                  <AlertTriangle size={13} />
                  <span>
                    <strong>{dup.original_filename}</strong>: Exact content
                    already exists in this workspace.
                  </span>
                </div>
              ))}
              {lastBatchResult.rejected.map((rej, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--red-text)",
                  }}
                >
                  <XCircle size={13} />
                  <span>
                    <strong>{rej.original_filename}</strong>: {rej.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
