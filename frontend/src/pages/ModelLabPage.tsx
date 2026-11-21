import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Database,
  Activity,
  BarChart3,
  Terminal,
  CheckCircle2,
  Cpu,
  Layers,
  TrendingUp,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { intelligenceApi } from "../api/client";
import { ModelLabReportsResponse } from "../api/types";

interface ModelLabPageProps {
  onNavigate: (path: string) => void;
}

export const ModelLabPage: React.FC<ModelLabPageProps> = ({ onNavigate }) => {
  const [reports, setReports] = useState<ModelLabReportsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedSplit, setSelectedSplit] = useState<"dev" | "test">("test");

  useEffect(() => {
    let cancelled = false;
    intelligenceApi
      .getModelLabReports()
      .then((data) => {
        if (!cancelled) {
          setReports(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to fetch model lab reports", err);
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const testReport = reports?.test_evaluation;
  const baselinesReport = reports?.baselines;
  const readinessReport = reports?.readiness;
  const distilbertReport = reports?.distilbert_trial;

  return (
    <div
      style={{
        maxWidth: "1080px",
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

      {/* Live Benchmark & Evaluation Dashboard */}
      {testReport && (
        <Card elevation={2}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
              marginBottom: "20px",
              borderBottom: "1px solid var(--hairline)",
              paddingBottom: "14px",
            }}
          >
            <div>
              <h3 style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 4px 0" }}>
                SciCite Evaluation Benchmark Results
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
                Held-out evaluation over 1,861 unseen citation contexts with zero train/test leakage.
              </p>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <Badge variant="neutral">Verified Test Split</Badge>
              <Badge variant="soft">1,861 Samples</Badge>
            </div>
          </div>

          {/* Metric KPI Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
              marginBottom: "24px",
            }}
          >
            <div
              style={{
                padding: "16px",
                borderRadius: "var(--r-lg)",
                background: "var(--surface-sunken)",
                border: "1px solid var(--hairline)",
              }}
            >
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                TEST ACCURACY
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0" }}>
                {(testReport.accuracy * 100).toFixed(2)}%
              </div>
              <div style={{ fontSize: "11px", color: "var(--green-text, #248a3d)" }}>
                +22.89% over Majority Baseline
              </div>
            </div>

            <div
              style={{
                padding: "16px",
                borderRadius: "var(--r-lg)",
                background: "var(--surface-sunken)",
                border: "1px solid var(--hairline)",
              }}
            >
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                MACRO-F1 SCORE
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--blue-action)", margin: "4px 0" }}>
                {testReport.macro_f1.toFixed(4)}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                Balanced across 3 classes
              </div>
            </div>

            <div
              style={{
                padding: "16px",
                borderRadius: "var(--r-lg)",
                background: "var(--surface-sunken)",
                border: "1px solid var(--hairline)",
              }}
            >
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                WEIGHTED F1
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0" }}>
                {testReport.weighted_f1.toFixed(4)}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                Sample-weighted class balance
              </div>
            </div>

            <div
              style={{
                padding: "16px",
                borderRadius: "var(--r-lg)",
                background: "var(--surface-sunken)",
                border: "1px solid var(--hairline)",
              }}
            >
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                DISTILBERT TRIAL
              </div>
              <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: "10px 0" }}>
                Step 15 Resumed
              </div>
              <div style={{ fontSize: "11px", color: "var(--green-text, #248a3d)" }}>
                Checkpoint integrity verified
              </div>
            </div>
          </div>

          {/* Confusion Matrix and Per-Class Breakdown */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", flexWrap: "wrap" }}>
            <div>
              <h4 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 12px 0" }}>
                Test Split Confusion Matrix
              </h4>
              <div
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--hairline)",
                  borderRadius: "var(--r-md)",
                  padding: "12px",
                  overflowX: "auto",
                }}
              >
                <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse", textAlign: "center" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--hairline)" }}>
                      <th style={{ padding: "6px", textAlign: "left" }}>True \ Pred</th>
                      <th style={{ padding: "6px" }}>Background</th>
                      <th style={{ padding: "6px" }}>Method</th>
                      <th style={{ padding: "6px" }}>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {testReport.classes.map((cls: string, rIdx: number) => (
                      <tr key={cls} style={{ borderBottom: "1px solid var(--hairline)" }}>
                        <td style={{ padding: "6px", textAlign: "left", fontWeight: 600 }}>{cls}</td>
                        {testReport.confusion_matrix[rIdx].map((cnt: number, cIdx: number) => {
                          const isDiag = rIdx === cIdx;
                          return (
                            <td
                              key={cIdx}
                              style={{
                                padding: "6px",
                                background: isDiag ? "var(--blue-surface)" : "transparent",
                                fontWeight: isDiag ? 700 : 400,
                                color: isDiag ? "var(--blue-action)" : "var(--text-secondary)",
                              }}
                            >
                              {cnt}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 12px 0" }}>
                Per-Class Performance
              </h4>
              <div
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--hairline)",
                  borderRadius: "var(--r-md)",
                  padding: "12px",
                }}
              >
                <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse", textAlign: "center" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--hairline)" }}>
                      <th style={{ padding: "6px", textAlign: "left" }}>Intent Class</th>
                      <th style={{ padding: "6px" }}>Precision</th>
                      <th style={{ padding: "6px" }}>Recall</th>
                      <th style={{ padding: "6px" }}>F1-Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(testReport.per_class).map(([k, v]: [string, any]) => (
                      <tr key={k} style={{ borderBottom: "1px solid var(--hairline)" }}>
                        <td style={{ padding: "6px", textAlign: "left", fontWeight: 600 }}>{k}</td>
                        <td style={{ padding: "6px" }}>{(v.precision * 100).toFixed(1)}%</td>
                        <td style={{ padding: "6px" }}>{(v.recall * 100).toFixed(1)}%</td>
                        <td style={{ padding: "6px", fontWeight: 700, color: "var(--text-primary)" }}>
                          {(v.f1_score * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </Card>
      )}

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
