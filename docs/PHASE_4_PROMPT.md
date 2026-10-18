# Antigravity handoff — publish Phase 3, implement Phase 4

Copy the prompt below into Antigravity. Resource candidates and paths were checked on 2026-10-18. Resolve mentions through autocomplete, or directly read their files. Command strings are staged instructions, not an automatically executable chain.

```text
Work in F:/Projects/ResearchMind AI. First publish the accepted Phase 3 checkpoint as authorized below, then implement Week 2 Phase 4: sectioning, token-safe chunking, and the Quality Center. Carry implementation through verification and a local commit. Do not push Phase 4 until independent review accepts it.

STAGE 0 — PUBLISH ACCEPTED PHASE 3

The user explicitly authorized publishing Phase 3 as the first step of this prompt. The accepted commit is:
6de34b3d9903227df7fd9b8cf7c46cc4427129ce

Read @docs/PHASE_3_FINAL_REVIEW.md and @docs/PHASE_3_VERIFICATION.md. The reviewed application was abdde12; the accepted documentation checkpoint is 6de34b3. Fresh review recorded 154 backend tests, 25 frontend tests, four diagnostic probes, static/build checks and 8/8 live Chrome library criteria passing. Do not present those historical results as a new run.

Inspect git status, branch, origin URL, the accepted commit and its ancestry. Preserve any unrelated work. Fetch origin, inspect both remote branches, and ensure publication is fast-forward-safe. Push this exact accepted commit, not a later HEAD containing Phase 4 or unrelated changes:

git push origin 6de34b3d9903227df7fd9b8cf7c46cc4427129ce:refs/heads/manav
git ls-remote origin refs/heads/manav

Verify origin/manav resolves to the accepted SHA before proceeding:

git push origin 6de34b3d9903227df7fd9b8cf7c46cc4427129ce:refs/heads/main
git ls-remote origin refs/heads/manav refs/heads/main

Run these sequentially with exit/ref checks. If already at the accepted SHA, record that and continue. If a remote is ahead or diverged, do not force-push, reset, merge unreviewed work into the release, or roll it back. Diagnose and report the precise publication blocker. Do not begin Phase 4 mutations until the publication step is confirmed. No redundant permission request is needed for the authorized safe pushes. Record verified remote SHAs.

STAGE 1 — CONTEXT AND RESOURCE ROUTING

Read these existing project contexts:
@docs/WEEK_2_PHASES.md
@WEEKLY_BUILD_PLAN.md
@ROADMAP.md
@API_SPEC.md
@DATABASE_SCHEMA.md
@decision.md
@workflow.md
@backend/app/core/config.py
@backend/app/db/models.py
@backend/app/services/processing_service.py
@backend/app/services/extraction_service.py
@worker/engine.py
@tests/backend/test_database.py
@tests/backend/test_phase3_processing.py
@frontend/src/api/client.ts
@frontend/src/api/types.ts
@frontend/src/app/App.tsx
@frontend/src/pages/LibraryPage.tsx
@frontend/src/components/library/PdfViewerModal.tsx
@frontend/src/styles/tokens.css
@scripts/run_browser_suite.ps1
@scripts/run_browser_verification.py

Refresh the current ecosystem by purpose, including project/workspace/global skills, workflows, rules, attachment ledgers, plugins, supported context and actually exposed MCP tools:
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md

Apply the following selected resources, reading each instruction file first. Inventory records workflows as host-registered and skills as host-discovered; current visible slash-menu activation is unverified. If a candidate is unavailable, directly read/apply its file. Project constraints override generic templates. Do not install a runtime merely to claim use.

- /gravitas + /plan: establish a concise implementation/acceptance matrix and dependency-aware plan, then execute without a redundant planning pause. Record scope, migration risk, verification layers and resource contributions; do not claim hooks ran if using guidance only.
  @F:/dev/.agents/skills/gravitas/SKILL.md
  @F:/dev/.agents/workflows/plan.md
- /database-design + /karpathy-engineering: design generation-aware pre-index storage, publication boundaries and minimal compatible changes. SQLite/Alembic/SQLAlchemy are already chosen; do not reopen that decision or copy PostgreSQL-only SQL.
  @F:/dev/AppData/.gemini/config/skills/database-design/SKILL.md
  @F:/dev/AppData/.gemini/config/skills/database-design/schema-design.md
  @F:/dev/AppData/.gemini/config/skills/database-design/migrations.md
  @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
- /rag-engineer: apply only document cleanup, sentence-aware chunk boundaries, overlap and provenance guidance. The project's exact token cap overrides generic advice against token limits. No semantic-embedding calls, retrieval, reranking or indexing in this phase.
  @F:/dev/AppData/.gemini/config/skills/rag-engineer/SKILL.md
- /visual-verification: implement the Quality Center within existing components/tokens and inspect actual desktop/tablet/mobile screens. Apply relevant skeleton, mobile navigation, focus and error-state guidance from the UX checklist.
  @F:/dev/.agents/skills/visual-verification/SKILL.md
  @F:/dev/.agents/docs/UX_COMPONENT_CHECKLIST.md
- /test + /python-testing-patterns: behavioral fixtures for migrations, token limits, source mappings, generation/retry races and ownership; frontend/browser tests for polling, inspection and recovery.
  @F:/dev/.agents/workflows/test.md
  @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
- /debug when a check fails; /ruthless-reviewer + /verification-before-completion for final data-preservation, security and evidence review.
  @F:/dev/.agents/workflows/debug.md
  @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
  @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md

TOOLS AND DESIGN RESPONSIBILITIES

Consider StitchMCP first for the new Quality Center design, after inspecting current UI conventions. Recheck live discovery/authentication and schemas in Antigravity; Codex had no exposed Stitch tools during prompt preparation. Cached schemas are references, not connection proof:
@F:/dev/AppData/.gemini/antigravity-ide/mcp/StitchMCP/list_projects.json
@F:/dev/AppData/.gemini/antigravity-ide/mcp/StitchMCP/get_project.json
@F:/dev/AppData/.gemini/antigravity-ide/mcp/StitchMCP/generate_screen_from_text.json
@F:/dev/AppData/.gemini/antigravity-ide/mcp/StitchMCP/get_screen.json

If connected, list_projects and get_project(name="projects/{returned-id}") identify relevant existing context. With a verified appropriate project, generate_screen_from_text(projectId, prompt, deviceType="DESKTOP" or "MOBILE", optional verified designSystem) can produce a Quality Center proposal using existing visual conventions and synthetic content only. Inspect returned screens via get_screen(name=returned-resource-name), implement locally, and verify. Never invent IDs, send private PDF contents, create new paid commitments, or blindly retry generation after timeout; follow its schema's recovery guidance. If unavailable or no suitable project exists, continue with local existing components and document the fallback. No public deployment or unrelated redesign.

Use official installed-version-compatible tokenizer/model and Alembic documentation when needed. If live scrapling make_request is exposed, its cached schema is @F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json; use url, method="GET", extraction_type="markdown" for public official references. Native browsing or installed-package documentation is the fallback. Record configured/discovered/authenticated/called states separately. Cataloged UX guidance is not proof an external website was visited. Native Mermaid may document generation/publication flow; do not assume an external Mermaid plugin. Do not re-add Antigravity Figma or move this project to Replit.

STAGE 2 — PIPELINE, STORAGE AND CONTRACTS

Implement conservative cleaning and sectioning: repeated header/footer removal, line-wrap hyphenation, common/numbered headings, honest unknown sections. Preserve raw text and raw-to-cleaned page/block mappings, including transformations and offsets needed to verify excerpts. Keep reference text inspectable and mark reference chunks excluded from default future retrieval. Repeated legitimate body text must survive.

Implement sentence-aware chunks around the project baseline of 200 tokens with a 20% target overlap. Load the configured MiniLM tokenizer, pin/record its revision and actual usable model sequence limit, and measure every final embedding input including special tokens and any prefixes. Do not use a huge tokenizer sentinel as the model limit. Never silently truncate. Split oversized sentences with a documented fallback, ensure progress/termination, and preserve source spans through overlap. Missing assets must produce an actionable failure, not character-count token estimates. Prefer cached assets; any required public tokenizer download must be explicit and reproducible, with no private-paper upload or paid inference.

Store immutable ingestion-generation sections/chunks independently of embedding indexes. Reconcile the old required chunks.embedding_index_id relationship in DATABASE_SCHEMA.md and API_SPEC.md; define later explicit index membership without fake indexes, placeholder vectors or fake readiness. Persist stable IDs, ordering, text, measured tokens, section, page/block spans, exclusions, tokenizer/model revision and chunk configuration. Reuse Phase 3 lease/claim fencing and stage-attempt history for sectioning/chunking, including atomic next-stage transitions under the one-active-job constraint.

Define when a complete page/section/chunk bundle becomes inspectable. Existing page publication happens after extraction: do not expose new pages alongside previous-generation chunks during reprocessing. Keep the last consistent bundle available with accurate stale flags, or expose explicitly versioned partial output without mixing generations. Failed or killed replacements must not overwrite published output. Preserve all valid older generations. New migrations must upgrade fresh, Phase 2, populated Phase 3 and multi-run databases safely; preserve accepted migration history and real files. Test on disposable databases; no resets or stamping shortcuts.

Implement GET /papers/{paper_id}/chunks with cursor pagination and page/section filters (resolve the older P1 label into Week 2 scope), typed fields and ownership checks. Add section inspection as needed, update public status and client types consistently, and bind pagination to a stable generation. Define how already-extracted Phase 3 papers enter the new stages without duplicate jobs or unnecessary PDF re-extraction. Completed Week 2 processing remains processing with an explicit awaiting-indexing state; only Week 3 can make it ready.

STAGE 3 — QUALITY CENTER

Provide a discoverable per-paper Quality Center from the library/navigation. Display real stage/attempt history, sanitized errors, metadata provenance, page flags, sections/chunks, token counts and source-page links. Support loading, empty, partial, failed, worker-unavailable and awaiting-indexing states with clear next actions. Distinguish a quiet completed queue from a missing worker; do not invent worker availability evidence.

Add retry/reprocess feedback and 409 conflict handling. Stop polling terminal Week 2 work even though paper.status remains processing; resume on accepted reprocess. Cancel requests/timers on paper/workspace changes and unmount, ignore late old responses, and avoid overlapping polls. Verify original PDF navigation. Claim coordinate highlighting only if implemented and visually checked. Reuse design tokens, existing modal/focus patterns and accessible controls. No Week 5 summaries/Explorer implementation.

STAGE 4 — ACCEPTANCE AND HANDOFF

Use ordinary, long-sentence, multi-page, multi-column/rotated, heading-free, references-heavy, repeated-body-text, scan/mixed-text and corrupt fixtures, plus embedded prompt instructions treated as untrusted PDF data. Verify exact token limits including special tokens, deterministic parameters, nonempty usable chunks, truthful unknown sections, source mappings and reference exclusions. Inspect representative chunks against original pages manually as well as with assertions.

Test two workers, kill/restart during sectioning/chunking, renewed leases, retry attempts, duplicate requests, deletion mid-stage, stable original hashes, foreign-workspace access, retained historical generations and failed replacement visibility. Use negative controls: oversized final input, wrong source mapping and stale cross-paper responses must fail the relevant checks.

Run backend pytest; Ruff lint/format including worker; frontend tests, lint, formatting, typecheck and build; migration/data-preservation/schema-drift checks. Extend live browser acceptance for upload -> stage history -> page/chunk source -> warnings -> controlled failure -> retry -> awaiting indexing. Check 1440/768/375 widths, keyboard/focus restoration, status announcements, reduced motion, console errors and late-response isolation. Existing eight library checks alone do not prove the new Quality Center.

Keep the separate Week 2 SciCite readiness and five-document extraction-evaluation sample deliverables visible in the weekly plan; report their actual status without silently moving them out of Week 2 or conflating them with this Phase 4 ingestion implementation. Do not begin heavy training, embeddings, FAISS/BM25, generated answers or later-phase analysis here.

Update schema/API/worker docs, decision.md, workflow.md and a Phase 4 verification report with tested commit, fixture manifest, exact commands/results, tokenizer revision/limit, source inspection evidence, browser artifacts, recovery evidence and remaining limits. Record resource contributions honestly; update shared inventories only if resources actually change. Provide the Week 3 handoff contract: accepted ingestion generation, chunk IDs/mappings, configuration, reference exclusions and future index membership. Review the final diff, create a local Phase 4 checkpoint, and stop for independent review. No Phase 4 push. End with scoped PASS or FAIL and concrete unmet criteria; unit/static success cannot replace migration, process or browser acceptance.
```
