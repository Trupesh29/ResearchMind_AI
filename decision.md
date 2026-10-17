# ResearchMind AI decisions

Updated: 2026-10-17. Scope: Week 1 Phase 2 review and publication gate.

## Current review and publication status

Phase 2 corrective repair loop completed. All eight findings from `docs/PHASE_2_REVIEW.md` (e5367c9) have been resolved with regression tests, static checks, and live browser verification on disposable storage. Phase 1 remains published on remote main at `24eadea`. This repaired Phase 2 checkpoint is committed locally and left unpushed for completion review per user instructions.


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


## D007 - Phase 2: Workspace Management, PDF Ingestion, Streaming & Deletion Cascade

1. **Workspace Multi-tenancy & Ownership:** Every workspace operation (`/api/workspaces`) and nested document operation (`/api/papers`) strictly scopes queries by `current_user.id`. Foreign or non-existent IDs return controlled 404s without data leakage. Workspace names are trimmed, validated (1–100 chars), and unique per user (HTTP 409 on collision).
2. **Tripartite Batch PDF Ingestion:** `POST /api/papers` consumes `multipart/form-data`, validates magic bytes (`%PDF-`), stream-calculates SHA-256 hashes, verifies openability and page counts with PyMuPDF, and prevents duplicate uploads within the same workspace (while allowing identical hashes across distinct workspaces). Returns HTTP 202 Accepted with tripartite feedback arrays: `papers`, `duplicates`, and `rejected`.
3. **Document Status Lifecycle:** Per Week 1 Phase 2 specifications, all uploaded papers remain in `status = 'uploaded'`. No mock background workers or premature transitions to `'ready'` are performed. Full processing pipelines (OCR, chunking, embeddings) remain deferred to future phases.
4. **Safe Original PDF Streaming:** `GET /api/papers/{id}/file` serves original document bytes directly from isolated storage (`DATA_DIR/pdfs/{paper_id}.pdf`) with RFC 6266 / RFC 5987 compliant UTF-8 Content-Disposition headers and RFC 9110 HTTP Byte Range support (HTTP 200, 206 Partial Content, 416 Range Not Satisfiable), clipping end boundaries exceeding file length. Storage paths are never leaked in API payloads or error details.
5. **Permanent Deletion Cascade & Failure Recovery:** `DELETE /api/papers/{id}` and `DELETE /api/workspaces/{id}` return HTTP 204 No Content. Deletion cleans physical files before committing row deletion, ensuring shared files across other workspaces (if any) are never deleted prematurely, and preserves database rows and raises HTTP 500 on filesystem lock failures so deletion remains safely retryable.
6. **Accessible Frontend Dialogs & Micro-interactions:** Built `ConfirmDialog` implementing ARIA `alertdialog` semantics with strict focus trapping, Escape cancellation, and focus restoration to the triggering element. Built `PdfViewerModal` with embedded iframe and direct download action.
7. **Upload Limits, UI Pagination & Selection Race Guards:** Enforced request body limits (250 MB) before multipart parsing and batch limits (20 files). Frontend `PaperList` consumes cursor-based pagination and search debouncing (250ms), and `LibraryPage` maintains ref-safe workspace tracking to ensure late-completing mutations do not hijack the user's active workspace selection.
