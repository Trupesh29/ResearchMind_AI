# PHASE_3_VERIFICATION.md — ResearchMind AI

> Phase 3 Follow-up Review Repair Checkpoint (2026-10-18): Repairs the independent follow-up review findings (`docs/PHASE_3_FOLLOWUP_REVIEW.md`, F1–F6) from commit `bd78083`. All defects converted into regression acceptance tests in `tests/backend/test_phase3_processing.py` and `tests/backend/test_database.py`. Both review probes (`scripts/review_phase3_probe.py` and `scripts/review_phase3_followup_probe.py`) pass 100%. Current status: Local repair complete on branch `manav`; unpushed pending independent review. Phase 2 remains accepted and published at `4058b2d` on `origin/manav` and `origin/main`.

## Week 2, Phase 3: Persistent Processing and PDF Extraction (Follow-up Review Repair)

**Date:** 2026-10-18
**Scope:** Ingestion pipeline vertical slice repair — Structured provenance backward compatibility (F1), immutable migration history with forward revision 0004 (F2), latest attempt status computation and generation staleness tracking (F3), heartbeat expiration update predicate (F4), generic fallback error sanitization (F5), and real subprocess worker recovery + visual overlay evidence (F6).
**Execution Environment:** Windows PowerShell / Python 3.14.2 / Node.js 20+
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

---

## 2. Resolution of Follow-Up Review Findings (F1–F6)

| Finding | Defect Description | Implementation Resolution | Acceptance Test & Verification Evidence |
|---|---|---|---|
| **F1** | Structured provenance schema rejected legacy string sources and broke HTTP endpoints | Created `ProvenanceDetail` model; typed `metadata_source` as `dict[str, ProvenanceDetail | str] | None` on backend schemas and frontend types. Preserves evidence while ensuring backward-compatibility with legacy string sources. | `test_f1_structured_provenance_and_http_contracts`: Uploaded PDF with structured provenance returns 200 on `/api/papers/{id}` and `/api/papers?workspace_id=...` with evidence intact; legacy paper with string sources returns 200. Probe: `STRUCTURED_PROVENANCE_SERIALIZES True`, `PAPER_HTTP_STATUS 200`, `LIBRARY_HTTP_STATUS 200`. |
| **F2** | Migration `0003` was rewritten in place, breaking migration history and failing on populated upgrades | Restored `0003` to exact immutable commit `2ef4ec2`. Created forward migration `0004_add_generation_and_fencing_controls` inspecting existing schema, backfilling `current_run_id`, `published_run_id`, and `pages.run_id`, reconciling duplicate active runs, and adding constraints/indexes safely. | `test_migration_0003_to_0004_data_preservation_and_reconciliation`: Tested historical 0003 databases, Week 1 databases, and empty databases without dropping records. Probe: `UPGRADE_HAS_CURRENT_RUN True`, `UPGRADE_REVISION 0004_add_generation_and_fencing_controls`. |
| **F3** | Status computed from oldest failed attempts; retries stuck on failed; pages had no staleness indicators | Status computation updated to evaluate each stage by latest attempt (`max(attempt)`); retried jobs do not remain stuck on failed; added `run_id`, `current_run_id`, and `published_run_id` to status response, and `run_id` + `is_stale` to pages and block responses. | `test_f3_retry_history_and_generation_staleness`: Verifies status is `processing` attempt 2 while retry is queued/running, and pages report `is_stale=True` when a newer run is active. Probe: `SUCCESS_AFTER_RETRY_PUBLIC_STATUS processing 1 None`. |
| **F4** | Recovery UPDATE had read-then-write race against heartbeats renewed right after SELECT | Added `heartbeat_at < threshold_iso` to the atomic recovery `UPDATE ... WHERE id = :id AND status = 'running'` statement. Rowcount checks determine whether the lease was actually expired or actively renewed. | `review_phase3_followup_probe.py`: Probe tests selection -> concurrent heartbeat renewal -> recovery attempt; verifies refreshed job is not killed: `REFRESHED_LEASE_RECOVERY [(1, 'running')]`. |
| **F5** | Regex error cleanup leaked unexpected exception traces, UNC paths, and internal tokens | Overhauled `sanitize_error_message` with an explicit category allowlist (not found, permission denied, invalid pdf, size/hash mismatch, unsupported text, lost lease, lease expired) and generic safe fallback: `"An error occurred during document processing."` | `test_r4_public_error_sanitization_no_paths_exposed`: Tests Windows drive paths, UNC paths (`\\storage\share`), Unix paths (`/var/log/...`), and private tokens (`token=secret-bearer-999`). Probe: `UNKNOWN_ERROR_SANITIZED An error occurred during document processing.` |
| **F6** | Verification claims lacked evidence (liveness poll shorter than lease; no real subprocess kill; no visual overlays) | Extended liveness test to poll after the 2.0s lease timeout while work remains active; verified real worker subprocess kill and recovery with independent worker; generated and asserted visual pixmap overlays for 0/90/180/270 rotated and cropped pages. | `test_r2_lease_liveness_and_worker_kill_recovery`: Polling worker cannot steal active job after 2.2s; subprocess victim killed and recovered by independent worker. `test_r5_rotated_and_cropped_geometry_consistency`: Generated and verified overlay pixmaps for all 4 rotations and cropped page. |

