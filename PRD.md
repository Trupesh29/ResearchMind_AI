# ResearchMind AI — Product Requirements Document

**Version:** 0.1 (draft for brainstorming)
**Status:** Planning
**Project type:** Full-stack AI/ML research platform (student group project)
**Core technologies:** RAG, Transformers, NLP, Deep Learning

> Items marked **[Proposed]** are recommendations not yet confirmed. Items marked **[Open]** need a decision. Everything else is established in the project context.

---

## 1. Overview

ResearchMind AI turns unstructured research-paper PDFs into an organized, searchable, auditable knowledge base. Users upload papers, ask questions, and receive answers backed by page-level citations. They can also compare papers and review structured experimental data extracted from them.

**One-line pitch:** An evidence-first research workspace, not a PDF chatbot.

## 2. Problem Statement

Researchers and students read many papers to understand a topic. Each paper uses different terminology, datasets, metrics, and experimental conditions. This causes:

- Slow manual reading and information extraction.
- Difficulty locating specific information across many PDFs.
- Hard-to-trust comparisons between results.
- Contradictions and missing evaluations that go unnoticed.
- Repeated manual work for every literature review.

General-purpose AI can summarize papers. ResearchMind's value is in **reusable, structured, inspectable** workflows.

## 3. Goals and Non-Goals

### Goals
1. Answer questions about uploaded papers with verifiable citations.
2. Abstain or flag uncertainty when evidence is insufficient.
3. Extract structured experimental information (model, dataset, metric, value, source).
4. Compare two or more papers on consistent attributes.
5. Include a real, independently fine-tuned NLP model with measured results.
6. Measure retrieval and answer quality with actual evaluations.

### Non-Goals (v1)
- OCR or scanned-PDF support.
- Chart, figure, or multimodal understanding.
- Automated paper discovery (DOI, arXiv, Semantic Scholar).
- Guaranteeing research novelty or that a "gap" is unstudied.
- Reproducing a paper's experiments.
- Training or fine-tuning a generative LLM.
- Large-scale multi-tenant deployment.

## 4. Target Users

| User | Primary need |
|---|---|
| College students | Understand papers; prepare projects and literature reviews |
| Research scholars | Compare studies; extract findings |
| Professors / mentors | Review evidence, methods, proposals |
| AI/ML engineers | Study architectures, datasets, evaluations |
| Technical researchers | Organize knowledge across publications |

**[Open] Primary persona for v1.** Single-paper understanding vs. multi-paper literature comparison. This decides whether v1 favors depth per paper or cross-paper comparison.

## 5. Scope Decisions

| Decision | Status | Recommendation |
|---|---|---|
| Domain | [Open] | Computer Science / AI papers only for v1 (predictable structure: datasets, baselines, results tables) |
| Differentiator | [Open] | Experiment intelligence + evidence verification |
| Input | Fixed | Text-based PDFs with selectable text |
| Capacity (pilot) | Target, unproven | 20–50 papers per workspace, ~25 MB configurable file limit |
| Deployment | [Open] | Local demo first; multi-user online later |
| Auth | [Open] | Not required for single-user local MVP |

## 6. User Journey

Landing → Authentication (optional in MVP) → Dashboard → Workspace → Upload → Processing → Research Explorer → AI Assistant → Comparison → Model Lab → Reports

Users must not need to know Python, vector databases, LLMs, or Deep Learning. Processing progress, errors, and citations must be understandable.

## 7. Functional Requirements

Priority: **P0** = MVP, **P1** = after MVP, **P2** = advanced / optional.

### 7.1 Research Library (P0)
- FR-1: Upload single or multiple PDFs with drag-and-drop.
- FR-2: Validate file type and size; reject invalid or corrupt PDFs with a clear message.
- FR-3: Extract metadata (title, authors, year, keywords, page count). Label fields as *read from PDF* vs. *inferred*.
- FR-4: Detect duplicate papers.
- FR-5: Show upload and processing status.
- FR-6: Search, delete, and reprocess papers; deleting a paper removes its index entries.
- FR-7: PDF preview and viewer.

### 7.2 Processing and Quality Center (P0 basic, P1 full)
- FR-8: Pipeline stages: validate → extract text and page locations → identify sections → normalize (original untouched) → chunk → embed → index → mark ready.
- FR-9: Report readable pages, pages with extraction issues, chunk count, and failed operations.
- FR-10: Flag scanned pages, missing equations, and poorly extracted tables instead of treating them as understood.
- FR-11: Allow reprocessing without losing the original PDF.
- FR-12: Keep processing history with model and index versions (P1).

