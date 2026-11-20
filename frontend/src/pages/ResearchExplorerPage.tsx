import React from "react";
import {
  Compass,
  BookOpen,
  Layers,
  CheckCircle2,
  AlertCircle,
  FileText,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface ResearchExplorerPageProps {
  onNavigate: (path: string) => void;
}

export const ResearchExplorerPage: React.FC<ResearchExplorerPageProps> = ({
  onNavigate,
}) => {
  return (
    <div
      style={{
        maxWidth: "960px",
        margin: "0 auto",
        padding: "16px 0 48px 0",
        display: "flex",
        flexDirection: "column",
        gap: "28px",
      }}
    >
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
              marginBottom: "8px",
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
              Research Explorer
            </h1>
            <Badge variant="neutral">Planned · Phase 5</Badge>
          </div>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: "15px",
              margin: 0,
              maxWidth: "680px",
              lineHeight: 1.5,
            }}
          >
            Synthesize cross-document evidence, compare methodology across
            papers, and trace scientific findings to page-level source
            citations.
          </p>
        </div>
        <Button variant="ink" onClick={() => onNavigate("/library")}>
          <BookOpen size={16} />
          <span>Paper Library</span>
        </Button>
      </div>

      {/* Feature Architecture Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "20px",
        }}
      >
        <Card elevation={1}>
          <div
            style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}
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
                color: "var(--blue-action)",
                flexShrink: 0,
              }}
            >
              <Compass size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Source Sections & Grounding
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Filter across extracted document sections (Abstract, Methods,
                Results, Discussion) with token-bounded chunk alignment and
                exact PDF coordinates.
              </p>
            </div>
          </div>
        </Card>

        <Card elevation={1}>
          <div
            style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}
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
                color: "var(--text-primary)",
                flexShrink: 0,
              }}
            >
              <Layers size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Two-Paper Comparison
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Directly compare study designs, dataset scales, sample sizes,
                and empirical claims with explicit comparability warnings and
                contrastive matrices.
              </p>
            </div>
          </div>
        </Card>

        <Card elevation={1}>
          <div
            style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--r-md)",
                background: "var(--green-surface, rgba(52, 199, 89, 0.12))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--green-text, #248a3d)",
                flexShrink: 0,
              }}
            >
              <CheckCircle2 size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 600,
                  margin: "0 0 6px 0",
                  color: "var(--text-primary)",
                }}
              >
                Hybrid Index Retrieval
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Powered by paired FAISS FlatIP dense embeddings and BM25 sparse
                lexical search, published through serialized workspace index
                snapshots.
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Prerequisites & Status Box */}
      <div
        style={{
          padding: "20px 24px",
          borderRadius: "var(--r-xl)",
          background: "var(--surface-sunken)",
          border: "1px solid var(--hairline)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "12px",
          }}
        >
          <AlertCircle size={18} color="var(--blue-action)" />
          <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
            Phase 5 Implementation Status
          </h3>
        </div>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-secondary)",
            lineHeight: 1.6,
            margin: "0 0 16px 0",
          }}
        >
          The backend embedding pipeline (all-MiniLM-L6-v2, 384 dimensions) and
          paired index publication (FAISS + BM25) are fully operational. The
          frontend exploration view is scheduled for implementation once
          multi-paper citation synthesis contracts are finalized.
        </p>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <Button
            variant="soft"
            size="sm"
            onClick={() => onNavigate("/quality")}
          >
            <FileText size={14} />
            <span>Inspect Ingestion Quality</span>
          </Button>
          <Button
            variant="soft"
            size="sm"
            onClick={() => onNavigate("/library")}
          >
            <BookOpen size={14} />
            <span>Manage Literature</span>
          </Button>
        </div>
      </div>
    </div>
  );
};
