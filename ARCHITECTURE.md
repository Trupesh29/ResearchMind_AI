# ARCHITECTURE.md — ResearchMind AI

**System Design: Components, Data Flows, Decisions & Trade-offs**
Companion to `PRD.md`, `TRD.md`, `DATABASE_SCHEMA.md`, and `API_SPEC.md` · Status: planning (v0.1)

**Priority tags:** **[P0]** MVP · **[P1]** after MVP · **[P2]** advanced. Performance figures here are design targets to be measured, not demonstrated results.

---

## 1. Purpose & Scope

This document explains **how the system is put together and why**: the major components, how data moves through them, where state lives, and which design decisions were made. It does not repeat field-level detail; use `DATABASE_SCHEMA.md` for tables and `API_SPEC.md` for endpoints.

---

## 2. Architectural Principles

| # | Principle | What it means in practice |
|---|---|---|
| 1 | **Evidence first** | An answer is only as strong as its retrieved sources. Every claim is traceable to paper, page, and passage. |
| 2 | **Abstain over guess** | If evidence is thin, the system says so and shows the closest passages instead of inventing an answer. |
| 3 | **Never silent about quality** | Scanned pages, unreliable tables, and missing equations are flagged and recorded, not treated as understood. |
| 4 | **Reproducible and inspectable** | Index versions, model versions, prompt versions, seeds, and timings are stored so a result can be explained or rerun. |
| 5 | **Derived data is rebuildable** | Original PDFs are the source of truth. Chunks, vectors, summaries, and experiments can be regenerated. |
| 6 | **Simple first** | One backend process and one worker for the MVP. Add queues, containers, and services only when measurements demand them. |
| 7 | **Honest metrics** | Every number shown in the UI comes from a stored, real evaluation or training run. |
| 8 | **Untrusted content stays data** | Text from uploaded papers is never allowed to act as instructions to the model. |

---

## 3. System Context

```
                        ┌─────────────────────────────────────────┐
                        │                  User                    │
                        │ (student / researcher / professor)       │
                        └───────────────────┬─────────────────────┘
                                            │ browser
                                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       ResearchMind AI                                       │
│                                                                              │
│   ┌───────────────┐    REST/SSE     ┌────────────────────────────────────┐ │
│   │ React SPA     │◄───────────────►│ FastAPI application                 │ │
│   │ (Vite, TS)    │                 │  • API routers + auth                │ │
│   └───────────────┘                 │  • Retrieval + generation services   │ │
│                                     │  • Analysis (summaries, compare…)    │ │
│                                     └───────┬──────────────┬──────────────┘ │
│                                             │              │ jobs            │
│                                             │              ▼                 │
│                                             │     ┌──────────────────┐       │
│                                             │     │ Background worker │       │
│                                             │     │ ingestion / eval  │       │
│                                             │     └────────┬─────────┘       │
│                                             ▼              ▼                 │
│                        ┌──────────────────────────────────────────────────┐ │
│                        │ Storage: relational DB · PDFs · FAISS · BM25 ·   │ │
│                        │          model artifacts · reports               │ │
│                        └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────┬─────────────────────────────────┘
                                           │ HTTPS (only external dependency)
                                           ▼
                                 ┌──────────────────┐
                                 │ Hosted LLM API    │
                                 │ (provider: open)  │
                                 └──────────────────┘
```

**External boundary:** The only data that leaves the machine is the question plus the retrieved passages sent to the hosted LLM. Everything else, including the PDFs, vectors, and the trained classifier, stays local. This must be disclosed to users.

---

## 4. Logical Layers

```
┌───────────────────────────────────────────────────────────────────┐
│ L5  Presentation     React pages, PDF viewer, chat, matrix, charts  │
├───────────────────────────────────────────────────────────────────┤
│ L4  API              FastAPI routers · auth · validation · errors   │
├───────────────────────────────────────────────────────────────────┤
│ L3  Intelligence     Q&A · summaries · comparison · experiments ·   │
│                      gaps · graph · report builder                  │
├───────────────────────────────────────────────────────────────────┤
│ L2  Knowledge        ingestion · chunking · embeddings · FAISS ·    │
│                      BM25 · reranker · citation verifier            │
├───────────────────────────────────────────────────────────────────┤
│ L1  Persistence      SQLite/PostgreSQL · file storage · indexes     │
├───────────────────────────────────────────────────────────────────┤
│ L0  ML Platform      Model Lab: SciCite fine-tuning, baselines,     │
│                      retrieval evaluation harness (offline)         │
└───────────────────────────────────────────────────────────────────┘
```