### 7.3 AI Research Assistant (P0)
- FR-13: Natural-language questions over selected papers.
- FR-14: Answer modes: **Paper-only**, **Multi-paper**, **Simple explanation**, **General AI** (outside knowledge, clearly labeled).
- FR-15: Every answer includes sources, page numbers, and supporting excerpts.
- FR-16: Citations link to the exact page in the PDF viewer.
- FR-17: In Paper-only mode, a claim appears only if a retrieved passage supports it. Otherwise the answer says "Not reported in this paper."
- FR-18: Abstain when retrieved evidence is insufficient.
- FR-19: Support follow-up questions in a conversation.
- FR-20: Treat instructions embedded in uploaded papers as data, not commands.

### 7.4 Research Explorer and Summaries (P0 basic)
- FR-21: Identify, where available: title, abstract, problem, objectives, methodology, models, datasets, findings, limitations, conclusion.
- FR-22: Summary types: Simple, Technical, Methodology, Results, Critical Reading (P1). Include source references where practical.

### 7.5 Paper Comparison Center (P0 for two papers)
- FR-23: Compare selected papers across chosen dimensions (objective, methodology, dataset, metrics, results, limitations, future work).
- FR-24: Output a side-by-side matrix with evidence linked to each cell.
- FR-25: Warn when results are not comparable (different datasets, hardware, protocols, or metrics).
- FR-26: Show common findings, differences, and missing information; contradictions (P1).

### 7.6 Experiment Intelligence Engine (P1; v1 limited to text-stated metrics and simple tables) **[Proposed differentiator]**
- FR-27: Extract experiment name, task, model, dataset, sample count, training and hardware configuration, evaluation method, metrics, baseline, source table/section/page, limitations.
- FR-28: Store as structured records for later comparison.
- FR-29: Display **Not Reported** for missing values.
- FR-30: Preserve provenance: paper, page, passage, extraction version.

### 7.7 Model Lab — Deep Learning Center (P0 minimum)
- FR-31: Fine-tune DistilBERT on SciCite for citation-intent classification **[Proposed]**.
- FR-32: Use the dataset's prescribed train/validation/test splits.
- FR-33: Show dataset overview, training config, learning curves, precision/recall/F1, confusion matrix, training time, error analysis.
- FR-34: Compare baseline vs. fine-tuned model.
- FR-35: Persist weights, tokenizer, config, and metrics; every displayed number comes from a real run.
- FR-36: The classifier is separate from the generative LLM used for answers.

### 7.8 Retrieval Evaluation Center (P1)
- FR-37: Compare semantic vs. keyword vs. hybrid retrieval, with and without reranker, across chunk sizes and embedding models.
- FR-38: Metrics: Recall@K, MRR, nDCG@K, query latency, citation coverage, citation correctness, answer faithfulness, missing-evidence handling.
- FR-39: Run against a hand-labeled question set (target 30–50 questions across a few papers).

### 7.9 Dashboard (P1)
- FR-40: Show paper count, workspaces, processing status, recent questions, saved comparisons, reports, and recent model runs, with quick actions.

### 7.10 Report Studio (P1)
- FR-41: Report types: paper summary, literature comparison, experiment evidence, research gaps, technical analysis, model evaluation.
- FR-42: Export PDF, DOCX, and CSV where applicable.
- FR-43: Preserve references, source information, and uncertainty notices.

### 7.11 Research Gap Explorer (P2)
- FR-44: Suggest candidate gaps from reported limitations, narrow evaluations, and contradictions within the uploaded corpus.
- FR-45: Attach supporting evidence and reasoning; separate paper-supported findings from generated hypotheses.
- FR-46: State that a gap within the corpus is not proof of novelty.

### 7.12 Knowledge Graph (P2)
- FR-47: Nodes: papers, authors, topics, algorithms, datasets, experiments, findings. Relationships: uses, evaluates, cites, solves, supports, potentially contradicts.
- FR-48: Clickable nodes open underlying evidence. Render with React Flow; no graph database needed initially.

## 8. System Architecture

### Pipeline A — Ingestion (on upload)
1. Upload from React.
2. FastAPI validates file, creates metadata, starts an async job.
3. PyMuPDF extracts text and page-level positions.
4. NLP preprocessing: sections, cleanup.
5. Chunking with overlap, preserving paper and page references.
6. Sentence-Transformer embeddings.
7. Index in FAISS (semantic) and BM25 (keyword).
8. Persist metadata, chunks, references, PDFs, jobs, index versions.

**Chunking constraint:** `all-MiniLM-L6-v2` truncates input at 256 word pieces. Use chunks of about 150–250 tokens with ~20% overlap, **or** use an embedding model with a 512-token window (for example `bge-small-en-v1.5`) for larger chunks. Chunk size is a tunable experiment in 7.8.

