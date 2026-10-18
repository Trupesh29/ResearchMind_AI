# PHASE_3_VERIFICATION.md — ResearchMind AI

> Phase 3 Multi-Generation Preservation Checkpoint (2026-10-18): Resolves finding H1 from `docs/PHASE_3_MULTIRUN_REVIEW.md` starting from application checkpoint `5e168f1` and review checkpoint `f548d00`. Preserves multiple successful page generations (`worker/engine.py:517-562` retention invariant), preventing unique constraint collisions and silent historical relabeling. Repaired `0005_repair_historical_generation_attribution` and added forward migration `0006_preserve_multirun_page_generations` ensuring a compatible upgrade path for databases stopped at 0004 and those already at 0005 without altering immutable 0003. Verified across 154 backend pytest tests, 25 vitest frontend tests, 4 standalone diagnostic probes, and full static checks. Kept Phase 3 strictly local on branch `manav`; unpushed pending independent review. Phase 4 is not started.

## Week 2, Phase 3: Persistent Processing and PDF Extraction (H1 Multi-Generation Preservation Repair)

**Date:** 2026-10-18
**Scope:** Ingestion pipeline vertical slice repair — Resolution of finding H1: preserve multiple successful page generations across reprocess runs; prevent unique constraint collisions and silent relabeling in migrations; provide compatible path for 0004 and 0005 databases via repaired 0005 and forward migration 0006; retain working API, worker recovery, stale-page attribution, and derotated overlay geometry.
**Execution Environment:** Windows PowerShell / Python 3.14.2 / Node.js 20+
**Overall Verdict:** `VERDICT: PASS` (Week 2, Phase 3 H1 Multi-Generation Preservation Checkpoint)

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

## 3. Resolution of Acceptance Review Findings (G1, G2)

| Finding | Defect Description | Implementation Resolution | Acceptance Test & Verification Evidence |
|---|---|---|---|
| **G1** | Historical generation attribution conflated current attempt with retained published pages; databases with failed/queued reprocess B after successful A had pages misattributed to B | Separated `current_run_id` (active/latest attempt) from `published_run_id` (successful extraction run that created the pages). Updated `0004_add_generation_and_fencing_controls` backfill and added forward-compatible migration `0005_repair_historical_generation_attribution` to repair affected databases without resets. If extraction history is ambiguous, pages are preserved under a dedicated `legacy-*` run ID without false attribution to failed runs. | `test_historical_generation_attribution_matrix`: Exhaustively verifies matrix (successful A + failed B, successful A + active B, ambiguous extraction history, duplicate active job reconciliation, and forward-repair of 0004). Acceptance Probe: `BACKFILLED_GENERATIONS ('run-new', 'run-old')`, `PAGE_ASSIGNED_RUN run-old`, `RETAINED_OLD_PAGES_IS_STALE True`. |
| **G2** | Rotated overlay drawing passed visual coordinates to unrotated PDF page, causing double rotation; test only checked file existence | Applied `fitz.Rect(bbox) * page.derotation_matrix` before drawing onto PDF pages with `page.new_shape()`. Added pixel-level text glyph enclosure assertions (`min_rx <= min_bx + 2`, `max_rx >= max_bx - 2`, etc.) and negative controls (omitted derotation / shifted bounding boxes fail) across 0°, 90°, 180°, 270°, and cropped pages. | `test_r5_rotated_and_cropped_geometry_consistency`: Red overlay pixels tightly enclose black text glyphs for all 4 rotations; blue overlay encloses cropped text. Negative controls verify un-derotated and shifted boxes fail enclosure. Acceptance Probe: `OVERLAY artifacts/review_phase3_geometry/test_overlay_rotation90.png` verified via visual inspection. |

---

## 4. Resolution of Multi-Generation Review Finding (H1)

| Finding | Defect Description | Implementation Resolution | Acceptance Test & Verification Evidence |
|---|---|---|---|
| **H1 (P1)** | `0005_repair_historical_generation_attribution.py` executed a blanket `UPDATE pages SET run_id = :pub` which collapsed valid historical generations (`worker/engine.py:517-562` retention invariant), raised unique constraint violations when page numbers overlapped (e.g. Run A page 1 + Run B page 1), and silently relabeled non-overlapping historical pages | Repaired `0005` to preserve pages belonging to any valid successful extraction run (`stage = 'extracting' AND status = 'succeeded'`). Pages belonging to valid runs are never altered. Misattributed or unassigned pages (pointing to failed/queued/running jobs or NULL) are safely assigned to `published_run_id` only if no page with that number exists; otherwise, assigned to an isolated `legacy-*` run to guarantee constraint safety. Created forward migration `0006_preserve_multirun_page_generations` ensuring databases stopped at 0004 and those already at 0005 advance cleanly to head without altering immutable 0003 or assuming an already-recorded migration reruns. | `scripts/review_phase3_multirun_probe.py`: `MULTIRUN_UPGRADE_SUCCEEDED`, `PAGES [('page-A', 'A', 'A'), ('page-B', 'B', 'B')]`, `REVISION 0006_preserve_multirun_page_generations`. `test_multirun_page_generation_preservation_matrix`: Verifies overlapping pages survive, non-overlapping pages remain distinct, active/failed replacement runs serve correct stale flags, ambiguous history is preserved, and unique constraint is enforced. `test_worker_multirun_migration_preservation`: Verifies a real worker-produced reprocess database upgrades and downgrades cleanly retaining all generations. |

