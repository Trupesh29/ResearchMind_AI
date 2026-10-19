# Independent review — 0e0fe95

Reviewed 2026-10-19 against d0271da. **Changes required; keep Phase 4 local.** This review adds evidence and a handoff, without editing application code.

## Confirmed progress

0009 now provides a forward path from 0008. Section-length and repeated-occurrence probes now produce bounded spans and preserve the c reference in the original repeated-text case. The prior stale=true/stale=false and filter-during-reprocess regressions all pass. Worker/seeding call sites now verify matching disposable database identities, and the wrapper checks Attach configuration. Automatic browser recovery now waits without changing the filter. Sidebar roadmap badges remain correct.

## M1 — P2: Known block IDs are still mistaken for proven provenance

`backend/migrations/versions/0009_repair_block_spans_and_chunks.py:219-232` accepts existing block IDs if they merely exist in a reconstructed section. It never checks whether their spans contain the chunk text. This retains the very approximate references the historical repair is meant to fix, and can incorrectly bless their page bounds. Block existence is not occurrence evidence.

Run `.venv/Scripts/python scripts/review_phase4_known_block_probe.py`. Block b contains `Repeated evidence.`; block c contains `Other unrelated evidence.`. A historical chunk containing b's text but referencing c survives the upgrade with `["c"]`, despite a unique correct match in b. The earlier repeated-text fixture passes because either block contains identical text, hiding this case.

Validate text/offset correspondence before preserving existing references. Use unique demonstrable matches for repair; represent ambiguity explicitly when it cannot be resolved, including chunks without reconstructable sections and partially invalid block lists. Preserve the previously valid repeated-occurrence case without assuming every historical ID is trustworthy. Supply a forward migration for databases already stamped 0009; do not rely only on rewriting its body.

## M2 — P2: A stale finally block clears the current action's busy state

`QualityCenterModal.tsx:549-556` now releases reprocess busy state using only paper/workspace/open identity. It omits the action token checked by success/error. Close and reopen the same paper, start a new reprocess request, then resolve the old one: its finally block sets `isReprocessing=false` while the new request is still pending. The button enables early and permits duplicate submissions. Pagination's finally at lines 487-494 has the same ownership gap after invalidation and a subsequent action.

The retained `scripts/review_phase4_action_owner.tsx.txt` snippet reproduces the reprocess case. Insert it in a temporary copy of the existing test describe and run with `-t 'review: old action'`. It fails because the button is enabled after only the old request settles. The diagnostic run also included the three prior review cases, which passed: **1 failed, 3 passed, 15 skipped**. The temporary test was removed from normal discovery.

Release busy state only for the action that currently owns it. On invalidation, explicitly reset the invalidated action without letting its later continuation clear a newer one. Retain the fixed filter-change behavior and independent pagination/reprocess tokens. Test close/reopen, filter replacement, generation changes and overlapping old/new actions.

## M3 — P2: Browser late-response gate cannot detect the actual leaked banner

`scripts/run_browser_verification.py:1573` asserts absence of `Ingestion pipeline queued`; the actual UI success text at `QualityCenterModal.tsx:526` is `Reprocessing job enqueued successfully. Pipeline restarted.` The absence check is therefore vacuous. After continuing A's request, the runner also sleeps 0.6 seconds instead of waiting for that response to complete, and its assertions do not prove B's chunks/run/status remain intact. A slow response or leaked current banner can still pass.

Register a response-completion gate before releasing A, wait for B's coherent loaded state, then assert B's identity/data/status and the actual message contract after A settles. Add a negative control that injects A's real banner or stale data and proves the gate fails. Do not report a sleep and an unrelated string's absence as race acceptance. This is a static finding; no fresh live browser acceptance run was performed here.

## Fresh checks

- Submitted frontend suite: **43 passed**. ESLint, Prettier, TypeScript and Vite build passed.
- Focused UI diagnostic: **1 failed, 3 passed** as above. Existing span/repeated-text probes pass their original cases; the new known-but-wrong-block probe exposes M1.
- Ruff lint and formatting passed across backend/tests/scripts/worker, including the new Python diagnostic.
- Full backend suite with disposable DATA_DIR/DATABASE_URL: **186 passed**, 126 warnings, 164.51 seconds. No failed-test rerun was needed. Passing existing suites does not cover the additional demonstrated M1/M2 cases.

Applied resources: existing scoped-review/verification guidance; attachment-web-quality for loading, errors, action feedback and truthful acceptance claims; current namespaced review/browser instructions for the corrective handoff. Payment, marketing, tracking and new design-generation resources do not apply. Resource metadata/status was refreshed; Antigravity slash activation and Chrome DevTools authentication/invocation were not verified. No live browser result is claimed from catalog presence. Policy remains compact, dependency-directed, impact-based, no delegation.
