# ResearchMind AI — Build Roadmap

## Purpose

Build ResearchMind AI as an evidence-first **universal research-document analyzer**: users upload text-based PDFs, ask questions over selected documents, receive verified page-level evidence, and see an explicit abstention when the evidence is insufficient.

The six-week release includes the supplied roadmap's foundation, document processing, retrieval, assistant, summaries, comparison, basic experiment extraction, report export, Transformer Model Lab, testing, and local deployment. Each phase ends with a usable and testable result.

The phases describe dependencies, not separate weeks. `WEEKLY_BUILD_PLAN.md` schedules the MVP across six weeks. This is a delivery target, subject to the acceptance gates below.

## Adopted product blueprint

This is the supplied development roadmap consolidated into one six-week schedule. The original eight development stages are mapped below; they are not a separate longer schedule. Features labeled future in the supplied roadmap remain future, while its experiment-extraction and report-export development tasks are included in Week 5.

The product serves students, researchers, and professors with evidence-backed understanding, comparison, experiment analysis, and reporting. No fixed subject selection is required. Basic structured experiment intelligence and reusable reports are part of this release.

### Six-week delivery sequence

| Week | Original development stages incorporated | Required outcome |
|---|---|---|
| 1 | Foundation and project setup | Working app, workspace, upload, library, original PDF preview |
| 2 | PDF intelligence and NLP | Traceable extraction/chunks, quality flags, recoverable processing |
| 3 | RAG retrieval; early Model Lab work | Evaluated hybrid search, classifier baselines and training trial |
| 4 | Research Assistant; Model Lab completion | Verified answers, abstention, PDF citations, saved classifier results |
| 5 | Research intelligence/comparison; Model Lab presentation | Explorer, summaries, comparison, basic experiment records, DOCX export, Model Lab UI |
| 6 | Testing/performance/reliability; deployment/demo | Evaluated, restart-tested local release with complete demo and documentation |

The six weeks are an intensive delivery target, not a guarantee independent of team capacity. Review progress weekly and record unmet gates honestly; do not silently remove extraction or reporting to preserve the date. Optional animation, streaming, additional export formats, and advanced dashboards are the first scope reductions.

### Page-by-page release map

| Page / workspace area | Deliverable | Release |
|---|---|---|
| Landing | Clear product purpose, supported inputs, privacy note, entry into local workspace; advertise only working features | MVP, minimal |
| Workspace / dashboard | Workspace selector, actual paper/status counts, upload and resume actions; richer saved-activity insights later | MVP basic / P1 full |
| Library | Upload, list, search, preview, delete, duplicate handling | MVP |
| Processing / Quality Center | Stage progress, page flags, extraction history, retry | MVP basic |
| Research Explorer | Source sections, cited summaries, findings and limitations when reported | MVP |
| Research Assistant | Document selection, conversation, split PDF/chat view, evidence drawer, abstention | MVP |
| Comparison | Two-document evidence matrix, configurable dimensions, missing-information and comparability warnings | MVP; larger selections later |
| Model Lab | Saved training runs, baseline comparison, real curves and metrics; training starts from CLI | MVP |
| Research Intelligence | Basic structured experiments and verified values from text/simple tables | Week 5; gap hypotheses future |
| Report Studio | Export saved summaries, comparisons, and experiment evidence to DOCX with references and uncertainties | Week 5; PDF/CSV later |
| Knowledge Graph | Evidence-linked relationships and navigation | P2 |
| Login / register | Account protection for multi-user release; local default user initially | Before public multi-user release |

### Three separate pipelines

1. **Ingestion:** PDF → validate → extract → clean/section → chunk → embed → publish FAISS/BM25 indexes → ready.
2. **Question answering:** selected documents + question → retrieve/fuse → optional rerank → evidence gate → bounded context → generate → verify claim support → cited answer or abstention.
3. **Training:** fixed dataset splits → tokenize → train baselines/fine-tune classifier → validate → final test evaluation → saved artifacts and Model Lab results.

Uploading a PDF never retrains the generator or classifier. Citations and quality flags connect the document and answer pipelines; Model Lab is independently reproducible.

### Implementation structure and compute

