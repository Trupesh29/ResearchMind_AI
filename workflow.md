# ResearchMind AI agent workflow

Independent completion review (2026-10-18, application `abdde12`): PASS for the reviewed Phase 3 repair. H1 is resolved; 154 backend tests, 25 frontend tests, four probes, static/build checks and 8/8 live browser library criteria passed. See `docs/PHASE_3_FINAL_REVIEW.md`. No corrective prompt needed. Keep local; publication and Phase 4 were not performed by this review.

Latest repair checkpoint (2026-10-18): Finding H1 resolved. Phase 3 remains local on branch manav. Repaired 0005 to preserve multi-generation pages and added forward migration 0006 for 0005 databases. 154 backend tests, 25 frontend tests, and all 4 probes pass. VERDICT: PASS -- multi-generation preservation repaired.

## Purpose

Guide implementation and review with less redundant agent context, while preserving correctness. This is a development-agent workflow, not application runtime functionality. Read `decision.md` for current scope and `docs/PHASE_2_PROMPT.md` for the Week 1 Phase 2 handoff.

## 1. Establish scope

Read applicable instructions, `git status --short`, the relevant diff, and the current task. Preserve existing uncommitted work. Current authorized implementation scope is Week 2 Phase 3 Multi-Generation Preservation repair (H1): preserve multiple successful page generations, prevent unique constraint collisions and silent relabeling in migrations, provide compatible upgrade path for 0004 and 0005 via repaired 0005 and forward migration 0006. Keep Phase 3 local for independent review; do not push or advance to Phase 4.

Gravitas policy equivalent:

```json
{"planning":"compact","context_depth":"dependency","verification_depth":"impact","delegation":"none","reason_codes":["phase-2-library","database-and-file-lifecycle"]}
```

This is a documented policy choice, not evidence that Gravitas CLI/hooks ran.

## 2. Understand the code efficiently

Read `F:/dev/.agents/skills/gravitas/SKILL.md` and `F:/dev/.agents/skills/gravitas/references/reconnaissance.md`.

Search the command/resource inventory by task purpose, read selected instructions, and verify current availability. Use `rg` for symbols and paths. Start with changed targets, direct callers, public types, configuration/migrations, and their tests. Expand only when dependencies or failures justify it. Avoid repeated full-file dumps, generated bundles, lockfile contents, node_modules, and model/data directories unless directly relevant.

Keep concise notes containing paths, contracts, findings, and observed results. Do not store hidden reasoning. Broad resource discovery does not require loading every skill body. Do not install a runtime merely to claim skill use or token savings.

## 3. Apply resources by responsibility

All slash-command registrations below are unverified; use the real file as a direct-read fallback. These are sequential instructions, not an executable slash chain.

| Candidate | Instruction file | Responsibility |
|---|---|---|
| `/gravitas` | `F:/dev/.agents/skills/gravitas/SKILL.md` | Scoped reconnaissance, decisions, evidence gates |
| `/debug` | `F:/dev/.agents/workflows/debug.md` | Reproduce and fix demonstrated defects |
| `/test` | `F:/dev/.agents/workflows/test.md` | Behavioral regression tests and affected checks |
| `/visual-verification` | `F:/dev/.agents/skills/visual-verification/SKILL.md` | Actual browser inspection and keyboard/responsive behavior |
| `/verification-before-completion` | `F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md` | Fresh evidence and accurate completion status |

## 4. Implement and verify

Reproduce each finding using disposable databases/storage. Write the relevant regression, make a focused correction, and run targeted plus affected tests. Do not reset user changes or real data. For migration changes, verify both fresh installs and populated upgrades without deleting records.

