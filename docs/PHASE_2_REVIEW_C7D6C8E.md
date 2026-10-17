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

## Verification scope

Disposable probes confirmed R1 and R2 and checked the actual response-shape mismatch in R3. They intentionally asserted observed bugs for review evidence, not desired behavior, and were removed afterward. No fresh full live-browser, clean-install, ML, or provider run was performed.

Fresh standard checks: 117 backend tests passed with 71 deprecation warnings in 75.82 seconds; 20 frontend tests passed in four files (existing JSDOM scrollTo warnings). Ruff lint and format (36 files), ESLint, Prettier, TypeScript, and production build passed. All 19 context-file references in the corrective prompt exist; git diff whitespace checks passed. Standard-suite success does not close R1–R3.

VERDICT: FAIL — R1–R3 remain. Phase 2 must stay local until accepted.

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