| Area | Planned components |
|---|---|
| `frontend/src/` | Components, pages, layouts, features, API services, hooks; React/TypeScript/Vite, Tailwind, Motion, Recharts |
| `backend/app/` | API routers, configuration, DB models, Pydantic schemas, services, RAG, NLP, and ML inference |
| `worker/` | Process entrypoint using shared backend services and persistent job records |
| `scripts/` | Training, retrieval evaluation, diagnostics, repeatable development commands |
| `data/` | Configurable private PDF/index/model/report storage, excluded from source control |
| `tests/`, `docs/` | Fixtures, checks, setup, decisions, demo and evaluation evidence |

Use the existing `data/` storage convention rather than introducing a competing `storage/` tree. PyMuPDF handles extraction, spaCy assists sentence processing, Sentence Transformers generates embeddings, and FAISS/BM25 handle retrieval. SQLite and local artifacts suffice initially; PostgreSQL and additional queue services need measured justification.

The documented development machine is the Lenovo LOQ with RTX 2050 4 GB VRAM. Benchmark actual memory and latency; use small batches and CPU fallback, and avoid scheduling training concurrently with GPU embedding/reranking work. The college Mac is optional until its chip and performance are measured. Hosted generation is the baseline; local generation is an optional measured experiment, not a six-week dependency.

Week 1 must smoke-test the selected Python/PyTorch/FAISS environment. If native installation is blocked, document and validate a WSL2 environment or a compatible retrieval adapter before committing to a fallback. Do not silently change the index contract.

## Product guardrails

- Original PDFs are the source of truth; derived text, chunks, indexes, and generated outputs can be rebuilt.
- In paper-only mode, every factual claim needs supporting evidence or the answer must say it is not reported.
- Processing quality problems, unreliable tables, scanned pages, and missing equations are visible to the user.
- No metric, comparison, or model result is displayed unless it comes from a real stored run.
- The initial release accepts text-based PDFs. OCR, figure understanding, and automatic paper discovery are post-MVP.
- The product analyzes and organizes source material; it does not validate scientific truth or reproduce reported findings.
- Universal means no subject whitelist, domain selector requirement, or subject-specific processing route. It does not imply support for every file format, language, or document layout. Record the languages and layouts actually evaluated; label untested or unreadable content honestly.
- Existing API/table names such as `papers` and `paper_only` remain implementation identifiers for uploaded documents; universal positioning does not require renaming the contract.

## Recommended scope decisions

Use these working defaults until the project owner changes them:

| Decision | Default |
|---|---|
| Scope | Universal analysis of text-based PDFs with selectable text |
| Deployment | Single-user local demonstration |
| Authentication | Disabled behind a configuration flag; create a default local user |
| Backend job runner | One persistent local worker with database-backed jobs |
| Embedding baseline | `all-MiniLM-L6-v2`, 200-token chunks, 20% overlap |
| Retrieval baseline | FAISS + BM25 + reciprocal-rank fusion; reranker evaluated later |
| Generation | Configurable hosted LLM provider, low temperature |
| Claim verification | Source-ID and numeric checks plus semantic claim-support verification using an evaluated NLI model or LLM judge; lexical overlap alone cannot establish support |
| UI | Apple Modern soft-raised design system in `DESIGN.md`, light theme first with token-ready dark mode |

**Chunk-size correction:** do not adopt the supplied 400–600-token chunk default with `all-MiniLM-L6-v2`. Its [official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) states that input beyond 256 word pieces is truncated by default. Start near 200 tokens, measure with its tokenizer, account for special tokens, and assert no silent truncation. Larger chunks require an evaluated compatible embedder and a new index version.

## Universal analysis rules

- Use a common evidence model for every paper: title, authors, year, sections, pages, chunks, citations, claims, uncertainties, and extraction-quality flags.
- Treat every source’s entities and attributes as flexible metadata; missing fields remain `Not Reported`.
- Section detection recognizes common headings and numbered sections, but always retains `unknown` when a document uses a different structure.
- Document-grounded modes use supplied passages. General mode may add clearly labeled outside knowledge, which must not be presented as document evidence.
- Comparison is permitted only when user-selected dimensions and available evidence make it meaningful. The interface must warn when the sources do not provide a defensible shared basis for comparison.
- Evaluation fixtures and labeled questions must cover varied writing structures, layouts, and subject matter so the system is not tuned to a narrow source type.

## Delivery order

### Phase 0 — Project foundation and decisions

**Goal:** create a reproducible workspace that can be developed and tested safely.

Build:

