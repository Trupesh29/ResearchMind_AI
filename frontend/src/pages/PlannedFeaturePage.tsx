import React from "react";
import { Clock, ArrowLeft, BookOpen } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface PlannedFeaturePageProps {
  featureName: string;
  roadmapPhase: number;
  description: string;
  onNavigate: (path: string) => void;
}

export const PlannedFeaturePage: React.FC<PlannedFeaturePageProps> = ({
  featureName,
  roadmapPhase,
  description,
  onNavigate,
}) => {
  return (
    <div
      style={{
        maxWidth: "680px",
        margin: "48px auto",
        padding: "0 16px",
      }}
    >
      <Card elevation={2}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "16px",
          }}
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "var(--r-md)",
              background: "var(--surface-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--blue-action)",
            }}
          >
            <Clock size={20} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h1
                style={{
                  fontSize: "20px",
                  fontWeight: 700,
                  margin: 0,
                  color: "var(--text-primary)",
                }}
              >
                {featureName}
              </h1>
              <Badge variant="neutral">Roadmap Phase {roadmapPhase}</Badge>
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "2px",
              }}
            >
              Scheduled for future implementation milestone
            </div>
          </div>
        </div>

        <p
          style={{
            fontSize: "14px",
            lineHeight: 1.6,
            color: "var(--text-secondary)",
            marginBottom: "20px",
          }}
        >
          {description}
        </p>

        <div
          style={{
            padding: "16px",
            borderRadius: "var(--r-md)",
            background: "var(--surface-sunken)",
            border: "1px solid var(--hairline)",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              fontSize: "12px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              color: "var(--text-muted)",
              marginBottom: "8px",
            }}
          >
            Currently Active Modules
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            <Badge variant="success">Paper Library</Badge>
            <Badge variant="success">PDF Ingestion & Extraction</Badge>
            <Badge variant="success">Sectioning & Document Cleaning</Badge>
            <Badge variant="success">
              Token-Safe Chunking & Quality Center
            </Badge>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Button variant="ink" onClick={() => onNavigate("/library")}>
            <BookOpen size={16} />
            <span>Open Paper Library</span>
          </Button>
          <Button variant="ghost" onClick={() => onNavigate("/dashboard")}>
            <ArrowLeft size={16} />
            <span>Return to Dashboard</span>
          </Button>
        </div>
      </Card>
    </div>
  );
};
