# ResearchMind AI — Six-Week Build Plan

## Target

Deliver the supplied development roadmap as a local universal analyzer in **six weeks**: PDF ingestion, traceable knowledge storage, hybrid retrieval, verified answers, summaries, comparisons, basic experiment extraction, DOCX reports, a measured SciCite Model Lab, testing, and local deployment.

This release includes extraction from reliable text/simple tables and one report format. Knowledge graphs, research-gap hypotheses, OCR, complex chart understanding, public multi-user hosting, and automatic literature discovery remain future features, as in the supplied roadmap. Local deployment and report export are required within the six weeks.

Six weeks is a target rather than a guaranteed estimate; team capacity is not yet specified. At each Friday review, update the remaining workload. Defer optional polish before weakening evidence checks or claiming unfinished work is complete.

Universal means any subject can be uploaded without a subject-specific workflow. The MVP still accepts selectable-text PDFs only; supported language/layout claims must match measured results. Existing `papers` API names remain compatible with the specifications.

This is the execution schedule for `ROADMAP.md`, incorporating the supplied roadmap's eight development stages into six weeks. No separate longer schedule applies. Preserve the technical corrections, including tokenizer-safe chunks and semantic claim verification. If a required gate is missed, record it and adjust the plan explicitly instead of silently deferring a required module.

## Roadmap-to-week mapping

| Week | Roadmap phases | Main gate |
|---|---|---|
| 1 | 0–1 | Working library and upload lifecycle |
| 2 | 2; preparation for 6 | Inspectable extraction and chunking |
| 3 | 3; baselines/training trials for 6 | Indexed retrieval and evaluation baseline |
| 4 | 4; saved final results for 6 | Grounded answers, abstention, trained classifier |
| 5 | 5, 5B; presentation for 6 | Summaries, comparison, extraction, DOCX export, Model Lab UI |
| 6 | 7 | Reliability, performance, local deployment and complete demo |

Add feature tests and accessibility checks every week. Keep brief demo evidence with commands, fixture IDs, results, defects, and decisions. The roadmap's quality gates apply to this schedule.

## Working rhythm

| Day | Focus |
|---|---|
| Monday | Confirm acceptance criteria, split tasks, and choose fixtures. |
| Tuesday–Thursday | Build one complete vertical slice and its meaningful tests. |
| Friday | Demo the flow, run checks, record results, and fix correctness blockers. |

Maintain a varied fixture set from Week 1: open-access text PDFs with different layouts and writing structures, plus corrupt, scan-like, table-heavy, duplicate, and prompt-injection PDFs.

---

## Week 1 — Foundation, app shell, and PDF library

**Outcome:** a local user can create a workspace and safely upload, view, and manage research papers.

### Build

- Create the project structure for `frontend`, `backend`, `worker`, `data`, `scripts`, and tests.
- Bootstrap React + TypeScript + Vite, FastAPI, pinned dependencies, environment templates, formatting, linting, and local development commands.
- Smoke-test the Python/PyTorch/FAISS environment and an embedding-model load early. Document native or WSL2 setup if needed; verify GPU/CPU fallback. Use the roadmap's single `data/` storage convention.
- Implement SQLite/Alembic foundation, default local-user setup, workspaces, and paper tables.
- Plan migrations and API contracts for experiments, metrics, and report jobs now; schedule their implementation for Week 5 despite older specifications labeling them P1.
- Verify the documented schema artifacts and reconcile API/schema gaps before migrations. Preserve workspace isolation even with local authentication disabled; store files outside the public web root.
- Select the generator provider and budget, verify credentials/connectivity, and document passage-sharing disclosure, timeout/retry limits, and secret handling.
- Add the Apple Modern design token system, responsive app shell, sidebar/topbar, keyboard focus states, and reduced-motion defaults.
- Create a minimal landing page and workspace dashboard with actual counts and upload/resume actions. Connect the frontend API service to centralized error responses; include empty, loading, and failed states. Login remains deferred for the local default-user release.
- Implement workspace CRUD and multi-file PDF upload with `%PDF-` validation, size limit, openability check, SHA-256 duplicate detection, and generated storage paths.
- Build the Research Library: workspace selector, drag-and-drop upload, file rejection/duplicate feedback, paper list/search, delete confirmation, and original PDF viewer/streaming.