- Monorepo layout for `frontend`, `backend`, `worker`, `data`, `scripts`, and tests.
- Python environment with pinned dependencies, React/TypeScript/Vite application, linting, formatting, and environment templates.
- SQLite database and Alembic migration setup using the P0 schema.
- Shared configuration for storage, upload size, embedding settings, LLM provider, and feature flags.
- Structured logs with request IDs and job IDs.
- Design-token foundation from `DESIGN.md`: colors, typography, radii, elevation, focus styles, responsive layout, and reduced-motion support.
- Resolve the LLM provider, credentials, cost limit, timeout/retry policy, and disclosure of retrieved passages sent externally before Week 4. Run a small connectivity check early; keep secrets and document contents out of logs.
- Reconcile the existing PRD/TRD/API/schema specifications with this roadmap in implementation plans. Verify referenced artifacts such as `schema.sql` actually exist before relying on them; record unresolved contract gaps.
- Include experiment/metric and report-job contracts in the initial migration/API planning. Their older P1 labels do not defer the basic versions now scheduled for Week 5; reconcile those labels when preparing implementation plans.

Exit criteria:

- Frontend and API start locally with one command each.
- A health endpoint, database migration, and basic UI shell work.
- The repository documents setup, environment variables, and development commands.

### Phase 1 — Workspace, library, and PDF lifecycle

**Goal:** let a local user organize and safely manage research PDFs.

Build:

- Default-user bootstrap and workspace CRUD.
- PDF upload endpoint with magic-byte validation, configurable size limit, openability check, SHA-256 duplicate detection, and server-generated storage paths.
- Paper records, paper list/search/filter, delete, original-PDF streaming with range support, and reprocess initiation.
- React library page with workspace selector, drag-and-drop upload, per-file status, duplicate/rejection feedback, and a basic PDF preview.
- Job status polling and clear failed/processing/ready states.

Exit criteria:

- A user can create a workspace, upload valid PDFs, see rejected/duplicate files correctly, list papers, view the original PDF, and delete a paper with derived-data cleanup.

### Phase 2 — Document ingestion and quality center

**Goal:** turn a valid PDF into inspectable, page-linked searchable text.

Build:

- Database-backed staged worker: validating, extracting, sectioning, chunking, embedding, indexing, ready/failed.
- PyMuPDF block extraction with page coordinates, metadata extraction, page count, and page-level records.
- Detection and surfacing of possible scans, unreliable tables, and likely missing equations.
- Header/footer cleanup, hyphen repair, flexible section detection, references identification, and sentence-aware chunking.
- Chunk token-count validation against the embedder tokenizer, page-range preservation, and idempotent retries/reprocessing.
- Quality Center UI: stage history, progress, errors, page flags, metadata provenance, and chunk counts.

Exit criteria:

- Extraction and chunking complete with correct page/block references. A document remains `processing` until Phase 3 successfully publishes its embeddings and indexes; chunk completion alone never means `ready`.
- Scanned, corrupt, and table-heavy fixture PDFs show appropriate quality outcomes.
- Reprocessing preserves the original document and resumes/rebuilds derived data correctly.

### Phase 3 — Search index and retrieval baseline

**Goal:** retrieve the strongest passages from selected ready papers.

Build:

- Per-workspace, versioned FAISS and BM25 indexes.
- L2-normalized embeddings; active-index lifecycle; tombstones and rebuild threshold after deletion.
- Dense top-30 plus BM25 top-30, reciprocal-rank fusion with `k=60`, and top-20 result set.
- Paper filters and exclusion of reference-section chunks by default.
- Retrieval diagnostics: timings, scores, selected chunks, model/index version.
- Initial labeled question set with answerable and unanswerable questions across varied source types; retrieval evaluation CLI for Recall@5, MRR, nDCG@10, and latency.

Exit criteria:

- Retrieval uses only selected ready papers and active-index chunks.
- Index changes never mix incompatible embeddings.
- The baseline evaluation produces and stores real results.
- Compare BM25-only, dense-only, and hybrid retrieval on identical questions; evaluate a cross-encoder reranker only after the baseline. Record both quality and latency, and freeze the chosen retrieval configuration before judging the generated answers.
- Restarting the worker recovers interrupted jobs without duplicating chunks or vectors. Publish rebuilt index files through an atomic active-version switch; failed rebuilds retain the last valid version.
- Deletion immediately excludes a document from both retrieval paths and invalidates derived summaries/comparisons. Old conversations visibly identify removed sources rather than showing stale evidence as current.

### Phase 4 — Evidence-grounded Research Assistant

**Goal:** deliver reliable answers with sources, uncertainty, and abstention.

Build:

