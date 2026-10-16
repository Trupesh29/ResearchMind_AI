import React from "react";
import { UploadCloud, FileText, CheckCircle2, ShieldAlert } from "lucide-react";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

export const LibraryPage: React.FC = () => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
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
              marginBottom: "6px",
            }}
          >
            <h1 style={{ fontSize: "28px" }}>Research Paper Library</h1>
            <Badge variant="info">Phase 2 Lifecycle</Badge>
          </div>
          <p style={{ color: "var(--text-muted)", fontSize: "14px" }}>
            Manage research papers, view processing statuses, and inspect
            original PDF evidence.
          </p>
        </div>
      </div>

      {/* Upload Dropzone Preview (Phase 2) */}
      <Card
        variant="sunken"
        style={{
          border: "2px dashed var(--border-control)",
          borderRadius: "var(--r-2xl)",
          padding: "48px 24px",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "16px",
        }}
      >
        <div
          style={{
            width: "64px",
            height: "64px",
            borderRadius: "50%",
            background: "var(--surface-soft)",
            boxShadow: "var(--raise-2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--blue-action)",
          }}
        >
          <UploadCloud size={32} />
        </div>

        <div>
          <h3 style={{ fontSize: "18px", marginBottom: "6px" }}>
            Multi-File PDF Upload Pipeline
          </h3>
          <p
            style={{
              fontSize: "14px",
              color: "var(--text-muted)",
              maxWidth: "480px",
              margin: "0 auto",
            }}
          >
            Drag and drop text-based academic papers or browse your file system.
            Files are validated via <code>%PDF-</code> magic bytes and
            deduplicated by SHA-256.
          </p>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <Button
            variant="soft"
            disabled
            title="Will be interactive in Phase 2"
          >
            Select PDF Files
          </Button>
          <Badge variant="neutral">Max 25 MB per document</Badge>
        </div>
      </Card>

      {/* Contract & Integrity Rules Card */}
      <Card elevation={1}>
        <h2 style={{ fontSize: "18px", marginBottom: "16px" }}>
          Document Ingestion Contract (Phase 2 Ready)
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "16px",
          }}
        >
          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-md)",
              background: "var(--surface)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "6px",
              }}
            >
              <CheckCircle2 size={16} color="var(--green-strong)" />
              <strong style={{ fontSize: "14px" }}>
                Binary Magic Bytes Check
              </strong>
            </div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                lineHeight: 1.5,
              }}
            >
              Files are verified by inspecting the first 4 bytes for{" "}
              <code>%PDF-</code>, preventing malicious or corrupted file
              extensions.
            </p>
          </div>

          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-md)",
              background: "var(--surface)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "6px",
              }}
            >
              <ShieldAlert size={16} color="var(--orange-strong)" />
              <strong style={{ fontSize: "14px" }}>
                SHA-256 Deduplication
              </strong>
            </div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                lineHeight: 1.5,
              }}
            >
              Database uniqueness constraint{" "}
              <code>UNIQUE(workspace_id, sha256)</code> strictly rejects
              duplicate uploads within the same workspace.
            </p>
          </div>

          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-md)",
              background: "var(--surface)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "6px",
              }}
            >
              <FileText size={16} color="var(--blue-action)" />
              <strong style={{ fontSize: "14px" }}>
                Private Storage & Streaming
              </strong>
            </div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                lineHeight: 1.5,
              }}
            >
              Original PDFs are stored with generated UUID filenames in private{" "}
              <code>data/pdfs/</code> and streamed through{" "}
              <code>GET /papers/&#123;id&#125;/file</code>.
            </p>
          </div>
        </div>
      </Card>

      {/* Empty State Table */}
      <Card elevation={1} style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--hairline)",
            background: "var(--surface-alt)",
          }}
        >
          <strong style={{ fontSize: "14px", color: "var(--text-primary)" }}>
            Workspace Documents (0)
          </strong>
        </div>
        <div style={{ padding: "48px 24px", textAlign: "center" }}>
          <p
            style={{
              color: "var(--text-muted)",
              fontSize: "14px",
              marginBottom: "8px",
            }}
          >
            No documents in this library yet.
          </p>
          <p style={{ color: "var(--text-disabled)", fontSize: "12px" }}>
            Uploading and library management lifecycle activates in Week 1,
            Phase 2.
          </p>
        </div>
      </Card>
    </div>
  );
};