### Friday acceptance check

- A clean checkout starts frontend and backend locally.
- A user creates a workspace, uploads a valid PDF, sees a duplicate identified, sees invalid/corrupt files rejected, opens the saved original PDF, and deletes it.

---

## Week 2 — Universal document processing and quality

**Outcome:** uploaded PDFs become inspectable, page-linked chunks ready for indexing, with honest quality indicators.

### Build

- Add persistent processing jobs and a local worker: validating → extracting → sectioning → chunking. Persist completed stages; keep the document `processing` until Week 3 completes embedding and indexing. Record failure and support retries without duplicate derived records.
- Extract page blocks and coordinates with PyMuPDF; persist page number, text count, metadata, and block locations.
- Extract title/authors/year/keywords with a source label for read vs inferred metadata.
- Flag possible scans, unreliable tables, and likely missing equations.
- Clean headers/footers and hyphenation; detect common/numbered headings, retain `unknown` for nonstandard structures, and exclude references from the default answer index.
- Add sentence-aware chunking: 200-token baseline, 20% overlap, tokenizer-count validation, and page-range provenance.
- Reject silent token truncation, including special-token overhead. The supplied 400–600-token suggestion is incompatible with MiniLM's default 256-word-piece limit; retain the corrected baseline in the roadmap.
- Build the Quality Center with processing history, status polling, errors, metadata provenance, pages, flags, and reprocessing.
- Prepare the independent SciCite experiment: verify dataset access/splits, dependencies, device memory, and a small training smoke test. This classifier does not gate document analysis.
- Select a small extraction evaluation sample with labeled fields, source passages, missing values, and unreliable tables; use it for Week 5 acceptance checks.

### Friday acceptance check

- Varied source documents process successfully.
- Extracted blocks and chunks map to the correct source pages.
- Scan-like, corrupt, and table-heavy fixtures display clear, accurate quality outcomes; the original PDF remains unchanged.

---

## Week 3 — Indexes, retrieval, and initial evaluation

**Outcome:** the system retrieves relevant evidence only from selected ready papers.

### Build

- Create versioned workspace indexes using `all-MiniLM-L6-v2`, normalized embeddings, FAISS, and BM25.
- Implement dense top-30 + sparse top-30 retrieval, reciprocal-rank fusion, selected-paper filtering, active-index lifecycle, deletion tombstones, and index rebuild handling.
- Return retrieval diagnostics: source passages, page/section locations, index/model version, scores, and timings.
- Create a hand-labeled evaluation set with answerable and deliberately unanswerable questions across varied source types.
- Implement a baseline evaluation CLI for Recall@5, MRR, nDCG@10, and retrieval latency.
- Run BM25-only, dense-only, and hybrid variants on the same evaluation set. Add a cross-encoder reranker only if measured quality benefits justify its latency/memory cost. Retrieve and inspect evidence successfully before integrating answer generation.
- Version 30–50 labeled questions over at least five varied documents, including 5–10 unanswerable cases. Separate calibration from held-out evaluation and agree on numeric acceptance targets after measuring the baseline, before final evaluation.
- Recover interrupted ingestion on restart, atomically publish completed index versions, and set `ready` only after publication. Exclude deleted documents immediately from FAISS and BM25 results; invalidate dependent caches.
- Run majority-class and TF-IDF/logistic-regression SciCite baselines and save their configurations/results.
- Run the first DistilBERT training trial with small batches, sequence length around 128, recorded seed, validation-based selection, and checkpoints. Reserve time for one failed-run recovery before Week 4 completion; keep the test split untouched.

### Friday acceptance check

- A query returns expected passages from only the chosen paper(s).
- Reference sections are absent from default retrieval.
- Baseline evaluation results are generated and saved; no result is shown as a product metric until it is measured.

---

## Week 4 — Evidence-grounded Research Assistant

