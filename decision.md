# ResearchMind AI decisions

Current independent status (2026-10-17): Review of 42baf49 accepted Week 1 Phase 2. Fresh 133 backend and 25 frontend tests, static/build checks, normal and delayed 8/8 browser runs passed; an ignored-filter negative control was correctly rejected. No corrective prompt is needed. Publish the accepted review checkpoint under the existing user authorization: manav first, verify, then main. This records acceptance and publication policy; remote results must be verified separately.

Historical implementation status (2026-10-17): Finding S1 (search acceptance race and filtering assertions) has been resolved and verified with fresh automated regressions (133 backend pytest, 25 frontend vitest) and live isolated Chrome browser acceptance suites under both normal execution and 750 ms injected route latency. All 8 browser acceptance criteria passed (search_success: true). Findings Q1, Q2, and S1 are fully resolved. Phase 2 is complete, committed locally for independent completion review, and unpushed per Phase 2 policy. Publication order for accepted releases remains manav first, verify, then main.

Historical review (306bd9e): Q1/Q2 passed independent code review and regressions; isolated browser run failed search acceptance (S1). S1 resolution closed the acceptance timing gap with pre-registered response waits, dual PDF fixtures, and positive/negative/empty/cleared verification.

Updated: 2026-10-17. Scope: Week 1 Phase 2 S1 search verification repair and publication gate.

## Historical corrective-checkpoint status

Phase 2 S1 corrective repair loop completed. All findings from `docs/PHASE_2_CURRENT_REVIEW.md` (Q1, Q2, S1) have been resolved with regression tests, static checks, and live browser verification on disposable storage. Phase 1 remains published on remote main at `24eadea`. This complete Phase 2 checkpoint is committed locally and left unpushed for completion review per user instructions.


## D001 - Phase boundaries

Retain the two-phase Week 1 plan. Phase 1 supplies project foundation and app shell; Phase 2 supplies workspace and PDF library lifecycle. The final Phase 1 wrapper finding was accepted in the review of `b084a3f`, recorded in `24eadea`. The user has now authorized moving to Week 1 Phase 2. Follow `docs/PHASE_2_PROMPT.md` for the implementation handoff. This is distinct from ROADMAP.md Phase 2 (Week 2 ingestion).

Phase 2 uploads remain `uploaded`; extraction, indexing, and processing jobs belong to later weeks. Reconcile the API specification's eventual background-job promise with this explicit incremental scope before implementing. Preserve its batch response shape and document the temporary behavior. Original PDF viewing is available before processing; analysis readiness is not implied.

## D002 - Gravitas is agent guidance

Use `F:/dev/.agents/skills/gravitas/SKILL.md` and its `references/reconnaissance.md` for dependency-directed codebase understanding. Optimize agent context consumption through targeted searches, relevant diffs, direct callers, and focused tests. Do not implement Gravitas inside ResearchMind AI or alter product prompts, model context limits, chunk sizes, retrieval, or runtime token budgets for this purpose. No measured token savings are claimed.

Use compact planning, dependency context, impact-based verification, and no delegation by default. Skill-file availability is verified; slash-menu registration and Gravitas runtime/hooks are unverified. Apply the documented workflow manually when the runtime is unavailable, and label project checks as project checks, not Gravitas-owned validators.

## D003 - Schema authority and readiness

Alembic migrations are the executable schema authority. Readiness must verify the database revision against the expected migration head(s), not just table names. Preserve user data during upgrades. ORM defaults, constraints, and schema snapshots must agree with migrations; schema comparison must not silently ignore non-table differences.

## D004 - Consistent dependency injection

Application lifespan, readiness, public configuration, identity/bootstrap, and database dependencies must use the same effective settings/session ownership. Endpoints and dependency helpers must use FastAPI's recognized `Request` type annotation (`request: Request = None`) rather than generic `object`, ensuring FastAPI injects the actual `Request` context at runtime and omits accidental `request` query parameters from OpenAPI schemas. Tests must execute against the real dependency functions (`get_settings` and `get_db`) without masking them via `app.dependency_overrides`. Tests must isolate storage, database files, environment, and lifespan effects and restore injected state in teardown. Never rely only on the main database file's modification time as proof of isolation; SQLite WAL/SHM and storage writes matter too.

