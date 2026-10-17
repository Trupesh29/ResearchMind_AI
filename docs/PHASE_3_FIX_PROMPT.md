# Phase 3 corrective implementation prompt — Antigravity

Copy the following prompt into the ResearchMind AI Antigravity task.

```text
Repair implementation Phase 3 in F:/Projects/ResearchMind AI, starting from fea8fce and the independent review. Implement and verify the corrections; do not stop at a plan.

Phase 2 is already accepted and published at 4058b2d on origin/manav and origin/main (verified 2026-10-18). Keep this Phase 3 repair local for independent review. Do not push HEAD, advance main, or implement Phase 4.

Read project context:
@docs/PHASE_3_REVIEW.md
@docs/PHASE_3_PLAN.md
@docs/PHASE_3_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@API_SPEC.md
@DATABASE_SCHEMA.md
@decision.md
@workflow.md
@worker/engine.py
@worker/main.py
@backend/app/services/processing_service.py
@backend/app/services/extraction_service.py
@backend/app/services/paper_service.py
@backend/app/services/quarantine_service.py
@backend/app/db/models.py
@backend/app/db/session.py
@backend/app/schemas/paper.py
@backend/app/api/papers.py
@tests/backend/test_phase3_processing.py
@tests/backend/conftest.py
@scripts/review_phase3_probe.py

Run the review probe on its temporary storage and convert its four demonstrated defects into acceptance regressions. Do not turn its current failing behavior into expected product behavior; its exit status alone is not an acceptance verdict.

DISCOVERY AND APPLICATION

Recheck current resources by purpose, including workflows, global/project skills, rules, attachment integrations, plugins, and actual MCP tool discovery:
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md
@F:/dev/.agents/docs/ATTACHMENT_INTEGRATION_LEDGER_20261017.md

Use the following complementary resources sequentially, with their stated outputs. Slash strings are candidates, not an executable chain. The current inventory records these workflows as host-registered and skills as host-discovered; visible slash-menu activation was not independently checked. Resolve exact @ paths through supported context selection or read them directly. Use instruction-file fallbacks if commands are unavailable or ambiguous. Preserve project conventions over generic skill defaults.

1. /gravitas
   @F:/dev/.agents/skills/gravitas/SKILL.md
   @F:/dev/.agents/skills/gravitas/references/reconnaissance.md
   Ground the work in current source/callers/tests and Git state. Build a compact R1–R7 acceptance matrix. Track evidence and blockers; do not claim runtime/hooks ran unless they did. Use sequential work and focused review.

2. /debug
   @F:/dev/.agents/workflows/debug.md
   Reproduce the demonstrated races, path leak, and geometry mismatch first. Diagnose failed checks with bounded hypothesis loops; avoid identical retries and unrelated changes.

3. /karpathy-engineering
   @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
   Implement cohesive corrections using existing FastAPI, SQLAlchemy, SQLite/Alembic, local identity, effective DATA_DIR, and storage/quarantine behavior. Do not introduce Redis/Celery/cloud dependencies or relocate project storage.

4. /test and /python-testing-patterns
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
   Create deterministic concurrent SQL tests and subprocess recovery tests with isolated storage. Assert failures before repairs, then success. Avoid mocks that remove the persistence/concurrency behavior under test.

5. /security-checklist
   @F:/dev/.agents/skills/security-checklist/SKILL.md
   Review error privacy, workspace ownership, path containment, untrusted PDF data, resource bounds, and deletion races. Preserve local authentication scope.

6. /audit and /ruthless-reviewer
   @F:/dev/.agents/workflows/audit.md
   @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
   Inspect migration integrity, transaction boundaries, run ownership, lease recovery, stale publication, and error handling after implementation. Fix blocking findings and verify them. Distinguish self-review from independent review.

7. /verification-before-completion
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md
   Recheck every acceptance criterion after the final relevant mutation and report actual evidence separately for tests, migrations, live processes, browser, and visual inspection.

MCP RESPONSIBILITIES AND FALLBACKS

Do not interpret MCP names as slash commands or @ entities. Discover tools in this Antigravity session and inspect their actual schemas before calling. Record configured/authenticated/tools-discovered/successfully-called separately; authentication may be not applicable for local servers.

- scrapling is present in the inspected Antigravity IDE configuration and has a local make_request schema at:
  @F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json
  If the session exposes this server/tool, use make_request with url, method="GET", extraction_type="markdown" to retrieve official SQLite transaction, SQLAlchemy conditional-update, and PyMuPDF page-coordinate documentation needed for the fixes. Expected output: source URLs and version-compatible conclusions recorded in the repair plan. Local schema inspection does not prove live discovery or a successful call. Fallback: available native web fetch/browser or installed package documentation; do not install a server merely to claim MCP use.

- Cached puppeteer schemas exist at:
  @F:/dev/AppData/.gemini/antigravity-ide/mcp/puppeteer/puppeteer_navigate.json
  @F:/dev/AppData/.gemini/antigravity-ide/mcp/puppeteer/puppeteer_screenshot.json
  puppeteer was absent from the inspected active MCP configuration, so treat it as unavailable unless live discovery proves otherwise. If exposed, inspect these exact schemas, navigate to disposable local verification pages, and capture rotated/cropped PDF overlay evidence plus relevant library regression states. Expected output: inspected screenshots and test outcomes, not screenshots alone. Fallback: the existing project browser verification scripts and locally rendered PDF images. Do not claim cached schemas establish a browser connection.

No relevant GitHub MCP tool is exposed to the reviewing Codex session; use Git CLI for branch evidence. Do not borrow Codex tool names as Antigravity tool names. Figma/Stitch/Cloud Run and unrelated attachment resources do not improve this backend repair and should not expand its scope.

REQUIRED CORRECTIONS

R1: Make claims, lease renewal/recovery, and publication atomic against current status/token. Check affected-row results. Never let stale ORM reads overwrite a new owner. Include a deterministic overlap between stale publication and reclaim, not just two sequential run_once calls.

R2: Maintain lease liveness during validation hashing and extraction. Support cancellation/lost ownership without publishing. Test a healthy extraction exceeding the configured lease while another worker polls; then separately kill a real worker process and prove bounded restart recovery.

R3: Enforce one active ingestion run per paper transactionally and in database constraints where appropriate. Concurrent reprocess must yield one accepted run and one 409. Persist current/published generation identity and fence page/metadata replacement against it. Old generations must not overwrite new ones; failed replacements must expose old output as belonging to the old generation, never as current fresh output.

R4: Replace raw public path/exception strings with stable sanitized errors. Check top-level and nested stage history through the HTTP endpoint. Keep diagnostics useful without leaking document text, filesystem paths, or secrets.

R5: Make page dimensions, crop offsets, rotation, and block coordinates consistent. Use intrinsic coordinates with an explicit transform or correctly transformed coordinates throughout. Verify 0/90/180/270-degree and cropped PDFs using source overlays and assertions.

R6: Do not equate PDF creation date with reported publication year or an arbitrary second block with authors. Label uncertain heuristics inferred or leave them absent. Store page/block/excerpt support for text-derived metadata, distinguish file properties from publication facts, and prevent stale metadata/provenance combinations after reprocess.

R7: Preserve separate stage-attempt history rather than incrementing away previous evidence. Replace unsupported current PASS claims with accurately scoped verification. The existing report's conditional SQL claim, concurrent test, and WorkerFencingViolation descriptions do not match implementation. Preserve historical evidence with a clear correction; do not invent visual checks or process recovery runs.

VERIFICATION AND HANDOFF

Run fresh migrations and populated upgrades, schema drift, all affected regressions, backend suite, Ruff lint/format including worker, and live API/worker checks on disposable storage. Preserve original-file hashes. Test deletion during validation/extraction/publication and foreign ownership. Run frontend tests, lint, formatting, typecheck/build and existing browser library regression where upload/status contracts are affected. Inspect each command's exit code independently.

Update the phase plan, API/schema contracts, worker setup instructions, decision/workflow status, and Phase 3 verification record. Record resources actually applied and MCP access limitations. Shared inventories need updates only if this task actually changes shared resources; preserve their configuration otherwise.

Review the diff and create a local commit containing task-owned repair and evidence files under the repository policy. Do not push. Finish with R1–R7 resolution evidence, remaining gaps, checks and counts, changed files, local commit, and a Phase 3-scoped VERDICT: PASS or VERDICT: FAIL -- <unmet criterion>.
```