**Outcome:** users receive source-backed answers with visible citations, uncertainty, and abstention.

### Build

- Implement the `POST /research/query` API, conversation/message storage, answer modes, and selected-paper constraints.
- Implement follow-up rewriting and persist the standalone query; conversation history must not override the current document selection.
- Assemble delimited, untrusted source context with stable source IDs, paper titles, sections, and pages.
- Implement paper-only, multi-paper, simple explanation, and labeled general-knowledge prompts.
- Require structured generated output; validate it and perform one repair attempt if malformed.
- Verify source IDs, numbers, units, entities, and semantic support with an evaluated NLI model or LLM judge. Save excerpts/page/block references, remove unsupported claims from rendered text, and abstain if none survive.
- Calibrate abstention on Week 3’s calibration subset using relevance/support signals, not RRF rank alone. Report held-out abstention and answerable-question refusal rates; return closest passages when evidence is insufficient.
- Enforce context-token and cost limits, handle generator failures, and ship non-streaming responses first.
- Complete DistilBERT training started in Week 3, select settings on validation data, and evaluate the chosen model on the held-out test split. Save weights, tokenizer, background/method/result labels, seed/configuration, curves, per-class metrics, confusion matrix, timings, and error examples.
- Finish model-run storage and read-only endpoints so Week 5 only needs the presentation. Define summary/comparison/extraction evidence payloads and the DOCX report template against existing API conventions before their implementation.
- Build the Assistant UI: composer, mode/paper selectors, conversation, evidence drawer, uncertainty/abstention states, citation-to-PDF navigation, and block highlighting.
- On desktop, provide the planned split PDF/chat workspace; on narrow screens, use accessible views that preserve selected page and conversation state. Treat streaming as optional after final verified responses work.

### Friday acceptance check

- Paper-only answers show only source-backed claims or explicitly say evidence is not reported.
- Unanswerable questions abstain and show closest passages.
- Citation clicks open the correct page/highlight; instructions embedded in uploaded PDFs are ignored.
- Baseline and fine-tuned classifier artifacts and measured results are saved and retrievable through the API; fixed-seed reproducibility evidence is recorded.

---

## Week 5 — Research intelligence, report export, and Model Lab

**Outcome:** users can summarize and compare documents, inspect extracted experiment evidence, export a DOCX report, and view real Model Lab results.

### Build

- Build Research Explorer for detected sections, paper metadata, and quality warnings.
- Show objectives, method, reported findings, limitations, and conclusions only where supported, with evidence on each item. Do not fill absent sections with inferred facts.
- Implement cached simple, technical, methodology, and results summaries, with source citations and cache keys tied to index/prompt/model versions.
- Implement two-document comparison with flexible user-selected dimensions.
- Add per-cell citations, missing-information states, common findings, differences, and non-comparability warnings when sources lack a defensible shared basis.
- Implement basic Experiment Intelligence: persistent extraction jobs and records for task, method, evidence/material, conditions, measure, raw value/unit, limitation, and source paper/page/passage. Use reliable text and simple tables only; optional fields follow the source, and missing values remain null/`Not Reported`.
- Verify values and context, show evidence for each record, exclude unverified values from findings, and preserve provenance/version history for user corrections. A document with no reported experiments receives an empty state, not invented records.
- Implement Report Studio: choose saved analysis, queue generation, poll status, retry errors, and download DOCX through ownership checks. Export summaries, comparison cells, verified experiment findings, references, excerpts/page numbers, and uncertainty. Mark outputs stale after source reprocessing/deletion.
- Build Model Lab UI from Week 4 results: run history, baseline comparison, configuration, learning curves, accuracy/macro-F1/per-class metrics, confusion matrix, timings, and errors. These measure citation-intent classification, not universal comprehension.

### Implementation sequence

| Order | Deliverable | Dependency |
|---|---|---|
| 1 | Explorer and cached summaries | Week 4 verified evidence pipeline |
| 2 | Two-document comparison | Per-document cited analysis |
| 3 | Basic extraction and evidence inspection | Verified structured outputs and Week 2 labeled sample |
| 4 | DOCX report generation/download | Saved summaries, comparisons, and experiment records |
| Alongside UI integration | Model Lab screens | Saved Week 4 runs; no new training required |

