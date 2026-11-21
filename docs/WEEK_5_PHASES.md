# ResearchMind AI — Week 5 Implementation Phases

**Date:** 2026-10-22  
**Status:** Planned  
**Outcome:** Advanced research intelligence features: Research Explorer with structured summaries, two-paper comparison matrix, experiment intelligence extraction, downloadable DOCX reports, and Model Lab dashboard.

---

## Roadmap-to-Week Mapping

Week 5 delivers roadmap **Phase 5** (Research Explorer, paper comparisons, and DOCX reporting), **Phase 5B** (basic experiment extraction), and the frontend presentation for **Phase 6** (Model Lab).

---

## Schedule & Phases

| Phase | Focus | Deliverable | Gate |
|---|---|---|---|
| Phase 10 | Research Explorer & Structured Summaries | Explorer UI, section extraction, cached summaries (simple, technical, methodology, results) | Evidence citations for all summary points; null states for missing sections |
| Phase 11 | Two-Paper Comparison Matrix | Flexible dimension comparison (objectives, methodology, dataset, results, limitations) | Per-cell citations; explicit non-comparable warnings |
| Phase 12 | Basic Experiment Intelligence | Extraction jobs, condition/measurement parsing, structured experiment records | Provenance links to source passages; empty states for papers without experiments |
| Phase 13 | Report Studio (DOCX Generation) | Server-side python-docx report generation, status polling, download endpoint | Valid DOCX file generation, accurate table formatting, complete citations |
| Phase 14 | Model Lab UI | Presentation of saved SciCite baseline & fine-tuned model metrics, confusion matrix, curves | Honest display of measured metrics without fabricated claims |
| Week 5 Acceptance | Integrated research intelligence verification | Multi-module test suites, browser verification, export validation | Exported DOCX verified, comparison verified, experiment provenance verified |

---

## Phase 10 — Research Explorer & Structured Summaries

**User result:** Users can explore auto-detected paper sections and generate grounded summaries across 4 distinct styles.

1. **Section Intelligence:**
   - Display detected section hierarchy (Introduction, Methods, Results, Discussion, etc.) with page anchors.
   - Highlight quality indicators and extraction warnings.
2. **Multi-Style Summaries:**
   - Simple (high-level executive overview), Technical (in-depth analysis), Methodology (experimental design), Results (key findings & data).
   - Cached by paper ID, prompt version, and model revision.
   - Every summary statement links to source page/chunk.

---

## Phase 11 — Two-Paper Comparison Matrix

**User result:** Structured side-by-side comparison of two papers across key research dimensions.

1. **Comparison Dimensions:**
   - Core research question / objective
   - Methodology & datasets
   - Quantitative & qualitative findings
   - Limitations & assumptions
2. **Evidence Integrity:**
   - Each comparison cell contains explicit source citations to both papers.
   - Clear visual indicators when papers are not directly comparable or lack shared experimental basis.

---

## Phase 12 — Basic Experiment Intelligence

**User result:** Automated extraction of experimental setups, parameters, conditions, and quantitative metrics.

1. **Extraction Schema:**
   - Task, method, conditions/environment, measured metrics, raw values, units, limitations, source excerpt.
   - Reliable text and simple table parsing only.
   - Missing or unverified values default to `Not Reported` (never hallucinated).
2. **Review & Provenance:**
   - Interactive evidence drawer displaying source passage and page number for every extracted record.

---

## Phase 13 — Report Studio (DOCX Generation)

**User result:** Professional formatted research reports exported to Microsoft Word (.docx).

1. **Document Structure:**
   - Executive summary, comparative tables, verified experimental findings, citation appendix.
   - Consistent typography, headers, footers, and clean tabular layouts.
2. **Job Lifecycle:**
   - Async generation queue with status polling (`queued`, `generating`, `completed`, `failed`).
   - Secure download endpoint with workspace ownership validation.

---

## Phase 14 — Model Lab UI

**User result:** Interactive machine learning dashboard presenting the SciCite classification experiments.

1. **Metrics Visualization:**
   - Accuracy, Macro-F1, per-class F1 for `method`, `background`, `result`.
   - Interactive confusion matrix with normalized values.
   - Training & validation loss curves across epochs.
2. **Model Comparison:**
   - Side-by-side comparison of Majority Class, TF-IDF Baseline, and Fine-Tuned DistilBERT.

---

## Friday Acceptance Gate

1. Explorer summaries generate with verifiable citations.
2. Comparison matrix correctly highlights differences and non-comparable dimensions.
3. Experiment extraction preserves raw units and provenance links.
4. DOCX reports download cleanly and open in standard word processors without errors.
5. Model Lab displays measured experiment results truthfully.
