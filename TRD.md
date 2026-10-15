# ResearchMind AI — Technical Requirements Document

**Version:** 0.1 (draft)
**Companion document:** PRD.md
**Status:** Planning. All values marked *default* are starting points to be tuned by evaluation, not proven results.

> **[Open]** = decision pending. **[Proposed]** = recommended, not confirmed.

---

## 1. Purpose and Scope

This document defines how ResearchMind AI will be built: architecture, components, data model, interfaces, algorithms, configuration, testing, and deployment. It covers the **MVP (P0)** in detail and outlines P1/P2 features at interface level.

## 2. System Context

```
┌────────────┐   HTTPS    ┌──────────────┐        ┌────────────────┐
│ React SPA  │──────────▶ │  FastAPI     │───────▶│ SQLite / PG    │
│ (Vite, TS) │◀────────── │  API server  │        └────────────────┘
└────────────┘            │              │───────▶ File storage (PDFs)
                          │              │───────▶ FAISS index files
                          │              │───────▶ BM25 index (per workspace)
                          │   Job queue  │───────▶ ML models (local)
                          │   (workers)  │───────▶ Hosted LLM API (external)
                          └──────────────┘
```

**Components**
| Component | Responsibility |
|---|---|
| Frontend (React SPA) | UI, PDF viewer, chat, comparison, dashboards |
| API server (FastAPI) | Request validation, auth, orchestration, citations |
| Worker | Async ingestion jobs (extract, chunk, embed, index) |
| Retrieval service | Hybrid search, fusion, reranking |
| Generation service | Prompt building, LLM call, grounding check |
| Model Lab | Training scripts, evaluation, model registry |
| Storage | Relational DB, PDF files, vector and keyword indexes |

For the MVP these run as one FastAPI process plus one background worker, not as separate microservices.

## 3. Technology Stack and Versions

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18, TypeScript, Vite | |
| Styling / motion | Tailwind CSS, Motion | |
| Data fetching | TanStack Query | polling for job status |
| PDF viewer | `react-pdf` (pdf.js) | page navigation, highlight overlay |
| Charts / graph | Recharts, React Flow | graph is P2 |
| Backend | Python 3.11, FastAPI, Uvicorn | |
| Validation | Pydantic v2 | |
| ORM / migrations | SQLAlchemy 2, Alembic | |
| Database | SQLite (dev/MVP), PostgreSQL (later) | keep SQL portable |
| Jobs | FastAPI `BackgroundTasks` for MVP; Celery/RQ + Redis later | **[Open]** |
| PDF extraction | PyMuPDF | |
| NLP | spaCy (sentence splitting), Hugging Face | |
| Embeddings | Sentence-Transformers | see 6.4 |
| Vector search | `faiss-cpu` (`IndexFlatIP`) | |
| Keyword search | `rank_bm25` | |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | optional |
| DL | PyTorch, Transformers, Datasets, scikit-learn (metrics) | |
| Reports | ReportLab (PDF), python-docx (DOCX) | |
| Generation | Hosted LLM API | provider **[Open]** |

Pin all dependency versions in `requirements.txt` / `package-lock.json`.

## 4. Repository Structure (proposed)

```
researchmind/
├── frontend/
│   └── src/ (pages, components, api, hooks, types)
├── backend/
│   └── app/
│       ├── api/          # routers
│       ├── core/         # config, security, logging
│       ├── db/           # models, migrations
│       ├── ingestion/    # extract, sections, chunk
│       ├── retrieval/    # embed, faiss, bm25, fusion, rerank
│       ├── generation/   # prompts, llm client, grounding
│       ├── analysis/     # compare, experiments, summaries
│       └── reports/
├── ml/
│   ├── scicite/          # data, train, evaluate
│   └── retrieval_eval/   # labeled questions, metrics runner
├── data/                 # pdfs, indexes, models (gitignored)
├── docs/                 # PRD.md, TRD.md
└── tests/
```

## 5. Data Model

Relational schema (SQLAlchemy / SQL). IDs are UUID strings.

