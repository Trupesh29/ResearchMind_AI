# API_SPEC.md — ResearchMind AI

**REST API Contract: Endpoints, Schemas, Errors & Conventions**
Derived from TRD v0.1 §11 and `DATABASE_SCHEMA.md` · Framework: FastAPI + Pydantic v2 · Base path: `/api`

**Priority tags:** **[P0]** MVP · **[P1]** after MVP · **[P2]** advanced. Endpoints marked [P1]/[P2] are specified now so the contract is stable, but need not be built for the MVP.

---

## 1. Scope & Source of Truth

This document is the contract between the React frontend and the FastAPI backend. FastAPI generates an OpenAPI document at `/openapi.json` and interactive docs at `/docs`; **the Pydantic models in the backend are the executable truth**, and this file explains them. If they disagree, fix the one that is wrong and update both.

Row fields map to the tables in `DATABASE_SCHEMA.md`. The API never exposes storage paths, password hashes, or other users' data.

---

## 2. Global Conventions

| Topic | Rule |
|---|---|
| Base URL | `/api` (e.g. `http://localhost:8000/api`) |
| Format | JSON (`application/json`) unless noted (uploads are `multipart/form-data`, PDFs are `application/pdf`, answers may stream as `text/event-stream`) |
| IDs | UUID strings |
| Timestamps | ISO-8601 UTC, e.g. `2026-10-15T09:30:00Z` |
| Naming | `snake_case` in all JSON fields |
| Auth | `Authorization: Bearer <access_token>` on every endpoint except register, login, refresh, and health. In a single-user local MVP, auth can be disabled by configuration; the contract does not change |
| Ownership | Every resource is resolved up to `workspaces.user_id`. A resource that exists but belongs to someone else returns **404**, not 403, so IDs cannot be probed |
| Null vs missing | Unknown values are `null`. Experiment values the paper does not report are `null` and displayed as "Not Reported" |
| Idempotency | `GET`, `PUT`, `DELETE` are idempotent. Uploads are deduplicated by file hash |
| Pagination | `?limit=` (default 25, max 100) and `?cursor=`; responses include `next_cursor` (null at the end) |
| Versioning | Path stays `/api` for v0.x. A breaking change in v1 moves to `/api/v1` |

### 2.1 Success status codes

| Code | Meaning |
|---|---|
| `200 OK` | Request succeeded and returns a body |
| `201 Created` | A resource was created synchronously |
| `202 Accepted` | Work was queued; poll the returned status resource |
| `204 No Content` | Success with no body (deletes) |

### 2.2 Error envelope

Every error uses the same shape:

```json
{
  "error": {
    "code": "PAPER_NOT_READY",
    "message": "This paper is still being processed.",
    "details": { "paper_id": "…", "status": "processing" },
    "request_id": "req_8f2c1a"
  }
}
```

`request_id` matches the server log entry for that request.

### 2.3 Error codes

| HTTP | `code` | When |
|---|---|---|
| 400 | `INVALID_REQUEST` | Body or query fails validation |
| 400 | `INVALID_FILE_TYPE` | Upload is not a PDF (checked by magic bytes, not extension) |
| 400 | `PDF_UNREADABLE` | PDF is corrupt or encrypted and cannot be opened |
| 401 | `UNAUTHENTICATED` | Missing, expired, or invalid token |
| 403 | `FORBIDDEN` | Authenticated but the action is not allowed |
| 404 | `NOT_FOUND` | Resource missing or not owned by the caller |
| 409 | `PAPER_NOT_READY` | Paper status is not `ready` (uploaded, processing, or failed) |
| 409 | `DUPLICATE_PAPER` | Same file hash already exists in the workspace |
| 409 | `INDEX_BUILDING` | The workspace's search index is being rebuilt |
| 409 | `NO_ACTIVE_INDEX` | The workspace has no active embedding index yet |
| 409 | `NAME_CONFLICT` | Workspace name already used by this user |
| 413 | `FILE_TOO_LARGE` | Upload exceeds `MAX_UPLOAD_MB` (default 25) |
| 422 | `UNPROCESSABLE` | Valid JSON but semantically wrong (e.g. fewer than two papers to compare) |
| 429 | `RATE_LIMITED` | Too many requests; see `Retry-After` header |
| 502 | `LLM_UNAVAILABLE` | Hosted LLM failed after retries |
| 503 | `SERVICE_BUSY` | Queue is full or a required model is not loaded |
| 500 | `INTERNAL_ERROR` | Unexpected failure; the message is generic, details are in logs |

