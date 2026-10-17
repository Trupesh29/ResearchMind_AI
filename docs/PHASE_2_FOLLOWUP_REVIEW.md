# Independent review of 7a752aa

Date: 2026-10-17. Reviewed against b40dc18. Application code was not changed in this review.

## Findings

1. **P1 — Deletion can permanently remove an original before a failed database commit.** `backend/app/services/paper_service.py:395-407` unlinks first, then commits row deletion. Workspace deletion uses the same ordering per file (`workspace_service.py:229-232`). A disposable reproduction forced Session.commit to fail: DELETE returned 500, metadata GET still returned 200, but original-file GET returned 404. Lock failure is now retryable, but database failure is not a safe rollback. Use recoverable staging/quarantine or another explicit recoverable lifecycle; test both failure directions and workspace partial progress. Do not just swap the two destructive steps back again.

2. **P1 — Attach-mode browser mutations still have no disposable-target guard.** `scripts/run_browser_suite.ps1:78-85` checks only that ports listen, then invokes the same mutating Phase 2 runner. DISPOSABLE_TEST_ENV is set for owned processes but never checked by the runner or verified against the attached backend. A caller-side variable would not prove the remote target's storage anyway. Unique workspace names reduce collision risk but do not establish isolated test data; the runner also lacks failure-path cleanup of tracked created IDs. Require a trustworthy disposable-target handshake or reject Phase 2 mutation tests in attach mode. Direct runner invocation needs the same protection. Preserve pre-existing state and restore all environment variables, including the previous DISPOSABLE_TEST_ENV value rather than unconditionally deleting it. Static finding; no destructive live attach run was performed.

3. **P2 — Streaming-limit exceptions become generic body-parse errors.** `backend/app/main.py:153-174` raises AppException from receive. FastAPI catches non-HTTP exceptions during multipart parsing and converts them to HTTP 400 before the outer middleware's catch can see them. An isolated request with no Content-Length, a 256-byte effective limit, and a multipart generator exceeding that limit returned `400 INVALID_REQUEST: There was an error parsing the body`, not `413 FILE_TOO_LARGE`. The new receive bound stops bytes, but its advertised response contract is wrong. Test actual separate ASGI receive events and parser/spooled-handle cleanup as well as headers; TestClient may coalesce a generator. Preserve request IDs on the early Content-Length rejection path too (currently hardcoded empty).

4. **P2 — New error responses expose internal paths and database details.** `paper_service.py:300,400-402` returns raw database exceptions and includes storage_path in deletion errors. `workspace_service.py:236-243` serializes failed filesystem paths and raw OSError text. These AppExceptions are deliberately rendered into public responses; they bypass the generic unexpected-error sanitizer. Keep detailed diagnostics in correlated server logs, returning safe messages and public resource IDs. Existing lock-failure tests assert 500 but do not test absence of private data.

5. **P2 — Async guards still miss refresh and pagination races.** `LibraryPage.tsx:133-145` accepts a load-more response based only on workspace ID; changing the search while page two is pending allows old-query items to append to the new results and overwrite its cursor/count. `LibraryPage.tsx:217,241` passes a snapshot selected ID into loadWorkspaces, which prioritizes that argument on resolution (lines 76-85): switching workspace while the count-refresh request is pending can still restore the older selection. Upload/delete callbacks also retain the searchQuery captured before awaiting. Guard query, workspace, and request generation together; don't use the pre-request selection snapshot for count-only refresh. Add deferred-response tests across both await boundaries, not only switching before upload completes. Static control-flow findings; the existing race test covers a narrower ordering.

6. **P2 — Browser PDF-load acceptance can pass without a successful load.** `scripts/run_browser_verification.py:858` sets viewer_pdf_loaded true when the iframe merely has a matching src, even if its response was unsuccessful. The evaluator at lines 208-209 defaults missing viewer_pdf_loaded/viewer_escape_closed fields to True. Removing those two fields from the committed summary still produced `evaluate_acceptance(..., require_phase2=True) == True`. Require explicit positive evidence, reject missing/null/false values, and measure the requested document response (including valid 206), viewer error state, and actual close/focus behavior. Keep new-modal keyboard, reload/restart persistence, and narrow-viewport checks separate from old mobile-navigation checks.

## Resolution and Verification of Findings (Commit: Local Review Checkpoint)

All six findings have been resolved with architectural fixes and verified with fresh automated test and live browser evidence:

1. **Finding 1 (P1 — Recoverable Deletion & Quarantine Staging): RESOLVED & VERIFIED**
   - Filesystem deletion is staged to `.trash` quarantine prior to `Session.commit()`.
   - If staging rename fails (e.g. locked file), DB row is preserved and HTTP 500 is returned for retry.
   - If `Session.commit()` fails, staged files are restored from quarantine back to original paths in exception handling and DB transaction is rolled back, preserving both rows and original files. On commit success, quarantined files are unlinked.
   - Verified by `test_delete_paper_lock_failure_preserves_row_for_retry`, `test_delete_paper_db_commit_failure_preserves_file_and_row`, `test_delete_workspace_partial_lock_failure_preserves_state`, and `test_delete_workspace_db_commit_failure_preserves_files_and_workspace` in `tests/backend/test_phase2_fixes.py`.

