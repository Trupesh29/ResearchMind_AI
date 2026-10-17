# Review of c7d6c8e and corrective prompt

Date: 2026-10-17. The fixes improve ordinary commit-failure restoration, disposable-target guarding, streaming 413 responses, error sanitization, and strict viewer criteria. Three actionable issues remain. No application code was changed during this review.

## Findings

### R1 — P2: Quarantine cleanup reports success after failure

`backend/app/services/paper_service.py:430-435` catches final quarantine unlink errors and only logs a warning; `workspace_service.py:273-279` does the same. Once database deletion commits, no row or durable cleanup task remains to drive a retry. An isolated test injected PermissionError only for `.trash` unlink: DELETE returned 204, one complete original remained under `.trash`, and retry returned 404. There is no reconciliation path in the repository.

Keep durable pending-cleanup state and a bounded retry/reconciliation path with truthful failure/pending semantics. Also account for failed rollback rename: those errors are currently logged while the response promises restoration. Reconciliation must distinguish staged originals belonging to live rows from committed deletions awaiting purge; never blindly purge all quarantine files.

### R2 — P2: Superseded pagination leaves Load more disabled

`frontend/src/pages/LibraryPage.tsx:169-170` clears isLoadingMore only when the request is still the active paper generation. A search/workspace change starts loadPapers, advancing that generation, but never resets isLoadingMore. The stale result is ignored, yet its loading state survives and blocks future pagination at line 139.

A disposable Vitest reproduction started deferred page two, changed search, waited for the replacement query (which had another page), then resolved the old request. Load more documents remained disabled. Reset loading ownership on generation changes without allowing stale completion to clear a newer request's loading state. Test stale success/rejection and a subsequent successful current-query Load more.

### R3 — P2: Browser failure cleanup captures the wrong response shape

`scripts/run_browser_verification.py:828` reads `ws_res.json().get("data", {}).get("id")`, but POST /api/workspaces returns the workspace at the top level. An actual isolated API call confirmed body.id exists while that capture expression produces None. Thus the finally block at lines 940-945 skips cleanup after a later browser failure. This leaks resources on disposable attach targets; removing the owned temp database only masks it for owned runs.

Read and validate the actual top-level ID immediately after successful creation. Fail if absent rather than continuing from a visible name. Preserve the ID until deletion is confirmed, check cleanup response status, and report cleanup failures. Inject failure after creation/upload and verify only the run-created ID is deleted while a sentinel workspace survives.

## Resolution of R1–R3 (Corrective Repair Checkpoint)

All three findings from this review have been resolved and verified with fresh evidence:

### R1 Resolution — Durable Quarantine Ledger & Reconciliation
- Created `backend/app/services/quarantine_service.py` introducing a durable ledger (`.trash/<id>.meta.json` + `.tmp`) that tracks operation state (`staged_pending_commit`, `committed_pending_purge`, `rollback_pending_restoration`) with atomic writes via `.meta.tmp`.
- Distinguishes staged files belonging to live records from committed deletions. If physical unlink fails after commit, metadata marks `committed_pending_purge` and API truthfully reports pending purge; subsequent DELETE retries inspect the ledger and return HTTP 204 once unlinked.
- If rollback restoration fails, metadata marks `rollback_pending_restoration` and API truthfully reports recovery quarantine; `paper_service.get_paper_file_path` falls back to `.trash` for live records so original bytes remain accessible.
- Integrated startup reconciliation `quarantine_service.reconcile_quarantine` into `backend/app/main.py` lifespan: restores live files with un-restored quarantined files, purges dead records, and strictly ignores foreign/untracked files.
- Verified in `tests/backend/test_phase2_fixes.py` (staging failure, rollback restoration failure with fallback recovery, final unlink failure returning 500 and retry succeeding with 204, restart reconciliation restoring live records while purging dead records and preserving unrelated files).

### R2 Resolution — Pagination Loading Ownership & Generation Reset
- Updated `frontend/src/pages/LibraryPage.tsx` with dedicated `activePaginationReqRef = useRef<number>(0)`.
- Query or workspace generation advancements in `loadPapers` and `handleSelectWorkspace` immediately reset `activePaginationReqRef.current = 0` and clear `isLoadingMore(false)`, re-enabling "Load more" for the new query.
- In `loadMorePapers`, stale pagination completions check both `currentPaperGen === activePaperReqRef.current` and `paginationReqId === activePaginationReqRef.current` before clearing `isLoadingMore(false)`, preventing stale completions from clearing the loading state of newer concurrent requests.
- Verified in `frontend/src/test/library.test.tsx` (superseded pagination leaves replacement "Load more" enabled, appends correct page, ignores stale errors, and preserves loading state of concurrent new pagination requests).

### R3 Resolution — Top-Level Workspace ID Capture & Cleanup Reporting
- Updated `scripts/run_browser_verification.py` to parse and validate top-level `id` (`res_json.get("id")`), asserting non-empty string and failing immediately if missing or malformed.
- Preserved `created_workspace_id` until confirmed HTTP 200/204 deletion.
- In `finally` cleanup, issues DELETE and logs/records any failure into `results["cleanup_errors"]`.
- Updated `evaluate_acceptance` to fail `clean_operation` and report failure reasons if `cleanup_errors` are present.
- Verified in `tests/backend/test_browser_runner.py` (verifies top-level ID response contract, asserts evaluate_acceptance fails on cleanup errors, and verifies injected browser failure deletes created workspace while preserving sentinel workspace).

