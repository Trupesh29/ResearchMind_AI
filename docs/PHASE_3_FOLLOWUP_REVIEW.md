# Phase 3 follow-up review — bd78083

Reviewed 2026-10-18 against `2ef4ec2`. Application code was not changed. The repair improves atomic claims, concurrent reprocess admission, ordinary missing-file errors, and the previously reproduced rotated geometry. The original diagnostic now reports one claim winner, one accepted reprocess plus one 409, a generic missing-file error, and transformed bounds within the visual page.

## Remaining findings

### F1 — P1: Structured provenance breaks paper responses

`backend/app/schemas/paper.py:15` still declares `metadata_source: dict[str, str]`, while extraction now persists nested evidence dictionaries. `PaperResponse.model_validate()` raises `ValidationError` on the new value. Both paper detail (`backend/app/api/papers.py:94`) and library listing (`backend/app/services/paper_service.py:377`) use that validator. A disposable TestClient probe confirmed HTTP 500 from both `/api/papers/p` and `/api/papers?workspace_id=w` with the new stored provenance format. Update the typed backend/OpenAPI/frontend contract together, retain an explicit policy for existing string-valued metadata, and test actual upload → worker → detail/list responses with nonempty provenance.

### F2 — P1: Rewriting revision 0003 leaves existing Phase 3 databases incompatible

`backend/migrations/versions/0003_add_processing_jobs_and_pages.py:22-23` adds generation fields inside an already-used revision, with other changes to page generation storage and indexes. A disposable database built from the original 0003 at `2ef4ec2`, followed by the current `upgrade head`, remained stamped 0003 without `papers.current_run_id`. The new ORM therefore queries columns that do not exist. Add a forward migration preserving original 0003 history and data. Handle both original and rewritten 0003 layouts explicitly, including generation backfill and potentially competing active jobs; do not reset or merely stamp databases. Test populated upgrades, not only fresh installs or upgrades from Week 1.

### F3 — P1: Successful retries permanently report failed

`backend/app/services/processing_service.py:147-162` marks a run failed if any preserved attempt failed, then selects the first attempt for each stage. After lease recovery preserves attempt 1 as failed and attempt 2 succeeds, the status API still returns `failed`, attempt 1, and the old lease error. The independent probe reproduced exactly this with the paper still processing. Derive current state from the latest relevant attempts while retaining historical failures in history. Test queued, running, successful, and exhausted retries through the HTTP status route.

### F4 — P1: Recovery can retire a refreshed live lease

`worker/engine.py:207-220` selects expired jobs, but its conditional UPDATE checks only ID/status/token, not whether the heartbeat is still expired. A renewal retains the same token. The probe renewed the heartbeat in a separate committed session after recovery's selection and before its UPDATE; recovery nevertheless marked attempt 1 failed and queued attempt 2. Include the expiry condition in the atomic retirement operation and verify affected rows against concurrent renewal. Test the exact selection → renewal → retirement interleaving.

### F5 — P2: Unknown errors still expose arbitrary exception text

`worker/engine.py:58-67` falls back to regex replacement and returns the remaining exception. The probe `parser failed at F:/private/paper.pdf; token=example-secret` was returned unchanged. Forward-slash Windows paths, UNC paths, other Unix roots, and arbitrary parser content are not reliably sanitized. Use an allowlist of public error categories with a generic fallback; keep restricted diagnostics separate. Verify top-level errors and stage history through HTTP with synthetic sentinel paths/content.

### F6 — P2: Recovery and visual acceptance claims remain unsupported

The verification report says subprocess termination/restart is tested by `test_r2_lease_liveness_and_worker_kill_recovery`. That test contains no subprocess/kill/restart: it runs one thread, sleeps 1 second, and polls the competitor once before the configured 2-second lease could expire. A 2.5-second total sleep does not make that early poll a liveness test. Poll after the original lease would expire while extraction is still active, and independently kill/restart a real worker. Geometric bounds tests improve coverage but do not establish the requested visual overlay alignment. Preserve prior reports as history and identify actual evidence versus pending gates.

## Additional contract gap

Published/current generation IDs are stored but omitted from status/pages/blocks response models. After a failed replacement, clients receive old pages with no generation/staleness marker. Complete the existing generation contract while repairing F1/F3; verify stale output is identifiable without inferring it from unrelated requests.

## Evidence and limits

- Fresh backend suite: **147 passed**, 97 warnings, 69.87 seconds; process-level storage/DB redirected to temporary locations.
- Ruff lint and formatting checks passed after formatting the new review probe (46 Python files); diff whitespace check passed.
- Original diagnostic rerun confirms the four narrow improvements above.
- New disposable diagnostic: `.venv/Scripts/python scripts/review_phase3_followup_probe.py`. Reproduced missing upgrade columns, provenance validation failure, refreshed-lease retirement, failed status after a successful retry, and unsafe unknown-error fallback. It prints observations; exit 0 is not an acceptance verdict.
- No frontend code changed in `bd78083`; frontend/build/browser checks were not repeated in this review. No actual worker kill/restart or visual overlay run was performed by this review.

VERDICT: FAIL -- F1–F6 and generation visibility must be resolved before Phase 3 acceptance. Keep Phase 3 local.