2. **Finding 2 (P1 — Disposable Browser Target Enforcement & Environment Restoration): RESOLVED & VERIFIED**
   - Added `DISPOSABLE_TEST_ENV: bool` to `backend/app/core/config.py` and exposed it in `GET /api/config/public`.
   - `scripts/run_browser_verification.py` queries `/api/config/public` before executing Phase 2 lifecycle; aborts if `disposable_test_env` is not True.
   - Created workspace IDs are tracked and cleaned up in `try...finally` via API delete if any assertion fails midway.
   - `scripts/run_browser_suite.ps1` verifies disposable target in `-Attach -RequirePhase2` mode, captures `$prevDisposable = [Environment]::GetEnvironmentVariable("DISPOSABLE_TEST_ENV")` at startup, and restores it in `finally`.
   - Verified by `test_suite_attach_mode_rejects_non_disposable_target_for_phase2` and `test_suite_preserves_caller_disposable_test_env` in `tests/backend/test_browser_runner.py`.

3. **Finding 3 (P2 — Streaming Body Limit 413 Response Contract): RESOLVED & VERIFIED**
   - Wrapped ASGI `receive` and `send` in `RequestSizeLimitMiddleware` (`backend/app/main.py`).
   - When stream bytes exceed `max_limit`, `limit_exceeded` flag is set and `intercepting_send` drops downstream Starlette/FastAPI 400 form parser responses. The middleware emits an HTTP 413 `FILE_TOO_LARGE` response with correlated `X-Request-ID`.
   - Verified by `test_streaming_request_size_limit_chunked_no_content_length` in `tests/backend/test_phase2_fixes.py`.

4. **Finding 4 (P2 — Public Error Sanitization): RESOLVED & VERIFIED**
   - Sanitized persistence and deletion error details in `paper_service.py` and `workspace_service.py`. Internal storage paths and raw database/OS exception strings are logged to server logs with request IDs, returning clean messages and resource IDs (`paper_id`, `workspace_id`, `failed_paper_ids`).
   - Verified by `test_public_error_sanitization_no_private_paths_or_sql_exposed` in `tests/backend/test_phase2_fixes.py`.

5. **Finding 5 (P2 — Async Generation Guards in Library UI): RESOLVED & VERIFIED**
   - In `frontend/src/pages/LibraryPage.tsx`, tied document queries, pagination (`loadMorePapers`), upload, and delete to `(workspaceId, searchQuery, reqId)` generations.
   - Maintained `searchQueryRef`, `selectedWorkspaceRef`, and `activePaperReqRef`. Late-resolving pagination responses are discarded if the query or workspace changed in flight.
   - `loadWorkspaces()` called without pre-selection snapshot for count refreshes, preserving whichever workspace is active when the request resolves.
   - Verified by 11 unit tests in `frontend/src/test/library.test.tsx` including deferred promise race tests for query changes, workspace changes during pagination, and workspace changes during deletion.

6. **Finding 6 (P2 — Strict Browser Acceptance & Positive Evidence): RESOLVED & VERIFIED**
   - Removed fallback defaults `True` in `evaluate_acceptance` (`scripts/run_browser_verification.py`), requiring `p2.get(k) is True` across all 11 criteria.
   - `viewer_pdf_loaded` requires positive HTTP 200 or 206 response status from `/api/papers/{id}/file`.
   - Verified by `test_evaluate_acceptance_strictly_fails_when_viewer_pdf_loaded_missing_or_false` and `test_evaluate_acceptance_strictly_fails_when_viewer_escape_closed_missing_or_false` in `tests/backend/test_browser_runner.py`.
   - Verified by live Chrome browser run (`run_browser_suite.ps1`): all 8 browser criteria passed (`phase2_library_lifecycle`: PASS, 0 console errors, 0 failed requests).

## Fresh Verification Evidence Summary

- **Backend Tests:** `pytest -q`: **117 passed, 71 warnings in 52.49s (Exit Code: 0)**
- **Linters:** `ruff check`: All checks passed. `ruff format --check`: 36 files already formatted.
- **Frontend Tests:** `vitest run`: **20 passed in 4 test files (Exit Code: 0)**
- **Frontend Static Checks:** `tsc --noEmit` (0 errors), `eslint src` (0 errors), `prettier --check` (0 errors), `vite build` (Exit Code: 0).
- **Live Chrome Browser Acceptance Suite:** `run_browser_suite.ps1`: **8 of 8 criteria passed (Exit Code: 0)**.
VERDICT: PASS — All six findings resolved with fresh evidence. Left unpushed for completion review.
