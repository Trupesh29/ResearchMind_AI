# Phase 4 independent review — 4e09867

Reviewed 2026-10-19 against b2052a5. Verdict: **changes still required; keep Phase 4 local**. This review changes documentation and adds a disposable diagnostic only.

Policy: compact planning, dependency-directed context, impact-based verification, no delegation. Applied Gravitas reconnaissance/evidence guidance, without claiming its runtime or hooks executed.

## Confirmed improvements

Worker section persistence now stores and restores block spans. Sectioning cleans each block before calculating offsets; chunking no longer invents proportional block spans. The tokenizer singleton is assigned only after validation. Poll failures explicitly schedule retries. Modal tab roles and guidance text now match the browser selectors. Sidebar phase mapping remains correct: Quality Center 2, Research Explorer 5, Assistant 4, Model Lab 6. These roadmap numbers differ from the Week 2 implementation-step numbers.

## K1 — P2: Action guards compare stale closure values

`frontend/src/components/library/QualityCenterModal.tsx:335-339` compares captured paper/filter/cursor values to copies made by the same handler. They cannot detect a subsequent render changing paper or filters. The reprocess guard at line 365 has the same problem; its stale `loadData(true)` can also supersede the current request counter and fetch the previous paper.

Reproduction: copy `frontend/src/test/quality-center.test.tsx` to a temporary sibling test, import `act`, and insert `await act(async () => { await Promise.resolve(); });` immediately before the absence assertion following `resolveReprocess(...)`. Run `npx vitest run src/test/quality-center.review.test.tsx -t 'guards late'`. Result: **1 failed, 1 passed, 9 skipped**. The late reprocess success message appears after switching papers. The analogous pagination test passed in that scheduling; code inspection still establishes that its closure comparisons are ineffective. The current tests assert absence before the delayed continuation has necessarily executed. Remove the temporary duplicate after running.

Use a current identity ref or cancellation/request tokens invalidated on paper/filter/generation changes and close. Guard success, error and finally updates for every action. Await B's loaded state before resolving A in tests; explicitly await A's continuation before negative assertions. Cover close/reopen, filter changes and generation changes as well as paper switches.

## K2 — P2: Initial loads publish mixed-generation snapshots

`QualityCenterModal.tsx:211` rejects resource disagreement only when `isPolling` is true. Initial/filter loads call `loadData(false)` and publish status/chunks/sections/pages even when their run IDs disagree. A generation can publish between those independent requests. If the resulting status is terminal for this phase, no subsequent poll repairs the mixed view.

Require a coherent snapshot before setting state on every load, with bounded retry/cancellation and an explicit unavailable state if agreement cannot be reached. Add an initial-load generation-race regression; polling-only tests do not cover it. This finding is established by code inspection, not a new live browser reproduction.

## K3 — P2: Migration backfill guesses incorrect cleaned offsets

`backend/migrations/versions/0008_add_block_spans_to_sections.py:91-98` falls back to matching the first 30 raw characters, then uses the entire raw block length for the cleaned endpoint. Dehyphenation makes those lengths unequal. A prefix match does not establish full-text correspondence.

Run `.venv/Scripts/python scripts/review_phase4_span_migration_probe.py`. This upgrades a disposable populated database from 0007 to head and prints:

```text
CLEANED_TEXT_LENGTH 46
MIGRATED_SPANS [['b', 1, 0, 48]]
SPAN_EXCEEDS_TEXT True
```

Use deterministic cleaning/full correspondence and validate all bounds. If exact reconciliation is impossible, retain an explicit unresolved state. Also implement the previously requested policy for already-published chunks with approximate provenance: 0008 updates sections only, so historical chunk references remain unchanged. Use a forward repair with safe reprocessing/versioning or explicit invalidation; preserve PDFs and historical records.

## K4 — P2: Configured tokenizer and persisted chunk identity still diverge

`backend/app/services/chunking_service.py:51-52` accepts configured model/revision; `get_tokenizer_metadata()` reports those settings, but chunk construction at line 350 still records the constant MiniLM model name. The 256-token cap remains hard-coded and only tokenizer metadata is checked. Alternate settings can therefore report a different model in worker metadata and chunk records, without resolving the embedding model's effective limit. Either enforce the supported MiniLM identity/revision explicitly or resolve and persist one consistent validated identity/cap. The rejected-singleton bug is fixed; this separate part of J4 remains open.

## Verification and acceptance limits

- Submitted frontend suite, after removing the temporary diagnostic: **36 passed**. ESLint and Prettier passed. TypeScript/build completed successfully.
- The settled deferred-response diagnostic fails as described in K1; migration probe confirms K3.
- Ruff lint passed across backend/tests/scripts/worker. Ruff formatting fails in `tests/backend/test_database.py` at the version assertions around lines 1251 and 1288.
- Backend suite with disposable process-level DATA_DIR/DATABASE_URL: **170 passed, 6 failed**, 122 warnings, 397.17 seconds. Failures: five browser-wrapper subprocess/lifecycle cases (`frontend_failure_terminates_owned_backend_tree`, `runner_failure_terminates_owned_backend_and_frontend`, `success_terminates_owned_backend_and_frontend`, `unrelated_process_and_attached_server_remain_alive`, and environment preservation with URL `http://127.0.0.1:18765`), plus `test_r2_lease_liveness_and_worker_kill_recovery`. Observed subprocess timeouts included 15/20-second limits; the recovery subprocess had not claimed extraction by its deadline. This concurrent run alone does not establish a Phase 4 regression. An isolated retry is recorded below.
- Isolated `.venv/Scripts/python -m pytest --lf -q --tb=short` with fresh disposable environment: **all 6 passed**, 2 warnings, 73.92 seconds. These failures were not reproduced in isolation; do not report them as confirmed application regressions or call the original full run a clean pass. Review-owned subprocess remnants from the timed-out run were cleaned up by matching its unique pytest temporary directory.
- Browser acceptance was not rerun in this review. The changed tracked summary reports PASS, but the harness remains unchanged: its Phase 4 gate checks headings/banner/modal/tabs/Escape, without owning a worker lifecycle or proving completed chunk processing, source correctness, page >1 navigation, pagination and race recovery. Treat that PASS as a scoped UI smoke result, not complete Phase 4 acceptance.

See `docs/PHASE_4_LATEST_PROMPT.md` for the corrective handoff. Historical review findings superseded by confirmed repairs above should not be reopened wholesale.