These map to the four product layers in the PRD: **Research Knowledge** (L1–L2), **Research Understanding** (L2–L3 Q&A and summaries), **Research Intelligence** (L3 comparison, experiments, gaps, graph, reports), and **AI Research and Evaluation** (L0).

**Dependency rule:** a layer calls only the layer directly beneath it. Routers never touch FAISS or the LLM directly; they call services.

---

## 5. Component Breakdown

### 5.1 Frontend (React SPA) [P0]

| Concern | Choice |
|---|---|
| Framework | React 18 + TypeScript + Vite |
| Server state | TanStack Query (caching, polling job status) |
| Styling | Tailwind CSS with design tokens |
| PDF display | `react-pdf` (pdf.js) with a highlight overlay from stored block coordinates |
| Charts / graph | Recharts (metrics), React Flow (knowledge graph, P2) |
| Auth state | Access token in memory; refresh via HTTP-only cookie |

Key UI behaviors that shape the architecture:
- Upload shows per-file progress and polls `/papers/{id}/status` every 2 seconds.
- A citation click calls the PDF viewer with `(paper_id, page_number, block ids)`.
- Provisional streamed text is replaced by the verified `final` answer, so an unverified claim never stays visible.
- Distinct UI states: processing, failed, abstained, low-quality extraction, non-comparable results.

### 5.2 API server (FastAPI) [P0]

Responsibilities: request validation (Pydantic), authentication and ownership checks, rate limiting, error envelope, orchestration of services, SSE streaming. It owns **no ML logic**; it calls services.

Cross-cutting middleware: request ID, structured logging, CORS (frontend origin only), exception-to-envelope mapping, rate limiter.

### 5.3 Ingestion service and worker [P0]

Runs the eight-stage pipeline in section 7. For the MVP the worker is an in-process background task with job state persisted in `processing_jobs`, so a restart can resume. If throughput or reliability demands it, swap in Celery or RQ with Redis. The service interface stays the same.

### 5.4 Retrieval service [P0]

Hybrid retrieval: dense (FAISS) + sparse (BM25), merged with Reciprocal Rank Fusion, optional cross-encoder reranking, and an abstention gate. Details in section 8.

### 5.5 Generation service [P0]

Builds the prompt from retrieved sources and the selected answer mode, calls the hosted LLM through a **provider-abstraction layer** (one interface, swappable provider), parses structured output, and hands claims to the verifier. Includes retry with backoff, timeouts, and response caching keyed by `(question, source ids, index version, prompt version, model)`.

### 5.6 Citation verifier [P0]

Checks that every cited source was actually supplied, that numbers appear verbatim in the cited passage, and that claims are entailed by their sources. Details in section 9.

### 5.7 Analysis services [P0 basic, P1–P2 later]

| Service | Approach |
|---|---|
| Summaries [P0] | Section-filtered retrieval, then map-reduce summarization for long papers; cached by `(paper, type, index, prompt, model)` |
| Comparison [P0] | Per paper per dimension: restricted retrieval, cited cell generation; a comparability check across datasets, metrics, and hardware adds warnings |
| Experiment extraction [P1] | Targeted retrieval over results chunks, structured JSON extraction, verbatim verification of numbers |
| Research gaps [P2] | Built from limitation statements and experiment records; always labeled as hypotheses |
| Knowledge graph [P2] | Nodes and edges stored in relational tables; no graph database |
| Report builder [P1] | Assembles stored analysis and citations into PDF (ReportLab), DOCX (python-docx), or CSV |

### 5.8 Model Lab (offline ML platform) [P0]

An offline workflow, not part of the request path. It fine-tunes DistilBERT on SciCite, trains baselines, evaluates, and writes results into `model_runs`. Details in section 11.

### 5.9 Persistence [P0]

| Store | Holds | Notes |
|---|---|---|
| SQLite (dev) / PostgreSQL (later) | All relational data in `DATABASE_SCHEMA.md` | Foreign keys on; SQLAlchemy 2 + Alembic |
| File storage | Original PDFs, model artifacts, reports | Server-generated names; outside the web root |
| FAISS files | One index per workspace and version | `IndexFlatIP` on normalized vectors |
| BM25 files | One keyword index per workspace and version | Rebuilt with the vector index |

