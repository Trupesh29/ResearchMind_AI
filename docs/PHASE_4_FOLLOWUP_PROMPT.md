# Antigravity prompt — finish Phase 4 repair

```text
Repair the remaining Phase 4 findings J1–J4 in F:/Projects/ResearchMind AI, application checkpoint fc38b35. Preserve the corrected sidebar phase mapping/routes, PDF page argument, bounded no-space splitter and formatting. Phase 3 is already published; keep Phase 4 local and do not advance to another phase.

Read project context (resolve @ through autocomplete or directly read the project-relative file):
@docs/PHASE_4_FOLLOWUP_REVIEW.md
@scripts/review_phase4_followup_probe.py
@scripts/review_phase4_polling.test.tsx.txt
@docs/PHASE_4_REVIEW.md
@docs/PHASE_4_PROMPT.md
@docs/PHASE_4_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@ROADMAP.md
@backend/app/services/chunking_service.py
@backend/app/services/sectioning_service.py
@backend/app/services/processing_service.py
@backend/app/db/models.py
@worker/engine.py
@frontend/src/components/library/QualityCenterModal.tsx
@frontend/src/app/App.tsx
@scripts/run_browser_verification.py
@tests/backend/test_chunking.py
@tests/backend/test_phase4_processing.py
@frontend/src/test/quality-center.test.tsx
@workflow.md
@decision.md

Refresh task-relevant commands, local/global skills, workflows, rules, attachment records and live MCP availability using:
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md

Apply these resources sequentially, reading their instructions first. Slash candidates are inventory-backed, but visible menu activation is unverified; use direct-read fallbacks. This list is not an executable slash-command chain.

1. /debug + /karpathy-engineering: reproduce J1–J4 and trace real worker/UI boundaries before editing. Produce a concise per-finding acceptance matrix and focused repair.
@F:/dev/.agents/workflows/debug.md
@F:/dev/.agents/skills/karpathy-engineering/SKILL.md
2. /rag-engineer: apply only source transformation, chunk boundaries and provenance guidance. Preserve exact token bounds; no embeddings, retrieval, model training or later-phase features.
@F:/dev/AppData/.gemini/config/skills/rag-engineer/SKILL.md
3. /test + /python-testing-patterns: turn the supplied reproducers into regressions and test persistence/reconstruction, unequal source blocks, failed loader retries, transient polling and deferred action responses. Test production paths instead of helper-only examples that bypass the failing boundary.
@F:/dev/.agents/workflows/test.md
@F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
4. /visual-verification: verify actual source navigation, loaded chunk pagination, recovery, narrow-screen and keyboard behavior locally; no redesign is needed.
@F:/dev/.agents/skills/visual-verification/SKILL.md
@F:/dev/.agents/docs/UX_COMPONENT_CHECKLIST.md
5. /ruthless-reviewer + /verification-before-completion: audit data truthfulness and all async paths, then reconcile each completion claim with fresh evidence.
@F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
@F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

J1: Persist or deterministically reconstruct exact raw/cleaned source spans through sectioning -> database -> chunking. Equal partitions, interpolated pages, proportional dehyphenation scaling and nearest-block guesses cannot be reported as exact provenance. Add a forward data-preserving migration if storage changes; preserve accepted history and existing pages/chunks. Handle already-created approximate mappings honestly with an explicit repair/reprocess policy. Verify actual worker output with unequal blocks on different pages, localized text transformations and repeated text.

J2: A failed timeout-driven poll must explicitly schedule the next bounded attempt; changing a ref does not rerun an effect. Preserve queued/running polling and terminal stopping. Make the supplied fake-timer regression pass, and verify real transient API failure/recovery without stale state.

J3: Guard Load More and reprocess as well as initial/poll fetches. Capture paper/workspace/filter/generation identity, cancel or ignore old completions, prevent late action responses from replacing new state, and reset action/filter state appropriately. Validate generation agreement across separately fetched status/pages/sections/chunks before displaying a combined snapshot. Cursor behavior must be explicit for generation/filter changes; test late Load More A after switch to B and late reprocess A after close/switch.

J4: Do not publish a tokenizer singleton before validation succeeds. A second call after rejection must also reject or load a valid candidate. Validate the actual model's usable sequence configuration, resolve supported model/revision identity, and persist accurate metadata in chunks and worker records. Either enforce supported configuration explicitly or support alternatives consistently. No silent unpinned fallback or fabricated identity; missing assets must be actionable and public errors sanitized.

Fix planned-feature descriptions to match ROADMAP.md: Explorer Phase 5 concerns source sections/cited summaries/findings; Model Lab Phase 6 concerns the SciCite classifier experiment/results. Retain correct roadmap phase numbers and active/planned navigation.

TOOLS: Recheck actual exposed tools and schemas. Use local browser automation/Chrome harness for the required UI outputs; cached MCP schemas do not prove authentication. If official tokenizer configuration documentation is needed and live scrapling make_request is available, use url, method="GET", extraction_type="markdown" (schema fallback @F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json). Native browsing or installed model/package assets are fallbacks. Record configured/discovered/authenticated/called states separately. No remote design generation, Antigravity Figma restoration, private PDF upload, paid service, or Replit relocation is needed for these repairs.

Extend Phase 4 browser acceptance beyond headings/modal/tabs: actual processed chunks, correct page>1 source navigation, >100-chunk paging, injected transient failure/recovery, late-response isolation, keyboard and 375/768/1440 layouts. Use response/state-driven waits and negative controls; do not turn fixed sleeps or screenshot existence into acceptance.

The independent live run failed phase4_quality_center: the runner expects different guidance text and role=tab controls that the UI does not render. The modal visibly opens, but shows validating/5% and zero chunks because the harness does not start a worker. Repair the selector/accessibility contract and own a disposable worker lifecycle for real pipeline evidence; do not simply drop the failing checks. Existing backend tests passed 173 and frontend tests passed 32; the new polling regression still fails.

Run affected regressions then full backend/frontend suites, Ruff including worker/scripts, frontend lint/format/typecheck/build, migration preservation/drift, process recovery and live browser checks. Inspect each exit code. Save fixture IDs/hashes, tokenizer identity, exact source comparisons, browser artifacts and limitations. Update verification/API/schema/decision/workflow docs as needed; distinguish historical evidence from fresh results. Create a task-owned local commit after verification, no push. Finish with each J finding's evidence and scoped PASS/FAIL, not a blanket complete claim based on old suites.
```
