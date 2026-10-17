# Phase 2 review — e5367c9 (Repaired in subsequent commit)

> Latest independent review (2026-10-17, commit 7a752aa): **NOT ACCEPTED**. The historical repair claims below are superseded by the follow-up findings in `docs/PHASE_2_FOLLOWUP_REVIEW.md`. Phase 2 remains local. Both remote main and manav were verified at Phase 1 checkpoint 24eadea.

Reviewed 2026-10-17. Phase 2 corrective repair loop completed. All eight findings from review e5367c9 have been resolved and verified with fresh regressions and live-browser evidence.

## Findings & Resolutions

1. **P1 — Browser mutation tests use the real default database/storage.**
   - *Status:* **RESOLVED**
   - *Resolution:* `scripts/run_browser_suite.ps1` now provisions an isolated, disposable directory under `.temp/browser_test_<guid>` and sets `DATA_DIR`, `DATABASE_URL`, and `DISPOSABLE_TEST_ENV=1`. Migrations (`alembic -c backend/alembic.ini upgrade head`) and user bootstrap are executed against the disposable target. `finally` block cleans up the disposable directory and restores process environment variables. `scripts/run_browser_verification.py` creates unique workspace identifiers (`E2E Workspace <uuid>`), tracks created resources, validates PDF viewer iframe 200 response and Escape key dialog closure, and deletes only resources created by the specific run. Sentinel and pre-existing workspaces remain untouched.

2. **P1 — Upload limits run after multipart spooling.**
   - *Status:* **RESOLVED**
   - *Resolution:* Added `MAX_BATCH_FILES = 20` and `MAX_REQUEST_BODY_BYTES = 250MB` settings in `backend/app/core/config.py`. Added `RequestSizeLimitMiddleware` in `backend/app/main.py` which inspects `Content-Length` and streams chunks to enforce request-level byte limits before or during multipart parsing, returning HTTP 413 `FILE_TOO_LARGE`. `backend/app/api/papers.py` enforces batch file count limits and closes upload file handles in a `try...finally` block.

3. **P2 — Failed database writes orphan published PDFs.**
   - *Status:* **RESOLVED**
   - *Resolution:* `backend/app/services/paper_service.py` (`process_paper_upload`) wraps `db.commit()` to unlink the published PDF on any commit failure (such as `OperationalError`), preventing orphaned files. If the commit succeeds but `refresh()` fails, the file and committed row are preserved. Duplicate responses are only returned if a real winning row exists in the database.

4. **P2 — Failed physical deletion still returns success.**
   - *Status:* **RESOLVED**
   - *Resolution:* In `backend/app/services/paper_service.py` (`delete_paper`) and `backend/app/services/workspace_service.py` (`delete_workspace`), unshared files are unlinked before committing row deletion. If an `OSError` occurs during unlinking (e.g., file lock), the database transaction is aborted and an `AppException(500)` is raised, keeping database rows intact so the operation and files can be retried.

5. **P2 — Unicode original filenames cannot be viewed.**
   - *Status:* **RESOLVED**
   - *Resolution:* Implemented `format_content_disposition` in `backend/app/services/paper_service.py` adhering to RFC 6266 and RFC 5987 (`filename="<safe_ascii>"; filename*=UTF-8''<url_encoded>`). Applied to both full and ranged responses in `backend/app/api/papers.py`.

6. **P2 — Valid ranges extending past EOF are rejected.**
   - *Status:* **RESOLVED**
   - *Resolution:* In `backend/app/api/papers.py`, range handling clips `end = min(end, file_size - 1)` when `start < file_size` and `end >= file_size` in accordance with RFC 9110 section 14.1.2, returning HTTP 206 Partial Content. Fully unsatisfiable ranges return HTTP 416.

7. **P2 — Pagination is discarded by the UI.**
   - *Status:* **RESOLVED**
   - *Resolution:* Added `listAllWorkspaces` in `frontend/src/api/client.ts`. Updated `frontend/src/pages/DashboardPage.tsx` to aggregate total papers across all workspaces. Added `nextCursor`, `onLoadMore`, pagination footer, and 250ms debounced search to `frontend/src/components/library/PaperList.tsx`. Integrated `loadMorePapers` in `frontend/src/pages/LibraryPage.tsx`.

8. **P2 — Late mutations restore an obsolete workspace.**
   - *Status:* **RESOLVED**
   - *Resolution:* In `frontend/src/pages/LibraryPage.tsx`, added `selectedWorkspaceRef` to track the user's active workspace across async uploads and deletions. Upload and deletion completion callbacks check if the active workspace has changed; if so, they avoid overwriting papers or switching active workspace selection back to the previous workspace.

## Verification and Coverage Evidence

- **Backend Pytest Suite:** 109 passed, 65 deprecation warnings in 41.91s (`tests/backend/test_phase2_fixes.py` covers all 8 regression areas).
- **Frontend Vitest Suite:** 17 passed in 4 test files (`library.test.tsx` includes workspace-switch race test with deferred promises).
- **Static Code Quality:**
  - `ruff check backend tests scripts`: Passed (0 errors).
  - `ruff format --check backend tests scripts`: Passed (36 files formatted).
  - `npm run lint`: Passed (0 errors).
  - `npm run format:check`: Passed (All matched files use Prettier style).
  - `npm run typecheck`: Passed (0 errors).
  - `npm run build`: Production bundle built successfully.
- **Live Chrome Browser Suite:** Executed on isolated disposable database/storage (`.temp/browser_test_*`):
  - 8/8 criteria passed (`no_horizontal_overflow`, `routes_and_navigation`, `mobile_drawer_accessibility`, `reduced_motion_suppressed`, `contrast_ratios`, `api_states_and_recovery`, `clean_operation`, `phase2_library_lifecycle`).
  - Verified PDF iframe loaded HTTP 200, Escape key closed modal, unique workspace lifecycle completed and cleaned up.

## Publication Checkpoint

Phase 1 remains published on remote `main` at `24eadea` and remote `manav` at `51e3071`. This repaired Phase 2 checkpoint is committed locally and left unpushed for completion review per instructions.

VERDICT: PASS — All 8 Phase 2 review findings resolved with fresh test and live-browser evidence. Unpushed for completion review.
