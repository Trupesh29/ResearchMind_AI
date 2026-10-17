# Current Phase 2 review — 6354bc0

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

## Verification scope

Two temporary tests using isolated database/storage fixtures confirmed Q1 and Q2. They asserted observed defects for evidence, not desired acceptance behavior, and were removed afterward. No real project data was mutated by these probes. No fresh full live-browser, clean-install, ML, or provider run was performed in this review.

Fresh checks: 125 backend tests passed with 77 deprecation warnings in 117.31 seconds; 23 frontend tests passed in four files, with existing JSDOM scrollTo warnings. Ruff lint and formatting (37 files), ESLint, Prettier, TypeScript, and Vite production build passed. Prompt context paths exist and git diff whitespace checks passed. Passing standard checks does not close Q1/Q2.

VERDICT: FAIL — Q1 and Q2 remain. Phase 2 stays local until accepted.

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