## Verification scope and evidence

Fresh automated checks:
- Backend: 125 passed, 77 warnings in 51.87s (`.venv/Scripts/python -m pytest -q`)
- Ruff: Lint passed (0 errors), Format check passed (37 files already formatted)
- Frontend: 23 passed in 4 test files (`npm test`)
- Frontend static checks: `npm run lint`, `npm run format:check`, `npm run typecheck`, and `npm run build` passed with 0 errors
- Live Browser Verification: `powershell -ExecutionPolicy Bypass -File scripts/run_browser_suite.ps1 -RequirePhase2 -BackendPort 8008 -FrontendPort 5178` passed all 8 acceptance criteria on disposable target (`.temp/browser_test_*`).

VERDICT: PASS — R1–R3 resolved with fresh automated and browser evidence. Committed locally for review; unpushed per Phase 2 policy.

## Copy-ready Antigravity prompt

Fix R1–R3 in @docs/PHASE_2_REVIEW_C7D6C8E.md against commit c7d6c8e in `F:/Projects/ResearchMind AI`. Preserve the existing fixes and Week 1 Phase 2 scope. Planning, implementation, and verification are authorized; proceed beyond a plan. This prompt supersedes the older six-finding repair handoff.

Read @decision.md @workflow.md @docs/PHASE_2_PROMPT.md @API_SPEC.md. Inspect @backend/app/services/paper_service.py @backend/app/services/workspace_service.py @frontend/src/pages/LibraryPage.tsx @scripts/run_browser_verification.py and relevant tests/callers before editing.

Apply these resources sequentially. Slash registrations are unverified; use matching autocomplete entries or read the exact instruction files. Pasted slash strings are not an executable command chain.

- Primary `/debug`: @F:/dev/.agents/workflows/debug.md. Use its **Ralph Loop** fallback: reproduce, diagnose, repair, verify, record evidence. No standalone Ralph skill/activation was found. Bound a failing hypothesis to 3–5 iterations; re-diagnose after two identical failures, then continue authorized work with a changed approach.
- `/gravitas`: @F:/dev/.agents/skills/gravitas/SKILL.md and @F:/dev/.agents/skills/gravitas/references/reconnaissance.md. Compact dependency-directed reading, impact verification, no delegation. Optimize agent context only; don't change product token budgets or claim hooks ran.
- `/file-uploads`: @F:/dev/AppData/.gemini/config/skills/file-uploads/SKILL.md. Apply file ownership and safe lifecycle principles to durable quarantine recovery. Preserve local storage.
- `/test`: @F:/dev/.agents/workflows/test.md. Write regressions for the exact failures and adverse async orderings; observe red then green.
- `/visual-verification`: @F:/dev/.agents/skills/visual-verification/SKILL.md. Verify pagination usability after a search/workspace change and browser failure cleanup against disposable data.
- `/verification-before-completion`: @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md. Require fresh per-finding evidence, not blanket completion from happy-path tests.

The accessible command inventory was reconsidered by task intent. For additional discovery use @F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv and @F:/dev/.agents/docs/CATALOG.md. Its loop-engineering entry is methodology, not installed-plugin evidence. For this repair prioritize actual project contracts, installed library source, and tests. Reuse the original prompt's official references only for relevant API/version questions; no unrelated website or UI-library activation is needed.

**R1 implementation and tests:** retain durable state distinguishing live originals requiring restoration from committed deletions awaiting purge. Provide bounded retry/reconciliation surviving restart and truthful outcomes. Don't merely return 500 after discarding recovery state or swap unlink/commit ordering again. Test staging failure, commit failure, rollback restoration failure, final unlink failure, partial workspace cleanup, retry/restart, and unrelated-file preservation. Live records with recoverable staged bytes must retain a recovery route. If a migration is needed, verify fresh setup, schema drift, and populated upgrades.

**R2 implementation and tests:** reset or transfer pagination loading ownership when query/workspace generations change. Add deferred tests that start page two, change search/workspace, resolve the replacement first page with a non-null cursor, then resolve/reject the old request. Assert no stale rows/cursors/errors, the current button becomes enabled, and clicking it fetches/appends the correct next page. Include a new current pagination request already active when the stale request finishes; stale completion must not clear its loading state.

**R3 implementation and tests:** validate the real top-level create response ID and track it until confirmed deletion. Cover failed creation, missing ID, failure after creation/upload, cleanup failure response, and normal success. Assert exact created-ID cleanup and sentinel preservation. Test against the actual response contract rather than a mock shaped to the wrong assumption. Keep direct/attach disposable guards and record cleanup errors instead of swallowing them.

Run focused regressions, then root `.venv/Scripts/python -m pytest -q`, `.venv/Scripts/ruff check backend tests scripts`, `.venv/Scripts/ruff format --check backend tests scripts`. From frontend run `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`; inspect each exit code. Run corrected browser verification only against disposable DB/storage, including injected failure cleanup and pagination recovery. Preserve real data, user services, and environment state.

Update this review and @docs/PHASE_2_VERIFICATION.md with fresh requirement-to-evidence mapping and limitations; correct current decision/workflow status. Don't copy historical outputs as new evidence. Commit locally for independent completion review; **do not push unfinished Phase 2**. Both remote branches contain Phase 1 checkpoint 24eadea. After acceptance, publish to manav first, verify its ref, then main at the same checkpoint. Report behavior changes, actual checks, remaining gaps, commit hash, and scoped VERDICT.