### 2.4 Rate limits (defaults, configurable)

| Scope | Limit |
|---|---|
| `POST /auth/login` | 10 per minute per IP |
| `POST /papers` | 30 files per hour per user |
| `POST /research/query` | 30 per minute per user |
| `POST /compare`, `POST /reports` | 10 per minute per user |
| Everything else | 120 per minute per user |

Exceeded limits return `429` with a `Retry-After` header in seconds.

---

## 3. Shared Schemas

### 3.1 `Paper`

```json
{
  "id": "7b1c…",
  "workspace_id": "a93e…",
  "original_filename": "ddr4_vs_ddr5.pdf",
  "title": "Performance Analysis of DDR4 and DDR5 RAM",
  "authors": ["A. Author", "B. Author"],
  "publication_year": 2024,
  "keywords": ["RAM", "DDR5"],
  "metadata_source": {
    "title": { "source": "pdf", "evidence": "Performance Analysis of DDR4 and DDR5 RAM", "page_number": 1 },
    "authors": { "source": "text", "evidence": "A. Author, B. Author", "page_number": 1 },
    "publication_year": { "source": "inferred", "evidence": "Published in 2024", "page_number": 1 },
    "keywords": { "source": "inferred", "evidence": "Keywords: RAM, DDR5", "page_number": 1 }
  },
  "page_count": 18,
  "size_bytes": 2516582,
  "status": "ready",
  "quality": {
    "readable_pages": 16,
    "flagged_pages": 2,
    "possible_scan_pages": [3],
    "table_unreliable_pages": [11],
    "chunk_count": 214
  },
  "created_at": "2026-10-15T09:30:00Z"
}
```

`status` is one of `uploaded | processing | ready | failed`.
`metadata_source` maps field names to `ProvenanceDetail` objects (`source`, `page_number`, `evidence`). For backward compatibility with previously stored records, simple string values (e.g. `{"title": "pdf"}`) remain fully supported and serializable across API endpoints.

### 3.2 `Citation`

```json
{
  "id": "c91f…",
  "paper_id": "7b1c…",
  "paper_title": "Performance Analysis of DDR4 and DDR5 RAM",
  "page_number": 11,
  "excerpt": "…supporting passage text…",
  "claim_text": "DDR5 reported higher bandwidth in the benchmark.",
  "supported": true,
  "score": 0.82
}
```

`supported = false` means the claim failed verification and the UI must show it as "unverified" or hide it.

### 3.3 `PageRef` (for the PDF viewer)

```json
{ "paper_id": "7b1c…", "page_number": 11, "blocks": [ { "id": "b12", "bbox": [72.0, 140.5, 523.2, 188.9] } ] }
```

Coordinates are in PDF points. The viewer uses them to highlight the cited passage.

### 3.4 Enums

| Enum | Values |
|---|---|
| `answer_mode` | `paper_only`, `multi_paper`, `simple`, `general` |
| `summary_type` | `simple`, `technical`, `methodology`, `results`, `critical` |
| `job_stage` | `validating`, `extracting`, `sectioning`, `chunking`, `embedding`, `indexing`, `ready` |
| `report_type` | `paper_summary`, `literature_review`, `experiment_evidence`, `research_gaps`, `technical_analysis`, `model_evaluation` |
| `report_format` | `pdf`, `docx`, `csv` |

---

## 4. Authentication [P0 if auth enabled]

Access tokens are short-lived (default 30 minutes). The refresh token is stored in an HTTP-only, `SameSite` cookie. No token is ever returned in a URL.

### `POST /auth/register`
Request:
```json
{ "email": "user@example.com", "password": "min 10 chars", "display_name": "Trupesh" }
```
Response `201`:
```json
{ "id": "…", "email": "user@example.com", "display_name": "Trupesh" }
```
Errors: `400 INVALID_REQUEST` (weak password, bad email), `409 NAME_CONFLICT` (email already registered; use a generic message to avoid revealing which emails exist).

### `POST /auth/login`
Request: `{ "email": "…", "password": "…" }`
Response `200`:
```json
{ "access_token": "eyJ…", "token_type": "bearer", "expires_in": 1800,
  "user": { "id": "…", "email": "…", "display_name": "…" } }
```
Sets the refresh cookie. Errors: `401 UNAUTHENTICATED` (same message for unknown email and wrong password), `429`.