Required current checks from the project root:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check backend tests scripts
.venv/Scripts/ruff format --check backend tests scripts
```

Before running pytest, verify isolation is complete; until then, redirect DATA_DIR and DATABASE_URL to disposable storage at process level. Do not equate a guarded run with proof that fixtures isolate themselves.

From `frontend/`:

```powershell
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
```

Inspect each exit code separately. Browser checks cover 1440, 768, and 375 pixel widths, Tab/Shift+Tab, Escape, focus restoration, background interaction, overflow, reduced motion, and console errors. If unavailable, record the exact limitation instead of claiming accessibility compliance.

## 5. Record and hand off

Publication order (user instruction, 2026-10-17): push an accepted release checkpoint to `manav` first, verify the remote ref, then push the same checkpoint to `main`. Before this completion review, both remote branches contained the Phase 1 checkpoint `24eadea`; verify current refs when publishing. Keep incomplete Phase 2 work local.

Commit/publication policy (user instruction updated 2026-10-17): after reviewing and checking task changes, create a local Git commit. Phase 1 has been explicitly published to remote main at 24eadea. Do not push Phase 2 until it is complete and accepted; the current corrective handoff ends with a local commit for independent review. A commit records a checkpoint, not proof of acceptance. Review staged files and exclude secrets, runtime data, and unrelated changes. Do not create empty commits.

Update `decision.md` only for actual decisions or changed evidence. Record Phase 2 commands, outcomes, warnings, and unresolved gates in `docs/PHASE_2_VERIFICATION.md`; retain Phase 1 reports as historical evidence. Distinguish static checks, tests, live application, browser, clean setup, ML, and generator results. Do not copy old timings or outputs as new evidence.

End each verification summary with `VERDICT: PASS` or `VERDICT: FAIL -- <unmet criterion>`, scoped to what was actually checked. A passing test suite does not override failed acceptance criteria.

## Current Phase 3 acceptance review (2026-10-18)

Independent review of `3c7743d` confirms the prior narrow API, migration-column, retry-status, lease-refresh, and error-fallback probes now pass. Acceptance remains blocked by G1 (migration misattributes retained pages to a newer failed run) and G2 (double-rotated overlay evidence passes without correspondence checks). Focused Phase 3/database tests returned 29 passed and 1 failed in subprocess recovery; frontend workers and a PowerShell harness rerun timed out. See `docs/PHASE_3_ACCEPTANCE_REVIEW.md` and `docs/PHASE_3_ACCEPTANCE_FIX_PROMPT.md`. Keep Phase 3 local.

VERDICT: FAIL -- G1/G2 and fresh verification gates remain open.

## Historical Phase 3 follow-up review (2026-10-18)

Independent review of `bd78083` confirms narrow claim/reprocess/geometry improvements but reproduces HTTP 500 paper responses, missing schema upgrades from original 0003, incorrect status after retries, refreshed-lease retirement, and unsafe unknown-error fallback. Process-recovery and visual evidence remain incomplete. See `docs/PHASE_3_FOLLOWUP_REVIEW.md` and `docs/PHASE_3_FOLLOWUP_PROMPT.md`. Keep Phase 3 local pending corrections and acceptance.

VERDICT: FAIL -- follow-up findings F1–F6 remain open.

## Historical Phase 3 Repair Status (2026-10-18)

Repaired Phase 3 implementation resolving findings R1–R7 from `docs/PHASE_3_REVIEW.md`:
- R1: Atomic single-query claims with rowcount check, atomic lease recovery, and fencing token validation.
- R2: Background `LeaseHeartbeat` keeping lease alive throughout validation hashing and extraction, plus cooperative cancellation if lease lost.
- R3: Database-enforced partial unique index `uq_active_job_per_paper` on `(paper_id) WHERE status IN ('queued', 'running')`, raising 409 Conflict on concurrent reprocess requests. Generation isolation: `Page.run_id` and `paper.published_run_id` protect published output from in-flight or failed generations.
- R4: Public error sanitization stripping drive letters, local paths, and private directory names in all public status and stage details.
- R5: Geometry consistency across rotation (0, 90, 180, 270) using `page.rotation_matrix` transformation and clamping coordinates within page dimensions.
- R6: Metadata heuristics distinction: PDF creationDate is never promoted to publication year; uncertain headers are not promoted to authors; structured evidence dictionary for provenance.
- R7: Separate stage-attempt history retention: expired leases mark previous attempt as `failed` with explanation and insert attempt+1 as a new row.

Verified by:
- 147 passed pytest backend tests (including all 7 R1–R7 acceptance regressions) in 61.74s.
- `scripts/review_phase3_probe.py` passing with 1 claim winner, 409 rejection on duplicate reprocess, sanitized error string without paths, and rotated box strictly bounded.
- Ruff lint and formatting clean on all 45 files (including `worker`).
- Frontend 25 vitest tests passed, ESLint, TypeScript (`tsc --noEmit`), and Vite build clean.
- Kept local on branch `manav` for independent review. Phase 2 remains published on remote at `4058b2d`.

VERDICT: PASS — Week 2 Phase 3 Repair (Local Checkpoint).

## Historical Phase 3 Implementation Status (2026-10-17)

Week 2 Phase 3 (Persistent Processing and PDF Extraction) is fully implemented and verified:
- Persistent processing jobs (`ProcessingJob`), stage attempts, generation identity (`run_id`), worker heartbeat leases, and claim-token fencing.
- Page text and block coordinate extraction (`Page`), 1-based page indices, bounding boxes `[x0, y0, x1, y1]` in points with top-left origin convention, visual rotation degrees.
- Quality heuristics (`possible_scan`, `table_unreliable`, `equations_may_be_missing`), metadata provenance (`pdf`, `text`, `inferred`), and strict rejection of all-image documents (`UnsupportedTextError`).
- Standalone CLI worker (`worker/main.py`, `worker/engine.py`) with short DB transactions, atomic claims, expired lease reclamation, and stale claim fencing.
- Inspection & Reprocessing APIs (`GET /status`, `GET /pages`, `GET /pages/{page_number}/blocks`, `POST /reprocess` with 409 conflict detection).
- Verified by 140 backend tests, 25 frontend tests, 0 Alembic schema drift, Ruff check/format clean, tsc and vite build clean.
- Scope boundary strictly preserved: papers halt in `status = 'processing'` awaiting Phase 4 sectioning/chunking.

VERDICT: PASS — Week 2 Phase 3.

## Historical Phase 2 status (2026-10-17)

Review of 42baf49 accepted Phase 2. Fresh 133 backend / 25 frontend tests and static/build checks passed. Normal and 750 ms delayed browser runs passed all 8 criteria. An independent injected unfiltered response failed the real browser search gate as expected. No corrective prompt is needed. Publish the accepted checkpoint to manav, verify the ref, then main under the existing user instruction.

VERDICT: PASS — Week 1 Phase 2.

## Historical implementation status (2026-10-17)

Finding S1 (search acceptance race and filtering assertions) has been resolved and verified. Search verification utilizes pre-registered response waits with URL/query/workspace matching predicates, dual distinct PDF fixtures, scoped row locators, and negative/empty/cleared verification. Verified with 133 backend pytest, 25 frontend vitest, static checks, and live isolated Chrome browser acceptance runs under normal execution and 750 ms deliberate network latency. All 8 browser acceptance criteria passed. Phase 2 remains committed locally for independent completion review; unpushed per Phase 2 policy.

- Scope: Workspace Management & PDF Research Library (Phase 2 S1 Corrective Repair)
- Tests: 133 pytest passed (including `test_phase2_fixes.py` with 22 tests, `test_browser_runner.py` with 50 tests), 25 Vitest passed (including 16 in `library.test.tsx`), tsc typecheck passed, eslint passed, prettier passed, ruff check/format passed (37 files), vite build passed.
- Live Browser Suite: 8 of 8 criteria passed on disposable database/storage across both standard run and 750 ms latency run (`no_horizontal_overflow`, `routes_and_navigation`, `mobile_drawer_accessibility`, `reduced_motion_suppressed`, `contrast_ratios`, `api_states_and_recovery`, `clean_operation`, `phase2_library_lifecycle`).
- `VERDICT: PASS`

## Historical review status (306bd9e)
Review of 306bd9e: Q1/Q2 resolved; 130 backend and 23 frontend tests passed; browser acceptance failed `search_success` (7/8 passed). S1 resolved via `docs/PHASE_2_SEARCH_VERIFICATION_PROMPT.md`.


## Ralph Loop guidance for corrective work

Apply the Ralph-style bounded loop in `F:/dev/.agents/workflows/debug.md`: reproduce, change one supported hypothesis, verify, and retain concise evidence. Limit a hypothesis loop to 3–5 iterations and re-diagnose after two identical failures. Continue remaining authorized findings after replanning. A standalone Ralph Loop skill/command was not found in accessible inventories; use the verified workflow directly instead of inventing activation. See `docs/PHASE_2_FIX_PROMPT.md` for the current repair task.
