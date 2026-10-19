# Antigravity corrective prompt

```text
Repair only the remaining N1–N2 findings for F:/Projects/ResearchMind AI at application checkpoint 573223a. Read @docs/PHASE_4_REVIEW_573223a.md. Preserve the repaired provenance mapping, forward migrations, action-finally ownership, stale-status handling and disposable database binding. Keep Phase 4 local; no push or next-phase implementation.

Context via real @ paths (direct-read project-relative fallback if autocomplete is unavailable):
@scripts/review_phase4_generation_paging.tsx.txt
@frontend/src/components/library/QualityCenterModal.tsx
@frontend/src/test/quality-center.test.tsx
@scripts/run_browser_verification.py
@scripts/run_browser_suite.ps1
@tests/backend/test_browser_runner.py
@docs/PHASE_4_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@ROADMAP.md
@workflow.md

Refresh the full task-relevant resource inventory through @F:/dev/.agents/README.md and F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md, ANTIGRAVITY_LOCAL_COMMANDS.csv, TASK_GUIDE.md, ROUTING.md, CATALOG.md, SOURCES.md, FILE_INDEX.md, ATTACHMENT_RESOURCE_STATUS_20261019.md and ATTACHMENT_INSTALL_MANIFEST_20261019.json. Consider current namespaced att- resources; do not activate unrelated collections.

Apply these resources sequentially. / candidates are inventory-backed, with active-host menu registration unverified; read their exact @ instruction paths as fallback. This is not an executable slash chain:
- /debug: reproduce the pagination lock and false-positive acceptance gate before changing code.
  @F:/dev/.agents/workflows/debug.md
- /test: regress generation changes/conflicts, old/new pagination ownership, wrong-paper data and delayed response bodies.
  @F:/dev/.agents/workflows/test.md
- /attachment-web-quality: apply loading, disabled-state and feedback criteria to the existing UI without redesign.
  @F:/dev/.agents/skills/attachment-web-quality/SKILL.md
- /att-addy-agent-skills-browser-testing-with-devtools: use actual DOM/network/response evidence for B's preserved data after A settles.
  @F:/dev/AppData/.gemini/config/skills/att-addy-agent-skills-browser-testing-with-devtools/SKILL.md
- /att-addy-agent-skills-code-review-and-quality and /verification-before-completion: audit all invalidation paths and align acceptance claims with fresh evidence.
  @F:/dev/AppData/.gemini/config/skills/att-addy-agent-skills-code-review-and-quality/SKILL.md
  @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

N1: Generation-conflict and generation-change paths invalidate pagination tokens without resetting busy state. The old request's correctly guarded finally therefore cannot clear the spinner. Release busy state explicitly at invalidation; retain guards against stale cleanup touching a newer request. Make the supplied reproduction pass and test a subsequent new request before the old one resolves. Preserve existing paper/filter/close/reopen coverage.

N2: The current browser helper accepts arbitrary chunks as long as a 'Loaded ' label is present. Capture B's actual chunk/run/status identity from the fixture and verify it after A's full response completes and the UI has settled. Use distinct populated A/B fixtures: the independent live run passed while B showed Processing Failed and Loaded 0 of 0 chunks. A response-event notification alone is not a response-body/application completion barrier. Add negative controls with A's real chunk data under B's title and a deliberately delayed body; require the gate to fail for corruption. Retain real success/error-banner and busy-state checks. Distinguish synthetic pagination fixtures from extracted provenance evidence.

MCP: inspect live Chrome DevTools tools/schemas in Antigravity before use. If unavailable, use the existing local Playwright/Chrome harness with an isolated profile and verified disposable backend/database. Report configured/discovered/authenticated/called states honestly. No live DevTools capability is established by this prompt; do not restore Figma, upload private papers, install unrelated tools or disturb the user's running app.

Run targeted regressions, existing backend/frontend suites, Ruff lint/format, frontend lint/format/typecheck/build and safe live browser acceptance including the new negative controls. Record actual exit codes and limitations; distinguish timing failures from product regressions. Update verification/workflow docs to reflect current results rather than appending a conflicting blanket PASS. Commit task-owned changes locally after verification; no push.
```
