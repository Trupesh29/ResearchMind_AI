import React, { useState, useEffect } from "react";
import {
  Compass,
  BookOpen,
  Layers,
  CheckCircle2,
  AlertCircle,
  FileText,
  Download,
  Sparkles,
  GitCompare,
  Beaker,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { api, intelligenceApi } from "../api/client";
import {
  PaperItem,
  PaperSectionsResponse,
  PaperSummaryResponse,
  SummaryStyle,
  ComparisonMatrixResponse,
  ExperimentExtractResponse,
  SummaryCitation,
} from "../api/types";

interface ResearchExplorerPageProps {
  onNavigate: (path: string) => void;
}

export const ResearchExplorerPage: React.FC<ResearchExplorerPageProps> = ({
  onNavigate,
}) => {
  const [activeTab, setActiveTab] = useState<"overview" | "summaries" | "comparison" | "experiments">("overview");
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<string>("");
  const [selectedPaperBId, setSelectedPaperBId] = useState<string>("");
  const [selectedStyle, setSelectedStyle] = useState<SummaryStyle>("simple");
  const [loading, setLoading] = useState<boolean>(false);
  const [summaryData, setSummaryData] = useState<PaperSummaryResponse | null>(null);
  const [sectionsData, setSectionsData] = useState<PaperSectionsResponse | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonMatrixResponse | null>(null);
  const [experimentsData, setExperimentsData] = useState<ExperimentExtractResponse | null>(null);
  const [exportingReport, setExportingReport] = useState<boolean>(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<SummaryCitation | null>(null);

  // Load available papers
  useEffect(() => {
    let cancelled = false;
    api.listPapers(null, 50).then((res) => {
      if (!cancelled && res.items.length > 0) {
        setPapers(res.items);
        setSelectedPaperId(res.items[0].id);
        if (res.items.length > 1) {
          setSelectedPaperBId(res.items[1].id);
        }
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const handleFetchSummaryAndSections = async () => {
    if (!selectedPaperId) return;
    setLoading(true);
    try {
      const [sumRes, secRes] = await Promise.all([
        intelligenceApi.getSummary(selectedPaperId, selectedStyle),
        intelligenceApi.getSections(selectedPaperId),
      ]);
      setSummaryData(sumRes);
      setSectionsData(secRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchComparison = async () => {
    if (!selectedPaperId || !selectedPaperBId) return;
    setLoading(true);
    try {
      const activePaper = papers.find((p) => p.id === selectedPaperId);
      const wsId = activePaper?.workspace_id || "default";
      const compRes = await intelligenceApi.getComparison(wsId, selectedPaperId, selectedPaperBId);
      setComparisonData(compRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchExperiments = async () => {
    if (!selectedPaperId) return;
    setLoading(true);
    try {
      const expRes = await intelligenceApi.extractExperiments(selectedPaperId);
      setExperimentsData(expRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleExportDocx = async () => {
    if (!selectedPaperId) return;
    setExportingReport(true);
    setExportSuccess(null);
    try {
      const activePaper = papers.find((p) => p.id === selectedPaperId);
      const wsId = activePaper?.workspace_id || "default";
      const pids = [selectedPaperId];
      if (selectedPaperBId && selectedPaperBId !== selectedPaperId) {
        pids.push(selectedPaperBId);
      }
      const rep = await intelligenceApi.generateReport({
        workspace_id: wsId,
        title: `Research Synthesis Report — ${activePaper?.title || "Selected Papers"}`,
        paper_ids: pids,
        summary_style: selectedStyle,
        include_comparison: pids.length >= 2,
        include_experiments: true,
      });
      setExportSuccess(`Report ready (${Math.round((rep.file_size_bytes || 0) / 1024)} KB)`);
      window.open(intelligenceApi.getReportDownloadUrl(rep.report_id), "_blank");
    } catch (e) {
      console.error(e);
    } finally {
      setExportingReport(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: "1080px",
        margin: "0 auto",
        padding: "16px 0 48px 0",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
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
        <div style={{ display: "flex", gap: "10px" }}>
          <Button variant="ink" onClick={() => onNavigate("/library")}>
            <BookOpen size={16} />
            <span>Paper Library</span>
          </Button>
          <Button
            variant="primary"
            onClick={handleExportDocx}
            disabled={exportingReport || papers.length === 0}
          >
            {exportingReport ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            <span>Export Report (.docx)</span>
          </Button>
        </div>
      </div>

      {exportSuccess && (
        <div
          style={{
            padding: "10px 16px",
            borderRadius: "var(--r-md)",
            background: "var(--green-surface, rgba(52, 199, 89, 0.12))",
            color: "var(--green-text, #248a3d)",
            fontSize: "13px",
            fontWeight: 500,
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <CheckCircle2 size={16} />
          <span>{exportSuccess}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          borderBottom: "1px solid var(--hairline)",
          paddingBottom: "8px",
        }}
      >
        <Button
          variant={activeTab === "overview" ? "primary" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("overview")}
        >
          <Compass size={14} />
          <span>Overview</span>
        </Button>
        <Button
          variant={activeTab === "summaries" ? "primary" : "ghost"}
          size="sm"
          onClick={() => {
            setActiveTab("summaries");
            if (!summaryData && selectedPaperId) handleFetchSummaryAndSections();
          }}
        >
          <Sparkles size={14} />
          <span>Multi-Style Summaries</span>
        </Button>
        <Button
          variant={activeTab === "comparison" ? "primary" : "ghost"}
          size="sm"
          onClick={() => {
            setActiveTab("comparison");
            if (!comparisonData && selectedPaperId && selectedPaperBId) handleFetchComparison();
          }}
        >
          <GitCompare size={14} />
          <span>Compare Literature</span>
        </Button>
        <Button
          variant={activeTab === "experiments" ? "primary" : "ghost"}
          size="sm"
          onClick={() => {
            setActiveTab("experiments");
            if (!experimentsData && selectedPaperId) handleFetchExperiments();
          }}
        >
          <Beaker size={14} />
          <span>Experiment Intelligence</span>
        </Button>
      </div>

      {/* Tab: Overview (Feature Architecture Cards & Status Box) */}
      {activeTab === "overview" && (
        <>
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
        </>
      )}

      {/* Tab: Multi-Style Summaries */}
      {activeTab === "summaries" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Controls */}
          <Card elevation={1}>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: "220px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                  Selected Paper
                </label>
                <select
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--border-control)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                  }}
                  value={selectedPaperId}
                  onChange={(e) => setSelectedPaperId(e.target.value)}
                >
                  {papers.map((p) => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                  Summary Style
                </label>
                <div style={{ display: "flex", gap: "6px" }}>
                  {(["simple", "technical", "methodology", "results"] as SummaryStyle[]).map((st) => (
                    <Button
                      key={st}
                      variant={selectedStyle === st ? "primary" : "soft"}
                      size="sm"
                      onClick={() => setSelectedStyle(st)}
                    >
                      {st.charAt(0).toUpperCase() + st.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>

              <div style={{ alignSelf: "flex-end" }}>
                <Button variant="ink" onClick={handleFetchSummaryAndSections} disabled={loading}>
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  <span>Generate Summary</span>
                </Button>
              </div>
            </div>
          </Card>

          {/* Results View */}
          {summaryData && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "20px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <Card elevation={1}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <h3 style={{ fontSize: "17px", fontWeight: 600, margin: 0 }}>
                      {summaryData.style.charAt(0).toUpperCase() + summaryData.style.slice(1)} Summary
                    </h3>
                    {summaryData.cached && <Badge variant="neutral">Cached</Badge>}
                  </div>
                  <p style={{ fontSize: "14px", color: "var(--text-secondary)", lineHeight: 1.6, margin: "0 0 16px 0" }}>
                    {summaryData.overview}
                  </p>

                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {summaryData.points.map((pt) => (
                      <div
                        key={pt.point_id}
                        style={{
                          padding: "12px 14px",
                          borderRadius: "var(--r-md)",
                          background: "var(--surface-sunken)",
                          border: "1px solid var(--hairline)",
                        }}
                      >
                        <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "4px" }}>
                          {pt.heading}
                        </div>
                        <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: "0 0 8px 0", lineHeight: 1.5 }}>
                          {pt.content}
                        </p>
                        {pt.citations.map((c) => (
                          <button
                            key={c.citation_id}
                            onClick={() => setActiveCitation(c)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                              padding: "2px 8px",
                              borderRadius: "var(--r-full)",
                              background: "var(--blue-surface)",
                              color: "var(--blue-action)",
                              border: "none",
                              fontSize: "11px",
                              cursor: "pointer",
                              marginRight: "6px",
                            }}
                          >
                            <span>[{c.citation_id}]</span>
                            <span>p. {c.page_number} ({c.section_title})</span>
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              {/* Section Hierarchy / Citation Inspector */}
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {activeCitation && (
                  <Card elevation={2}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--blue-action)" }}>
                        Citation [{activeCitation.citation_id}]
                      </span>
                      <button
                        onClick={() => setActiveCitation(null)}
                        style={{ border: "none", background: "none", cursor: "pointer", fontSize: "12px", color: "var(--text-secondary)" }}
                      >
                        ✕
                      </button>
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                      <strong>Section:</strong> {activeCitation.section_title} | <strong>Page:</strong> {activeCitation.page_number}
                    </div>
                    <blockquote
                      style={{
                        margin: 0,
                        padding: "8px 10px",
                        borderLeft: "3px solid var(--blue-action)",
                        background: "var(--surface-sunken)",
                        fontSize: "12px",
                        color: "var(--text-primary)",
                        fontStyle: "italic",
                      }}
                    >
                      "{activeCitation.quote}"
                    </blockquote>
                  </Card>
                )}

                {sectionsData && (
                  <Card elevation={1}>
                    <h4 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 10px 0" }}>
                      Document Sections ({sectionsData.total_sections})
                    </h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {sectionsData.sections.map((sec) => (
                        <div
                          key={sec.section_index}
                          style={{
                            padding: "8px 10px",
                            borderRadius: "var(--r-sm)",
                            background: "var(--surface)",
                            border: "1px solid var(--hairline)",
                            fontSize: "12px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                              {sec.section_title}
                            </span>
                            <Badge variant={sec.quality_status === "complete" ? "neutral" : "soft"}>
                              {sec.chunk_count} chunks
                            </Badge>
                          </div>
                          <div style={{ color: "var(--text-secondary)", fontSize: "11px" }}>
                            Pages {sec.page_start}–{sec.page_end}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Two-Paper Comparison */}
      {activeTab === "comparison" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <Card elevation={1}>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: "200px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                  Paper A
                </label>
                <select
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--border-control)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                  }}
                  value={selectedPaperId}
                  onChange={(e) => setSelectedPaperId(e.target.value)}
                >
                  {papers.map((p) => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
              </div>

              <div style={{ flex: 1, minWidth: "200px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                  Paper B
                </label>
                <select
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--border-control)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                  }}
                  value={selectedPaperBId}
                  onChange={(e) => setSelectedPaperBId(e.target.value)}
                >
                  {papers.map((p) => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
              </div>

              <div style={{ alignSelf: "flex-end" }}>
                <Button variant="ink" onClick={handleFetchComparison} disabled={loading || !selectedPaperId || !selectedPaperBId}>
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <GitCompare size={14} />}
                  <span>Generate Comparison</span>
                </Button>
              </div>
            </div>
          </Card>

          {comparisonData && (
            <Card elevation={1}>
              <div style={{ marginBottom: "16px" }}>
                <h3 style={{ fontSize: "16px", fontWeight: 600, margin: "0 0 6px 0" }}>
                  Cross-Paper Synthesis
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: "0 0 10px 0" }}>
                  {comparisonData.overall_synthesis}
                </p>
                <Badge variant="neutral">{comparisonData.comparability_summary}</Badge>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ background: "var(--surface-sunken)", borderBottom: "1px solid var(--hairline)", textAlign: "left" }}>
                      <th style={{ padding: "10px", width: "20%" }}>Dimension</th>
                      <th style={{ padding: "10px", width: "30%" }}>Paper A</th>
                      <th style={{ padding: "10px", width: "30%" }}>Paper B</th>
                      <th style={{ padding: "10px", width: "20%" }}>Comparability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonData.dimensions.map((dim) => (
                      <tr key={dim.dimension_id} style={{ borderBottom: "1px solid var(--hairline)" }}>
                        <td style={{ padding: "10px", fontWeight: 600, verticalAlign: "top" }}>
                          {dim.dimension_name}
                        </td>
                        <td style={{ padding: "10px", verticalAlign: "top", color: "var(--text-secondary)" }}>
                          <p style={{ margin: "0 0 4px 0" }}>{dim.paper_a_claim}</p>
                          {dim.paper_a_citations.map((c) => (
                            <span key={c.citation_id} style={{ fontSize: "11px", color: "var(--blue-action)" }}>
                              [p. {c.page_number}]
                            </span>
                          ))}
                        </td>
                        <td style={{ padding: "10px", verticalAlign: "top", color: "var(--text-secondary)" }}>
                          <p style={{ margin: "0 0 4px 0" }}>{dim.paper_b_claim}</p>
                          {dim.paper_b_citations.map((c) => (
                            <span key={c.citation_id} style={{ fontSize: "11px", color: "var(--blue-action)" }}>
                              [p. {c.page_number}]
                            </span>
                          ))}
                        </td>
                        <td style={{ padding: "10px", verticalAlign: "top" }}>
                          <Badge variant={dim.comparable_status === "comparable" ? "neutral" : "soft"}>
                            {dim.comparable_status.replace("_", " ")}
                          </Badge>
                          <p style={{ fontSize: "11px", color: "var(--text-secondary)", margin: "4px 0 0 0" }}>
                            {dim.synthesis_notes}
                          </p>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Tab: Experiment Intelligence */}
      {activeTab === "experiments" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <Card elevation={1}>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: "220px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                  Selected Paper
                </label>
                <select
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--border-control)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                  }}
                  value={selectedPaperId}
                  onChange={(e) => setSelectedPaperId(e.target.value)}
                >
                  {papers.map((p) => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
              </div>

              <div style={{ alignSelf: "flex-end" }}>
                <Button variant="ink" onClick={handleFetchExperiments} disabled={loading}>
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Beaker size={14} />}
                  <span>Extract Experiments</span>
                </Button>
              </div>
            </div>
          </Card>

          {experimentsData && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ fontSize: "16px", fontWeight: 600, margin: 0 }}>
                  Experimental Protocols & Measured Results
                </h3>
                <Badge variant={experimentsData.status === "experiments_extracted" ? "neutral" : "soft"}>
                  {experimentsData.status.replace("_", " ")}
                </Badge>
              </div>

              {experimentsData.experiments.length === 0 ? (
                <div style={{ padding: "24px", textAlign: "center", color: "var(--text-secondary)", background: "var(--surface-sunken)", borderRadius: "var(--r-lg)" }}>
                  No quantitative experimental configurations detected in the parsed document.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
                  {experimentsData.experiments.map((exp) => (
                    <Card key={exp.experiment_id} elevation={1}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                        <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)" }}>
                          {exp.task}
                        </span>
                        <Badge variant="soft">{exp.method}</Badge>
                      </div>

                      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "8px" }}>
                        <strong>Conditions:</strong> {Object.entries(exp.conditions).map(([k, v]) => `${k}: ${v}`).join(", ")}
                      </div>

                      <div style={{ marginBottom: "12px" }}>
                        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: "4px" }}>
                          Extracted Metrics:
                        </span>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          {exp.metrics.map((m, i) => (
                            <span
                              key={i}
                              style={{
                                padding: "3px 8px",
                                borderRadius: "var(--r-sm)",
                                background: "var(--surface-sunken)",
                                border: "1px solid var(--hairline)",
                                fontSize: "11px",
                              }}
                            >
                              <strong>{m.metric_name}:</strong> {m.value} {m.unit || ""}
                            </span>
                          ))}
                        </div>
                      </div>

                      {exp.provenance && (
                        <div style={{ fontSize: "11px", color: "var(--text-secondary)", borderTop: "1px solid var(--hairline)", paddingTop: "8px" }}>
                          Provenance: <strong>{exp.provenance.section_title}</strong> (p. {exp.provenance.page_number})
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
