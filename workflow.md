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

Commit policy (user instruction, 2026-10-16): after reviewing and checking task changes, create a local Git commit. Do not push. A commit records a checkpoint, not proof of acceptance; document unresolved findings and distinguish them from passing checks. Review the staged files and exclude secrets, generated runtime data, and unrelated changes. Do not create empty commits when nothing changed.

Update `decision.md` only for actual decisions or changed evidence. Record Phase 2 commands, outcomes, warnings, and unresolved gates in `docs/PHASE_2_VERIFICATION.md`; retain Phase 1 reports as historical evidence. Distinguish static checks, tests, live application, browser, clean setup, ML, and generator results. Do not copy old timings or outputs as new evidence.

End each verification summary with `VERDICT: PASS` or `VERDICT: FAIL -- <unmet criterion>`, scoped to what was actually checked. A passing test suite does not override failed acceptance criteria.

## Phase 2 Verification Status (2026-10-17)
- Scope: Workspace Management & PDF Research Library (Phase 2)
- Tests: 99 pytest passed, 16 Vitest passed, tsc typecheck passed, eslint passed, prettier passed, ruff passed, vite build passed.
- Live Browser Suite: 8 of 8 criteria passed (`no_horizontal_overflow`, `routes_and_navigation`, `mobile_drawer_accessibility`, `reduced_motion_suppressed`, `contrast_ratios`, `api_states_and_recovery`, `clean_operation`, `phase2_library_lifecycle`).
- `VERDICT: PASS`
