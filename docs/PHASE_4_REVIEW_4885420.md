# Independent Phase 4 review — 4885420

2026-10-19, compared with e628d3f. **Changes required; keep Phase 4 local.** Application code was not changed by this review.

## Improvements

Current identity refs now protect the previous paper-switch reproduction. Generation checks run on initial loads, and the supported tokenizer model/revision is explicitly restricted. Fresh upgrades clean dehyphenated block lengths correctly. The browser harness exercises processing and pagination. Sidebar roadmap badges remain correct (2, 5, 4, 6).

## L1 — P2: Existing 0008 databases never receive the migration repair

The changes replace `backend/migrations/versions/0008_add_block_spans_to_sections.py` without adding a successor revision. An installation already stamped 0008 skips its new code on `upgrade head`.

Run `.venv/Scripts/python scripts/review_phase4_existing_0008_probe.py`. It constructs a disposable 0007 database, upgrades using the original 0008 from e628d3f, then upgrades with the current migration directory. Output remains `CLEANED_TEXT_LENGTH 46`, `MIGRATED_SPANS [['b', 1, 0, 48]]`, `SPAN_EXCEEDS_TEXT True`. The existing fresh-upgrade probe passes but does not cover this transition. Add a forward reconciliation revision and test both existing-0008 and fresh paths without resetting data or revision stamps.

## L2 — P2: Historical chunk reconciliation rewrites repeated passages incorrectly

At `0008_add_block_spans_to_sections.py:169-178`, chunks are selected by section label and matched with `sec_text.find(ch_text)`, always choosing the first occurrence. Neither a section label nor identical text establishes which occurrence a historical chunk belongs to. Multiple sections can share a label, and chunks may overlap or repeat.

Run `.venv/Scripts/python scripts/review_phase4_repeated_provenance_probe.py`. Two blocks b/c contain identical text and have exact separate spans. A historical chunk belonging to c is changed to `SECOND_OCCURRENCE_CHUNK_BLOCKS ["b"]`. This corrupts a previously correct reference. Use persisted occurrence identity where available; otherwise mark ambiguity/unresolved provenance and safely regenerate a new version. Do not guess or silently retain inaccurate references as verified. The broad exception handler currently hides reconciliation failures too.

## L3 — P2: Coherent stale artifacts suppress current failed-run status

`QualityCenterModal.tsx:270-280` treats any `is_stale` flag as generation disagreement. The backend intentionally marks the published old bundle stale when a newer current run exists, including when that new run fails. All artifact run IDs can agree with `published_run_id`; this is not a mixed artifact snapshot.

The UI rejects the current status along with those artifacts, leaving a spinner or old status and retrying indefinitely. `MAX_GENERATION_RETRIES` only controls a message; it does not stop scheduling retries. Show current run status separately from the coherent published bundle, label older artifacts, and stop/recover according to actual terminal state. Reserve conflict recovery for genuine artifact-generation disagreement.

The retained snippets in `scripts/review_phase4_ui_regressions.tsx.txt`, inserted into a temporary copy of the existing Vitest describe, reproduce this: failed replacement status/error is hidden when `is_stale=true`; the identical case with `is_stale=false` passes as a negative control.

## L4 — P2: Shared action invalidation can leave Reprocess permanently disabled

The filter effect at `QualityCenterModal.tsx:157` increments the token also used by reprocess. If a user changes filters while enqueueing, the reprocess completion and its finally block at line 550 both become invalid. The filter effect resets pagination busy state but never resets `isReprocessing`. The same shared-token design permits one action to invalidate another without releasing its busy state.

A deferred-response test in the retained snippets clicks Reprocess, changes section, then settles the response. The button remains disabled as Enqueueing. Use independent action ownership/cancellation or explicitly release the invalidated action's busy state while preserving paper/close guards. Test overlapping pagination/reprocess, filters, and generation changes.

## L5 — P1: Browser worker helper can target an unrelated local database in Attach mode

`scripts/run_browser_verification.py:64` constructs WorkerEngine from local settings (or inherits local environment in its subprocess). It drains globally queued jobs, without checking database ownership or restricting fixture IDs. The wrapper's Attach branch verifies the HTTP server's disposable flag but does not bind local DATABASE_URL to that server. Thus a permitted Attach run can process jobs from a different local database while the browser tests another backend. The new seeding helper has the same unverified database binding.

Fail closed before local worker/seeding operations unless an owned disposable database identity is verified against the tested backend. Reject unsupported Attach configurations explicitly, or provide a verified disposable fixture mechanism. Add tests proving mismatched/absent environment cannot mutate local data. This is a code-path finding; this review did not run the unsafe Attach path.

## Acceptance evidence issues

- `run_browser_verification.py:1407` changes the filter after removing the failure route. That proves user-triggered recovery, not automatic polling recovery as documented.
- At line 1444, `late_response_isolation` is only `closed_immediately and qc_dialog.is_visible()`. It never asserts the identity, data, messages or loading state after the delayed response. A broken stale-response handler can still pass. Replace sleeps with request/response gates, verify B remains correct after A settles, and demonstrate a negative control fails.
- The verification report claims an explicit empty span list on unresolved migration, but the implementation leaves the field unchanged/null. It also claims a retry count of five while code uses three and continues indefinitely. Correct the report to fresh observed behavior.
- No live browser run was repeated in this review; the above conclusions come from code and focused probes. The current browser summary is submitted evidence, not independent validation.

## Fresh checks

- Submitted frontend suite: **40 passed**. ESLint and TypeScript/Vite build passed. Prettier passed after removing the temporary diagnostic copy.
- Focused UI diagnostic: **2 failed, 1 passed**, 15 unrelated tests skipped. Failures confirm L3/L4; passing stale=false case is the negative control. The snippets are retained outside normal test discovery.
- Both disposable migration probes confirm L1/L2. Ruff lint/format passed across backend/tests/scripts/worker including the new probes.
- Full backend suite with disposable DATA_DIR/DATABASE_URL: **178 passed, 1 failed**, 124 warnings, 224.82 seconds. The failure was `test_suite_runner_failure_terminates_owned_backend_and_frontend`, exceeding its 15-second subprocess timeout. This concurrent-run timeout is not by itself a confirmed product regression; isolated retry is recorded below.
- Isolated retry of that exact browser-runner test: **1 passed**, 1 warning, 8.97 seconds. Its timeout was not reproduced. Six subprocess remnants from this review's failed test were identified by its unique pytest fixture path and stopped; unrelated app processes were left alone.

Policy: compact planning, dependency-directed review, impact-based evidence, no delegation. Existing Gravitas guidance and verification-before-completion were applied as instructions; no runtime/hook execution claimed. Current attachment inventory was refreshed; the newly installed code-review-and-quality and browser-testing-with-devtools instructions inform the handoff. Chrome DevTools MCP was not exposed here, and Antigravity host activation/authentication was not verified.