Build simple tables and reusable components first. Preserve the listed module outcomes; additional chart polish and export formats are optional.

### Friday acceptance check

- Summaries and comparison cells trace back to paper evidence.
- Comparisons visibly distinguish a supported contrast from an invalid comparison.
- At least one real baseline run and one fine-tuned SciCite run are saved with reproducible configuration and metrics.
- Extraction records link to passages, missing/unverified values are handled correctly, and field-level precision/recall plus numeric correctness are recorded against the labeled sample.
- A DOCX report opens and contains the selected analysis, readable references/page numbers, and uncertainty notices without unsupported added findings. Failed extraction/report jobs retry successfully; stale outputs are visibly identified.
- Model Lab renders actual saved curves, metrics, and baseline comparisons.

---

## Week 6 — Testing, optimization, local deployment, and demonstration

**Outcome:** the complete MVP is tested, measurable, accessible, and ready to demonstrate.

### Build

- Freeze feature scope and verify every Week 1–5 screen, including Experiment Intelligence, Report Studio, and Model Lab. Use this week for integration fixes and release evidence rather than first implementations of required modules.
- Add API contract, upload validation, worker/retry, retrieval, citation-verification, and end-to-end tests.
- Test varied fixtures, malformed PDFs, oversized files, duplicates, scan/table flags, and prompt-injection content.
- Add wrong-page citations, conflicting source claims, long documents, interrupted jobs, and multiple-paper workspace tests. Preserve conflicting findings with attribution instead of forcing agreement.
- Test extraction schema validation, number/unit mismatches, missing fields, DOCX citations, report download ownership, report-job recovery, and invalidation after source changes.
- Complete keyboard navigation, focus visibility, contrast checks, responsive layouts, and reduced motion in light mode. Preserve theme-ready tokens; a fully tested dark theme is optional after the core release gates pass.
- Measure and document 20-page ingestion, retrieval, generation, and model-training performance on available hardware.
- Produce setup instructions, a demo script, known limitations, and an evidence-based evaluation report.
- Package the local release with model-download/setup steps, database migrations, private-storage backup/restore instructions, and tested restart commands. Public hosting is a separate release with authentication, durable storage, quotas, and a cost plan.

### Friday acceptance check

- A first-time user completes: workspace → upload → process → ask → inspect citation → summarize → compare → inspect experiment evidence → export DOCX → inspect Model Lab.
- All P0 acceptance tests pass, documented metrics are measured, and known limitations are visible in the demo material.
- Held-out evaluation and a manual claim/citation audit are saved with counts and denominators. No known fabricated source IDs, selected-document leaks, or unsupported numeric findings remain in deterministic fixtures.
- Worker restart, failed index rebuild, generator outage, reprocessing, and deletion recovery checks pass. Re-run from documented setup on a clean environment.

---

## After the six-week MVP

| Priority | Work |
|---|---|
| P1 | Richer extraction/table support, comparable cross-document charts, additional report templates, PDF/CSV export. Basic extraction and DOCX are delivered in Week 5. |
| P1 | Retrieval Evaluation Center: reranker/embedding experiments, UI dashboards, and regression thresholds. |
| P1 | Authentication, public multi-user deployment, container packaging, and operational scaling. Local deployment and recoverable report jobs are delivered within six weeks. |
| P2 | Research-gap hypotheses, knowledge graph, external discovery, OCR, and multimodal analysis. |

### Release completion record

At the end of Week 6, record each required module as accepted or incomplete with its test evidence. Required modules are library/workspaces, processing, retrieval, assistant/citations, Explorer/summaries, comparison, basic experiment extraction, DOCX reports, Model Lab, and the local release package. Future features above are explicitly outside this release; required modules cannot be relabeled future without a scope decision.

## Start point

Begin with Week 1. The first detailed implementation plan should define the exact folder structure, chosen packages, environment variables, API/database boundaries, design-token integration, and acceptance tests before writing code.