---

## 6. Process & Deployment View

### 6.1 MVP (local demonstration) [P0]

```
┌────────────── one machine (Lenovo LOQ) ──────────────┐
│  Browser ──► Vite dev/static ──► FastAPI (uvicorn)    │
│                                   │      │            │
│                                   │      └─ background worker (same process)
│                                   ▼                   │
│                       SQLite file · ./data/ folders   │
│                                   │                   │
│                                   └──► Hosted LLM API │
└───────────────────────────────────────────────────────┘
```

One process to start, no containers required. Embedding models load once at startup so queries do not pay load time.

### 6.2 Later deployment [P1+]

```
Reverse proxy (TLS)
   ├─► Static frontend
   └─► API container(s) ──► PostgreSQL
            │            └─► Object storage (PDFs, reports, artifacts)
            └─► Redis ──► Worker container(s) ──► GPU/CPU embedding
```

Triggers for moving from the MVP to this layout: more than one concurrent user, ingestion blocking queries, or the need for durable job queues. Hosting provider is an open decision.

---

## 7. Data Flow A — Document Ingestion

```
Upload (React)
   │ multipart
   ▼
POST /api/papers ── validate: magic bytes, size, openable, SHA-256 duplicate
   │ 202 + paper ids
   ▼
processing job (worker), each stage recorded in processing_jobs
   │
   1. validating   → reject corrupt/encrypted
   2. extracting   → PyMuPDF blocks per page, coordinates saved, page flags set
   3. sectioning   → remove headers/footers, fix hyphenation, detect headings
   4. chunking     → sentence-aware, ~200 tokens, 20% overlap (MiniLM), page range per chunk
   5. embedding    → Sentence-Transformer, L2-normalized vectors
   6. indexing     → append to FAISS and BM25; map faiss_id ↔ chunks row
   7. persisting   → metadata, quality summary, index version
   8. ready        → paper.status = 'ready'
```

**Failure handling:** each stage is idempotent. A failed stage retries up to twice automatically, then waits for a manual reprocess. The original PDF is never changed, and partial chunks from a failed run are removed before retry.

**Quality surface:** flagged pages (`possible_scan`, `table_unreliable`, `equations_may_be_missing`) are stored and shown in the Quality Center. They also lower the confidence of answers that rely on those pages.

**Index lifecycle:** adding a paper appends vectors to the active index. Deleting marks chunks as tombstoned and rebuilds when about 20% are deleted or on demand. Changing the embedding model or chunking creates a **new index version** and re-embeds; versions are never mixed.

---

## 8. Data Flow B — Question Answering

```
POST /api/research/query
   │
   ├─ 1. authorize: workspace → papers all ready, active index exists
   ├─ 2. rewrite follow-up into a standalone query (when conversation_id given)
   │
   ├─ 3a. DENSE   embed query → FAISS top 30     ┐
   ├─ 3b. SPARSE  BM25 top 30                    ├─ filter to selected papers, skip tombstones
   │                                             ┘
   ├─ 4. FUSE     Reciprocal Rank Fusion (k = 60) → top 20
   ├─ 5. RERANK   cross-encoder → top K (default 6)     [optional, decided by evaluation]
   │
   ├─ 6. GATE     best score below threshold?  ──► return abstention + closest passages
   │
   ├─ 7. PROMPT   sources labeled [S1…Sk] with paper, pages, section;
   │               mode-specific instructions; paper text declared untrusted
   ├─ 8. GENERATE hosted LLM → structured JSON: answer, claims[], uncertainties[]
   ├─ 9. VERIFY   citation ids exist · numbers verbatim · claims entailed by sources
   │
   └─10. RESPOND  answer + verified citations + uncertainties + timings
                  (store message, message_papers, citations)
```

**Where latency goes:** embedding the query and FAISS search are fast on a small corpus; reranking and generation dominate. Timings per stage are returned and stored so bottlenecks are measured, not guessed.

**Why hybrid:** dense search finds meaning ("higher data transfer rate" for "bandwidth"); BM25 finds exact terms, model names, and numbers that embeddings blur. RRF merges them without needing comparable scores.