### `POST /auth/refresh`
Uses the refresh cookie. Response `200` with a new `access_token`. Errors: `401`.

### `POST /auth/logout`
Clears the refresh cookie and revokes the refresh token. Response `204`.

### `GET /auth/me`
Response `200`: the current user object.

---

## 5. Workspaces [P0]

### `POST /workspaces`
Request: `{ "name": "DDR memory study", "description": "optional" }`
Response `201`: `{ "id": "…", "name": "…", "description": "…", "created_at": "…" }`
Errors: `409 NAME_CONFLICT`.

### `GET /workspaces`
Response `200`:
```json
{ "items": [ { "id": "…", "name": "…", "paper_count": 12, "ready_count": 11, "created_at": "…" } ],
  "next_cursor": null }
```

### `GET /workspaces/{workspace_id}`
Response `200`: workspace with counts and active index info (`{ "model_name": "all-MiniLM-L6-v2", "version": 1 }`, or `null` if none).

### `PATCH /workspaces/{workspace_id}`
Request: any of `name`, `description`. Response `200`.

### `DELETE /workspaces/{workspace_id}`
Deletes the workspace, its papers, chunks, indexes, conversations, and reports (database cascade plus file cleanup). Response `204`.

### `GET /workspaces/{workspace_id}/insights` [P1]
Dashboard data: paper counts by status, recent questions, saved comparisons, reports, recent model runs.
```json
{
  "papers": { "total": 12, "ready": 11, "processing": 1, "failed": 0 },
  "recent_questions": [ { "message_id": "…", "question": "…", "created_at": "…" } ],
  "saved_comparisons": [ { "id": "…", "title": "…", "created_at": "…" } ],
  "recent_reports": [ { "id": "…", "report_type": "…", "status": "ready" } ],
  "recent_model_runs": [ { "id": "…", "name": "…", "status": "completed" } ]
}
```

---

## 6. Papers (Research Library) [P0]

### `POST /papers`
`multipart/form-data`: `workspace_id` (field), `files` (one or more PDFs).

Response `202`:
```json
{
  "papers": [ { "id": "7b1c…", "original_filename": "a.pdf", "status": "uploaded" } ],
  "duplicates": [ { "original_filename": "b.pdf", "existing_paper_id": "…" } ],
  "rejected": [ { "original_filename": "c.txt", "code": "INVALID_FILE_TYPE", "message": "Only PDF files are accepted." } ]
}
```
Each accepted file starts a background job. A request can partly succeed; check all three arrays. A request where every file is rejected or duplicated still returns `202` with empty `papers`.

Server checks, in order: magic bytes `%PDF-`, size limit, can the PDF be opened, SHA-256 duplicate within the workspace. The stored filename is generated by the server.

### `GET /papers`
Query: `workspace_id` (required), `status`, `q` (title/author search), `limit`, `cursor`.
Response `200`: `{ "items": [Paper], "next_cursor": null }`

### `GET /papers/{paper_id}`
Response `200`: `Paper`.

### `GET /papers/{paper_id}/status`
Cheap endpoint for polling (every 2 seconds is fine). Status is computed from the latest attempt per pipeline stage.
```json
{
  "status": "processing",
  "stage": "extracting",
  "progress": 0.5,
  "attempt": 1,
  "run_id": "9a1b…",
  "current_run_id": "9a1b…",
  "published_run_id": null,
  "error": null,
  "stages": [
    { "stage": "validating", "status": "succeeded", "finished_at": "…" },
    { "stage": "extracting", "status": "running", "started_at": "…" }
  ]
}
```
`progress` is an estimate from completed stages, not a promise. When `status = failed`, `error` holds a sanitized public message.

### `GET /papers/{paper_id}/pages`
Response `200`:
```json
{
  "run_id": "9a1b…",
  "is_stale": false,
  "items": [
    { "page_number": 1, "char_count": 3120, "extraction_status": "ok", "flags": [] },
    { "page_number": 3, "char_count": 12,   "extraction_status": "partial", "flags": ["possible_scan"] }
  ]
}
```
`is_stale` is `true` if a newer generation is actively processing or failed, preventing outdated pages from being silently treated as current output.

