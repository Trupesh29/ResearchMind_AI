# ResearchMind AI agent workflow

## Purpose

Guide implementation and review with less redundant agent context, while preserving correctness. This is a development-agent workflow, not application runtime functionality. Read `decision.md` for current scope and `docs/PHASE_2_PROMPT.md` for the Week 1 Phase 2 handoff.

## 1. Establish scope

Read applicable instructions, `git status --short`, the relevant diff, and the current task. Preserve existing uncommitted work. Current authorized implementation scope is Week 1 Phase 2: workspace CRUD, safe PDF upload/storage, library search/list/delete, original PDF viewing, related tests, and documentation. Preserve Phase 1 behavior and defer ingestion, retrieval, and analysis to their scheduled weeks. Do not push changes.

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

Publication order (user instruction, 2026-10-17): push an accepted release checkpoint to `manav` first, verify the remote ref, then push the same checkpoint to `main`. Both remote branches now contain the completed Phase 1 checkpoint `24eadea`. Keep incomplete Phase 2 work local.

Commit/publication policy (user instruction updated 2026-10-17): after reviewing and checking task changes, create a local Git commit. Phase 1 has been explicitly published to remote main at 24eadea. Do not push Phase 2 until it is complete and accepted; the current corrective handoff ends with a local commit for independent review. A commit records a checkpoint, not proof of acceptance. Review staged files and exclude secrets, runtime data, and unrelated changes. Do not create empty commits.

Update `decision.md` only for actual decisions or changed evidence. Record Phase 2 commands, outcomes, warnings, and unresolved gates in `docs/PHASE_2_VERIFICATION.md`; retain Phase 1 reports as historical evidence. Distinguish static checks, tests, live application, browser, clean setup, ML, and generator results. Do not copy old timings or outputs as new evidence.

End each verification summary with `VERDICT: PASS` or `VERDICT: FAIL -- <unmet criterion>`, scoped to what was actually checked. A passing test suite does not override failed acceptance criteria.

## Phase 2 Verification Status (2026-10-17)
Findings Q1 and Q2 from `docs/PHASE_2_CURRENT_REVIEW.md` resolved via architectural fixes and verified with fresh automated test and live Chrome browser evidence. Left unpushed for completion review per Phase 2 policy.

- Scope: Workspace Management & PDF Research Library (Phase 2 Q1/Q2 Corrective Repair)
- Tests: 130 pytest passed (including `test_phase2_fixes.py` with 22 tests, `test_browser_runner.py` with 48 tests), 23 Vitest passed (including 14 in `library.test.tsx`), tsc typecheck passed, eslint passed, prettier passed, ruff passed (37 files), vite build passed.
- Live Browser Suite: 8 of 8 criteria passed on disposable database/storage (`no_horizontal_overflow`, `routes_and_navigation`, `mobile_drawer_accessibility`, `reduced_motion_suppressed`, `contrast_ratios`, `api_states_and_recovery`, `clean_operation`, `phase2_library_lifecycle`).
- `VERDICT: PASS`


## Ralph Loop guidance for corrective work

Apply the Ralph-style bounded loop in `F:/dev/.agents/workflows/debug.md`: reproduce, change one supported hypothesis, verify, and retain concise evidence. Limit a hypothesis loop to 3–5 iterations and re-diagnose after two identical failures. Continue remaining authorized findings after replanning. A standalone Ralph Loop skill/command was not found in accessible inventories; use the verified workflow directly instead of inventing activation. See `docs/PHASE_2_FIX_PROMPT.md` for the current repair task.
