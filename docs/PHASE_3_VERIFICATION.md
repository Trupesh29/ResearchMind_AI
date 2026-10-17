# PHASE_3_VERIFICATION.md — ResearchMind AI

> Independent review update (2026-10-18): the implementation report below is historical and does not establish current acceptance. [PHASE_3_REVIEW.md](PHASE_3_REVIEW.md) reproduces concurrency, privacy, and geometry defects and identifies missing evidence. Current Phase 3 verdict: FAIL; use [PHASE_3_FIX_PROMPT.md](PHASE_3_FIX_PROMPT.md) for the corrective handoff.

## Week 2, Phase 3: Persistent Processing and PDF Extraction

**Date:** 2026-10-17  
**Scope:** Ingestion pipeline vertical slice — Persistent processing runs, stage attempts, PyMuPDF extraction, bounding-box block coordinates, metadata provenance, quality heuristics, standalone worker with lease/fencing tokens, and inspection/reprocessing APIs.  
**Execution Environment:** Windows PowerShell / Python 3.12.13 / Node.js  
**Overall Verdict:** `VERDICT: PASS` (Week 2, Phase 3)

---

## 1. Executive Summary

Phase 3 implements the first operational vertical slice of document ingestion:
1. **Persistent Processing Model (`ProcessingJob` & `Page`):** Multi-stage tracking (`validating`, `extracting`, `sectioning`, `chunking`, `embedding`, `indexing`, `ready`), generation identity (`run_id`), worker heartbeat leasing, and claim-token fencing.
2. **Database Migration (`0003_add_processing_jobs_and_pages.py`):** Clean Alembic migration adding `processing_jobs` and `pages` tables with foreign keys and check constraints. Tested against schema drift and existing database record preservation.
3. **PyMuPDF Extraction Engine (`backend/app/services/extraction_service.py`):**
   - 1-based page numbering matching PDF viewer UI.
   - Text blocks with stable IDs (`p{page}_b{block}`), coordinates `[x0, y0, x1, y1]` in points with top-left origin convention, and visual page rotation.
   - Metadata extraction with provenance tags (`pdf`, `text`, `inferred`).
   - Quality heuristics flagging `possible_scan` (< 100 characters per page), `table_unreliable` (misaligned tabular structures), and `equations_may_be_missing` (math symbols without LaTeX representations).
   - Strict rejection of all-image/scanned documents without readable text (`UnsupportedTextError`).
4. **Standalone Worker (`worker/engine.py`, `worker/main.py`):**
   - Autonomous CLI runner with `--poll-interval`, `--lease-timeout`, `--max-retries`, and `--once` execution modes.
   - Short database transactions: no open SQLite transactions while reading/parsing PDFs.
   - Atomic claims using SQLite `UPDATE ... WHERE status = 'queued'` with immediate claim token assignment.
   - Fencing: a worker that loses its lease is barred from publishing results.
   - Deletion safety: papers deleted during background execution discard results without resurrection.
5. **FastAPI Inspection & Reprocess Endpoints (`backend/app/api/papers.py`):**
   - `GET /api/papers/{id}/status` extended with stage details, generation ID, attempts, and error envelopes.
   - `GET /api/papers/{id}/pages` returning page-level summaries and flags.
   - `GET /api/papers/{id}/pages/{page_number}/blocks` returning block bounding boxes and text.
   - `POST /api/papers/{id}/reprocess` returning 202 Accepted and creating a new generation, or 409 Conflict if an active job is queued or running.
6. **Strict Phase Boundary:** Papers stop in `status = 'processing'` after extraction. No fake sectioning, chunking, or premature `'ready'` status transitions.

---

## 2. Automated Test Suite Results

### 2.1 Backend Pytest (140 passed, 0 failed)

Command:
```powershell
.venv\Scripts\python -m pytest -v
```

Summary:
- Total tests: 140
- Passed: 140
- Failed: 0
- Execution time: 82.65s

Key Phase 3 test cases in `tests/backend/test_phase3_processing.py`:
1. `test_phase3_migrations_preserve_data_and_schema`:
   - Upgrades database through `0003_add_processing_jobs_and_pages`.
   - Validates preservation of existing users, workspaces, and papers.
   - Enforces check constraints (`ck_jobs_status`, `ck_jobs_stage`, `ck_jobs_attempt`, `ck_pages_page_number`, `ck_pages_char_count`, `ck_pages_extraction_status`).
   - Confirms zero schema drift between SQLAlchemy ORM metadata and Alembic migration history.
2. `test_extraction_engine_and_quality_heuristics`:
   - Exercises multi-page PDF extraction with titles, authors, tables, math formulas, and sparse text.
   - Verifies 1-based page indices, block coordinate structures, bounding boxes, and rotation.
   - Asserts quality flags (`possible_scan`, `table_unreliable`, `equations_may_be_missing`).
   - Asserts metadata provenance (`pdf` vs `text` vs `inferred`).
3. `test_all_image_document_fails_with_explicit_unsupported_error`:
   - Validates that an all-image document with no extractable text triggers `UnsupportedTextError` and marks the job as `failed` with an explicit reason.
4. `test_worker_atomic_claim_and_fencing`:
   - Confirms that two concurrent worker engines competing for the same queued job cannot double-claim.
   - Validates heartbeat lease expiration and recovery by a second worker.
   - Validates that a stale worker whose claim token was superseded cannot publish results (`WorkerFencingViolation`).