- `POST /research/query` contract, conversations, follow-up question rewriting, and paper-selection rules.
- Context assembly with stable source labels, paper titles, sections, page ranges, and untrusted-paper-content delimiters.
- Answer-mode prompts: paper-only, multi-paper, simple explanation, and labeled general knowledge.
- Structured generation parsing and one repair attempt.
- Abstention gate based on calibrated retrieval scores; closest-passages response when evidence is inadequate.
- RRF ranks candidates but is not a confidence probability. Calibrate the gate using measured relevance/support signals; a high fused rank alone must not authorize an answer.
- Citation verification: supplied-source validation, support checks, verbatim numeric validation, and storage of supported citations/excerpts.
- Check semantic support, including negation, units, qualifiers, and which entity a number describes. A verbatim number or overlapping words alone cannot prove a claim. Remove failed claims from the answer itself and abstain if none survive.
- Bound context to the generator's token budget, preserve source-to-block mappings, and handle provider timeouts, malformed output, and unavailable models with recoverable errors. Ship non-streaming first; streaming is optional.
- Assistant UI with conversations, evidence drawer, uncertainty state, abstention state, and PDF jumps/highlights.

Exit criteria:

- Paper-only answers contain only verified citations or explicitly state missing evidence.
- An unanswerable test set produces abstentions at an agreed measured rate.
- Clicking a citation opens the source paper at the cited page and block.

### Phase 5 — Core research analysis

**Goal:** provide useful single-paper and two-paper workflows beyond chat.

Build:

- Cached simple, technical, methodology, and results summaries with citations.
- Research Explorer page for detected sections, metadata, summary types, and quality warnings.
- Two-document comparison across user-selected dimensions inferred from available content, with editable labels. Missing or inapplicable attributes must not be invented to fill a fixed template.
- Per-cell evidence, missing-information states, common findings, differences, and comparability warnings.

Exit criteria:

- Summary cache invalidates correctly when model, prompt, or index version changes.
- Comparison cells trace to sources and visibly distinguish non-comparable conditions from findings.

### Phase 5B — Basic Experiment Intelligence and Report Studio (Week 5)

**Goal:** inspect structured findings and export reusable, source-linked analysis in the six-week release.

Build:

- Extract flexible records from reliable text and simple tables: task, method, evidence/material, conditions, measure, raw reported value, unit, limitation, and source paper/page/passage. Optional attributes follow the document; absent values stay null and display as `Not Reported`.
- Verify numeric values and their context against the cited passage. Unsupported values remain visibly unverified and are excluded from findings. No extraction implies reproduction of an experiment.
- Add persisted extraction jobs, status/retry, extraction/model/prompt versions, and an evidence inspection table. Corrections preserve the extracted value and provenance and are labeled as user edits rather than automatically verified findings.
- Evaluate field-level precision/recall and numeric correctness on a small manually labeled set; include missing-value and unreliable-table cases. Documents with no experiments show an honest empty state.
- Generate DOCX reports from saved summaries, comparisons, and verified experiment records, using background report jobs and ownership-checked downloads. Include source references, page numbers, excerpts, uncertainty notices, and generation/version metadata.
- Invalidate or mark affected records/reports stale after reprocessing or deletion. Exports must not introduce new unsupported claims; extra PDF/CSV formats are future work.

Exit criteria:

- A user extracts findings, inspects each supporting passage, sees missing fields clearly, and compares only compatible results.
- A generated DOCX opens correctly and preserves references and uncertainty; every exported finding can be traced back to evidence.
- Extraction/report failures can be retried, and stale or deleted sources are never silently presented as current evidence.

### Phase 6 — Model Lab: SciCite experiment

**Goal:** demonstrate independently trained, reproducible deep-learning work.

Build:

- Dataset preparation for `allenai/scicite`, split validation, label distribution check, and data-card output.
- Majority-class and TF-IDF/logistic-regression baselines.
- DistilBERT fine-tuning script with fixed seed, CUDA/MPS/CPU selection, gradient accumulation, mixed precision where supported, checkpointing, and early stopping on validation macro-F1.
- Persisted model artifacts, hyperparameters, metrics, curves, confusion matrix, timings, and misclassified examples.
- Read-only Model Lab API and UI for runs and baseline-versus-fine-tuned comparison.
- Start training trials with per-device batch size 2–4 and sequence length around 128; measure truncation and memory, then tune gradient accumulation and epochs on validation results. Record label mapping for background/method/result with the tokenizer and weights.
- Optional later integration classifies extracted citation sentences. Reliable citation-context extraction is a prerequisite; the classifier does not verify claim truth or construct a citation graph by itself.