**Abstention gate:** the threshold is calibrated on the labeled evaluation set, including questions that cannot be answered. A gate set by guess would either refuse good questions or accept bad ones.

**Answer modes** change the prompt and verification strictness, not the retrieval:

| Mode | Prompt behavior | Verification |
|---|---|---|
| `paper_only` | Only supplied sources; "Not reported" when unsupported | Strict: unsupported claims removed or marked |
| `multi_paper` | Attribute every claim to its paper; flag non-comparable conditions | Strict, per paper |
| `simple` | Same grounding in plain language | Strict |
| `general` | May use outside knowledge, labeled "General knowledge (not from your papers)" | Only paper-attributed claims verified |

---

## 9. Grounding and Verification Architecture

This subsystem is the core of the product's trust model.

```
LLM output (claims with [S#] ids)
   │
   ├─ Check 1  every [S#] exists in the supplied context      → reject fabricated ids
   ├─ Check 2  every number/metric appears verbatim in the     → else not shown as a finding
   │           cited passage
   ├─ Check 3  claim entailed by cited text                    → NLI cross-encoder or LLM judge [open]
   │
   ├─ pass  → citation stored with supported = true, score
   └─ fail  → claim removed or shown as "unverified"; failure logged for evaluation
```

Design choices:
- **Tiered cost:** checks 1 and 2 are cheap and always run. Check 3 runs on key claims, or all claims if latency allows.
- **Stored excerpt:** a citation keeps its own text and page, so it survives reindexing.
- **Prompt injection:** the prompt delimits paper text, states it is untrusted data, and the verifier never executes instructions found in it.
- **Honest residual risk:** verification reduces unsupported claims but cannot guarantee zero. Faithfulness is therefore a measured metric in the evaluation harness.

---

## 10. State & Consistency Model

| State | Source of truth | Derived from it |
|---|---|---|
| Original PDF | File storage | everything below |
| Pages, chunks, metadata | Relational DB | FAISS and BM25 files |
| Vectors | FAISS file (id mapped through `chunks.faiss_id`) | rebuilt from `chunks.text` |
| Answers and citations | Relational DB | UI views |
| Summaries, comparisons | Relational DB (cache) | regenerated when keys change |
| Model artifacts | File storage + `model_runs` row | — |

**Consistency risk:** the database and the FAISS/BM25 files are separate stores, so a crash can leave them out of step. Mitigations: write the database rows and the index in one job with a status flag; mark the index `building` until complete; run a consistency check that compares chunk count with index size and rebuilds on mismatch. If PostgreSQL arrives later, keyword search can move to its full-text engine so deletes become transactional.

**Concurrency:** SQLite allows one writer at a time; enable WAL mode. Ingestion writes are batched, and queries are read-only, so contention is low for a single user. Concurrent ingestion into the same index is serialized per workspace.

---

## 11. Model Lab Architecture [P0]

```
allenai/scicite  ──►  tokenize (max length 128)
                        │
         ┌──────────────┼───────────────────────┐
         ▼              ▼                       ▼
   baselines        DistilBERT fine-tune     (optional) frozen-embedding probe
   • majority       • batch 4 × accum 4
   • TF-IDF + LR    • fp16, AdamW, warmup
                    • early stop on val macro-F1
         │              │
         └──────┬───────┘
                ▼
        evaluate on held-out test split (used once)
                ▼
   weights · tokenizer · config · metrics → data/models/{run_id}/
                ▼
   model_runs row (hyperparams, metrics, seed, device, status)
                ▼
   API (read-only) ──► Model Lab UI
   Backend loads best run to tag citation sentences in papers
```

Decisions:
- **Training runs from the command line**, not the web UI. This keeps the web app simple and makes runs reproducible from a script and seed.
- **Device selection** is `cuda` → `mps` → `cpu`. The same script is benchmarked on the RTX 2050 and the college Mac before choosing the main training machine.
- **Separation:** the classifier is independent of the generative LLM. Uploading a paper never triggers retraining.
- **Baselines are stored as runs** (`run_type = baseline`), so "fine-tuned vs. baseline" is a real stored comparison.

### Retrieval evaluation harness [P1]

A labeled set (30–50 questions across 3–5 papers, including unanswerable ones) is run through a grid of configurations: dense / BM25 / hybrid, with and without reranker, several chunk sizes, and two embedding models. Output is Recall@K, MRR, nDCG, latency, citation correctness, faithfulness, and abstention accuracy, stored in `eval_runs`. The abstention threshold and the default reranker setting are chosen from these results.

