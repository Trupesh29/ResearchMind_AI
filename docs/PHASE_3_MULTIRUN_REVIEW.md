# Phase 3 multi-generation migration review

Reviewed application commit `5e168f1` against `b5d1349` on 2026-10-18. No application code changed during this review.

## H1 — P1: 0005 collapses valid page generations and blocks upgrades

`backend/migrations/versions/0005_repair_historical_generation_attribution.py:111-115` updates every page for a paper to the latest successful extraction run. The worker deliberately retains older pages when publishing a new generation (`worker/engine.py:517-562`). A valid 0004 database can therefore have page 1 for successful run A and page 1 for successful run B, with current/published=B. The blanket UPDATE changes A's row to B and violates `(paper_id, run_id, page_number)` uniqueness. This is an ordinary successful reprocess history, not corrupt input.

Reproduction: `.venv/Scripts/python scripts/review_phase3_multirun_probe.py`. The script creates a disposable 0004 database with two successful extraction jobs and their distinct pages, then attempts upgrade to head:

```text
MULTIRUN_UPGRADE_FAILED UNIQUE constraint failed: pages.paper_id, pages.run_id, pages.page_number
PAGES [('page-A', 'A', 'A'), ('page-B', 'B', 'B')]
REVISION 0004_add_generation_and_fencing_controls
```

The diagnostic catches the exception so it can print preserved rows and revision; exit zero does not mean migration success. With non-overlapping page numbers, the same broad UPDATE can silently relabel historical pages instead of raising. Preserve already-valid per-run page identities. Restrict repair to demonstrably incorrect legacy attribution and handle ambiguity without collapsing separate generations. Add a real multi-success fixture and a worker-produced successful reprocess database; the existing historical matrix only inserts one page generation per paper.

An appended migration alone cannot fix an upgrade that fails before reaching it. Support databases still at 0004 and those already at 0005; document the compatibility strategy, preserve 0003, and do not reset/stamp away history or delete retained output.

## Confirmed improvements and evidence

- Full backend suite with process-level disposable DATA_DIR/DATABASE_URL: **151 passed**, 106 warnings, 128.40 seconds. Includes subprocess kill/recovery, browser-runner integration, migration matrix, and rotated/cropped overlay tests.
- Frontend `npm test -- --run`: **25 passed**, four files, 44.29 seconds.
- Ruff lint and formatting across backend, worker, tests, scripts: passed; 50 files formatted.
- Original and follow-up probes confirm one claim winner, duplicate reprocess rejection, HTTP 200 detail/library responses, refreshed-lease preservation, retry processing status, and generic public fallback.
- The prior acceptance probe now reports current=run-new, published/pages=run-old and `is_stale=True`.
- Regenerated and personally inspected the 90-degree overlay: its red rectangle now surrounds the text. Rotation/crop tests include pixel enclosure and negative controls. G2 is resolved for the tested cases.
- Frontend ESLint, Prettier, TypeScript checking, and production build passed. No fresh live browser acceptance run was performed; harness tests are not a live browser run.

VERDICT: FAIL -- H1 blocks valid populated upgrades despite passing existing suites. Keep Phase 3 local.
