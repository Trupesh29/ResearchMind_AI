# Independent review — 573223a

Compared with 0d89546 on 2026-10-19. **Changes required; keep Phase 4 local.** No application repair was made in this review.

## Improvements confirmed

0010 supplies the forward provenance repair, and the known-but-unrelated-block probe now resolves to b, the correct source. Reprocess/pagination finally blocks now check their action tokens, addressing the earlier close/reopen race. The browser gate uses the actual success-message contract and includes negative controls for leaked banners. The sidebar roadmap mapping remains correct.

## N1 — P2: Generation invalidation leaves pagination permanently busy

`frontend/src/components/library/QualityCenterModal.tsx:284` and `:326` invalidate pagination when artifacts conflict or the published generation changes. Neither path clears `isLoadingMoreChunks`. With the new token guard in finally at line 489, the invalidated request can no longer release that flag. If generation 2 publishes while generation 1's Load More request is pending, generation 2's chunks and cursor load but its Load More button stays disabled indefinitely.

Reproduction retained in `scripts/review_phase4_generation_paging.tsx.txt`: start a deferred generation-1 pagination request, trigger a fresh load with generation 2, wait for generation-2 content, then settle generation 1. The enabled-button assertion fails. Focused run: **1 failed, 20 skipped**. The temporary duplicate test was removed from discovery.

Reset the invalidated action's busy state at the invalidation boundary, preserving ownership checks so an old finally cannot clear a newer action. Cover generation conflict, successful publication, and a new pagination request started before the old one settles. Keep the already-fixed paper/filter/close cases passing.

## N2 — P2: Late-response gate accepts chunks from the wrong paper

`scripts/run_browser_verification.py:302-332` defines `b_chunks_intact` as the presence of any `Loaded ` text. It does not check B's chunk text, IDs, run, count, or status. A helper-level probe with B's title, an enabled button, `Loaded 1 of 1 chunks`, and exclusively `UNIQUE CHUNK FROM PAPER A` returns **True for every check**. The new negative controls test banners/title/button state, but do not detect the stale-data condition the gate claims to verify.

The response waiter near line 1598 observes the reprocess response event, then immediately runs synchronous DOM-count checks. It does not explicitly finish the body or establish that the application's completion has been applied. Capture B's actual fixture identity/data before releasing A, wait for A's full response and an observable settled UI state, then compare B's exact data/status afterward. Add a wrong-paper/wrong-generation data negative control and a delayed-body case; keep the real-banner controls.

This is an acceptance-test defect, not a claim that the current application demonstrably leaks chunks in this scenario. The helper-level false positive is reproduced independently.

## Verification

- Existing frontend suite: **45 passed**. ESLint, Prettier and TypeScript/Vite build passed.
- Known-block provenance probe now reports `["b"]`, confirming the prior M1 reproduction is fixed.
- Ruff lint and format passed across backend/tests/scripts/worker.
- Backend suite with disposable DATA_DIR/DATABASE_URL: **192 passed, 1 failed**, 128 warnings, 199.73 seconds. `test_suite_preserves_caller_disposable_test_env` exceeded its 20-second subprocess timeout during concurrent checks; an isolated retry is recorded below. This timeout alone is not a confirmed product regression.
- Isolated retry of that exact test: **1 passed**, 1 warning, 8.65 seconds. No remnants matching this run's failed-test fixture path remained.
- Independent live Chrome command `scripts/run_browser_suite.ps1 -BackendPort 18083 -FrontendPort 15176 -RequirePhase2 -RequirePhase4`: **exit 0, all nine implemented gates passed**; owned processes/storage were cleaned up. The tracked browser summary contains this fresh run. Inspected `artifacts/browser_verification/screenshots/desktop_quality_center_modal.png`: B is displayed with Processing Failed, Chunks (0), and Loaded 0 of 0 chunks. The gate accepts this as a loaded chunk list; its PASS does not establish exact B data/run preservation or resolve N2. Do not describe this screenshot as successful B chunk extraction.

Resources: refreshed Antigravity command/status metadata and relevant catalog routing; applied existing review/verification instructions and attachment web-quality loading/action-feedback criteria. No new screen generation, tracking, policy or payment work is applicable. Antigravity command activation and MCP authentication are not claimed; local CLI/Chrome tooling supplies actual execution evidence. No delegation or push.