Exit criteria:

- A fixed-seed run reproduces within the agreed tolerance.
- The UI shows actual stored metrics, not placeholders.
- SciCite measures the separate citation-intent classifier, not universal document comprehension. The analyzer must work without this classifier. Select training settings on validation data and reserve the test split for final evaluation.

### Phase 7 — MVP hardening and demonstration

**Goal:** make the complete MVP dependable and presentation-ready.

Build:

- API contract tests, ownership tests, malformed/upload security tests, worker/retry tests, and end-to-end upload-to-citation tests.
- Accessibility review: keyboard paths, focus states, contrast, reduced motion, responsive re-composition, and PDF-viewer interactions.
- Fixture suite: varied open-access text PDFs, scan-like PDF, table-heavy PDF, corrupt PDF, and prompt-injection test PDF.
- Performance measurement for 20-page ingestion, retrieval, generation, and Model Lab training on the available hardware.
- Setup guide, demo script, known limitations, and a final evidence-based evaluation report.

Exit criteria:

- A first-time user can follow the demo flow: workspace → upload → process → ask → verify citation → compare → inspect experiment evidence → export DOCX → inspect model metrics.
- All P0 tests pass and every stated performance figure is measured.

## Post-MVP roadmap

### Phase 8 — Expanded extraction and exports [Later]

Extend the Week 5 foundation with richer table extraction, comparable cross-document charts, additional templates, and PDF/CSV export. Basic experiment extraction, report jobs, and DOCX export are already required within the six weeks.

### Phase 9 — Evaluation Center and operational scaling [P1]

Retrieval experiment grid, reranker and alternate-embedder evaluation, visual evaluation dashboards, PostgreSQL/Redis queue migration if measurements justify it, and Docker/CI.

### Phase 10 — Knowledge intelligence [P2]

Evidence-linked research-gap hypotheses, contradiction handling, graph nodes/edges, and React Flow exploration. All generated hypotheses remain visibly distinct from supported findings.

### Phase 11 — Broader product capabilities [Later]

Authentication rollout, multi-user deployment, DOI/arXiv discovery, OCR, figures/tables beyond best-effort text extraction, and external literature workflows.

The first release is a reproducible local demonstration: browser → React → FastAPI → worker/retrieval/database/private storage, with the configured generator as an external service. Package a setup guide, dependency/model-download instructions, migrations, backup/restore procedure, and a restart-tested demo dataset. Public release requires authentication, ownership enforcement, durable storage, recoverable jobs, quotas, and an explicit inference/hosting cost plan; no free always-on hosting is assumed.

## Planning cadence

### Quality gates and evidence

- Build a versioned set of 30–50 questions over at least five varied documents, including 5–10 unanswerable questions, gold pages/passages, numeric claims, and follow-ups. Keep calibration questions separate from held-out evaluation; do not tune on final test results.
- In Week 3, record the baseline and agree on numeric retrieval and abstention targets before evaluating the final candidate. Report answerable-question refusal rate alongside unanswerable-question abstention rate, with raw counts and denominators.
- Manually audit a fixed answer sample for claim support, citation correctness, and numeric accuracy. Deterministic fixtures must have zero fabricated source IDs, zero selected-document/workspace leaks, and zero known unsupported numeric findings. Passing fixtures is not a guarantee for all documents.
- Each weekly demo records tested commit/version, fixture IDs, commands, results, known defects, and recovery steps. Add tests with each feature; the final week consolidates them.
- Light mode is the six-week release baseline. Keep tokens theme-ready; a complete dark theme, streaming, decorative effects, and additional summary variants may be deferred before cutting evidence verification, two-document comparison, or real Model Lab results.

For each phase, create a short implementation plan before coding that includes:

1. The exact user-visible outcome.
2. Database/API/UI changes.
3. Acceptance tests and fixture data.
4. Risks, decisions, and measurable success criteria.
5. A review checkpoint before beginning the next phase.

Dependent features proceed after their prerequisite gates pass. Model Lab preparation starts in Week 2, baselines and training trials run in Week 3, and saved final results are due in Week 4. Week 5 presents them while completing research analysis and export; GPU training and ingestion are scheduled separately on the development machine.

## Recommended first implementation plan

Start with **Phase 0**, then plan **Phase 1** immediately after its foundation is verified. This minimizes rework while creating a visible upload-and-library flow early.
