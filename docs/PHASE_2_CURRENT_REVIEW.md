# Current Phase 2 review — 306bd9e

Independent review, 2026-10-17: Q1 and Q2 are resolved in the reviewed diff and regression suite. One acceptance-runner finding remains; Phase 2 is not accepted for publication. Use `docs/PHASE_2_SEARCH_VERIFICATION_PROMPT.md`; the Q1/Q2 prompt below is historical and superseded.

## S1 — P2: Search acceptance races loading and does not prove filtering

At `scripts/run_browser_verification.py:866-872`, the runner fills the query, sleeps 500 ms, and immediately samples a title locator with `count()`. The UI debounces for 250 ms before issuing the request. The remaining fixed delay does not establish response completion or rendered results. An existing matching title can also satisfy this check even if filtering never runs; there is no nonmatching fixture or empty-result assertion.

Fresh isolated Chrome run exited 1: seven criteria passed, but `phase2_library_lifecycle` failed solely because `search_success` was false. Upload, duplicate detection, corrupt rejection, PDF response/viewer, cancel/confirm deletion, workspace deletion, and clean operation passed. This demonstrates an unresolved acceptance gate, not a proven application search defect. Capture the matching request/response and await rendered query-specific results with a bounded timeout; test nonmatching exclusion, empty results, and clearing the query. Do not merely increase sleeps or rerun until green.