### `GET /papers/{paper_id}/pages/{page_number}/blocks`
Returns page dimensions, rotation, and block coordinates for citation highlighting and inspection. `404` if the page does not exist.
Response `200`:
```json
{
  "page_number": 1,
  "width": 612.0,
  "height": 792.0,
  "rotation": 0,
  "run_id": "9a1b…",
  "is_stale": false,
  "blocks": [
    {
      "id": "p1_b0",
      "bbox": [72.0, 140.5, 523.2, 188.9],
      "text": "Deep Residual Learning for Image Recognition...",
      "text_hash": "c1a9e8f2b740..."
    }
  ]
}
```

### `GET /papers/{paper_id}/file`
Streams the original PDF (`application/pdf`) after the ownership check. Supports HTTP range requests so the viewer can load pages lazily.

### `GET /papers/{paper_id}/chunks` [P1]
Query: `page`, `section`, `limit`, `cursor`. Lets the Quality Center show chunk counts and token lengths.

### `POST /papers/{paper_id}/reprocess`
Starts a fresh processing job without deleting the original PDF. Response `202` with the same shape as `GET …/status`. Errors: `409` if a job is already running.

### `DELETE /papers/{paper_id}`
Deletes the PDF file, pages, chunks, experiments, and derived analysis; tombstones its vectors and schedules an index rebuild if needed. Response `204`.

---

## 7. Research Q&A [P0]

### `POST /research/query`

Request:
```json
{
  "workspace_id": "a93e…",
  "paper_ids": ["7b1c…"],
  "question": "What is the difference between DDR4 and DDR5, and which performs better?",
  "mode": "paper_only",
  "conversation_id": null,
  "stream": false
}
```
- `paper_ids` must contain ready papers from the workspace; empty means all ready papers.
- `conversation_id` null starts a new conversation; otherwise the question is a follow-up.
- `mode` is an `answer_mode`.

Response `200` (`stream = false`):
```json
{
  "conversation_id": "…",
  "message_id": "…",
  "answer_markdown": "Based on the selected paper, DDR5 reports higher bandwidth [S1]…",
  "citations": [ Citation ],
  "uncertainties": ["The paper does not report power consumption."],
  "abstained": false,
  "mode": "paper_only",
  "timings_ms": { "rewrite": 0, "dense": 12, "bm25": 5, "rerank": 140, "generate": 1820, "verify": 260 }
}
```

**Abstention response** (not an error; HTTP `200`):
```json
{
  "message_id": "…",
  "answer_markdown": "The selected papers do not contain enough evidence to answer this.",
  "citations": [],
  "closest_passages": [ { "paper_id": "…", "page_number": 4, "excerpt": "…", "score": 0.31 } ],
  "uncertainties": [],
  "abstained": true,
  "mode": "paper_only",
  "timings_ms": { }
}
```

**Streaming** (`stream = true`, `Content-Type: text/event-stream`):

| Event | Data |
|---|---|
| `retrieval` | `{ "candidates": 20, "kept": 6 }` |
| `token` | `{ "text": "…" }` (answer text as it is generated) |
| `final` | The complete non-streaming response body, with **verified** citations |

Because citations are verified after generation, treat `token` text as provisional. The UI replaces it with the `final` answer, so unverified claims never remain on screen.

Errors: `409 PAPER_NOT_READY`, `409 NO_ACTIVE_INDEX`, `422 UNPROCESSABLE` (empty question, more papers than the limit), `502 LLM_UNAVAILABLE`, `429`.

**Behavior contract**
1. In `paper_only` mode, every factual claim has a citation to a supplied source, or the answer says "Not reported in the selected papers."
2. In `general` mode, sentences using outside knowledge are labeled "General knowledge (not from your papers)."
3. Text inside papers is treated as data, never as instructions.
4. Numbers shown as findings must appear verbatim in the cited passage.

### `GET /conversations`
Query: `workspace_id` (required), `limit`, `cursor`. Response `200`: `{ "items": [ { "id": "…", "title": "…", "created_at": "…" } ], "next_cursor": null }`

### `GET /conversations/{conversation_id}`
Response `200`:
```json
{
  "id": "…", "title": "…",
  "messages": [
    { "id": "…", "role": "user", "content": "…", "created_at": "…" },
    { "id": "…", "role": "assistant", "mode": "paper_only", "content": "…",
      "citations": [ Citation ], "abstained": false, "uncertainties": [], "created_at": "…" }
  ]
}
```