---

## 3. Automated Test Suite Results

### 3.1 Backend Pytest (All 16 Phase 3 Tests Passed)

Command:
```powershell
python -m pytest tests/backend/test_phase3_processing.py -v
```

Summary:
- Total Phase 3 tests: 16 passed (100%)
- `test_phase3_migrations_preserve_data_and_schema` (PASSED)
- `test_extraction_engine_and_quality_heuristics` (PASSED)
- `test_all_image_document_fails_with_explicit_unsupported_error` (PASSED)
- `test_worker_atomic_claim_and_fencing` (PASSED)
- `test_reprocess_conflict_and_generation_consistency` (PASSED)
- `test_deletion_during_processing_drops_results_cleanly` (PASSED)
- `test_api_inspection_and_foreign_ownership_security` (PASSED)
- `test_r1_concurrent_job_claim_race` (PASSED)
- `test_r2_lease_liveness_and_worker_kill_recovery` (PASSED)
- `test_r3_concurrent_reprocess_conflict_and_generation_isolation` (PASSED)
- `test_r4_public_error_sanitization_no_paths_exposed` (PASSED)
- `test_r5_rotated_and_cropped_geometry_consistency` (PASSED)
- `test_r6_metadata_provenance_and_clean_heuristics` (PASSED)
- `test_r7_attempt_history_preservation` (PASSED)
- `test_f1_structured_provenance_and_http_contracts` (PASSED)
- `test_f3_retry_history_and_generation_staleness` (PASSED)

### 3.2 Database Migration & Schema Drift Suite (14 Passed)

Command:
```powershell
python -m pytest tests/backend/test_database.py -v
```
Summary:
- 14 passed (100%), including `test_alembic_schema_drift_regression` (0 diffs), `test_upgrade_populated_database_preserves_records`, and `test_migration_0003_to_0004_data_preservation_and_reconciliation`.

### 3.3 Diagnostic Verification Probes

1. **Original Probe (`scripts/review_phase3_probe.py`):**
```
CLAIM_WINNERS 1 DISTINCT_TOKENS 1
REPROCESS_ACCEPTED ['processing', 409] ACTIVE_RUNS 1
PUBLIC_ERROR An error occurred during document processing.
ROTATION 90 SIZE 792.0 612.0 BBOX [88.71, 72.0, 103.83, 290.9]
```
Exit code: 0.

2. **Follow-up Probe (`scripts/review_phase3_followup_probe.py`):**
```
UPGRADE_HAS_CURRENT_RUN True
UPGRADE_REVISION 0004_add_generation_and_fencing_controls
STRUCTURED_PROVENANCE_SERIALIZES True
PAPER_HTTP_STATUS 200
LIBRARY_HTTP_STATUS 200
REFRESHED_LEASE_RECOVERY [(1, 'running')]
SUCCESS_AFTER_RETRY_PUBLIC_STATUS processing 1 None
UNKNOWN_ERROR_SANITIZED An error occurred during document processing.
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
