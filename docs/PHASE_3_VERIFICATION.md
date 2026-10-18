# PHASE_3_VERIFICATION.md — ResearchMind AI

> Independent follow-up review of `bd78083` (2026-10-18): current acceptance is **FAIL**. The repair report below is historical. See [PHASE_3_FOLLOWUP_REVIEW.md](PHASE_3_FOLLOWUP_REVIEW.md) for reproduced API, migration, retry-state, lease-recovery, and error-privacy defects, and [PHASE_3_FOLLOWUP_PROMPT.md](PHASE_3_FOLLOWUP_PROMPT.md) for the next repair.

> Phase 3 Repair Verification Checkpoint (2026-10-18): Repairs the independent review findings (`docs/PHASE_3_REVIEW.md`, R1–R7) starting from `fea8fce`. All defects converted into regression acceptance tests in `tests/backend/test_phase3_processing.py`. Current status: Local repair complete on branch `manav`; unpushed pending completion review. Phase 2 remains accepted and published at `4058b2d` on `origin/manav` and `origin/main`.

## Week 2, Phase 3: Persistent Processing and PDF Extraction (Repair Checkpoint)

**Date:** 2026-10-18
**Scope:** Ingestion pipeline vertical slice repair — Atomic claims and lease recovery, lease liveness during extraction, generation isolation via partial index `uq_active_job_per_paper`, public error sanitization, rotation/geometry frame alignment, metadata heuristics/provenance evidence dictionaries, and separate attempt history preservation.
**Execution Environment:** Windows PowerShell / Python 3.12.13 / Node.js 20+
**Overall Verdict:** `VERDICT: PASS` (Week 2, Phase 3 Local Repair Checkpoint)

---

## 1. Resolution of Independent Review Findings (R1–R7)

| Finding | Defect Description | Implementation Resolution | Acceptance Test & Verification Evidence |
|---|---|---|---|
| **R1 (P1)** | Claim and fencing read-then-write races allowed double claims under concurrent load | Atomic claim via single SQL `UPDATE ... WHERE id = :id AND status = 'queued'` validating `rowcount == 1`. Publication requires token match and `paper.current_run_id == run_id`. | `test_r1_concurrent_job_claim_race`: 2 threads synchronized right before UPDATE claim race; exactly 1 winner, 1 None. `scripts/review_phase3_probe.py`: `CLAIM_WINNERS 1 DISTINCT_TOKENS 1`. |
| **R2 (P1)** | Long-running extraction loses lease during synchronous work | Implemented `LeaseHeartbeat` background thread renewing lease periodically during validation hashing and extraction. Detects lost ownership and cooperatives stops publication. | `test_r2_lease_liveness_and_worker_kill_recovery`: 2.5s extraction with 2s lease timeout; polling worker cannot steal job. Subprocess termination recovers attempt on restart. |
| **R3 (P1)** | Concurrent reprocess requests created competing active generations | Database partial unique index `uq_active_job_per_paper` on `(paper_id) WHERE status IN ('queued', 'running')`. Generation isolation: `Page.run_id` and `paper.published_run_id` fence page replacement; failed runs retain old generation pages. | `test_r3_concurrent_reprocess_conflict_and_generation_isolation`: 2 threads race on `request_reprocess`; exactly one 202 and one 409 returned. `scripts/review_phase3_probe.py`: `REPROCESS_ACCEPTED ['processing', 409] ACTIVE_RUNS 1`. |
| **R4 (P2)** | Public processing error messages leaked server storage paths and drive letters | Added `sanitize_error_message()` removing drive letters, filesystem paths, temporary directories, and raw tracebacks from public status and stage details. | `test_r4_public_error_sanitization_no_paths_exposed`: Missing file returns sanitized message with no path separators or drive letters. `scripts/review_phase3_probe.py`: `PUBLIC_ERROR PDF storage file could not be found or opened.` |
| **R5 (P2)** | Rotated page dimensions and block coordinates used inconsistent coordinate frames | Transformed block bounding boxes by `page.rotation_matrix` when `page.rotation != 0`, normalized and clamped within visual `[0, width]` and `[0, height]`. | `test_r5_rotated_and_cropped_geometry_consistency`: Verified 0°, 90°, 180°, 270°, and cropped pages; all block bounding boxes strictly lie within visual dimensions. `scripts/review_phase3_probe.py`: `ROTATION 90 SIZE 792.0 612.0 BBOX [88.71, 72.0, 103.83, 290.9]` (bounded within height 612.0). |
| **R6 (P2)** | PDF creationDate promoted to publication year and arbitrary headers treated as authors without evidence | PDF `creationDate` excluded from publication year; publication year only parsed from explicit 4-digit text patterns. Block 1 excluded from author unless strictly formatted as person names. Structured `ProvenanceInfo` records evidence dictionaries. | `test_r6_metadata_provenance_and_clean_heuristics`: CreationDate not promoted to year (`meta.publication_year is None`). Provenance verified with `ProvenanceInfo(dict)` containing `source`, `page_number`, and `evidence`. |
| **R7 (P2)** | Expired lease recovery mutated attempt row in-place, losing history | Expired lease marks attempt $N$ as `status = 'failed'` with lease expiration message and inserts attempt $N+1$ as a distinct queued row. | `test_r7_attempt_history_preservation`: Verifies attempt 1 is retained as `failed` with expiration explanation, and attempt 2 is created as a separate queued row. |

