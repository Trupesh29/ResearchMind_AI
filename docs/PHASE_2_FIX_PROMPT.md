# Antigravity corrective prompt — Phase 2 review

Copy the following prompt into Antigravity. Command registration is unverified; all referenced instruction files exist. Resolve @ mentions using autocomplete or read the exact files directly. Apply resources sequentially, not as an executable slash chain.

---

Fix the reviewed Week 1 Phase 2 implementation in `F:/Projects/ResearchMind AI`. Read @docs/PHASE_2_REVIEW.md first and close all eight findings with evidence. Preserve Phase 1 and the existing Phase 2 features. Implementation is authorized; proceed through scoped investigation, fixes, and verification without stopping after a plan.

Context: @docs/PHASE_2_PROMPT.md @docs/PHASE_2_PLAN.md @docs/PHASE_2_VERIFICATION.md @decision.md @workflow.md @API_SPEC.md @DESIGN.md. Read affected sources/tests from the review and their direct dependencies; do not reload the whole repository each iteration.

## Resource responsibilities, including Ralph Loop

1. Primary `/debug` candidate: read and apply @F:/dev/.agents/workflows/debug.md. This verified local workflow explicitly incorporates **Ralph Loop** and supplies the bounded Plan-Code-Test-Iterate behavior requested by the user. A standalone Ralph Loop SKILL.md or registered command was NOT found in the accessible inventories; do not invent `/ralph-loop` activation or claim its runtime ran. If the user supplies an actual skill path or the host discovers one, read it and verify compatibility before applying it. Until then, use this documented Ralph Loop fallback.
2. `/gravitas`: read/apply @F:/dev/.agents/skills/gravitas/SKILL.md and @F:/dev/.agents/skills/gravitas/references/reconnaissance.md for compact dependency-directed context, impact-based verification, and no delegation. This optimizes agent reading only, not product tokens or model behavior. Runtime/hook availability is unverified; project tests remain project tests.
3. `/file-uploads`: read/apply @F:/dev/AppData/.gemini/config/skills/file-uploads/SKILL.md to bounded multipart receiving, safe headers/paths, temporary storage, and compensating file/DB operations. Keep local storage and existing architecture.
4. `/test`: read/apply @F:/dev/.agents/workflows/test.md to behavioral regression tests. Tests must fail for the demonstrated defect before the repair and verify correct behavior afterward, rather than asserting the bug as success.
5. `/visual-verification`: read/apply @F:/dev/.agents/skills/visual-verification/SKILL.md to the repaired UI and real-browser flows, including dialog keyboard behavior and the selected-workspace race.
6. `/verification-before-completion`: read/apply @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md for fresh results and requirement-by-requirement completion evidence.

Use the existing @F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv and @F:/dev/.agents/docs/CATALOG.md for relevant additions only. The catalog's [loop-engineering reference](https://github.com/cobusgreyling/loop-engineering) is background for bounded iterative work, not proof of an installed Ralph plugin. Use [RFC 9110 byte ranges](https://www.rfc-editor.org/rfc/rfc9110.html#section-14.1.2) for the range regression and the installed Starlette response/parser source for version-specific behavior. Consult the previously selected FastAPI/PyMuPDF references only as needed. Preserve DESIGN.md instead of adding a design framework.

## Ralph-style repair loop

Maintain a small checklist of finding IDs, current evidence, changed paths, and next check in the review/verification documents. For each related defect group:

1. Inspect the failing boundary and rank plausible causes.
2. Write a minimal regression using disposable storage or deferred UI responses; reproduce the failure.
3. Apply the smallest coherent fix.
4. Run the regression plus affected tests; record actual output.
5. Repeat only with new evidence or a changed hypothesis. Bound a hypothesis loop to 3–5 iterations; after two identical failures, stop repeating it and diagnose/replan. Report an external blocker if progress truly requires missing input. Do not use an endless loop or a fake completion marker.