### Pipeline B — Question Answering (per query)
1. Question input and selected-paper context.
2. Query embedding with the same model used for indexing.
3. Hybrid retrieval (FAISS + BM25).
4. Optional cross-encoder reranking.
5. Context assembly with document IDs and page references.
6. LLM generation per the selected answer mode.
7. Grounding and citation checks.
8. Response with explanation, sources, and optional tables.

Uploading a paper requires indexing only; it never retrains DistilBERT or the LLM.

### Models in the system (keep distinct)
| Role | Model |
|---|---|
| Embedder | Sentence-Transformer (MiniLM or similar) |
| Reranker | Cross-Encoder MiniLM (optional) |
| Own fine-tuned classifier | DistilBERT on SciCite |
| Answer generator | Generative LLM, hosted API recommended **[Open]** |

## 9. Technology Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite, Tailwind CSS, Motion |
| Backend | Python + FastAPI |
| ML/DL | PyTorch, Hugging Face Transformers, Sentence Transformers |
| NLP | spaCy, Hugging Face |
| Retrieval | FAISS, BM25, optional Cross-Encoder reranker |
| RAG orchestration | Custom Python or LangChain **[Open]** |
| Database | SQLite initially, PostgreSQL later |
| PDF extraction | PyMuPDF |
| Visualization | React Flow, Recharts |
| Reports | ReportLab, python-docx |
| Generation | Hosted LLM API or lightweight local model **[Open]** |

## 10. Data Model

| Entity | Contents |
|---|---|
| Users | Identity, authentication |
| Workspaces | Research project info |
| Papers | File paths, metadata, status |
| Chunks | Text and source locations |
| Processing Jobs | Progress, errors, timestamps |
| Embedding Indexes | Model and index versions |
| Conversations | Questions and answers |
| Citations | Document and page references |
| Experiments | Extracted methods and reported results |
| Knowledge Graph | Nodes and supported relationships |
| Model Runs | Hyperparameters, metrics |
| Reports | Generated outputs |

Original documents, extracted content, embedding references, and generated analysis must remain traceable.

## 11. API (initial)

| Endpoint | Purpose |
|---|---|
| `POST /api/papers` | Upload PDF |
| `GET /api/papers` | List papers |
| `GET /api/papers/{id}/status` | Processing status |
| `GET /api/papers/{id}/pages` | Page information |
| `POST /api/research/query` | Question answering |
| `POST /api/compare` | Paper comparison |
| `GET /api/workspaces/{id}/insights` | Saved insights |
| `GET /api/model-runs` | Training history |
| `POST /api/reports` | Generate report |

Additional endpoints needed: authentication, deletion, model configuration, workspace management.

## 12. Compute Strategy

- **Lenovo LOQ (RTX 2050, 4 GB VRAM):** main development; PDF processing, NLP, FAISS indexing, MiniLM embeddings, small inference, DistilBERT fine-tuning.
- **DistilBERT fine-tuning settings:** batch size 2–4, sequence length around 128, gradient accumulation if needed, mixed precision, efficient checkpointing.
- **College Mac (16 GB RAM, processor unidentified):** optional. Identify the chip, benchmark the same model, then decide. No speed advantage is established.
- **LLM generation:** hosted API recommended; a small quantized local model is an optional experiment with slower, lower-quality output.

## 13. UX and Design Direction

- Light-first scholarly theme; warm white and subtle gray surfaces; dark navy titles; restrained blue/teal highlights; modern typography.
- Persistent sidebar, workspace selector, upload zone, paper cards/tables, interactive PDF reader, source-evidence drawer, chat interface, comparison matrix, metrics dashboards, export interface, progress and error indicators.
- Prioritize readability and research productivity over effects.
- **[Open]** Final branding and color system. **[Open]** Guided workflow (DataVision-style) vs. free access to independent tools.

## 14. Non-Functional Requirements

**Performance (targets, not proven):** keep heavy processing asynchronous; never freeze the browser; store embeddings so repeated questions do not re-index; cache safe summaries; measure retrieval and generation latency separately.

**Reliability:** invalid-PDF handling; scanned-page detection; missing table/equation warnings; duplicate handling; retry support; citation validation; abstention on weak evidence.

**Security and compliance:** secure file storage; protection against unauthorized document access; deletion with index cleanup; respect paper licenses; prompt-injection resistance for text inside uploaded papers.

**Trust principle:** trustworthy answers over confident-sounding guesses. The assistant must never fabricate findings, values, references, or conclusions.

## 15. Evaluation Plan

| Area | Metrics |
|---|---|
| Retrieval | Recall@5, MRR, nDCG@K, latency |
| Answer quality | Citation correctness, claim support, relevance, faithfulness, unsupported-question handling, contradiction handling |
| Classifier | Accuracy, macro F1, per-class precision/recall, confusion matrix, validation loss, train/inference time |
| Extraction (if built) | Field-level precision/recall against hand-labeled records |

