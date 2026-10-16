import React from "react";
import {
  FileText,
  CheckCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
  Database,
  Cpu,
  HardDrive,
  Bot,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { ReadyResponse, PublicConfigResponse } from "../api/types";

interface DashboardPageProps {
  onNavigateToLibrary: () => void;
  readyStatus: "online" | "degraded" | "offline" | "loading";
  readyData: ReadyResponse | null;
  configData: PublicConfigResponse | null;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onNavigateToLibrary,
  readyStatus,
  readyData,
  configData,
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
      {/* Header Row */}
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
          <h1 style={{ fontSize: "28px", marginBottom: "6px" }}>
            Workspace Dashboard
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
            Overview of uploaded research documents, processing statuses, and
            system foundation.
          </p>
        </div>

        <Button variant="ink" onClick={onNavigateToLibrary}>
          <span>Open Library</span>
          <ArrowRight size={16} />
        </Button>
      </div>

      {/* Metric KPI Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
        }}
      >
        <Card elevation={1}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-muted)",
              }}
            >
              Total Papers
            </span>
            <FileText size={18} color="var(--blue-action)" />
          </div>
          <div
            className="tabular-nums"
            style={{
              fontSize: "32px",
              fontWeight: 800,
              color: "var(--text-muted)",
            }}
          >
            —
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            Uploads activate in Phase 2
          </div>
        </Card>

        <Card elevation={1}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-muted)",
              }}
            >
              Ready for Search
            </span>
            <CheckCircle size={18} color="var(--green-strong)" />
          </div>
          <div
            className="tabular-nums"
            style={{
              fontSize: "32px",
              fontWeight: 800,
              color: "var(--text-muted)",
            }}
          >
            —
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            FAISS & BM25 indexing in Week 3
          </div>
        </Card>

        <Card elevation={1}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-muted)",
              }}
            >
              Extraction Jobs
            </span>
            <Clock size={18} color="var(--orange-strong)" />
          </div>
          <div
            className="tabular-nums"
            style={{
              fontSize: "32px",
              fontWeight: 800,
              color: "var(--text-muted)",
            }}
          >
            —
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            PyMuPDF parsing in Week 2
          </div>
        </Card>

        <Card elevation={1}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-muted)",
              }}
            >
              Quality Alerts
            </span>
            <AlertTriangle size={18} color="var(--gray-500)" />
          </div>
          <div
            className="tabular-nums"
            style={{
              fontSize: "32px",
              fontWeight: 800,
              color: "var(--text-muted)",
            }}
          >
            —
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            Scan & table detection in Week 2
          </div>
        </Card>
      </div>

      {/* System Foundation & Environment Verification Panel */}
      <Card elevation={2}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px",
          }}
        >
          <div>
            <h2 style={{ fontSize: "18px", marginBottom: "4px" }}>
              System Architecture & Environment
            </h2>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Live runtime status verified via FastAPI <code>/api/ready</code>{" "}
              probe.
            </p>
          </div>
          <Badge
            variant={
              readyStatus === "online"
                ? "success"
                : readyStatus === "loading"
                  ? "info"
                  : "error"
            }
          >
            {readyStatus === "online"
              ? "System Operational"
              : readyStatus === "loading"
                ? "Probing..."
                : "Offline / Degraded"}
          </Badge>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "16px",
          }}
        >
          {/* Database Block */}
          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-sunken)",
              boxShadow: "var(--inset-1)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "8px",
              }}
            >
              <Database size={16} color="var(--blue-action)" />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}
              >
                Database
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
              <div>
                <strong>Engine:</strong> SQLite (WAL + FK)
              </div>
              <div>
                <strong>Status:</strong>{" "}
                {readyData?.checks.database?.status === "healthy"
                  ? "Operational & Schema Verified"
                  : readyData?.checks.database?.message || "Connecting..."}
              </div>
              <div>
                <strong>Schema:</strong> Alembic Head (Core & Constraints)
              </div>
            </div>
          </div>

          {/* Storage Block */}
          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-sunken)",
              boxShadow: "var(--inset-1)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "8px",
              }}
            >
              <HardDrive size={16} color="var(--green-strong)" />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}
              >
                Private Storage
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
              <div>
                <strong>Directory:</strong> <code>data/</code>
              </div>
              <div>
                <strong>Write Status:</strong>{" "}
                {readyData?.checks.storage?.status === "healthy"
                  ? "Writable (Verified)"
                  : readyData?.checks.storage?.message || "Checking..."}
              </div>
              <div>
                <strong>Max Upload:</strong> {configData?.max_upload_mb || 25}{" "}
                MB
              </div>
            </div>
          </div>

          {/* Machine Learning Block */}
          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-sunken)",
              boxShadow: "var(--inset-1)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "8px",
              }}
            >
              <Cpu size={16} color="var(--orange-strong)" />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}
              >
                ML Embedder
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
              <div>
                <strong>Model:</strong>{" "}
                {configData?.embedding_model || "all-MiniLM-L6-v2"}
              </div>
              <div>
                <strong>Dimension:</strong> 384 vectors
              </div>
              <div>
                <strong>Runtime:</strong> Installed (Weights load on demand)
              </div>
            </div>
          </div>

          {/* Generator Provider Block */}
          <div
            style={{
              padding: "16px",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-sunken)",
              boxShadow: "var(--inset-1)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "8px",
              }}
            >
              <Bot size={16} color="var(--ink)" />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}
              >
                Generator
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
              <div>
                <strong>Provider:</strong>{" "}
                {readyData?.checks.generator?.provider ||
                  configData?.generator_provider ||
                  "mock"}
              </div>
              <div>
                <strong>Model:</strong>{" "}
                {readyData?.checks.generator?.model || "gpt-4o-mini"}
              </div>
              <div>
                <strong>Status:</strong>{" "}
                {readyData?.checks.generator?.message || "Unverified"}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Workspace Readiness Overview Card */}
      <Card elevation={1}>
        <h2 style={{ fontSize: "18px", marginBottom: "16px" }}>
          Workspace Foundation & Capabilities
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              borderRadius: "var(--r-md)",
              background: "var(--surface-soft)",
            }}
          >
            <div>
              <strong
                style={{ fontSize: "14px", color: "var(--text-primary)" }}
              >
                Universal Document Architecture
              </strong>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Evidence-first universal PDF research analyzer. Full local
                privacy and schema-enforced workspace isolation.
              </div>
            </div>
            <Badge variant="success">Foundation Ready</Badge>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              borderRadius: "var(--r-md)",
              background: "var(--surface)",
            }}
          >
            <div>
              <strong
                style={{ fontSize: "14px", color: "var(--text-primary)" }}
              >
                Document Library & Ingestion
              </strong>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Multi-file drag-and-drop, PDF validation, SHA-256 deduplication,
                and viewer activate in Week 1 Phase 2.
              </div>
            </div>
            <Badge variant="info">Phase 2 Target</Badge>
          </div>
        </div>
      </Card>
    </div>
  );
};