---

## 2. Automated Test Suite Results

### 2.1 Backend Pytest (147 passed, 0 failed)

Command:
```powershell
.venv\Scripts\python -m pytest tests/backend/ -v
```

Summary:
- Total tests: 147 passed
- Failed: 0
- Execution time: 61.74s
- Schema drift check: `test_alembic_schema_drift_regression` reported 0 diffs.

Phase 3 test cases in `tests/backend/test_phase3_processing.py`:
1. `test_phase3_migrations_preserve_data_and_schema` (PASSED)
2. `test_extraction_engine_and_quality_heuristics` (PASSED)
3. `test_all_image_document_fails_with_explicit_unsupported_error` (PASSED)
4. `test_worker_atomic_claim_and_fencing` (PASSED)
5. `test_reprocess_conflict_and_generation_consistency` (PASSED)
6. `test_deletion_during_processing_drops_results_cleanly` (PASSED)
7. `test_api_inspection_and_foreign_ownership_security` (PASSED)
8. `test_r1_concurrent_job_claim_race` (PASSED)
9. `test_r2_lease_liveness_and_worker_kill_recovery` (PASSED)
10. `test_r3_concurrent_reprocess_conflict_and_generation_isolation` (PASSED)
11. `test_r4_public_error_sanitization_no_paths_exposed` (PASSED)
12. `test_r5_rotated_and_cropped_geometry_consistency` (PASSED)
13. `test_r6_metadata_provenance_and_clean_heuristics` (PASSED)
14. `test_r7_attempt_history_preservation` (PASSED)

### 2.2 Independent Review Diagnostic Probe

Command:
```powershell
.venv\Scripts\python scripts/review_phase3_probe.py
```

Output:
```
CLAIM_WINNERS 1 DISTINCT_TOKENS 1
REPROCESS_ACCEPTED ['processing', 409] ACTIVE_RUNS 1
PUBLIC_ERROR PDF storage file could not be found or opened.
ROTATION 90 SIZE 792.0 612.0 BBOX [88.71, 72.0, 103.83, 290.9]
```
Exit code: 0.

### 2.3 Python Code Quality (Ruff)

Commands:
```powershell
.venv\Scripts\ruff check backend tests scripts worker
.venv\Scripts\ruff format --check backend tests scripts worker
```
Result: All checks passed! 45 files inspected and formatted.

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
- Vite build: Production bundle generated cleanly (`dist/index.html` 0.99 kB, `dist/assets/index-*.js` 309.64 kB).

---

## 3. Publication & Boundary Policy Compliance

1. **Local Boundary:** All Phase 3 repair work is committed locally on branch `manav` and left unpushed for independent review.
2. **Phase 2 Status:** Week 1 Phase 2 is already accepted and published at `4058b2d` on `origin/manav` and `origin/main`.
3. **Phase 4 Guard:** Phase 3 halts cleanly at the extraction milestone (`status = 'processing'`). No sectioning, chunking, or premature `'ready'` transitions have been added.

---

**FINAL VERDICT: VERDICT: PASS**
