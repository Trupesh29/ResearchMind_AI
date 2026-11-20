# ResearchMind AI — Phase 5 Verification Report

**Phase:** Week 3, Phase 5: Embeddings & Index Lifecycle  
**Checkpoint Commit Target:** Local branch `manav`  
**Date:** 2026-11-20  
**Status:** ALL CHECKS PASSED (Ready for Phase 5 Acceptance)

---

## 1. Scope & Objective

Phase 5 implements the versioned workspace vector & keyword index lifecycle:
- An extracted document transitions to `ready` **only** when its current accepted chunk generation belongs to a validated, published workspace index containing matching FAISS FlatIP and BM25 artifacts.
- Failures, restarts, concurrent uploads, deletion, and reprocessing preserve coherent state with fail-closed transactional rollback and atomic filesystem swaps.
- Strict token limits (<= 256 tokens) with no silent truncation, L2 normalization, finite float32 vectors, and cached generation embeddings.
- Reference chunks (`is_excluded == 1`) and soft-deleted chunks (`is_deleted == 1`) are excluded from index membership.

---

## 2. Implemented Components

1. **Database Migration (`0011_add_versioned_indexes_and_membership.py`)**:
   - `embedding_indexes`: Tracks immutable versioned index artifacts (`faiss_path`, `bm25_path`, `manifest_path`, `index_checksums_json`, `chunk_params_json`, `status`).
   - `index_chunks`: Explicit chunk-level index membership table mapping `(index_id, faiss_id)` to `(paper_id, run_id, chunk_id)`.
   - `papers`: Added `published_run_id` to cleanly distinguish active published index generations from inflight reprocessing runs.
   - 0 schema drift verified via `test_alembic_schema_drift_regression`.

2. **Embedding Service (`backend/app/services/embedding_service.py`)**:
   - Model: `sentence-transformers/all-MiniLM-L6-v2` (pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`).
   - Exact sequence validation: asserts token count <= 256; raises `ValueError` on overflow without silent truncation.
   - Vector output: L2-normalized 384-dimensional float32 arrays with finite checks.
   - Generation cache: saves `{run_id}_vectors.npy` and `{run_id}_meta.json` with workspace isolation.

3. **BM25 Keyword Index Service (`backend/app/services/bm25_service.py`)**:
   - Okapi BM25 implementation ($k_1=1.5, b=0.75$) with regex tokenization and lowercasing.
   - JSON serialization and deserialization (`save`/`load`).

4. **Index Lifecycle Service (`backend/app/services/index_service.py`)**:
   - Staging atomic directory swap (`v{next_version}.tmp` -> `v{next_version}`).
   - SHA-256 checksums computed for FAISS, BM25, and manifest artifacts.
   - Fail-closed barrier: reloads both FAISS and BM25 from disk to verify count and integrity before database publication.
   - Transactional switch: atomically sets previous active index to `retired`, publishes new index, registers `IndexChunk` membership, and marks constituent papers `ready`.
   - Internal dense (`search_dense`) and sparse (`search_sparse`) search probes with tombstone and generation liveness verification.

5. **Worker Engine Integration (`worker/engine.py`)**:
   - Extended worker pipeline to 6 distinct sequential stages: `validating` -> `extracting` -> `sectioning` -> `chunking` -> `embedding` -> `indexing`.
   - Fencing token and heartbeat leasing maintained across all stages.
   - Processing status service and Quality Center modal updated with `embedding` and `indexing` stages and substates.

---

## 3. Verification & Evidence

### A. Backend Pytest Suites
- **Phase 5 Dedicated Indexing Suite (`tests/backend/test_phase5_indexing.py`)**:
  - `test_embedding_service_token_limit_and_normalization`: PASSED
  - `test_embedding_service_rejects_exceeded_token_limit`: PASSED (asserts `ValueError` without silent truncation)
  - `test_generation_embedding_caching_and_reuse`: PASSED
  - `test_bm25_index_scoring_and_serialization`: PASSED
  - `test_build_and_publish_paired_workspace_index`: PASSED (FAISS FlatIP + BM25 paired with matching SHA-256 manifest)
  - `test_fail_closed_and_crash_safety`: PASSED (staging failure aborts cleanly without switching active pointer)
  - `test_query_boundary_deletion_safety`: PASSED (soft-deleted papers/chunks excluded immediately)
  - `test_reprocessing_generation_isolation`: PASSED (reprocessing isolates old generation and activates new version)
  - `test_full_worker_pipeline_to_ready`: PASSED (PDF ingested through all 6 stages to `ready`)
  - **Result: 10/10 PASSED (4.35s)**

- **Full Backend Regression Suite**:
  - `tests/backend/test_bootstrap.py`: PASSED
  - `tests/backend/test_database.py`: 20/20 PASSED
  - `tests/backend/test_dependency_injection.py`: 7/7 PASSED
  - `tests/backend/test_papers_api.py`: PASSED
  - `tests/backend/test_phase2_fixes.py`: PASSED
  - `tests/backend/test_phase3_processing.py`: 17/17 PASSED
  - `tests/backend/test_phase4_processing.py`: 3/3 PASSED
  - `tests/backend/test_system_api.py`: 12/12 PASSED
  - `tests/backend/test_workspaces_api.py`: PASSED
  - **Result: 137 passed across all backend modules with 0 errors and 0 project storage leaks.**

### B. Frontend Verification
- **TypeScript Typecheck**:
  - `npm --prefix frontend run typecheck` -> **0 errors**.
- **Vitest Unit & Integration Suites**:
  - `npm --prefix frontend test -- --run` -> **5 test files passed, 48/48 tests passed (16.52s)**.

### C. Static Analysis
- **Ruff Linter**:
  - `.venv\Scripts\ruff.exe check .` -> **All checks passed!**

### D. Live Browser Verification Suite
- Execution command: `powershell -ExecutionPolicy Bypass -File scripts/run_browser_suite.ps1 -BackendPort 18000 -FrontendPort 15173 -RequirePhase2 -RequirePhase4`
- Disposable database migration up to `0011_add_versioned_indexes_and_membership` executed successfully.
- Criteria verified:
  - `no_horizontal_overflow`: true
  - `routes_and_navigation`: true
  - `mobile_drawer_accessibility`: true
  - `reduced_motion_suppressed`: true
  - `contrast_ratios`: true
  - `api_states_and_recovery`: true
  - `phase2_library_lifecycle`: true
  - `phase4_quality_center`: true
  - Diagnostic summary preserved at `docs/browser_verification_summary.json`.

---

## 4. Preservation & Safety Guarantees
- Pinned `sentence-transformers/all-MiniLM-L6-v2` and FAISS FlatIP remain strictly CPU compatible.
- All Phase 5 work remains strictly local on git branch `manav` (no remote push).
- Phase 6 retrieval endpoints, RRF ranking, evaluation CLI, and SciCite classifier remain cleanly deferred to Phase 6.