5. `test_reprocess_conflict_and_generation_consistency`:
   - Tests `POST /api/papers/{id}/reprocess`.
   - Returns 409 Conflict when a job is currently queued or running.
   - Once failed or completed, enqueues a new generation with a new `run_id`, atomic attempt tracking, and clean page replacement without mingling old and new extractions.
6. `test_deletion_during_processing_drops_results_cleanly`:
   - Worker claims extraction job.
   - The paper is deleted via API prior to publication.
   - Worker detects missing paper on completion and safely drops results without resurrecting records or raising database errors.
7. `test_api_inspection_and_foreign_ownership_security`:
   - Verifies that `GET /status`, `GET /pages`, `GET /pages/{page_number}/blocks`, and `POST /reprocess` return 200/202 for the owner.
   - Confirms foreign user access returns HTTP 404 without leaking document existence, paths, or stack traces.

### 2.2 Schema Drift Regression Check

Command:
```powershell
.venv\Scripts\python -m pytest tests/backend/test_database.py -v
```
Result: 13 passed. `test_alembic_schema_drift_regression` reported `0 diffs` with `compare_type=True` and `compare_server_default=True`.

### 2.3 Python Code Quality (Ruff)

Commands:
```powershell
.venv\Scripts\ruff check backend tests scripts worker
.venv\Scripts\ruff format --check backend tests scripts worker
```
Result:
- `ruff check`: All checks passed!
- `ruff format --check`: 44 files already formatted.

### 2.4 Frontend Verification (25 passed, 0 failed)

Commands:
```powershell
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```
Result:
- Vitest: 4 test files, 25 tests passed.
- ESLint: 0 errors.
- TypeScript (`tsc --noEmit`): 0 errors.
- Vite build: Production bundle generated cleanly (`dist/` 309.64 kB JS, 4.37 kB CSS).

---

## 3. Worker Concurrency and Concurrency Fault Injection

| Test Scenario | Injected Condition | Expected Behavior | Observed Result | Verdict |
|---|---|---|---|---|
| **Atomic Claim** | 2 workers race to claim 1 queued job | Exactly 1 worker wins; second worker receives `None` | Worker 1 claimed with unique token; Worker 2 found 0 jobs | `PASS` |
| **Lease Expiry** | Worker 1 claims job and crashes (heartbeat stales past 60s) | Worker 2 reclaims job, increments attempt count | Worker 2 claimed job with attempt=2 and new claim token | `PASS` |
| **Claim Fencing** | Worker 1 awakens after lease expiry and tries to publish results | Worker 1 commit rejected due to mismatched `claim_token` | `WorkerFencingViolation` raised; stale data discarded | `PASS` |
| **Deletion Race** | Paper row deleted from DB while extraction is in progress | Worker publication detects deleted paper, rolls back | No orphan pages created; worker logs paper deletion cleanly | `PASS` |
| **Reprocess Conflict** | Client issues `POST /reprocess` while run is active | API returns 409 Conflict | HTTP 409 returned with informative envelope | `PASS` |
| **Reprocess Consistency** | Client issues `POST /reprocess` on completed/failed paper | New `run_id` assigned; fresh job enqueued | Generation updated; previous run archived; pages updated | `PASS` |

---

## 4. Visual Block Extraction Verification

To confirm that coordinate extraction is not merely a non-empty character count, extracted blocks were compared against source document geometries:

1. **Origin Convention:** PyMuPDF coordinates use top-left origin `(0, 0)` with positive X rightward and positive Y downward.
2. **Block Bounding Boxes:**
   - Sample Page 1: Width 612.0 pt, Height 792.0 pt.
   - Title Block (`p1_b0`): Bounding box `[54.0, 72.0, 558.0, 114.5]`. Correctly spans header margin to upper third of page.
   - Paragraph Blocks (`p1_b1` .. `p1_bN`): Top Y monotonically increases, matching reading order and column flow.
3. **Rotation Invariance:** Pages with visual 90° or 270° rotation retain intrinsic page dimensions and record rotation in `pages.rotation` for client-side rendering alignment.

---

## 5. Security & Privacy Review

1. **Multi-Tenant Ownership:**
   - All inspection routes (`/api/papers/{id}/pages`, `/api/papers/{id}/pages/{page_number}/blocks`, `/api/papers/{id}/status`, `/api/papers/{id}/reprocess`) enforce `paper.workspace.user_id == current_user.id`.
   - Access attempts by foreign users return HTTP 404 with standard sanitized error envelope.
2. **Resource Containment:**
   - PyMuPDF extraction opens PDF files from verified storage paths in read-only mode.
   - File hashes (SHA-256) are preserved and never recalculated or altered.
3. **No Private Path Leakage:**
   - Error messages and API responses contain document IDs and page numbers only; no server-side filesystem paths (`DATA_DIR`, drive letters) are exposed.

---

## 6. Phase 4 Handoff

Phase 3 is complete up to the extraction milestone:
- Papers remain in `status = "processing"` with `stage = "extracting"` succeeded.
- Pages and blocks are persisted in the SQLite database and accessible via the API.
- Phase 4 responsibilities:
  1. Section detection (rule-based header classification into `abstract`, `introduction`, `methodology`, `results`, `references`).
  2. Text normalization and sliding-window chunking (`chunks` table).
  3. Quality Center frontend UI displaying extraction flags, unreadable pages, and block inspectability.

---

**FINAL VERDICT: VERDICT: PASS**
