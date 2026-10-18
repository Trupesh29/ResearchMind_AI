# Antigravity corrective prompt — Phase 3 follow-up

```text
Repair ResearchMind AI Phase 3 at F:/Projects/ResearchMind AI from bd78083. Implement the remaining findings in the follow-up review and verify them. Keep Phase 3 local for independent review; do not push or begin Phase 4. Preserve the already-fixed claim admission, reprocess conflict, missing-file error, and rotated-coordinate behavior.

Read project evidence and contracts:
@docs/PHASE_3_FOLLOWUP_REVIEW.md
@scripts/review_phase3_followup_probe.py
@scripts/review_phase3_probe.py
@docs/PHASE_3_VERIFICATION.md
@docs/WEEK_2_PHASES.md
@docs/PHASE_3_PLAN.md
@API_SPEC.md
@DATABASE_SCHEMA.md
@workflow.md
@decision.md

Inspect sources and their callers:
@backend/app/schemas/paper.py
@backend/app/api/papers.py
@backend/app/services/paper_service.py
@backend/app/services/processing_service.py
@backend/app/services/extraction_service.py
@backend/app/db/models.py
@backend/migrations/versions/0003_add_processing_jobs_and_pages.py
@worker/engine.py
@worker/main.py
@frontend/src/api/types.ts
@tests/backend/test_phase3_processing.py
@tests/backend/test_database.py
@tests/backend/test_papers_api.py

RESOURCE DISCOVERY

Recheck current command/skill/workflow/rule/plugin/MCP resources by purpose. Search broadly, then read selected instructions. Include newly added resources only where complementary; no fixed command-count limit and no unrelated padding.
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md
@F:/dev/.agents/docs/ATTACHMENT_INTEGRATION_LEDGER_20261017.md

Apply the following sequentially. Slash strings are candidates, not an executable chain. Current inventory records host-discovered skills/registered workflows; visible menu activation is unverified. Resolve @ mentions through autocomplete or read the exact file directly. Do not let generic skill defaults replace this project's SQLite/Alembic architecture, local identity, storage, or authorization.

1. /gravitas
   @F:/dev/.agents/skills/gravitas/SKILL.md
   @F:/dev/.agents/skills/gravitas/references/reconnaissance.md
   Inspect current Git state, callers, and acceptance gates; produce an F1–F6 requirement-to-evidence checklist. Do not claim installed hooks or validators executed without evidence.

2. /debug
   @F:/dev/.agents/workflows/debug.md
   Reproduce the five follow-up probe failures before repairing them. Keep evidence for each root cause and use bounded, hypothesis-driven debugging.

3. /karpathy-engineering and /fastapi-router-py
   @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
   @F:/dev/AppData/.gemini/config/skills/fastapi-router-py/SKILL.md
   Make focused fixes across persistence, response validation, and actual API consumers. Preserve existing routes, error envelopes, ownership, and dependency injection. Reconcile backend/frontend/OpenAPI contracts together.

4. /test and /python-testing-patterns
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
   Build behavioral regressions with real SQLite transactions, isolated storage, deterministic barriers, and real worker subprocesses. A probe printing desired values is not an assertion-based acceptance test.

5. /security-checklist and /ruthless-reviewer
   @F:/dev/.agents/skills/security-checklist/SKILL.md
   @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
   Audit public error leakage, generation isolation, upgrade data preservation, lease races, and ownership/deletion behavior. Fix blocking issues and label self-review honestly.

6. /verification-before-completion
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md
   Require observed evidence for every final claim. Distinguish unit tests, populated upgrades, HTTP integration, process recovery, browser checks, and visual inspection.

MCP AND EXTERNAL REFERENCES

Use actual Antigravity tool discovery and schemas, not invented slash or @ names. The inspected scrapling configuration and local make_request schema are candidates only:
@F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json
If the live scrapling server exposes make_request, use its url/method/extraction_type parameters for read-only retrieval of official Alembic migration, SQLAlchemy conditional-update, and Pydantic response-validation guidance. Expected output: cited, version-compatible decisions for F1/F2/F4. Record configured, authenticated or not-applicable, tools-discovered, and successfully-called states separately. If unavailable, use native fetch/browser or installed-package docs without installing an MCP server.

Consider native Mermaid for a compact retry/lease sequence if it clarifies the race; do not claim an external Mermaid plugin is connected. This backend repair requires no Replit migration, hosted deployment, design generation, or Figma. Antigravity Figma was removed by the user: do not restore it or route this repair through historical Figma artifacts. Codex plugin availability does not establish Antigravity access.

REPAIRS AND ACCEPTANCE

F1: Define typed structured provenance with compatibility for previously stored string sources. Update backend schema, frontend type, API specification, and consumers. A real uploaded and processed PDF with nonempty provenance must return 200 from both paper detail and library listing, with the evidence intact. Exercise these HTTP routes, not just extraction helpers.

F2: Restore immutable migration history and add a forward revision. Upgrade original 0003 databases, already-rewritten 0003 databases, Week 1 databases, and empty databases without dropping user records/files. Backfill current/published generation associations consistently and reconcile duplicate active runs before enforcing uniqueness. Reproduce the historical schema from Git; do not use current ORM create_all as a substitute for upgrade testing. No reset, data deletion, or stamping workaround.

F3: Compute status from latest attempts/current stage while retaining old failure history. Test queued/running/succeeded retries and final retry exhaustion. A successful extraction retry must remain processing awaiting Phase 4, not failed because attempt 1 expired. Add explicit current/published generation and staleness information to inspection contracts so retained old pages are never silently represented as new output after reprocess failure.

F4: Add an expiry predicate to the atomic recovery UPDATE, protecting a heartbeat renewed after SELECT. Use row counts to decide whether to retire/queue. Test the selection → concurrent renewal → attempted retirement sequence and legitimate expiry recovery, without weakening token fencing or publication safety.

F5: Use stable public error categories with a generic fallback for unknown exceptions. Regex cleanup must not be the only defense. Test forward/backslash Windows, UNC, arbitrary Unix paths, and sentinel private/parser content through top-level and nested HTTP error fields. Keep private diagnostics separate and sanitized according to project policy.

F6: Replace unsupported verification claims with real evidence. The existing liveness test polls at 1 second with a 2-second lease and has no subprocess termination. Poll after the original lease expires while work remains active, prove renewal prevents takeover, and independently terminate/restart a real worker with temporary DB/storage. Capture and inspect 0/90/180/270-degree and cropped-page overlays; bounded boxes alone are insufficient. Preserve earlier reports as history and clearly state remaining limits.

Run targeted red–green regressions, full backend suite, schema drift/populated upgrades, Ruff lint/format including worker/scripts, and relevant frontend tests/lint/format/typecheck/build after the contract changes. Run the existing library browser regression with actual processed documents and record errors. Preserve original file hashes and ownership/deletion guarantees. Inspect each command's exit code separately.

Update phase plan, API/schema docs, verification evidence, decision/workflow status, and resource-use record. Update shared resource inventories only if shared capabilities actually change. Review task-owned changes and create a local commit under project policy; no push. Finish with F1–F6 outcomes, generation visibility evidence, exact checks/results, limitations, and a scoped PASS/FAIL verdict.
```