Fresh independent checks: 130 backend tests passed (82 warnings, 69.58 s); 23 frontend tests passed; Ruff lint/format, ESLint, Prettier, TypeScript, and Vite build passed. Browser command: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_browser_suite.ps1 -RequirePhase2 -BackendPort 8008 -FrontendPort 5178`. Disposable database migrated successfully; wrapper reported owned-process and temporary-storage cleanup. Current JSON evidence is `docs/browser_verification_summary.json`. Clean installation, ML inference, and provider connectivity were not rerun.

VERDICT: FAIL -- search browser acceptance remains unresolved. Keep Phase 2 local; eventual accepted publication remains manav first, verify, then main.

## Historical review and implementation report — 6354bc0

Reviewed 2026-10-17 against 0a9295b. Application code was not changed during review. Pagination loading ownership and top-level browser cleanup ID handling are improved, with dedicated regressions. The new quarantine ledger introduces two remaining lifecycle/ownership gaps.

## Findings

### Q1 — P2: Pending-purge retries bypass resource ownership

`backend/app/services/paper_service.py:412-420` falls back from an ownership-filtered row lookup to a ledger lookup using only paper_id. `workspace_service.py:210-216` does the same for workspace_id. Ledger entries have no owner field, so once the original rows are gone the retry path cannot enforce the original ownership boundary.

Disposable reproduction: create and upload as the local owner, force purge failure so the row is deleted and a pending ledger remains, then resolve the request as a different User through the existing identity-dependency test seam. The foreign user's DELETE returned 204 and removed all retained bytes. This is a demonstrated isolation-contract defect, not a claim that a public multi-user login is currently enabled. A foreign caller must receive the same not-found behavior as normal resource access and leave the ledger/files untouched.

Persist sufficient ownership evidence before row deletion and apply it to paper and workspace retry lookups. Handle old ownerless ledgers conservatively: never grant deletion authority merely from possession of an ID. Test both resource types, genuine owner retry, foreign retry, missing/legacy ownership, and no-mutation rejection.

### Q2 — P2: Deleting a live paper already in quarantine returns false success

`paper_service.py:443` and `workspace_service.py:238` only stage files when the original storage_path exists. After a commit failure followed by restoration failure, the live row's bytes instead reside in the quarantine ledger and are accessible through the new fallback. Retrying DELETE skips that existing staged file, deletes the live row, and returns 204 without transitioning/purging its ledger.

Disposable reproduction: force delete commit failure and failed restoration, confirm GET /file still serves the fallback bytes, then retry DELETE after clearing the failures. It returned 204 while one original remained in `.trash`; another retry returned 404 because the ledger was still `staged` rather than `committed_pending_purge`. Startup reconciliation may eventually purge it, but immediate deletion success and retry semantics are wrong.

Resolve the full file lifecycle for both normal-path and already-quarantined live records. Adopt the matching existing ledger into the delete transaction, preserve its rollback meaning until commit succeeds, then transition/purge or return truthful pending cleanup. Cover workspace cascades with mixed normal and quarantined files. Do not simply delete every ledger for an ID without ownership and state checks.

## Resolution of Q1 and Q2 (Corrective Repair Checkpoint)

Both findings Q1 and Q2 have been resolved via architectural enhancements and verified with fresh regression evidence:

### Q1 Resolution — Ownership Enforcement on Pending-Purge Retries
- In [quarantine_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/quarantine_service.py), `stage_file_for_deletion` now records `user_id` in `.meta.json`.
- `find_pending_purges` and `find_pending_purges_by_workspace` strictly enforce `data.get("user_id") == user_id`. If `user_id` is missing, None, or belongs to a different user, pending ledger entries are NOT returned.
- In [paper_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/paper_service.py) and [workspace_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/workspace_service.py), unauthorized retries by foreign callers or callers targeting ownerless ledgers receive controlled 404 Not Found without modifying any retained file or ledger metadata.
- Conservative handling of legacy ownerless records: deletion authority is never granted merely from possessing a resource ID; legacy/unowned entries are left untouched by user routes and managed only via server restart reconciliation.
- Verified in `tests/backend/test_phase2_fixes.py` (`test_q1_paper_pending_purge_foreign_and_ownerless_rejection` and `test_q1_workspace_pending_purge_foreign_and_ownerless_rejection`).

### Q2 Resolution — Adoption and Purge of Already-Quarantined Live Documents
- Implemented `find_adoptable_quarantine` in [quarantine_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/quarantine_service.py), discovering existing staged or rollback-failed files belonging to live papers owned by `user_id`.
- In [paper_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/paper_service.py) and [workspace_service.py](file:///f:/Projects/ResearchMind%20AI/backend/app/services/workspace_service.py), when deleting a paper whose physical file is not at `storage_path` (due to prior failed restoration), the delete transaction adopts the matching quarantine ledger.
- If database commit fails, the adopted file is restored or preserved in `rollback_pending_restoration` so live fallback retrieval remains accessible.
- If database commit succeeds, the adopted metadata is transitioned to `committed_pending_purge` and purged; on unlink failure, it returns 500 with `pending_purge` for truthful owner retry.
- Covered mixed workspace cascades containing both normal on-disk files and already-quarantined files, ensuring complete purge of all associated documents.
- Verified in `tests/backend/test_phase2_fixes.py` (`test_q2_paper_already_in_quarantine_adopted_and_purged`, `test_q2_paper_already_in_quarantine_purge_failure_then_owner_retry`, and `test_q2_workspace_cascade_mixed_normal_and_quarantined_files`).

## Verification scope and evidence

Fresh automated checks:
- Backend: 130 passed, 82 warnings in 79.69s (`.venv/Scripts/python -m pytest -q`)
- Ruff: Lint passed (0 errors), Format check passed (37 files already formatted)
- Frontend: 23 passed in 4 test files (`npm test`)
- Frontend static checks: `npm run lint`, `npm run format:check`, `npm run typecheck`, and `npm run build` passed with 0 errors
- Live Browser Acceptance: `powershell -ExecutionPolicy Bypass -File scripts/run_browser_suite.ps1 -RequirePhase2 -BackendPort 8008 -FrontendPort 5178` passed all 8 acceptance criteria on disposable target (`.temp/browser_test_*`).

VERDICT: PASS — Q1 and Q2 resolved with fresh automated and browser evidence. Committed locally for review; unpushed per Phase 2 policy.

## Copy-ready Antigravity corrective prompt

Fix Q1 and Q2 in @docs/PHASE_2_CURRENT_REVIEW.md against commit 6354bc0 in `F:/Projects/ResearchMind AI`. Preserve the now-working pagination and browser cleanup changes and the existing Week 1 scope. Planning, implementation, and verification are authorized; proceed through completion, not just a plan.

Read @decision.md @workflow.md @docs/PHASE_2_PROMPT.md @API_SPEC.md. Inspect @backend/app/services/quarantine_service.py @backend/app/services/paper_service.py @backend/app/services/workspace_service.py @backend/app/api/papers.py @backend/app/api/workspaces.py and relevant tests/dependencies before editing. The current review supersedes older 'all resolved' claims.

Apply resources sequentially; slash registration is unverified, so use matching autocomplete entries or read the exact file. Pasted slash strings do not automatically execute a chain:

- Primary `/debug` + @F:/dev/.agents/workflows/debug.md: use the requested **Ralph-style bounded repair loop**. Reproduce, rank causes, fix coherently, verify, and retain concise evidence. No standalone Ralph skill activation is claimed. Bound a failed hypothesis to 3–5 iterations and re-diagnose after two identical failures; continue authorized findings with new evidence.
- `/gravitas` + @F:/dev/.agents/skills/gravitas/SKILL.md and @F:/dev/.agents/skills/gravitas/references/reconnaissance.md: compact dependency-directed context, impact-based checks, no delegation. Agent efficiency only; no product token changes or claimed runtime hooks.
- `/file-uploads` + @F:/dev/AppData/.gemini/config/skills/file-uploads/SKILL.md: apply local-file ownership, generated-path safety, and lifecycle principles to quarantine handling. Keep local storage.
- `/test` + @F:/dev/.agents/workflows/test.md: failing behavioral regressions for ownership and chained failure/retry transitions, then verify the fix.
- `/verification-before-completion` + @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md: fresh per-requirement evidence, separate from historical success reports.

The full accessible inventory was reconsidered by task intent. Use @F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv and @F:/dev/.agents/docs/CATALOG.md only for useful additional discovery. The catalog's loop-engineering reference is methodology, not proof of an installed plugin. This focused repair needs actual API/ledger contracts and installed library behavior, not unrelated web/design tools. Preserve the previously selected official references for API questions as needed.

**Q1 requirements:** record durable user ownership before deleting the source DB rows; enforce it when finding pending paper/workspace purges. Unauthorized retries must return controlled not-found and leave every ledger/file byte unchanged. Treat legacy ownerless records conservatively and document recovery; don't infer authority from the submitted resource ID. Test owner, foreign user, missing owner, and both paper/workspace paths using the existing identity test seam. Preserve the local single-user default and AUTH_ENABLED behavior.

**Q2 requirements:** explicitly resolve a live row whose original is already staged after failed restoration. Adopt its existing matching ledger into the new delete operation rather than skipping missing storage_path. On DB failure, keep or restore accessible live bytes; after commit, transition the ledger and purge or return pending cleanup. Cover individual papers and workspace cascades mixing normal/staged files. Verify the complete sequence commit failure -> restoration failure -> readable fallback -> successful retry (no bytes/ledger left), plus retry with purge failure -> pending ledger -> subsequent owner retry success. Also verify startup reconciliation and unrelated-file preservation still work.

Keep lifecycle transitions and ownership checks centralized where practical. Validate ledger state/resource matching and path boundaries before file operations. Do not mask failures with broad catch-and-success behavior, blindly purge quarantine, or claim deletion complete merely because the DB row is gone.

Run focused red/green regressions, then root `.venv/Scripts/python -m pytest -q`, `.venv/Scripts/ruff check backend tests scripts`, `.venv/Scripts/ruff format --check backend tests scripts`. From frontend run `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`; inspect each exit code. Run the existing browser lifecycle against verified disposable data as integration evidence for changed deletion behavior. Preserve real data, user services, and environment. Keep runtime files/screenshots/secrets out of Git.

Update this review and @docs/PHASE_2_VERIFICATION.md with fresh evidence and limitations; correct current decision/workflow status. Commit locally for independent completion review. **Do not push incomplete Phase 2 work.** Accepted-release order remains manav first, verify, then main at the same checkpoint. End with changes, exact checks, remaining gaps, commit hash, and scoped VERDICT.