Loop limits apply to a failing hypothesis, not permission to abandon the remaining authorized findings. Retain compact factual progress across context resets. No parallel agents, hook installation, or automated push is implied by this loop.

## Required corrections

- **Isolate browser mutations first.** Owned test servers need a disposable DATA_DIR, database, migrations, and bootstrap, plus complete environment restoration and owned-process cleanup. Alternate ports alone are insufficient. Attach mode must not mutate an arbitrary existing database. Use unique run identities and only delete resources whose creation succeeded in that run; use finally cleanup with explicit failure reporting. Test that sentinel real data and pre-existing workspaces survive success and failure. Do not run current destructive lifecycle tests against live user data.
- **Bound input before multipart spooling.** Enforce actual receive-byte limits including chunked/no-Content-Length requests; specify aggregate/batch limits in settings/docs and preserve per-file batch rejection semantics. Close parser/spooled/staging handles on failures. A check inside process_paper_upload alone is too late. Test bounded rejection without allocating huge files.
- **Make file/DB lifecycle recoverable.** Cover non-IntegrityError commit failures, move/write failures, duplicate races, and post-commit refresh failures. No orphan files, fabricated duplicate IDs, or deletion of a successfully committed original. For paper/workspace deletion, retain enough state to retry locked/unlink-failed files and report failure/pending cleanup honestly; don't delete rows, swallow errors, and return 204. Test workspace deletion with several files and a failure partway through. Preserve unrelated and cross-workspace files.
- **Fix original-file responses.** Encode Unicode and quoted filenames safely for full and ranged responses. Clip a valid end past EOF instead of rejecting a satisfiable request; cover suffix/open-ended/zero-length/huge-number/malformed ranges. Reuse the installed framework response behavior if suitable. Keep ownership, exact bytes, and controlled missing-file errors.
- **Wire pagination throughout.** Consume next_cursor in paper browsing and workspace selection; make every item reachable. Dashboard counts must cover the full intended dataset rather than just page one. Test >100 records, page boundaries, filtering, and deterministic ordering.
- **Respect latest UI selection.** Upload/delete completion may refresh its originating workspace but must not force the user back after they selected another workspace. Guard workspace fetches, clear/invalidate stale paper requests, and preserve the active search. Add deferred-promise tests switching A -> B before A completes, including error paths and removal of the last workspace.
- **Close acceptance gaps.** Require Phase 2 results in Phase 2 verification and test missing/false outcomes. Check actual original-PDF response/load, not only modal visibility. Verify fresh persistence across reload/restart, keyboard focus containment/restoration/background exclusion for new dialogs, responsive overflow, loading/error states, and absence of unexpected errors. Don't reinterpret historical Phase 1 modal checks as coverage of new dialogs. Correct inaccurate API/storage/documentation claims.

## Verification, commit, and publication gate

Run focused regressions first, then from the root:
`.venv/Scripts/python -m pytest -q`
`.venv/Scripts/ruff check backend tests scripts`
`.venv/Scripts/ruff format --check backend tests scripts`

From frontend: `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`. Inspect each exit code. Run the corrected, disposable live-browser suite and capture actual evidence. If schema changes are necessary, verify drift, fresh migration, and data-preserving upgrade. Keep real data untouched and runtime artifacts out of Git.

Update @docs/PHASE_2_REVIEW.md and @docs/PHASE_2_VERIFICATION.md with findings resolved/unresolved and fresh evidence. Update decision.md/workflow.md for changed decisions only. Scope the verdict to checked behavior; no fabricated browser, clean-install, ML, or provider success.

Commit reviewed task changes locally on the current development branch. **Do not push Phase 2 in this corrective handoff.** Phase 1 is already published on remote main at 24eadea. The user permits Phase 2 publication only once it is complete; leave the repaired checkpoint ready for the independent completion review before that publication. Never push current HEAD, merge into main, force-push, or move the Phase 1 checkpoint as part of an unfinished repair. Report the commit hash, exact verification results, unresolved limitations, and final scoped verdict.