All figures shown in the application must come from actual evaluations.

## 16. Differentiation

The goal is not a stronger LLM. It is a more inspectable, structured workflow:

1. Structured evidence database that persists across sessions.
2. Repeatable comparisons.
3. Per-fact provenance (paper, page, passage, extraction version).
4. Comparability warnings for incompatible experiments.
5. Visual navigation of papers, methods, and findings.
6. Measurable NLP and DL, with its own evaluation tooling.

Do not claim that general-purpose AI cannot summarize papers or cite sources.

## 17. MVP Definition

**Includes**
1. Research Library with PDF upload.
2. Processing and indexing with source locations.
3. AI Research Assistant with working citations and abstention.
4. Basic paper summarization.
5. Comparison of at least two papers.
6. One fine-tuned NLP model with real evaluation results.

**Excludes:** knowledge graph, automated discovery, advanced gap detection, multimodal chart understanding.

**Success condition:** A user uploads papers, asks relevant questions, gets evidence-backed answers, compares findings, and sees the measured performance of a real trained NLP model.

## 18. Development Phases

| Phase | Focus | Done when |
|---|---|---|
| 1 Foundation | React, FastAPI, workspace, upload, library, PDF viewer, DB | A paper can be uploaded, stored, inspected |
| 2 Document intelligence | Extraction, sections, chunking, embeddings, FAISS, BM25, processing history | Passages are searchable with source locations |
| 3 RAG assistant | Query UI, hybrid retrieval, grounded generation, citations, PDF navigation, uncertainty handling | Users can ask and verify evidence |
| 4 Research intelligence | Summaries, comparison, experiment extraction, evidence records, export | Papers can be compared with cited information |
| 5 Model Lab | SciCite pipeline, DistilBERT, evaluation, history, metrics UI, baseline | Trained-model performance is reproducible and visible |
| 6 Advanced | Research gaps, knowledge graph, contradictions, external discovery | Insights are traceable to evidence |
| 7 Optimization | Benchmarks, job reliability, access control, caching, diagnostics, deployment, tests | System is stable and tested |

Phase 5 is independent of Phases 2–4 and can run in parallel.

## 19. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Scope too large for a student project | Unfinished product | Hold strictly to the MVP; schedule P1/P2 only after P0 works |
| PDF table and equation extraction is unreliable | Wrong or missing experiment data | Best-effort tables in v1; flag low-confidence pages; show Not Reported |
| Chunks exceed embedding model's input limit | Silent loss of searchable text | Use sizes in section 8 or a longer-context embedder; test chunk sizes |
| Hallucinated or unsupported citations | Loss of trust | Citation validation step; abstention; Paper-only mode rules |
| No ground truth for evaluation | Metrics are meaningless | Build a hand-labeled question set early |
| 4 GB VRAM limit | Training failures or slow runs | Small batches, short sequences, mixed precision; benchmark Mac |
| Hosted LLM cost or rate limits | Unreliable demo | Set a budget; cache answers; keep a fallback model **[Open]** |
| Prompt injection via uploaded PDFs | Manipulated answers | Treat paper text as data; isolate it from system instructions |
| Licensing of uploaded papers | Compliance issues | Keep files private per user; no redistribution |

## 20. Open Decisions

| # | Decision | Needed before |
|---|---|---|
| 1 | Primary persona (single-paper vs. multi-paper) | Phase 1 UI |
| 2 | Domain (CS/AI only vs. general) | Phase 2 |
| 3 | Differentiator feature | Phase 4 |
| 4 | LLM provider, budget, local vs. hosted | Phase 3 |
| 5 | Embedding model and chunk size | Phase 2 |
| 6 | Auth and user model | Phase 1 |
| 7 | Guided workflow vs. independent tools | Phase 1 UI |
| 8 | Whether SciCite/DistilBERT stays the only DL experiment, or a second model (reranker or evidence classifier) is added | Phase 5 |
| 9 | Branding and final color system | Phase 1 UI |
| 10 | Deployment target | Phase 7 |
| 11 | Mac processor and training benchmark | Phase 5 |
| 12 | OCR and multimodal support | Post-MVP |

## 21. Glossary

- **RAG:** Retrieval-Augmented Generation. Retrieve evidence first, then generate an answer from it.
- **Embedding:** A numeric vector representing the meaning of a text passage.
- **FAISS:** Library for fast similarity search over vectors.
- **BM25:** Keyword-based ranking function.
- **Reranker (Cross-Encoder):** Model that rescores retrieved passages against the query.
- **Recall@K / MRR / nDCG@K:** Standard retrieval metrics.
- **Faithfulness:** Whether an answer's claims are supported by the retrieved evidence.
- **Provenance:** The traceable origin (paper, page, passage) of each fact.