---

## 12. Security Architecture

| Threat | Control |
|---|---|
| Unauthorized access to another user's papers | Every query resolves to `workspaces.user_id`; foreign resources return 404 |
| Malicious or malformed uploads | Magic-byte check, size limit, openability check, generated filenames, no path traversal, files outside web root |
| Credential theft | Argon2/bcrypt hashing, short-lived access tokens, refresh token in HTTP-only cookie, generic login errors, login rate limit |
| Secret leakage | Keys in environment variables only; never in the repo or the frontend bundle |
| Prompt injection via PDFs | Paper text delimited and labeled untrusted; outputs verified against sources; verifier never follows instructions in context |
| XSS from extracted text | Render excerpts as plain text or sanitized markdown, never raw HTML |
| Abuse and cost overrun | Per-user rate limits; LLM budget cap; response caching |
| Data exposure to a third party | Only the question and retrieved passages go to the LLM; disclosed to users; provider retention terms recorded |
| Data retention | Deleting a paper removes the PDF, chunks, derived analysis, and vectors (tombstone plus rebuild) |
| Licensing | Papers stay private per user; no redistribution |

---

## 13. Observability & Operations

- **Structured logs** with request ID, job ID, workspace ID, and stage timings. No paper text or passwords in logs.
- **Per-request timings** in the response and in `messages.timings_json`.
- **Health:** `/health` (alive) and `/ready` (database, model loaded, storage writable, LLM configured).
- **Quality Center** doubles as an operations view: failed jobs, flagged pages, index versions.
- **Metrics worth tracking:** ingestion time per stage, query latency per stage, abstention rate, verification failure rate, LLM error rate and cost.
- **Backups:** the database file and `data/pdfs` are the irreplaceable parts. Everything else can be rebuilt.

---

## 14. Performance & Capacity Design

| Area | Design decision | Status |
|---|---|---|
| Browser responsiveness | Upload returns `202` immediately; processing is asynchronous | Hard requirement |
| Embedding | Models loaded once; batch 32 (CPU) / 64 (GPU) | Tune by measurement |
| Search | Exact `IndexFlatIP` is enough for tens of thousands of chunks, so no approximate index is needed yet | Revisit beyond ~100k chunks |
| Caching | Summaries and answers cached with version keys | Planned |
| Reranking | Adds latency; kept optional and decided by evaluation | Open |
| Capacity | 20–50 papers per workspace is a pilot target, not a proven limit | Unproven |
| Memory | Training must fit 4 GB VRAM; embedding falls back to CPU if GPU memory is short | Hard requirement |

Scaling steps if measurements demand them, in order of cost: move to PostgreSQL → add a real job queue → run workers separately → switch to an approximate FAISS index → move storage to object storage.

---

## 15. Failure Modes & Responses

| Failure | Behavior |
|---|---|
| PDF corrupt or encrypted | Rejected at upload with `PDF_UNREADABLE` |
| Scanned PDF | Pages flagged `possible_scan`; paper still usable on readable pages; UI warns; OCR is a later feature |
| Table or equation extraction poor | Flagged and shown; answers relying on those pages carry an uncertainty notice |
| Worker crash mid-ingestion | Job state persisted; resumes or retries from the failed stage |
| Index out of step with database | Consistency check triggers a rebuild |
| LLM unavailable or rate-limited | Retries with backoff, then `502 LLM_UNAVAILABLE`; retrieval results (closest passages) can still be shown |
| LLM returns invalid JSON | One repair retry, then treat as failure |
| Weak evidence | Abstain and show closest passages |
| Verification fails for a claim | Claim removed or marked "unverified" |
| GPU out of memory in training | Lower batch size, raise accumulation, shorten sequences, or fall back to CPU |

---

## 16. Key Architecture Decisions (ADRs)

