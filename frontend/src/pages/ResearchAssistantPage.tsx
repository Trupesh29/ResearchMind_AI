import React from "react";
import {
  BookOpen,
  MessageSquare,
  ShieldCheck,
  AlertCircle,
  FileSearch,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface ResearchAssistantPageProps {
  onNavigate: (path: string) => void;
}

export const ResearchAssistantPage: React.FC<ResearchAssistantPageProps> = ({
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
              Research Assistant
            </h1>
            <Badge variant="neutral">Planned · Phase 4</Badge>
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
            Evidence-grounded conversational synthesis over selected research
            documents with split PDF viewing and verifiable citations.
          </p>
        </div>
        <Button variant="ink" onClick={() => onNavigate("/library")}>
          <BookOpen size={16} />
          <span>Paper Library</span>
        </Button>
      </div>

      {/* Capabilities Grid */}
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
              <MessageSquare size={20} />
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
                Conversational Grounding
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Ask complex research questions with strict answer grounding.
                Every generated claim includes direct quotes from source chunks
                and explicit page references.
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
              <FileSearch size={20} />
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
                Split PDF & Evidence Drawer
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Side-by-side conversational interface with integrated PDF
                viewer, highlighting exact text spans and bounding boxes when
                clicking citation pills.
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
              <ShieldCheck size={20} />
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
                Explicit Abstention
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Refuses hallucination. If a query cannot be answered with high
                confidence from ingested workspace literature, the assistant
                reports evidence gaps explicitly.
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Roadmap & Status Box */}
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
            Phase 4 Foundation
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
          Document sectioning and semantic chunking with token bounding are
          complete. The assistant interactive interface will connect to the
          active FAISS/BM25 retrieval engine in the upcoming synthesis
          milestone.
        </p>
        <Button variant="soft" size="sm" onClick={() => onNavigate("/library")}>
          <BookOpen size={14} />
          <span>Prepare Papers in Library</span>
        </Button>
      </div>
    </div>
  );
};