```sql
users(id, email UNIQUE, password_hash, created_at)

workspaces(id, user_id → users, name, created_at)

papers(
  id, workspace_id → workspaces,
  filename, storage_path, sha256 UNIQUE PER workspace,
  title, authors_json, year, keywords_json,
  metadata_source_json,        -- per field: "pdf" | "inferred"
  page_count, size_bytes,
  status,                      -- uploaded|processing|ready|failed
  quality_json,                -- readable pages, flagged pages
  created_at
)

pages(id, paper_id → papers, page_number, char_count,
      extraction_status, has_text, flags_json)

chunks(
  id, paper_id, page_start, page_end, section,
  chunk_index, text, token_count,
  embedding_index_id → embedding_indexes
)

embedding_indexes(id, workspace_id, model_name, dim,
                  chunk_params_json, faiss_path, bm25_path,
                  version, created_at)

processing_jobs(id, paper_id, stage, status, error,
                started_at, finished_at, attempt)

conversations(id, workspace_id, title, created_at)
messages(id, conversation_id, role, mode, content, created_at)
citations(id, message_id, chunk_id, paper_id, page_number,
          excerpt, supported BOOLEAN, score)

experiments(id, paper_id, name, task, model, dataset, n_samples,
            config_json, hardware, metric_name, metric_value,
            baseline, source_page, source_chunk_id,
            extraction_version)         -- missing values stored as NULL → "Not Reported"

model_runs(id, name, base_model, dataset, hyperparams_json,
           metrics_json, artifact_path, started_at, finished_at)

reports(id, workspace_id, type, params_json, file_path, created_at)
```

**Rules**
- Original PDFs are never modified; extracted text is derived data.
- Every generated claim links through `citations` → `chunks` → `papers`.
- Deleting a paper cascades to pages, chunks, experiments, and triggers index rebuild or tombstoning (section 7.7).

## 6. Ingestion Pipeline (Pipeline A)

Executed by a worker per uploaded paper. Each stage writes a `processing_jobs` row so progress and errors are visible.