## D005 - Completion is evidence-based

Passing unit tests/builds does not establish browser accessibility, clean-install reproducibility, ML inference, or generator connectivity. Keep those statuses separate. No hosted provider or spending budget is approved by this review. Generator live connectivity remains unverified in this review (mock mode active). Browser acceptance is verified via live Google Chrome automation.

## D006 - Browser acceptance enforcement and reproducibility

Browser acceptance verification must not rely on passive logging or unconditional success messages. The browser runner (`scripts/run_browser_verification.py`) must evaluate explicit acceptance criteria, fail with a nonzero exit code on any violation, and preserve diagnostic JSON and screenshots on failure. Simulated network faults must be recorded separately from unexpected runtime errors. The runner must support configurable arguments (`--chrome-path`, `--base-url`, `--output-dir`, `--summary-path`, `--no-headless`) and environment variables, with screenshots kept out of Git via `.gitignore`. Claims of accessibility must be backed by actual measurements (e.g. WCAG contrast ratios, active CSS animation/transition suppression under reduced motion, modal background interaction blocking, and Escape focus restoration) rather than assumptions or emulated queries alone.

## Historical Phase 1 review evidence (before final wrapper correction)

- Backend: 75 passed, 37 warnings with full database and storage isolation (including 32 dedicated unit/regression tests in `tests/backend/test_browser_runner.py` verifying criteria failure conditions, modal ARIA/dialog contracts, dynamic proxy propagation, and owned PID tree lifecycle termination).
- Dependency injection defect resolved: fixed `get_settings(request: Request = None)` and `get_db(request: Request = None)`. FastAPI now injects runtime `Request` instead of treating parameters as optional query inputs. OpenAPI schema confirmed to have zero `request` query parameters across all routes.
- Integration regressions: verified sentinel `app.state.settings` reaches `/api/config/public`, sentinel `app.state.session_factory` bypasses a poisoned global factory on `/api/ready`, `app.state.settings` controls readiness storage and identity checks, normal defaults work without overrides, and state/overrides are restored cleanly.
- Environment sensitivity resolved: `test_settings_defaults` isolated from caller environment via monkeypatch; explicit URL overrides tested separately.
- Frontend: 9 tests passed; lint (`eslint`), formatting (`prettier`), typecheck (`tsc`), and production build (`vite build`) passed with zero errors.
- Python: Ruff lint passed; format check reported 43 files already formatted.
- Readiness migration checks: deep revision comparison implemented covering `up_to_date`, `outdated`, `empty`, `absent`, and `unknown` states; pending migrations return HTTP 503 without mutating database.
- Schema comparison: `papers.status` aligned with `server_default="uploaded"`; Alembic regression check tests all differences (`compare_type=True`, `compare_server_default=True`) with 0 diffs.
- Populated database upgrade: verified upgrade from `0001` to `head` (`0002`) preserves existing records and enforces newly added check constraints on subsequent inserts.
- Browser Acceptance Gate CLOSED & ENFORCED: Automated live browser verification executed via host Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`) driven by Playwright (`F:\dev\apps\scrapling\Scripts\python.exe`) and orchestrated via `scripts/run_browser_suite.ps1`.
  - All 7 acceptance criteria verified and passed: `no_horizontal_overflow` (0px overflow on 768px tablet and 375px mobile), `routes_and_navigation` (landing, dashboard, library, 404 route + recovery button navigation to dashboard), `mobile_drawer_accessibility` (initial focus close button, Tab and Shift+Tab containment, Escape focus restoration, backdrop click closes, background interaction blocked), `reduced_motion_suppressed` (0.00001s transition duration under `prefers-reduced-motion: reduce` vs 0.16s normal), `contrast_ratios` (heading 15.46:1, body text 9.2:1, status pill 15.46:1, button 16.83:1 — all $\ge 4.5:1$), `api_states_and_recovery` (connected status, offline alert banner on simulated failure, clean recovery on retry), and `clean_operation` (0 unexpected console errors, 0 unexpected failed requests).
- Defect remediations:
  - Mobile horizontal overflow on 375px viewport fixed in `Topbar.tsx`, `StatusPill.tsx`, and `globals.css` (reduced to 0px).
  - Heading hierarchy on 404 page fixed in `NotFoundPage.tsx` (`<h1>`).
  - Text contrast on status pill and body/footer text fixed in `StatusPill.tsx`, `Sidebar.tsx`, `DashboardPage.tsx`, and `LibraryPage.tsx` using `--text-secondary` and `--text-primary` (all $\ge 9.2:1$, exceeding WCAG AA 4.5:1).
- Generator status: offline development mode; live provider connectivity unverified (no external API key or spend approved; scheduled for Week 4).

## Status of corrections

1. [COMPLETED] Check actual migration head(s) in readiness and cover old/empty/unknown revisions.
2. [COMPLETED] Fix FastAPI dependency injection signatures (`request: Request = None`) in `get_settings` and `get_db`; remove masking `app.dependency_overrides` from test client; add dedicated integration regressions.
3. [COMPLETED] Unify effective settings/session access and fully restore test overrides; isolate default-settings tests from caller environment; enforce full recursive storage directory snapshot guard.
4. [COMPLETED] Align ORM server defaults and compare all supported schema changes; explicitly test constraints and data-preserving upgrades.
5. [COMPLETED] Strengthen browser runner (`scripts/run_browser_verification.py`) with explicit acceptance evaluation, configurable CLI flags, separate simulated network collections, lazy playwright import, and nonzero exit code on failure.
6. [COMPLETED] Add 30 focused unit/regression tests in `tests/backend/test_browser_runner.py` verifying all criteria failure conditions, modal ARIA/dialog contracts, and process lifecycle behaviors produce a failed verdict and nonzero exit code.
7. [COMPLETED] Execute live Google Chrome browser verification suite; all 7 criteria passed; portable summary saved at `docs/browser_verification_summary.json` with screenshots ignored in `.gitignore`; Browser Acceptance Gate is CLOSED.
8. [COMPLETED] Protect runner suite lifecycle in `scripts/run_browser_suite.ps1` with strict port collision checking, strict port binding in Vite (`strictPort: true`), tracked process tree cleanup via `taskkill.exe /PID $pid /T /F`, removal of broad OS/path sweeps, and explicit non-destructive `-Attach` mode.
9. [COMPLETED] Enforce complete modal dialog & ARIA criteria in `scripts/run_browser_verification.py` (Escape closure, dialog role, aria-modal, trigger state transitions) with 10 dedicated regression tests.
10. [COMPLETED] Propagate selected `-BackendPort` dynamically to Vite dev server via `VITE_BACKEND_URL` in `scripts/run_browser_suite.ps1` and `frontend/vite.config.ts`, verified by real HTTP proxy routing test.
11. [COMPLETED] Strengthen process lifecycle tests with identifiable disposable PIDs and descendant trees, asserting termination of owned processes on startup failure, runner failure, and suite success, and verifying survival of attached servers and unrelated background processes.
12. [COMPLETED] Execute Phase 2 implementation, backend & frontend unit/integration tests, and live Chrome browser acceptance suite; all 8 acceptance criteria satisfied (100% PASS).
13. [COMPLETED] Execute Phase 2 corrective repair loop resolving all 8 review findings: browser test mutation isolation on disposable storage/db, early request body limits (250MB) and batch limits (20 files), atomic/recoverable file and DB lifecycles, RFC 6266 / RFC 5987 Unicode Content-Disposition, RFC 9110 range clipping, UI cursor pagination and debounced search, and async workspace selection race protection; verified by 109 pytest, 17 vitest, static checks, and live Chrome browser suite.
14. [COMPLETED] Execute Phase 2 R1–R3 corrective repair loop: durable quarantine ledger and startup reconciliation (`quarantine_service.py`), decoupled pagination loading ownership and query generation reset (`LibraryPage.tsx`), and top-level workspace ID capture with cleanup failure evaluation (`scripts/run_browser_verification.py`); verified by 125 pytest, 23 vitest, static checks, and live Chrome browser suite.
15. [COMPLETED] Execute Phase 2 Q1/Q2 corrective repair loop: pending-purge retry resource ownership enforcement and conservative ownerless rejection (`quarantine_service.py`, `paper_service.py`, `workspace_service.py`), and adoption of already-quarantined live records ensuring full purge on commit and fallback access on rollback, including mixed workspace cascades; verified by 130 pytest, 23 vitest, static checks, and live Chrome browser suite.




## D007 - Phase 2: Workspace Management, PDF Ingestion, Streaming & Deletion Cascade

1. **Workspace Multi-tenancy & Ownership:** Every workspace operation (`/api/workspaces`) and nested document operation (`/api/papers`) strictly scopes queries by `current_user.id`. Foreign or non-existent IDs return controlled 404s without data leakage. Workspace names are trimmed, validated (1–100 chars), and unique per user (HTTP 409 on collision).
2. **Tripartite Batch PDF Ingestion:** `POST /api/papers` consumes `multipart/form-data`, validates magic bytes (`%PDF-`), stream-calculates SHA-256 hashes, verifies openability and page counts with PyMuPDF, and prevents duplicate uploads within the same workspace (while allowing identical hashes across distinct workspaces). Returns HTTP 202 Accepted with tripartite feedback arrays: `papers`, `duplicates`, and `rejected`.
3. **Document Status Lifecycle:** Per Week 1 Phase 2 specifications, all uploaded papers remain in `status = 'uploaded'`. No mock background workers or premature transitions to `'ready'` are performed. Full processing pipelines (OCR, chunking, embeddings) remain deferred to future phases.
4. **Safe Original PDF Streaming:** `GET /api/papers/{id}/file` serves original document bytes directly from isolated storage (`DATA_DIR/pdfs/{paper_id}.pdf`) with RFC 6266 / RFC 5987 compliant UTF-8 Content-Disposition headers and RFC 9110 HTTP Byte Range support (HTTP 200, 206 Partial Content, 416 Range Not Satisfiable), clipping end boundaries exceeding file length. Storage paths are never leaked in API payloads or error details.
5. **Permanent Deletion Cascade & Failure Recovery:** `DELETE /api/papers/{id}` and `DELETE /api/workspaces/{id}` return HTTP 204 No Content. Deletion cleans physical files before committing row deletion, ensuring shared files across other workspaces (if any) are never deleted prematurely, and preserves database rows and raises HTTP 500 on filesystem lock failures so deletion remains safely retryable.
6. **Accessible Frontend Dialogs & Micro-interactions:** Built `ConfirmDialog` implementing ARIA `alertdialog` semantics with strict focus trapping, Escape cancellation, and focus restoration to the triggering element. Built `PdfViewerModal` with embedded iframe and direct download action.
7. **Upload Limits, UI Pagination & Selection Race Guards:** Enforced request body limits (250 MB) before multipart parsing and batch limits (20 files). Frontend `PaperList` consumes cursor-based pagination and search debouncing (250ms), and `LibraryPage` maintains ref-safe workspace tracking to ensure late-completing mutations do not hijack the user's active workspace selection.

## D008 - Phase 3: Persistent Processing Jobs, PDF Extraction & Worker Architecture

1. **Multi-Stage Processing Model (`ProcessingJob` & `Page`):** Migrated schema via `0003_add_processing_jobs_and_pages.py` adding `processing_jobs` and `pages` tables. Every document processing attempt belongs to a generation identified by `run_id`. Check constraints enforce valid stages (`validating`, `extracting`, `sectioning`, `chunking`, `embedding`, `indexing`, `ready`), valid statuses (`queued`, `running`, `succeeded`, `failed`), positive 1-based page numbers, non-negative char counts, and extraction statuses (`ok`, `partial`, `failed`).
2. **Transactional Upload Enqueuing:** When a new paper is accepted in `paper_service.py`, a `validating` processing job is transactionally created before the database commit. If upload validation or DB insert fails, no orphan job is created. Existing uploaded papers can enter processing via `POST /api/papers/{id}/reprocess`.
3. **Standalone Worker Architecture & Short SQLite Transactions:** The local worker (`worker/engine.py`, `worker/main.py`) operates autonomously outside web requests. To avoid SQLite write-lock contention, worker execution uses short DB transactions: (a) claim job atomically, (b) release DB connection and parse PDF on disk, (c) re-open DB connection to verify fencing token and persist results or transition to the next stage (`extracting`).
4. **Lease Heartbeats & Claim-Token Fencing:** Every claimed job receives a unique UUID `claim_token` and periodic `heartbeat_at` updates. Expired leases (> 60s) are reclaimed by active workers with attempt increments. A worker that recovers after lease expiry is barred from committing stale results by verifying its `claim_token` on write.
5. **PyMuPDF Extraction & Quality Heuristics:** Extracted text preserves 1-based page numbers, raw text, character counts, stable block IDs (`p{page}_b{block}`), coordinates `[x0, y0, x1, y1]` (PDF points with top-left origin convention), and visual page rotation. Metadata provenance distinguishes `pdf`, `text`, and `inferred` sources. Quality heuristics detect `possible_scan` (< 100 characters), `table_unreliable`, and `equations_may_be_missing`. Documents with zero extractable text across all pages fail explicitly with `UnsupportedTextError`.
6. **Inspection & Reprocessing APIs:** Extended `GET /api/papers/{id}/status` with generation run details, per-stage status, attempts, and error messages. Added `GET /api/papers/{id}/pages` and `GET /api/papers/{id}/pages/{page_number}/blocks`. Added `POST /api/papers/{id}/reprocess` returning 202 Accepted, and returning 409 Conflict if a processing run is currently active.
7. **Strict Phase Boundary:** Papers halt in `status = 'processing'` upon completing the `extracting` stage. Sectioning, chunking, Quality Center UI, and embeddings are deferred to Phase 4 and Week 3. No synthetic data or fake `'ready'` transitions are emitted.

## D009 - Phase 3 Corrective Repair: Atomic Claims, Lease Liveness, Generation Isolation & Geometry (R1–R7)

1. **R1: Atomic Claims & Fencing (P1):** Job claiming executes an atomic `UPDATE processing_jobs SET status = 'running', claim_token = :token WHERE id = :id AND status = 'queued'` and checks `rowcount == 1`. Publication requires both `claim_token` match and `paper.current_run_id == run_id`, raising `WorkerFencingViolation` on mismatch.
2. **R2: Lease Liveness via Heartbeat Thread (P1):** A background daemon thread (`LeaseHeartbeat`) periodically renews `heartbeat_at` during PDF hashing and extraction, preventing premature reclamation during long-running tasks. If the lease is lost, extraction publication is aborted cleanly.
3. **R3: Generation Invariant & Isolation (P1):** SQLite partial unique index `uq_active_job_per_paper` on `processing_jobs (paper_id) WHERE status IN ('queued', 'running')` ensures at most one active job exists per paper, rejecting concurrent reprocesses with 409 Conflict. Pages and paper outputs are partitioned by `run_id` (`uq_pages_paper_run_page`); failed generations never overwrite or expose partial output over previous published generations (`paper.published_run_id`).
4. **R4: Public Error Sanitization (P2):** All public error messages returned by `/api/papers/{id}/status` and nested stage histories are stripped of drive letters, filesystem path separators, temporary directories, and sensitive stack traces via `sanitize_error_message()`.
5. **R5: Rotation & Geometry Frame Alignment (P2):** Extracted block bounding boxes from PyMuPDF are transformed by `page.rotation_matrix` when `page.rotation != 0`, normalized, and clamped to `[0, width]` and `[0, height]` to ensure coordinate consistency across 0°, 90°, 180°, and 270° orientations.
6. **R6: Metadata Provenance & Conservative Heuristics (P2):** PDF `creationDate` is no longer promoted to publication year; publication year is only extracted when explicit 4-digit text patterns appear in document text. Unclear header blocks are not treated as author names. Provenance info records rich evidence dictionaries (`source`, `page_number`, `block_id`, `evidence`).
7. **R7: Attempt History Preservation (P2):** When an expired lease is recovered, the expired job is marked `status = 'failed'` with an explicit expiration message and retained, while attempt $N+1$ is inserted as a distinct queued row, preserving complete audit trails across retries.
