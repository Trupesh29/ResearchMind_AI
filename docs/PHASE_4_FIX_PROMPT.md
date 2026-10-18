# Antigravity corrective prompt — Phase 4 review and sidebar accuracy

```text
Repair ResearchMind AI at F:/Projects/ResearchMind AI, application checkpoint 1cf85bf, using docs/PHASE_4_REVIEW.md. Fix P4-01 through P4-07 and complete actual Phase 4 acceptance. Preserve successful Phase 3 behavior and all user data. Phase 3 is already verified published at 6de34b3 on both origin branches; do not republish or push Phase 4. Finish with a local commit for independent review.

Read these real @ contexts, or directly read their paths under the project root if autocomplete does not resolve them:
@docs/PHASE_4_REVIEW.md
@scripts/review_phase4_probe.py
@docs/PHASE_4_PROMPT.md
@docs/PHASE_4_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@ROADMAP.md
@WEEKLY_BUILD_PLAN.md
@API_SPEC.md
@DATABASE_SCHEMA.md
@workflow.md
@decision.md
@backend/app/services/chunking_service.py
@backend/app/services/sectioning_service.py
@backend/app/services/processing_service.py
@worker/engine.py
@frontend/src/components/layout/Sidebar.tsx
@frontend/src/app/App.tsx
@frontend/src/pages/DashboardPage.tsx
@frontend/src/pages/LibraryPage.tsx
@frontend/src/components/library/QualityCenterModal.tsx
@frontend/src/components/library/PdfViewerModal.tsx
@tests/backend/test_chunking.py
@tests/backend/test_phase4_processing.py
@frontend/src/test/quality-center.test.tsx

RESOURCE ROUTING
Refresh inventory by purpose across project/global skills, workflows, rules, attachments, plugins, supported contexts and live MCP tools:
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md

Read/apply these resources sequentially; slash candidates are not an executable chain. Inventory confirms workflow registration/skill discovery, but current slash-menu activation is unverified. Use the real instruction-file fallback. Existing project scope overrides generic defaults.

1. /debug + /karpathy-engineering: reproduce each finding, then make focused changes with a criterion/evidence matrix.
@F:/dev/.agents/workflows/debug.md
@F:/dev/.agents/skills/karpathy-engineering/SKILL.md

2. /rag-engineer: lossless splitting, real tokenizer identity/limits and source-offset preservation. Apply document preprocessing guidance only; do not add embedding calls, retrieval, training or semantic clustering. Exact token bounds take precedence over generic chunking advice.
@F:/dev/AppData/.gemini/config/skills/rag-engineer/SKILL.md

3. /test + /python-testing-patterns: regressions must first expose truncation, nontermination, wrong provenance, bad cursor generations and polling races, then pass after repair.
@F:/dev/.agents/workflows/test.md
@F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md

4. /visual-verification: inspect navigation labels, usable Quality Center entry, PDF page jumps, responsive pagination, keyboard/focus and async states in the running application.
@F:/dev/.agents/skills/visual-verification/SKILL.md
@F:/dev/.agents/docs/UX_COMPONENT_CHECKLIST.md

5. /ruthless-reviewer + /verification-before-completion: review all source/data boundaries, fresh checks and completion claims; keep unit/static, migration, process, tokenizer, API and live browser evidence separate.
@F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
@F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

SIDEBAR FIRST: retain one explicit numbering scheme. Roadmap mapping is Quality Center=2, Research Explorer=5, Assistant=4, Model Lab=6. Implementation Phase 4 is not roadmap Phase 4. Prefer user-facing availability labels for working/planned features, with explicitly named roadmap timing separately if retained. Make Quality Center navigate to usable inspection/paper selection; planned features must not go to an unexplained 404. Update stale dashboard library promises and ensure desktop/mobile consistency. Do not implement the future Assistant/Explorer/Model Lab just to make links work.

PIPELINE REPAIRS: replace sentence[:1000] with lossless splitting that strictly reduces oversized units, carries offsets, and cannot loop forever. Test no-whitespace multilingual text, punctuation and long identifiers under a bounded subprocess timeout. Every final input must fit the verified model cap with special tokens, preserving all source content. Map each chunk only to contributing pages/blocks through cleanup and overlap, with raw-to-cleaned offsets. Pin verified tokenizer assets; no unpinned fallback masquerading as the configured revision. Resolve and record actual model/tokenizer configuration and usable sequence limit; report missing assets actionably without leaking server paths.

UI/API REPAIRS: propagate pageNumber all the way into real PDF navigation. Poll queued uploads and active stages; recover from transient request failure; stop at awaiting-indexing/failure. Abort/invalidate stale requests and actions, reset old paper/filter data appropriately, and avoid cross-paper render races. Paginate beyond 100 chunks; make search semantics honest. Bind API cursors to stable generation and filter context, and prevent assembled pages/chunks/sections from mixing publication generations. Preserve ownership, retention, migration history and retry/deletion safety.

TOOLS: use the destination's actual exposed browser tool or local Chrome harness for real UI verification. Do not assume cached schemas prove authentication. Existing UI fixes need no generated remote design. Consider Stitch only if a genuinely new screen is necessary and live tool discovery succeeds; follow the original Phase 4 prompt's checked schemas/fallbacks. Do not re-add Antigravity Figma or move to Replit. Native Mermaid is optional for documenting request/generation state, not proof of an external plugin.
For official tokenizer/model configuration documentation, use native web access or live scrapling make_request only after discovering its exact schema (cached reference @F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json; url, method="GET", extraction_type="markdown"). Expected output: verified configuration/revision decisions. Installed-package/model assets are the local fallback. No private PDF upload or paid-service commitment.

VERIFICATION: retain all earlier migration and worker regressions. Add fresh queued-status polling, transient-failure recovery, close/switch cancellation, >100-chunk pagination, publish-between-pages, correct page>1 navigation, no-space token progress, and narrow-screen/keyboard tests. Prove wrong source mappings and late responses are rejected. Extend the browser runner to cover Phase 4; eight old library checks and mocked PDF callbacks do not prove the new features. Run full backend/frontend suites, Ruff including worker/scripts, ESLint, Prettier (currently failing three files), typecheck and build. Inspect every exit status. Save actual browser/provenance artifacts and commands.

Update verification, decision/workflow status and API/schema docs where changed. Remove unsupported PASS/zero-truncation/exact-highlighting claims; preserve prior reports as historical evidence. Record configured/discovered/authenticated/called resource states honestly. Create a task-owned local commit after checks, no push, no Phase 5 work. Finish with per-finding evidence and scoped PASS/FAIL.
```