### `DELETE /conversations/{conversation_id}`
Response `204`. Messages and citations are removed with it.

### `GET /messages/{message_id}/citations`
Returns the `Citation` list for one answer, ordered by page number. Used by the evidence drawer.

---

## 8. Summaries [P0 basic]

### `POST /papers/{paper_id}/summary`
Request: `{ "type": "technical", "refresh": false }`
Response `200`:
```json
{
  "paper_id": "…",
  "type": "technical",
  "content": "…markdown…",
  "citations": [ Citation ],
  "cached": true,
  "prompt_version": "v1",
  "model_name": "…",
  "created_at": "…"
}
```
`refresh = true` ignores the cache. A cached summary is reused only if the index, prompt version, and model are unchanged. Errors: `409 PAPER_NOT_READY`.

### `GET /papers/{paper_id}/summaries`
Lists cached summaries for the paper.

### `GET /papers/{paper_id}/sections`
Response `200`: detected sections with page ranges (`abstract`, `introduction`, `methodology`, …), used by the Research Explorer. Sections that were not detected are omitted, not invented.

---

## 9. Paper Comparison [P0 for two papers]

### `POST /compare`
Request:
```json
{
  "workspace_id": "a93e…",
  "paper_ids": ["7b1c…", "d44a…"],
  "dimensions": ["objective", "methodology", "dataset", "metrics", "results", "limitations"],
  "title": "optional"
}
```
Response `200`:
```json
{
  "id": "…",
  "paper_ids": ["7b1c…", "d44a…"],
  "dimensions": ["objective", "methodology", "dataset", "metrics", "results", "limitations"],
  "cells": {
    "dataset": {
      "7b1c…": { "text": "SciCite", "citation_ids": ["c1"] },
      "d44a…": { "text": "Not reported", "citation_ids": [] }
    }
  },
  "warnings": [
    { "dimension": "results", "type": "non_comparable",
      "reason": "The papers use different datasets and hardware." }
  ],
  "common_findings": [ "…" ],
  "differences": [ "…" ],
  "missing_information": [ "…" ],
  "created_at": "…"
}
```
Rules: at least 2 and at most 5 papers (configurable); all must be `ready`. `warnings` is always present, even when empty. Errors: `422 UNPROCESSABLE` (fewer than two papers), `409 PAPER_NOT_READY`.

### `GET /compare?workspace_id=…` / `GET /compare/{comparison_id}` / `DELETE /compare/{comparison_id}`
List, fetch, and delete saved comparisons.

---

## 10. Experiment Intelligence [P1]

### `POST /papers/{paper_id}/experiments/extract`
Starts extraction. Request: `{ "refresh": false }`. Response `202`:
```json
{ "job_id": "…", "status": "queued" }
```

### `GET /papers/{paper_id}/experiments`
Response `200`:
```json
{ "items": [
  {
    "id": "…", "name": "Memory bandwidth benchmark", "task": "benchmarking",
    "model": null, "dataset": "STREAM", "n_samples": null,
    "hardware": "Not reported", "baseline": "DDR4-3200",
    "source_page": 11, "source_section": "results",
    "extraction_version": "v1",
    "metrics": [
      { "metric_name": "bandwidth_gbps", "value_text": "38.4", "value_numeric": 38.4,
        "unit": "GB/s", "verified": true, "source_page": 11 },
      { "metric_name": "latency_ns", "value_text": null, "value_numeric": null,
        "unit": null, "verified": false, "source_page": null }
    ]
  }
] }
```
A null value means **Not Reported**. `verified = true` means the value was found word for word in the source passage. Unverified values must not be shown as findings.

### `GET /experiments`
Cross-paper table for a workspace. Query: `workspace_id`, `dataset`, `metric_name`, `paper_ids`. Used to build comparison charts and to flag non-comparable results.

---

## 11. Model Lab [P0]

`model_runs` is a global log (not workspace-scoped). All endpoints are read-only; training is started from the command line (see `ARCHITECTURE.md`), not from the web UI.

### `GET /model-runs`
Query: `task`, `run_type` (`fine_tuned` | `baseline`), `status`, `limit`, `cursor`.
Response `200`:
```json
{ "items": [
  { "id": "…", "name": "distilbert-scicite-seed42", "task": "citation_intent",
    "base_model": "distilbert-base-uncased", "dataset": "allenai/scicite",
    "run_type": "fine_tuned", "device": "cuda", "seed": 42, "status": "completed",
    "summary": { "accuracy": null, "macro_f1": null },
    "started_at": "…", "finished_at": "…" }
] }
```
`summary` values come from stored metrics. They are `null` while a run is in progress.

