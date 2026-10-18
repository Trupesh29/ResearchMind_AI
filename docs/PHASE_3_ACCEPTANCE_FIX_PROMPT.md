# Antigravity prompt — remaining Phase 3 acceptance repairs

```text
Repair the remaining Phase 3 acceptance findings for ResearchMind AI at F:/Projects/ResearchMind AI, starting from 3c7743d. Implement and verify G1/G2 from the current review. Preserve the API, concurrency, retry, sanitization, and generation-visibility improvements already made. Keep the checkpoint local for independent review; do not push or start Phase 4.

Read actual project context:
@docs/PHASE_3_ACCEPTANCE_REVIEW.md
@scripts/review_phase3_acceptance_probe.py
@docs/PHASE_3_VERIFICATION.md
@docs/PHASE_3_FOLLOWUP_REVIEW.md
@docs/WEEK_2_PHASES.md
@backend/migrations/versions/0003_add_processing_jobs_and_pages.py
@backend/migrations/versions/0004_add_generation_and_fencing_controls.py
@backend/app/services/processing_service.py
@backend/app/services/extraction_service.py
@tests/backend/test_database.py
@tests/backend/test_phase3_processing.py
@scripts/review_phase3_followup_probe.py
@scripts/review_phase3_probe.py
@workflow.md
@decision.md

RESOURCE DISCOVERY AND STAGED APPLICATION

Recheck the full current resource metadata by purpose: commands, workspace/global skills, workflows, rules, attachment ledgers, plugins, live MCP tools, and supported context. Read chosen instructions before applying. Use complementary resources that materially help; do not add unrelated activations.
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md
@F:/dev/.agents/docs/ATTACHMENT_INTEGRATION_LEDGER_20261017.md

Slash candidates below are sequential resource instructions, not an executable chain. The inventory records host-discovered skills/registered workflows; current visible menu activation is unverified. Resolve @ mentions through autocomplete or directly read the exact path if unavailable. Project scope and architecture override generic resource defaults.

1. /gravitas and /debug
   @F:/dev/.agents/skills/gravitas/SKILL.md
   @F:/dev/.agents/workflows/debug.md
   Inspect Git state and affected callers; reproduce both defects using the supplied synthetic probe. Keep a two-finding acceptance matrix and diagnose failures before changing strategy. Do not claim runtime hooks or independent reviewers executed unless observed.

2. /plan and /karpathy-engineering
   @F:/dev/.agents/workflows/plan.md
   @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
   Define a data-preserving migration correction and concise validation changes, then implement without a redundant planning pause. Keep SQLite/Alembic, current storage/session conventions, and existing provenance contracts. No database reset, loss of retained pages, migration stamping workaround, or unrelated refactor.

3. /test and /python-testing-patterns
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
   Turn G1/G2 into failing behavioral regressions and prove they pass after repair. Exercise multiple historical generations and intentionally incorrect overlays, not only happy-path single-run data or nonempty image assertions.

4. /visual-verification
   @F:/dev/.agents/skills/visual-verification/SKILL.md
   Apply its open/inspect/iterate loop specifically to PDF-source overlays. Preserve the application design; no UI redesign is needed. Inspect the rendered image and actual correspondence with text, not just dimensions.

5. /ruthless-reviewer and /verification-before-completion
   @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md
   Review generation attribution, migration safety, coordinate-frame correctness, negative controls, and evidence claims. Separate static/tests/browser/process/visual results. Never translate timeout, skipped checks, or artifact existence into PASS.

MCP RESPONSIBILITIES

Check live Antigravity discovery and exact schemas before invoking MCP tools. Configuration and cached schemas are not authentication or successful calls.
@F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json
If scrapling exposes make_request, use url, method="GET", extraction_type="markdown" to read relevant official Alembic migration and PyMuPDF rotation/derotation/shape-coordinate documentation. Expected output: source-backed, installed-version-compatible migration and coordinate decisions. Record configured/authenticated-or-not-applicable/tools-discovered/called separately. Fallback: native web fetch or installed-package documentation; no new server installation required.

Use the destination's actual image viewer/local browser to inspect generated overlays. A cached Puppeteer schema is not a connected browser; fall back to local rendering and the project's existing browser harness. Native Mermaid may help document run/current/published relationships, but do not imply an external Mermaid plugin exists. This task needs no Replit move, design generation, Figma integration, or hosting. Antigravity Figma was removed by the user; do not re-add it.

G1 — CORRECT HISTORICAL GENERATION ATTRIBUTION

Separate current attempt identity from the identity of retained published pages. For original 0003 data with successful extraction A and later failed/queued reprocess B, backfill current=B and published/pages=A when supported by history; inspection must show stale output. Do not attach old pages to B just because B has the newest job timestamp. When source history is ambiguous, preserve records and expose uncertainty or require safe reprocessing instead of inventing provenance. Keep any surviving active job consistent with the selected current run.

Add fixtures for successful A followed by failed B, active B, ambiguous/missing successful history, and competing runs. Verify populated upgrades from original 0003, the previously rewritten 0003 layout, and already-applied 0004, plus clean installs. Since 0004 has now been exercised, provide a forward-compatible repair for affected databases; do not silently rewrite it and assume existing installs will rerun it. Preserve original PDFs and page text. Document any history that cannot be reconstructed reliably.

G2 — FIX AND VALIDATE OVERLAY EVIDENCE

The extraction API returns visual coordinates. The current test draws those on an unrotated PDF page and rendering rotates them again. Either convert boxes back through page.derotation_matrix before PDF drawing or draw on the pixmap in its displayed coordinate frame with explicit scale/crop handling. Verify 0/90/180/270 and cropped pages. Save and inspect overlays showing boxes around the intended text. Add a negative control that shifts or double-rotates boxes and must fail. Do not change correct API coordinates merely to satisfy the wrong test.

VERIFICATION AND HANDOFF

The reviewing environment encountered frontend fork-worker startup timeouts and repeated PowerShell browser-harness failures. Diagnose exact failures and rerun with controlled concurrency/environment as appropriate; do not increase timeouts blindly, skip checks, or edit application behavior to hide runner failures. Preserve unrelated user processes and real data.

The focused Phase 3/database run returned 29 passed and 1 failed: test_r2_lease_liveness_and_worker_kill_recovery never observed subprocess extraction and the new validation job stayed queued. Diagnose child startup/readiness, capture useful failure output, and prove actual kill/recovery with bounded state-driven synchronization. Its Poll=1 was captured after the test killed the child, so do not infer an independent worker crash from that value. The occupied-port browser-wrapper rerun exceeded its 15-second subprocess deadline. These are unresolved verification gates, not proven application defects.

Run affected migrations, Phase 3 tests, database tests, both earlier probes, the new corrected assertions, Ruff lint/format, and relevant frontend/static/build checks. Complete the full backend/frontend suites and library browser acceptance when the environment permits. Clearly report any remaining blocker instead of claiming phase completion.

Update API/schema/migration docs where contracts change, phase verification, decision/workflow status, and the resource-use record. Preserve historical evidence and correct unsupported visual PASS claims. Update shared inventories only if shared resources actually change. Review the diff and create a task-owned local commit under project policy. No push. Finish with G1/G2 evidence, exact commands/results, limitations, and scoped PASS/FAIL verdict.
```
