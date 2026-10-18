# Phase 3 acceptance review — 3c7743d

Reviewed 2026-10-18 against `0398c09`. Application code was not changed during this review.

## Confirmed improvements

The original claim/reprocess probes now produce one claim winner and one accepted reprocess plus one 409. The follow-up probe confirms structured provenance serialization and HTTP 200 for both paper detail and library listing, a forward migration to 0004, preservation of a concurrently refreshed lease, processing status after the retry scenario, and a generic unknown-error fallback. The new tests include a real worker subprocess kill/recovery path and a competitor poll beyond the original lease duration.

These improvements resolve the narrow prior reproducers. Two acceptance issues remain below.

## G1 — P1: Migration attributes retained pages to a failed replacement run

In `backend/migrations/versions/0004_add_generation_and_fencing_controls.py`, the backfill selects the latest job's `run_id`, sets `current_run_id` from it, and assigns that same run to `published_run_id` whenever any pages exist. It then tags old pages with that run. A normal original-0003 history can contain successful extraction A, pages from A, and a later failed reprocess B that retained A's pages. The migration relabels those pages as B and exposes them as fresh.

Reproduced with a disposable original-0003 database containing an old successful extraction, an old page, and a later failed extraction:

```text
BACKFILLED_GENERATIONS ('run-new', 'run-new')
PAGE_ASSIGNED_RUN run-new
RETAINED_OLD_PAGES_IS_STALE False
```

Current-run selection and published-output attribution must be separate. Infer the published run from valid successful extraction/page evidence when possible; preserve uncertainty explicitly when historical provenance is ambiguous rather than inventing a successful generation. Keep retained pages visible with accurate staleness. Reconcile surviving active jobs with the chosen current run as part of the same migration policy. Add migration fixtures with multiple runs and failed/queued replacement attempts, not only duplicate attempts within one run.

## G2 — P2: Rotated overlay test applies rotation twice and cannot detect misalignment

`tests/backend/test_phase3_processing.py::test_r5_rotated_and_cropped_geometry_consistency` sends visual/rotated extraction bounds directly into `page.new_shape().draw_rect()`, which draws in the page's unrotated coordinates. Rendering then rotates those shapes again. The test only asserts file existence, dimensions, and nonempty pixels; none establish alignment with source text.

The review reproduced the exact test's 90-degree procedure and visually inspected `artifacts/review_phase3_geometry/test_overlay_rotation90.png`: the text is near the left edge while the red rectangle is near the upper right. The test accepts this visibly incorrect evidence. This is a defect in the validation artifact, not a new claim that the API's visual coordinates are wrong.

For PDF-page drawing, convert visual bounds back through the inverse rotation transform; alternatively draw in the rendered pixmap's coordinate frame with the correct scale. Add meaningful correspondence assertions and inspect persistent overlays for 0/90/180/270 degrees and cropped pages. Ensure a deliberately shifted/double-rotated box fails the gate. Update the verification report so generating a nonempty screenshot is not called visual acceptance.

## Evidence

Run `.venv/Scripts/python scripts/review_phase3_acceptance_probe.py` to reproduce G1 and generate G2's local artifact. It uses disposable database storage and writes only synthetic PDF/PNG evidence under `artifacts/review_phase3_geometry`. It prints observations; exit 0 is not acceptance.

- Both previous diagnostic scripts completed with the improved outputs described above.
- Ruff lint/format checks passed (48 files, including the new diagnostic); application static checks were not weakened.
- Frontend ESLint, Prettier, type checking, and production build completed successfully. Vitest ran no tests: all four fork workers timed out during startup. This is a verification limitation, not a demonstrated frontend application regression.
- The full backend run was stopped after repeated failures in PowerShell browser-runner integration tests. No full-suite pass is claimed. A focused rerun of `test_suite_rejects_occupied_port_without_touching_existing_server` failed with `subprocess.TimeoutExpired`: the PowerShell wrapper exceeded the test's 15-second deadline. This does not by itself establish an application regression.
- Focused `tests/backend/test_phase3_processing.py tests/backend/test_database.py`: **29 passed, 1 failed** in 102.97 seconds. `test_r2_lease_liveness_and_worker_kill_recovery` never observed its subprocess enter extraction; its new validation job remained queued. Captured output contained only the PyMuPDF deprecation warning. The test kills the process before printing `Poll=1`, so that value does not prove the worker exited independently. Real kill/recovery acceptance remains unverified; diagnose startup/readiness and retain a bounded, deterministic state-driven test.
- A live browser acceptance run was not performed during this review. Earlier reports remain historical evidence, not fresh acceptance.

VERDICT: FAIL -- G1 and G2 remain; broader verification must also be completed without overstated results. Keep Phase 3 local.