### 6.1 Upload and validation
- Accept `application/pdf` only; check magic bytes (`%PDF-`), not just the extension.
- Default max size **25 MB** (configurable). Reject encrypted PDFs that cannot be opened.
- Compute SHA-256; duplicate within a workspace returns the existing paper.
- Store as `data/pdfs/{workspace_id}/{paper_id}.pdf` with a generated filename (never use the user's filename for the path).

### 6.2 Extraction
- PyMuPDF `page.get_text("blocks")` per page, keeping block coordinates for citation highlights.
- Per page record `char_count`. A page with very few characters but with images is flagged `possible_scan`.
- Use `page.find_tables()` best-effort; if it returns nothing on a page that looks tabular, flag `table_unreliable`. **Tables are never silently treated as understood.**
- Flag pages with likely math content (high ratio of special symbols) as `equations_may_be_missing`.

### 6.3 Cleaning and sectioning
- Remove repeated headers/footers (text repeated across many pages at the same position).
- Fix hyphenated line breaks; preserve paragraph boundaries.
- Detect section headings by font size/weight and numbering patterns (`1.`, `2.1`, "Abstract", "Introduction", "Methodology", "Results", "Conclusion", "References"); fall back to `section = "unknown"`.
- Exclude the references section from the answer index by default (store it, mark `section = "references"`).

### 6.4 Chunking and embedding

**Constraint:** `all-MiniLM-L6-v2` has a 256 word-piece input limit; longer text is truncated silently.

| Parameter | Default | Notes |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` (384-d) | alternative: `bge-small-en-v1.5` (384-d, 512-token window) **[Open]** |
| Chunk size | 200 tokens (MiniLM) / up to 400 (bge-small) | measured with the model's own tokenizer |
| Overlap | 20% | |
| Boundaries | sentence-aware (spaCy); never split mid-sentence if avoidable | |
| Page tracking | each chunk stores `page_start`, `page_end` | |

- Normalize embeddings (L2) and use inner product on a `faiss.IndexFlatIP`; exact search is sufficient at this scale (tens of thousands of chunks).
- If `bge-small-en-v1.5` is chosen, apply its query instruction prefix on queries, not documents.
- Batch size for embedding: 32 on CPU, 64 on GPU (reduce if OOM).

### 6.5 Indexing
- One FAISS index and one BM25 index per workspace; stored files plus `embedding_indexes` row with model name and chunk parameters.
- Adding a paper appends vectors. Deleting a paper marks chunk IDs deleted and rebuilds the index when the deleted fraction exceeds a threshold (default 20%) or on demand.
- Changing the embedding model or chunk parameters creates a new `embedding_indexes` version and requires re-embedding; never mix vectors from different models in one index.

### 6.6 Job states and retries
`uploaded → validating → extracting → chunking → embedding → indexing → ready`, or `failed` at any stage with the error stored. Each stage is idempotent; retry up to 2 times automatically, then manual reprocess from the UI.

## 7. Question-Answering Pipeline (Pipeline B)

### 7.1 Request
`POST /api/research/query` with workspace, selected paper IDs, question, answer mode, optional conversation ID.

### 7.2 Query processing
- Restrict retrieval to chunks of the selected papers (filter by paper ID before or after search; with exact search, filter after retrieving top-N with N large enough, or search a per-selection sub-index).
- For follow-ups, rewrite the question into a standalone query using the last few turns (small LLM call or rule-based), and log both versions.

### 7.3 Hybrid retrieval
1. Dense: embed query → FAISS top **N=30**.
2. Sparse: BM25 over tokenized chunks → top **N=30**.
3. Fuse with **Reciprocal Rank Fusion**: `score(d) = Σ 1 / (k + rank_i(d))`, `k = 60`.
4. Keep top **20** fused candidates.

### 7.4 Reranking (optional, evaluated)
- Cross-encoder scores (query, chunk) pairs for the 20 candidates; keep top **K=6** for generation (default; tune).
- Disabled by default on CPU-only runs if latency exceeds budget; the Retrieval Evaluation Center decides.

### 7.5 Abstention gate
Before calling the LLM, if the best reranker score (or best fused score when no reranker) is below a tuned threshold, return an "insufficient evidence" response with the closest passages shown. The threshold is calibrated on the labeled question set, including deliberately unanswerable questions.

### 7.6 Prompt assembly and generation
- Context = top-K chunks, each labeled `[S1]…[Sk]` with paper title, page range, and section.
- System prompt requirements (by answer mode):
  - **Paper-only:** use only the supplied sources; every factual claim carries a `[S#]` marker; if unsupported, say "Not reported in the selected papers."
  - **Multi-paper:** attribute each claim to its paper; flag non-comparable conditions.
  - **Simple explanation:** same grounding, simpler language.
  - **General AI:** may use outside knowledge, but outside-knowledge sentences are explicitly labeled "General knowledge (not from your papers)."
- Uploaded text is delimited and declared as untrusted data; instructions inside it must be ignored.
- Ask for structured output (JSON): `answer_markdown`, `claims[] {text, source_ids[]}`, `uncertainties[]`. Validate with Pydantic; one repair retry on invalid JSON.
- Temperature low (default 0.1–0.2); max output tokens configured per mode.

### 7.7 Grounding and citation verification
For each claim:
1. Confirm every cited `[S#]` exists in the supplied context (reject fabricated IDs).
2. Check support: lexical overlap of key numbers and terms **and** an entailment check (NLI cross-encoder or LLM-as-judge) between the chunk text and the claim. **[Open]** which method.
3. Claims failing support are removed or marked "unverified" in the UI, and the failure is logged.
4. Numeric values (e.g., metrics) must appear verbatim in the cited chunk, else they are not displayed as findings.

Persist surviving citations to `citations` with `supported` flag and score, including page number and excerpt for the PDF viewer.

### 7.8 Response
Return answer, citations, uncertainties, mode, retrieval debug info (latency per stage, top scores) for the Quality Center.

## 8. Analysis Features

### 8.1 Summaries (P0 basic)
- Per-section extraction with the generator, using section-filtered chunks; summary types map to different prompt templates.
- Long papers use map-reduce summarization: summarize sections, then combine. Cache results keyed by `(paper_id, summary_type, index_version, prompt_version)`.

### 8.2 Paper comparison (P0, two papers)
- User selects papers and dimensions.
- For each paper × dimension, retrieve evidence restricted to that paper, generate a cell with citations, then assemble the matrix.
- **Comparability check:** compare extracted dataset, metric, and hardware fields; if they differ, attach a warning to the relevant cell.

### 8.3 Experiment extraction (P1)
- Targeted retrieval over `results`, `experiments`, and table-like chunks, then LLM extraction into a fixed JSON schema (name, task, model, dataset, metric, value, baseline, page).
- Missing fields remain `null` and render as **Not Reported**.
- Numeric values are verified against the source chunk text (7.7 rule 4).
- Evaluate against a hand-labeled sample (field-level precision/recall).

### 8.4 Research gaps and knowledge graph (P2)
- Gap candidates are generated from limitation statements and experiment records, always tagged "generated hypothesis" with linked evidence.
- Graph is built from `experiments` plus entity extraction; stored as `nodes` / `edges` tables; rendered in React Flow. No graph database.

## 9. Model Lab — SciCite Fine-Tuning

| Item | Specification |
|---|---|
| Dataset | SciCite via Hugging Face Datasets (`allenai/scicite`) |
| Task | 3-class citation intent: background, method, result |
| Model | `distilbert-base-uncased` + classification head |
| Splits | Dataset's own train / validation / test; test used once at the end |
| Max sequence length | 128 (check truncation rate on the data) |
| Batch size | 16 target via per-device batch 4 × gradient accumulation 4 (reduce to 2 × 8 if OOM) |
| Precision | Mixed precision (fp16) on CUDA |
| Optimizer | AdamW, lr 2e-5 to 5e-5, weight decay 0.01 |
| Schedule | Linear warmup (~6%) then decay |
| Epochs | 3–4, early stopping on validation macro-F1 |
| Seeds | Fixed seed recorded in `model_runs`; target 3 seeds for mean ± std if time allows |
| Class imbalance | Check label distribution; use class weights if skewed |

**Outputs per run:** weights, tokenizer, config, learning curves (train/val loss), accuracy, macro-F1, per-class precision/recall/F1, confusion matrix, training time, inference latency, misclassified examples for error analysis.

**Baseline:** (a) majority class, (b) TF-IDF + logistic regression, and optionally (c) the zero-shot or frozen-embedding model, so "fine-tuned vs. baseline" is a real comparison.

**Integration:** The classifier is loaded by the backend to tag citation sentences inside papers; it is separate from the generative LLM. If the Mac is used, device selection is `cuda` → `mps` → `cpu`, and the same script is benchmarked on both machines before choosing the training machine.

## 10. Retrieval Evaluation Harness

- **Labeled set:** 30–50 questions across 3–5 papers, each with the gold chunk(s)/page(s); include 5–10 unanswerable questions.
- **Metrics:** Recall@5, MRR, nDCG@10, latency per stage, citation correctness (is the cited chunk the gold one), faithfulness (claim support rate), abstention accuracy on unanswerable questions.
- **Experiment grid:** dense only / BM25 only / hybrid; with and without reranker; chunk size {128, 200, 300, 400}; embedding model {MiniLM, bge-small}.
- Results stored as JSON per run and displayed in the UI; no figure is shown unless produced by this harness.

## 11. API Specification (MVP)

Base path `/api`. JSON unless noted. Errors use a consistent envelope:
`{"error": {"code": "string", "message": "string", "details": {}}}`.

### 11.1 Papers
**`POST /papers`** (multipart: `files[]`, `workspace_id`) → `202`
```json
{ "papers": [ { "id": "…", "filename": "…", "status": "processing" } ],
  "duplicates": [ { "filename": "…", "existing_id": "…" } ] }
```
**`GET /papers?workspace_id=`** → list with metadata and status
**`GET /papers/{id}/status`** → `{status, stage, progress, error}`
**`GET /papers/{id}/pages`** → page list with flags
**`GET /papers/{id}/file`** → PDF stream (authorization-checked)
**`DELETE /papers/{id}`**, **`POST /papers/{id}/reprocess`**

### 11.2 Research
**`POST /research/query`**
```json
// request
{ "workspace_id": "…", "paper_ids": ["…"], "question": "…",
  "mode": "paper_only", "conversation_id": null }
// response
{ "message_id": "…",
  "answer_markdown": "…",
  "citations": [ { "paper_id": "…", "page": 7, "excerpt": "…", "supported": true } ],
  "uncertainties": ["…"],
  "abstained": false,
  "timings_ms": { "retrieve": 0, "rerank": 0, "generate": 0, "verify": 0 } }
```
Streaming (SSE) for the answer text is an optional enhancement; citations arrive after verification.

### 11.3 Analysis
**`POST /compare`** `{paper_ids[], dimensions[]}` → matrix with per-cell citations and warnings
**`POST /papers/{id}/summary`** `{type}` → summary with citations
**`GET /workspaces/{id}/insights`**

### 11.4 Model Lab and reports
**`GET /model-runs`**, **`GET /model-runs/{id}`**
**`POST /reports`** `{type, params}` → `202` with report ID; **`GET /reports/{id}/download`**

### 11.5 Auth (if enabled)
`POST /auth/register`, `/auth/login`, `/auth/logout`. Short-lived access token plus refresh token in an HTTP-only cookie.

## 12. Frontend Requirements

- Route map: `/` landing, `/login`, `/app` dashboard, `/app/library`, `/app/papers/:id`, `/app/assistant`, `/app/compare`, `/app/model-lab`, `/app/reports`.
- Upload: drag-and-drop, per-file progress, status polling every 2 s while processing.
- PDF viewer: citation click navigates to the page and highlights the cited block (use stored block coordinates).
- Evidence drawer: shows excerpt, page, section, and `supported` status for each citation.
- UI states for: processing, failed, abstained answer, low-quality extraction warning, non-comparable comparison warning.
- Accessibility: keyboard navigation, sufficient contrast, ARIA labels on interactive elements.
- Visual direction per PRD section 13; design tokens defined in Tailwind config.

## 13. Non-Functional Requirements

| Area | Requirement | Type |
|---|---|---|
| Upload responsiveness | API returns before processing finishes | Hard |
| Ingestion time | Measure per-stage; report time for a 20-page paper on the dev laptop | Measured, no promise |
| Query latency | Measure retrieval and generation separately; target interactive (a few seconds to first token) | Target |
| Capacity | 20–50 papers per workspace | Pilot target |
| Memory | Embedding and training must fit in 4 GB VRAM; fall back to CPU or smaller batch | Hard |
| Reliability | Failed jobs recoverable without re-upload | Hard |
| Observability | Structured logs with request ID, job ID, stage timings | Hard |
| Reproducibility | Pinned dependencies, recorded seeds, saved configs for every model run | Hard |

## 14. Security and Privacy

- **Access control:** every paper, chunk, conversation, and report query is filtered by the owner's workspace; verify ownership in the data layer, not only in the UI.
- **Uploads:** magic-byte check, size limit, generated storage names, no path traversal, files outside the web root, optional malware scan.
- **Passwords:** Argon2 or bcrypt; no plaintext logging.
- **Secrets:** API keys in environment variables, never in the repo or frontend bundle.
- **Prompt injection:** uploaded text is delimited and treated as data; the model never receives instructions from paper content as authority; outputs are verified against sources (7.7).
- **External LLM:** paper text sent to a hosted API leaves the machine; disclose this to users and document the provider's data-retention terms. **[Open]**
- **Rate limiting:** per-user limits on upload and query endpoints.
- **Deletion:** removes the PDF, chunks, vectors (or tombstones), and derived analysis.
- **Licensing:** the app stores uploaded papers privately per user and does not redistribute them.
- **CORS:** restrict to the frontend origin.

## 15. Testing Strategy

| Level | What | Tools |
|---|---|---|
| Unit | Chunker (size, overlap, page tracking), fusion, validators, citation checker | pytest |
| Integration | Upload → process → query on fixture PDFs; deletion cleanup; reprocess | pytest + test DB |
| ML regression | Retrieval metrics on labeled set must not drop below a recorded baseline | custom harness |
| Classifier | Metric thresholds and reproducibility check with fixed seed | pytest + script |
| API | Contract and error-envelope tests; auth and ownership tests | pytest, httpx |
| Frontend | Component tests; end-to-end upload → ask → click citation | Vitest, Playwright |
| Security | Unauthorized access, oversized/malformed files, injected-instruction PDF | pytest |
| Adversarial answers | Unanswerable questions must abstain; fabricated-citation test | harness |

Fixture set: a few open-access papers (check licenses), one scanned PDF, one table-heavy PDF, one corrupt file, one PDF containing an injected instruction.

## 16. Deployment

- **MVP:** local run for demonstration. `uvicorn` backend, `vite` dev or built static frontend, SQLite, local file storage.
- **Later:** Docker Compose (frontend, API, worker, Postgres, Redis); object storage for PDFs; CI running tests and linting on every push. Hosting platform **[Open]**.
- Configuration through environment variables: `DATABASE_URL`, `STORAGE_DIR`, `EMBEDDING_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `LLM_PROVIDER`, `LLM_API_KEY`, `MAX_UPLOAD_MB`, `USE_RERANKER`, `ABSTAIN_THRESHOLD`.

## 17. Compute Allocation

| Task | Device |
|---|---|
| PDF extraction, chunking, BM25, FAISS search | CPU |
| MiniLM / bge-small embeddings | GPU (RTX 2050) when available, else CPU |
| Cross-encoder reranking | CPU or GPU, chosen by latency measurement |
| DistilBERT fine-tuning | GPU with the settings in section 9; compare against the college Mac after identifying its chip |
| Answer generation | Hosted LLM API; a small quantized local model is an optional experiment |

## 18. Implementation Plan (technical milestones)

| Milestone | Deliverable | Exit test |
|---|---|---|
| M1 | Schema, upload endpoint, storage, library UI | Upload, list, delete, duplicate detection tests pass |
| M2 | Extraction, sections, chunker with page tracking | Chunk page references verified on fixture PDFs |
| M3 | Embeddings, FAISS, BM25, RRF | Recall@5 measured on a first labeled set |
| M4 | Query endpoint, prompt, citation verification, abstention | Unanswerable questions abstain; no fabricated citations in tests |
| M5 | PDF viewer with citation highlighting, chat UI | End-to-end demo flow |
| M6 | SciCite training pipeline and Model Lab UI (parallel with M2–M5) | Metrics reproduce from a fixed seed |
| M7 | Summaries and two-paper comparison | Cells carry citations and comparability warnings |
| M8 | Retrieval evaluation harness and UI | Grid of experiments runs from one command |
| M9+ | Experiment extraction, reports, advanced features | Per PRD priorities |

## 19. Technical Risks

| Risk | Mitigation |
|---|---|
| PDF layout breaks section and table detection | Best-effort parsing, quality flags, fixtures; no silent failure |
| Embedding truncation | Chunk sizes tied to the model's token limit; unit test asserts chunk token counts |
| Hallucinated numbers | Verbatim numeric verification (7.7); abstention |
| NLI/judge verifier adds latency or cost | Make verification tiered: cheap checks always, entailment on key claims |
| FAISS/vector index drifts from the DB after deletes | Tombstones plus periodic rebuild; consistency check job |
| Background tasks lost on restart | Persist job state; resume on startup; move to a real queue if needed |
| 4 GB VRAM limits | Small batches, gradient accumulation, fp16, shorter sequences, CPU fallback |
| LLM provider outage or cost | Cache, retries with backoff, provider abstraction layer, budget cap |
| Evaluation set too small to be convincing | Report confidence caveats; expand set as time allows |

## 20. Open Technical Decisions

| # | Decision |
|---|---|
| 1 | Embedding model: MiniLM (short chunks) vs. bge-small (longer chunks) |
| 2 | Job runner: `BackgroundTasks` vs. Celery/RQ |
| 3 | Claim verification method: NLI cross-encoder vs. LLM judge |
| 4 | LLM provider, budget, data-retention terms |
| 5 | Whether to use LangChain or a thin custom RAG layer |
| 6 | Reranker enabled by default or not (decided by evaluation) |
| 7 | Table extraction approach beyond PyMuPDF (e.g., a dedicated table tool) |
| 8 | Authentication scope for the demo |
| 9 | Hosting target and CI setup |
| 10 | Second DL model (reranker or evidence classifier) beyond SciCite |