| # | Decision | Alternatives | Rationale | Status |
|---|---|---|---|---|
| ADR-1 | Modular monolith (API + worker in one codebase) | Microservices | Small team, one machine, fewer moving parts; module boundaries leave room to split later | Decided |
| ADR-2 | Hybrid retrieval with RRF | Dense only | Mixes semantic and exact-term matching without calibrating scores | Decided; confirmed by evaluation |
| ADR-3 | FAISS `IndexFlatIP` (exact) | HNSW / IVF | Corpus is small; exact search avoids tuning and recall loss | Decided |
| ADR-4 | SQLite first, PostgreSQL later | PostgreSQL from day one | Zero setup for development; schema kept portable | Decided |
| ADR-5 | Hosted LLM behind a provider abstraction | Local quantized model | 4 GB VRAM limits local generation; abstraction allows swapping | Provider open |
| ADR-6 | Verify claims after generation | Trust the model | Reduces unsupported claims and fabricated citations | Decided; method open |
| ADR-7 | Index versions, never mixed | Update in place | Prevents mixing vectors from different models | Decided |
| ADR-8 | Citations store their own excerpt | Reference chunk only | Old answers survive reindexing | Decided |
| ADR-9 | Training from the command line | Train from the web UI | Reproducible, simpler UI and server | Decided |
| ADR-10 | Knowledge graph in relational tables | Graph database | Scale is small; React Flow renders the result | Decided (P2) |
| ADR-11 | Embedding model choice | MiniLM (short chunks) vs. bge-small (longer chunks) | MiniLM truncates at 256 word pieces; chunk size must match | **Open** |
| ADR-12 | Job runner | `BackgroundTasks` vs. Celery/RQ | Start simple; switch if reliability or throughput requires | **Open** |
| ADR-13 | Claim-verification method | NLI cross-encoder vs. LLM judge | Trade-off of speed, cost, accuracy | **Open** |
| ADR-14 | Reranker on by default | On / off | Decided from evaluation results | **Open** |

---

## 17. Extension Points

| Future need | Where it attaches |
|---|---|
| OCR for scanned papers | New extraction strategy in stage 2; page flag already exists |
| Table and figure understanding | Additional extractor plus a multimodal model; new chunk types |
| Import by DOI / arXiv / Semantic Scholar | New ingestion source feeding the same pipeline |
| Annotations and notes | New `annotations` table keyed by paper and page |
| Workspace sharing | `workspace_members` table; ownership checks widen from user to membership |
| LLM cost tracking | `llm_calls` table written by the provider abstraction |
| Second DL model (reranker or evidence classifier) | New Model Lab task; same `model_runs` and artifact layout |
| PostgreSQL full-text for keyword search | Replace the BM25 file; deletes become transactional |
| Multi-user online deployment | Container layout in section 6.2, object storage, real job queue |

---

## 18. Architectural Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Scope outgrows a student project | Unfinished system | Build in the order of the PRD phases; hold to the MVP |
| Embedding truncation | Silent loss of searchable text | Chunk size tied to the model's token limit; a test asserts chunk token counts |
| PDF layout breaks sectioning and tables | Wrong or missing evidence | Best-effort parsing, page flags, fixture PDFs, "Not Reported" |
| Hallucinated numbers | Loss of trust | Verbatim number check, abstention, faithfulness measured |
| No evaluation ground truth | Meaningless metrics | Build the labeled question set early |
| Database/index drift | Missing or phantom results | Consistency check and rebuild |
| LLM dependency | Outage, cost, rate limits | Provider abstraction, caching, budget cap, retrieval-only fallback |
| 4 GB VRAM ceiling | Training failures | Small batches, accumulation, fp16, CPU fallback, Mac benchmark |
| Prompt injection from papers | Manipulated answers | Delimit untrusted text, verify outputs |

---

## 19. Build Order (architecture view)

| Step | Builds | Proves |
|---|---|---|
| 1 | Schema, upload, storage, library UI, PDF viewer | A paper can be stored and inspected |
| 2 | Extraction, sectioning, chunking with page ranges | Chunks carry correct page references |
| 3 | Embeddings, FAISS, BM25, RRF | Retrieval works and is measurable |
| 4 | Query endpoint, prompt, verifier, abstention | Answers are grounded; unanswerable questions abstain |
| 5 | Citation click-through to PDF highlights | Evidence is verifiable by the user |
| 6 | Model Lab pipeline (parallel with steps 2–5) | A real trained model with real metrics |
| 7 | Summaries and two-paper comparison | Cited cross-paper analysis |
| 8 | Evaluation harness | Design choices are chosen by data |
| 9+ | Experiment extraction, reports, graph, gaps | Advanced features per PRD priorities |