### `GET /model-runs/{run_id}`
Full run: `hyperparams`, complete `metrics` (per-class precision/recall/F1, confusion matrix, loss curves, timings, misclassified examples), and `artifact_available` (boolean).

### `GET /model-runs/compare?task=citation_intent`
Returns completed baseline and fine-tuned runs side by side for the Model Lab comparison view.

### `POST /model-runs/classify` [P1]
Runs the saved classifier on supplied text.
Request: `{ "texts": ["We use the method of Smith et al."], "run_id": null }` (`null` = best completed run)
Response `200`: `{ "run_id": "…", "predictions": [ { "label": "method", "probabilities": { "background": 0.1, "method": 0.8, "result": 0.1 } } ] }`
Limit: 64 texts per request.

---

## 12. Retrieval Evaluation [P1]

### `POST /eval/questions`
Request: `{ "workspace_id": "…", "question": "…", "answerable": true, "gold": [ { "paper_id": "…", "pages": [7, 8] } ] }`
Response `201`: the stored question. Use `answerable: false` for abstention tests.

### `GET /eval/questions?workspace_id=…` / `DELETE /eval/questions/{id}`

### `POST /eval/runs`
Request:
```json
{
  "workspace_id": "…",
  "config": { "retrieval": "hybrid", "reranker": true, "chunk_tokens": 200,
              "embedder": "all-MiniLM-L6-v2", "top_k": 6 }
}
```
Response `202`: `{ "run_id": "…", "status": "queued" }`. Some configs (a different chunk size or embedder) require a temporary index build and take longer.

### `GET /eval/runs/{run_id}`
Response `200`: `config`, `n_questions`, and `metrics` (`recall_at_5`, `mrr`, `ndcg_at_10`, latency percentiles, `citation_correctness`, `faithfulness`, `abstention_accuracy`). Fields are `null` until the run completes.

### `GET /eval/runs?workspace_id=…`
Lists runs so the UI can chart configurations against each other.

---

## 13. Reports [P1]

### `POST /reports`
Request:
```json
{
  "workspace_id": "…",
  "report_type": "literature_review",
  "format": "pdf",
  "params": { "paper_ids": ["…", "…"], "comparison_id": "…" }
}
```
Response `202`: `{ "id": "…", "status": "pending" }`

### `GET /reports/{report_id}`
Response `200`: `{ "id": "…", "report_type": "…", "format": "pdf", "status": "ready", "created_at": "…" }`. `status = failed` includes an error message.

### `GET /reports/{report_id}/download`
Streams the file with the right content type. `409` if the report is not ready.

### `GET /reports?workspace_id=…` / `DELETE /reports/{report_id}`

Reports preserve paper references, source information, and uncertainty notices. A generated claim without a supporting citation is excluded or marked "unverified" in the output.

---

## 14. Knowledge Graph & Research Gaps [P2]

### `POST /workspaces/{workspace_id}/graph/build`
Rebuilds graph nodes and edges from experiments and extracted entities. Response `202` with a `job_id`.

### `GET /workspaces/{workspace_id}/graph`
```json
{
  "nodes": [ { "id": "n1", "type": "algorithm", "label": "DistilBERT", "paper_id": null } ],
  "edges": [ { "id": "e1", "source": "n1", "target": "n7", "relation": "evaluates",
               "confidence": 0.7, "evidence": { "paper_id": "…", "page_number": 5 } } ]
}
```
Clicking a node or edge should open its evidence through `evidence`.

### `POST /workspaces/{workspace_id}/gaps/generate`
Response `202`. Then `GET /workspaces/{workspace_id}/gaps`:
```json
{ "items": [
  { "id": "…",
    "gap_text": "Uploaded studies compare accuracy but give limited analysis of low-memory systems.",
    "research_question": "Can model compression reduce memory use while keeping acceptable quality?",
    "reasoning": "…",
    "is_hypothesis": true,
    "evidence": [ { "paper_id": "…", "page_number": 12, "excerpt": "…" } ] }
] }
```
`is_hypothesis` is always `true`. A gap found in the uploaded corpus is not proof that nobody else has studied the topic.

