import React from "react";
import {
  LayoutDashboard,
  Database,
  Activity,
  BarChart3,
  Terminal,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface ModelLabPageProps {
  onNavigate: (path: string) => void;
}

export const ModelLabPage: React.FC<ModelLabPageProps> = ({ onNavigate }) => {
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
              Model Lab
            </h1>
            <Badge variant="neutral">Planned · Phase 6</Badge>
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
            SciCite citation intent classification experimentation, baseline
            model evaluation, learning curves, and local CLI reproducibility.
          </p>
        </div>
        <Button variant="ink" onClick={() => onNavigate("/dashboard")}>
          <LayoutDashboard size={16} />
          <span>Dashboard</span>
        </Button>
      </div>

      {/* Model Lab Cards */}
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
              <Database size={20} />
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
                SciCite Intent Taxonomy
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Categorizes citation contexts into Background, Method, or Result
                Comparison with balanced splits and strict label schemas.
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
              <BarChart3 size={20} />
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
                Baselines & DistilBERT
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Benchmarked against Majority Class and TF-IDF baselines.
                Fine-tuned DistilBERT models with confusion matrices and macro
                F1 scores.
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
              <Activity size={20} />
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
                Learning Curves & Telemetry
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Tracks loss progression, validation accuracy, early stopping
                checkpoints, and hardware performance metrics across training
                epochs.
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* CLI Note */}
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
          <Terminal size={18} color="var(--blue-action)" />
          <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0 }}>
            CLI-Driven Training & Reproducibility
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
          To maintain strict hardware boundary isolation and avoid GPU memory
          conflicts with the web server, model training, evaluation, and
          artifact generation are executed via dedicated command-line scripts in{" "}
          <code>ml/</code>:
        </p>
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-control)",
            borderRadius: "var(--r-md)",
            padding: "12px 16px",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "12px",
            color: "var(--text-primary)",
            overflowX: "auto",
          }}
        >
          .venv\Scripts\python -m ml.train --dataset scicite --model distilbert
          --epochs 3
        </div>
      </div>
    </div>
  );
};
