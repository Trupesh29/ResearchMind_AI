# Antigravity prompt — remaining Phase 4 corrections

```text
Repair K1–K4 from @docs/PHASE_4_LATEST_REVIEW.md for application checkpoint 4e09867 in F:/Projects/ResearchMind AI. Preserve confirmed repairs and correct sidebar roadmap badges (Quality Center 2, Explorer 5, Assistant 4, Model Lab 6). Keep Phase 4 local; no push or next-phase implementation.

Read real project context (use @ autocomplete where supported; otherwise directly read these paths relative to the project):
@docs/PHASE_4_LATEST_REVIEW.md
@scripts/review_phase4_span_migration_probe.py
@docs/PHASE_4_FOLLOWUP_REVIEW.md
@docs/PHASE_4_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@ROADMAP.md
@workflow.md
@frontend/src/components/library/QualityCenterModal.tsx
@frontend/src/test/quality-center.test.tsx
@backend/migrations/versions/0008_add_block_spans_to_sections.py
@backend/app/services/sectioning_service.py
@backend/app/services/chunking_service.py
@backend/app/core/config.py
@worker/engine.py
@tests/backend/test_database.py
@scripts/run_browser_suite.ps1
@scripts/run_browser_verification.py

Refresh resource discovery across @F:/dev/.agents/README.md and @F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md, ANTIGRAVITY_LOCAL_COMMANDS.csv, TASK_GUIDE.md, ROUTING.md, CATALOG.md, SOURCES.md and FILE_INDEX.md (all in that docs directory). Check project resources and live exposed MCP schemas too. Inventory presence does not prove menu registration or successful invocation.

Apply these inventory-backed candidates sequentially; registration in the active Antigravity menu is unverified. These are resource instructions, not an executable slash chain. Read each exact instruction file as fallback:
1. /debug and /karpathy-engineering: reproduce K1–K4, trace production boundaries, make scoped corrections.
   @F:/dev/.agents/workflows/debug.md
   @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
2. /test and /python-testing-patterns: regression tests for deferred React responses and populated migration upgrades, plus supported/unsupported tokenizer configuration.
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
3. /visual-verification: verify actual completed processing, source links, paging, recovery and keyboard/responsive behavior in the existing UI.
   @F:/dev/.agents/skills/visual-verification/SKILL.md
4. /ruthless-reviewer and /verification-before-completion: inspect final diff and map each acceptance claim to fresh evidence.
   @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

K1: Replace same-closure comparisons with current identity/request tokens or cancellation. Invalidate on close, paper/workspace, filters and generation changes. Guard action success/error/finally and stale reprocess-triggered reloads. Test A's delayed actions after B is fully loaded and after close/reopen. Settle promises/state with act before asserting absence; the supplied reprocess test fails when that missing wait is added. Do not simply weaken the assertion.

K2: Enforce status/pages/sections/chunks generation agreement on initial/filter loads as well as polling. Never publish mixed snapshots. Use bounded recovery and explicit unavailable state. Test a generation publishing between requests, including awaiting_indexing status that would otherwise stop polling.

K3: Reconcile raw-to-cleaned spans exactly; no first-30-character prefix guess or raw-length endpoint. The disposable upgrade probe currently records end=48 for a 46-character section. Test localized dehyphenation, repeated prefixes, unequal blocks and multi-page data. Add a forward data-preserving repair and explicit treatment of historical chunks with approximate provenance; preserve accepted migration history, PDFs and records. Verify both fresh install and populated upgrades.

K4: Preserve validate-before-cache behavior. Either enforce the supported MiniLM model/revision or resolve actual usable configuration consistently. Chunk rows, worker metadata and token cap must agree with the loaded identity; tokenizer.model_max_length alone does not establish the embedding model limit. Test alternate/invalid settings and repeat failures.

Fix Ruff formatting in the changed test_database.py assertions. The backend run had 170 passes and six subprocess/timing failures; all six passed in isolation. Preserve that evidence distinction and use disposable data for verification. Do not attribute those failures to a product regression without reproduction, or present the initial full run as clean.

MCP/browser responsibilities: inspect live exposed capabilities first. Use an available local browser tool or the existing Chrome harness to produce behavioral evidence and screenshots. No Antigravity MCP invocation is verified by this prompt; if unavailable use local test/browser tooling and report limitations. Official installed tokenizer/model configuration is the first reference for K4; if external documentation is required, use a currently exposed read-only browsing tool with its actual schema and official sources. No design generation, Figma restoration, private-paper upload or external deployment is needed.

Extend the existing browser smoke gate with a disposable worker lifecycle, real processed chunks, page >1 source navigation, >100-chunk pagination, injected transient recovery and late-response isolation. Use response-driven waits and negative controls. Preserve ownership/cleanup boundaries and do not stop the user's unrelated running app. Do not present headings/tabs/Escape alone as full Phase 4 acceptance.

Run focused regressions, backend/frontend suites, Ruff lint/format including worker/scripts, frontend lint/format/typecheck/build, migration preservation and the expanded browser checks. Record exit codes, fixture/run identities and limitations. Update verification/workflow documentation so current findings supersede historical PASS statements. Create a task-owned local commit after checks; do not push. Report per-finding results and evidence rather than a blanket completion claim.
```