---

## 15. System Endpoints

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /health` | Liveness: `{ "status": "ok" }` | none |
| `GET /ready` | Readiness: database reachable, embedding model loaded, storage writable, LLM configured | none |
| `GET /config/public` | Non-secret limits for the UI: `max_upload_mb`, answer modes available, whether auth is enabled | none |

`/ready` never exposes secrets or internal paths.

---

## 16. Asynchronous Job Pattern

Slow work (ingestion, experiment extraction, evaluation runs, report generation, graph builds) never blocks the request.

1. The client calls the starting endpoint and receives `202` with an id.
2. The client polls the matching status endpoint every 2 seconds, backing off after one minute.
3. Terminal states are `ready`/`completed` or `failed`; `failed` always includes a readable `error`.
4. A failed job can be retried through the matching `reprocess` or restart endpoint; the original data is untouched.

Server-sent progress events for ingestion are an optional later enhancement; polling is the supported baseline.

---

## 17. Security Notes for API Consumers

- Send the access token only in the `Authorization` header.
- Treat `404` as "not found or not yours."
- Uploaded files are validated by content, not by extension or declared MIME type.
- Responses never include server file paths, hashes of passwords, or provider API keys.
- CORS allows only the configured frontend origin.
- Text extracted from papers and returned in excerpts is **untrusted content**: render it as plain text or sanitized markdown, never as raw HTML.
- Paper text sent to a hosted LLM leaves the machine; the UI should disclose this to users.

---

## 18. Endpoint Summary

| Method | Path | Purpose | Priority |
|---|---|---|---|
| POST | `/auth/register` | Create account | P0* |
| POST | `/auth/login` | Sign in | P0* |
| POST | `/auth/refresh` | New access token | P0* |
| POST | `/auth/logout` | Sign out | P0* |
| GET | `/auth/me` | Current user | P0* |
| POST/GET | `/workspaces` | Create / list workspaces | P0 |
| GET/PATCH/DELETE | `/workspaces/{id}` | Read / update / delete | P0 |
| GET | `/workspaces/{id}/insights` | Dashboard data | P1 |
| POST | `/papers` | Upload PDFs | P0 |
| GET | `/papers` | List papers | P0 |
| GET/DELETE | `/papers/{id}` | Read / delete paper | P0 |
| GET | `/papers/{id}/status` | Processing status | P0 |
| GET | `/papers/{id}/pages` | Page info and flags | P0 |
| GET | `/papers/{id}/pages/{n}/blocks` | Highlight coordinates | P0 |
| GET | `/papers/{id}/file` | Stream the PDF | P0 |
| GET | `/papers/{id}/chunks` | Chunk inspection | P1 |
| POST | `/papers/{id}/reprocess` | Reprocess | P0 |
| POST | `/research/query` | Ask a question | P0 |
| GET | `/conversations`, `/conversations/{id}` | History | P0 |
| DELETE | `/conversations/{id}` | Delete conversation | P0 |
| GET | `/messages/{id}/citations` | Evidence for an answer | P0 |
| POST | `/papers/{id}/summary` | Generate or fetch summary | P0 |
| GET | `/papers/{id}/summaries`, `/papers/{id}/sections` | Cached summaries, sections | P0 |
| POST/GET/DELETE | `/compare`, `/compare/{id}` | Paper comparison | P0 |
| POST | `/papers/{id}/experiments/extract` | Extract experiments | P1 |
| GET | `/papers/{id}/experiments`, `/experiments` | Extracted records | P1 |
| GET | `/model-runs`, `/model-runs/{id}`, `/model-runs/compare` | Model Lab | P0 |
| POST | `/model-runs/classify` | Classify text | P1 |
| POST/GET/DELETE | `/eval/questions` | Labeled questions | P1 |
| POST/GET | `/eval/runs`, `/eval/runs/{id}` | Retrieval evaluation | P1 |
| POST/GET/DELETE | `/reports`, `/reports/{id}`, `/reports/{id}/download` | Reports | P1 |
| POST/GET | `/workspaces/{id}/graph/build`, `/graph` | Knowledge graph | P2 |
| POST/GET | `/workspaces/{id}/gaps/generate`, `/gaps` | Research gaps | P2 |
| GET | `/health`, `/ready`, `/config/public` | System | P0 |

\* Required only if authentication is enabled; a single-user local MVP can skip it.