### Compatibility Path and Historical Limitation
- **Databases stopped at 0004:** Upgrade executes repaired `0005` followed by `0006`. Valid multi-generation pages survive with their exact row identities, texts, and run IDs.
- **Databases already at 0005:** Upgrade executes `0006` directly to reach head. Any remaining orphan or misattributed pages are safely reconciled.
- **Historical limitation:** For databases that had previously applied the buggy 0005 on non-overlapping pages (e.g. Run A had page 1, Run B had page 2), the blanket update had overwritten `pages.run_id` in place from `'run-A'` to `'run-B'`. Because SQLite's `pages` table does not maintain an audit history log of previous `run_id` values, that prior label cannot be reconstructed without external database backups. Going forward, both repaired 0005 and 0006 guarantee that valid multi-run page identities remain preserved.

---

## 5. Automated Test Suite Results

### 5.1 Backend Pytest (All 154 Tests Passed)

Commands:
```powershell
python -m pytest tests/backend/test_phase3_processing.py -v
python -m pytest tests/backend/test_database.py -v
python -m pytest tests/backend/test_system_api.py -v
python -m pytest -v
```
Summary:
- `test_phase3_processing.py`: 17 passed (100%), including `test_reprocess_conflict_and_generation_consistency` and `test_worker_multirun_migration_preservation`.
- `test_database.py`: 17 passed (100%), including `test_historical_generation_attribution_matrix`, `test_multirun_page_generation_preservation_matrix`, and `test_clean_install_and_already_0005_upgrade`.
- `test_system_api.py`: 12 passed (100%), including `test_ready_endpoint_healthy` verifying head revision `0006_preserve_multirun_page_generations`.
- Full backend suite: **154 passed**, 116 warnings in 108.02s.

### 5.2 Diagnostic Verification Probes

1. **Multi-Run Probe (`scripts/review_phase3_multirun_probe.py`):**
```
MULTIRUN_UPGRADE_SUCCEEDED
PAGES [('page-A', 'A', 'A'), ('page-B', 'B', 'B')]
REVISION 0006_preserve_multirun_page_generations
```
Exit code: 0.

2. **Original Probe (`scripts/review_phase3_probe.py`):**
```
CLAIM_WINNERS 1 DISTINCT_TOKENS 1
REPROCESS_ACCEPTED [409, 'processing'] ACTIVE_RUNS 1
PUBLIC_ERROR An error occurred during document processing.
ROTATION 90 SIZE 792.0 612.0 BBOX [88.71, 72.0, 103.83, 290.9]
```
Exit code: 0.

3. **Follow-up Probe (`scripts/review_phase3_followup_probe.py`):**
```
UPGRADE_HAS_CURRENT_RUN True
UPGRADE_REVISION 0006_preserve_multirun_page_generations
STRUCTURED_PROVENANCE_SERIALIZES True
PAPER_HTTP_STATUS 200
LIBRARY_HTTP_STATUS 200
REFRESHED_LEASE_RECOVERY [(1, 'running')]
SUCCESS_AFTER_RETRY_PUBLIC_STATUS processing 1 None
UNKNOWN_ERROR_SANITIZED An error occurred during document processing.
```
Exit code: 0.

4. **Acceptance Probe (`scripts/review_phase3_acceptance_probe.py`):**
```
BACKFILLED_GENERATIONS ('run-new', 'run-old')
PAGE_ASSIGNED_RUN run-old
RETAINED_OLD_PAGES_IS_STALE True
OVERLAY artifacts/review_phase3_geometry/test_overlay_rotation90.png
```
Exit code: 0. Visual inspection of overlay image confirms tight bounding around rotated text.

### 5.3 Python Code Quality (Ruff)

Commands:
```powershell
ruff check backend tests scripts worker
ruff format --check backend tests scripts worker
```
Result: All checks passed! 51 files inspected and formatted.

### 5.4 Frontend Verification

Commands:
```powershell
cd frontend
npm test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```
Result:
- Vitest: 4 test files, **25 passed** (100%).
- TypeScript (`tsc --noEmit`): 0 errors.
- ESLint: 0 errors.
- Prettier: All matched files use Prettier code style.
- Vite build: Production bundle generated cleanly (`dist/index.html` 0.99 kB, `dist/assets/index-*.js` 309.64 kB).

---

## 6. Publication & Boundary Policy Compliance

1. **Local Boundary:** All Phase 3 repair work is committed locally on branch `manav` and left unpushed for independent review.
2. **Phase 2 Status:** Week 1 Phase 2 is already accepted and published at `4058b2d` on `origin/manav` and `origin/main`.
3. **Phase 4 Guard:** Phase 3 halts cleanly at the extraction milestone (`status = 'processing'`). No sectioning, chunking, or premature `'ready'` transitions have been added.

---

**FINAL VERDICT: VERDICT: PASS**
