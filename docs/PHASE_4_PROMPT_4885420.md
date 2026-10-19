# Antigravity corrective prompt

```text
Repair the remaining findings L1–L5 in F:/Projects/ResearchMind AI at application checkpoint 4885420. Read @docs/PHASE_4_REVIEW_4885420.md first. Preserve the working paper-switch guards, pinned tokenizer restrictions and correct sidebar roadmap mapping. Keep Phase 4 local; no push and no next phase.

Context (@ autocomplete where supported, otherwise direct-read relative to the project):
@scripts/review_phase4_existing_0008_probe.py
@scripts/review_phase4_repeated_provenance_probe.py
@scripts/review_phase4_ui_regressions.tsx.txt
@backend/migrations/versions/0008_add_block_spans_to_sections.py
@backend/app/services/processing_service.py
@frontend/src/components/library/QualityCenterModal.tsx
@frontend/src/test/quality-center.test.tsx
@scripts/run_browser_suite.ps1
@scripts/run_browser_verification.py
@tests/backend/test_database.py
@tests/backend/test_browser_runner.py
@docs/PHASE_4_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@ROADMAP.md
@workflow.md

Refresh discovery using @F:/dev/.agents/README.md and the real files under F:/dev/.agents/docs/: ANTIGRAVITY_PROMPTING.md, ANTIGRAVITY_LOCAL_COMMANDS.csv, TASK_GUIDE.md, ROUTING.md, CATALOG.md, SOURCES.md, FILE_INDEX.md, ATTACHMENT_RESOURCE_STATUS_20261019.md and ATTACHMENT_INSTALL_MANIFEST_20261019.json. Select complementary resources by task purpose, including newly installed attachments. Do not mistake catalog or file presence for menu activation or MCP authentication.

Apply these selected resources sequentially. Slash candidates are inventory-backed but active-host registration is unverified; read the exact @ instruction files as fallback. This is not an executable slash-command chain.
1. /debug — reproduce L1–L5, trace the boundaries, make minimal causal fixes.
   @F:/dev/.agents/workflows/debug.md
2. /test and /python-testing-patterns — meaningful migration, UI concurrency and database-ownership regressions with negative controls.
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
3. /att-addy-agent-skills-browser-testing-with-devtools — inspect real DOM, network completion, console and screenshots for corrected UI behavior; use only supported live tools.
   @F:/dev/AppData/.gemini/config/skills/att-addy-agent-skills-browser-testing-with-devtools/SKILL.md
4. /att-addy-agent-skills-code-review-and-quality and /verification-before-completion — review correctness, state ownership and migration compatibility, and reconcile final claims with fresh output.
   @F:/dev/AppData/.gemini/config/skills/att-addy-agent-skills-code-review-and-quality/SKILL.md
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

L1: Add a forward repair reachable from an already-applied original 0008; do not rely on rewriting its upgrade body. Preserve history, PDFs and records. Test existing-0008 -> new head and fresh install separately. The provided existing-0008 probe currently retains end=48 for 46 characters.
L2: Never infer historical chunk occurrence using the first matching text or section label alone. The probe changes a correct second-occurrence block c into b. Use proven occurrence identity or mark ambiguity and safely regenerate a new version. Cover repeated text, same-label sections, overlaps, unresolved mappings and visible repair errors.
L3: Separate current processing status from the coherent published artifact bundle. is_stale is expected when a replacement run is active or failed; it is not itself cross-resource disagreement. Show terminal failures and labeled older artifacts. Retry true publication races with a genuinely bounded strategy. Make the stale=true regression pass while retaining the stale=false negative control and existing mixed-generation protection.
L4: Give pagination and reprocess independent action ownership or explicitly clear busy state when invalidating an action. Filter changes, generation changes or another action must not strand Enqueueing/Load More. Preserve protection against close/reopen and paper/workspace switches. Settle delayed promises before asserting final state.
L5: Before any worker drain or chunk seed, verify that the local database is the owned disposable database served by the tested backend. HTTP disposable=true alone does not bind local settings to that server. Reject unsafe Attach/missing/mismatched configurations before mutations; do not touch the user's real database or unrelated running app. Test this boundary with independent disposable databases.

Fix acceptance assertions: test automatic transient recovery without changing filters; hold A's response, fully load B, release A and verify B's data/messages/busy state. Demonstrate these gates fail when protections are disabled. Distinguish synthetic pagination fixtures from actual extraction/provenance evidence. Use response/state-driven waits and exact source checks rather than screenshot existence or close/reopen alone.

Tool responsibilities: check live Chrome DevTools MCP tools and schemas in Antigravity before using the browser-testing skill. If unavailable, use the repaired local Playwright/Chrome harness with an isolated profile and owned disposable services; record that fallback. No DevTools MCP invocation/authentication is verified by this prompt. No Figma restoration, remote design generation, private PDF upload, paid service or deployment is needed. Do not install unrelated tools merely to exercise resources.

Run focused regressions, full backend/frontend suites, Ruff lint/format, frontend lint/format/typecheck/build, populated upgrades and safe live browser checks. Review each exit code, distinguish timing/environment failures from reproduced regressions, and update verification/workflow docs to match actual evidence. The current report overclaims bounded retries, unresolved-span handling and browser race recovery. Finish with per-finding evidence and a task-owned local commit; do not push.
```
