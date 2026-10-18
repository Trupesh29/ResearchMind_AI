# Antigravity prompt — preserve multiple successful page generations

```text
Fix H1 in ResearchMind AI at F:/Projects/ResearchMind AI, starting from application checkpoint 5e168f1 and the subsequent review checkpoint. Preserve the working API, worker recovery, stale-page attribution, and corrected overlay behavior. Keep Phase 3 local; no push or Phase 4 work.

Read these project contexts (resolve @ in autocomplete; otherwise directly read the exact project-relative path under F:/Projects/ResearchMind AI):
@docs/PHASE_3_MULTIRUN_REVIEW.md
@scripts/review_phase3_multirun_probe.py
@backend/migrations/versions/0004_add_generation_and_fencing_controls.py
@backend/migrations/versions/0005_repair_historical_generation_attribution.py
@worker/engine.py
@backend/app/services/processing_service.py
@tests/backend/test_database.py
@tests/backend/test_phase3_processing.py
@docs/PHASE_3_VERIFICATION.md
@workflow.md
@decision.md

Refresh resource discovery by purpose across commands, local/global skills, workflows, rules, attachment records, plugins and live MCP schemas. Consult:
@F:/dev/.agents/README.md
@F:/dev/.agents/docs/ANTIGRAVITY_PROMPTING.md
@F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv
@F:/dev/.agents/docs/TASK_GUIDE.md
@F:/dev/.agents/docs/ROUTING.md
@F:/dev/.agents/docs/CATALOG.md
@F:/dev/.agents/docs/SOURCES.md
@F:/dev/.agents/docs/FILE_INDEX.md

Apply the following resources sequentially by responsibility. These are supported inventory candidates, not an executable slash chain. Current visible menu activation is unverified; read/apply the instruction-file fallback if unavailable. Project scope takes precedence over generic defaults.

1. /debug — reproduce the exact migration failure and trace the worker's retention invariant.
   @F:/dev/.agents/workflows/debug.md
   Expected result: a failing migration regression from an actual 0004 multi-generation database, with before/after row identities, texts and revision.

2. /karpathy-engineering — implement a minimal data-preserving repair.
   @F:/dev/.agents/skills/karpathy-engineering/SKILL.md
   Expected result: preserve valid page run IDs; repair only demonstrated legacy misattribution; keep current/published selection separate from page-row ownership. Explain ambiguity and compatibility rather than inferring all rows belong to the latest success.

3. /test and /python-testing-patterns — add behavioral upgrade and preservation tests.
   @F:/dev/.agents/workflows/test.md
   @F:/dev/AppData/.gemini/config/skills/python-testing-patterns/SKILL.md
   Expected result: prove two successful runs retaining the same page numbers survive unchanged, latest publication remains visible, and older rows stay distinct. Include worker-produced reprocessing history, non-overlapping historical pages, failed/active replacement runs, ambiguous history, populated original 0003, 0004, already-applied 0005, and clean installs. Test row identity/text preservation, correct stale flags, uniqueness and revision advancement. Retain G1/G2 regression coverage.

4. /ruthless-reviewer and /verification-before-completion — audit migration safety and final evidence.
   @F:/dev/.agents/skills/ruthless-reviewer/SKILL.md
   @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md
   Expected result: no blanket generation collapse, deletion workaround, schema reset, migration stamping shortcut, or unsupported acceptance claim. Review the diff and report exact checks independently.

Migration requirement: 0005 currently runs UPDATE pages SET run_id=:latest_success for every differing row. A=page1 plus B=page1 raises a uniqueness error; non-overlapping page numbers can be silently relabeled. Preserve valid multi-generation data. A later migration alone cannot help an upgrade that fails inside 0005. Design and document a compatible path both for databases stopped at 0004 and those already at 0005, without altering original 0003 or assuming an already-recorded migration reruns. Explain any attribution that cannot be reconstructed after prior relabeling.

MCP/reference responsibility: recheck live Antigravity tools and schemas, separate configured/authenticated/tools-discovered/successfully-called states. The cached scrapling make_request schema exists at:
@F:/dev/AppData/.gemini/antigravity-ide/mcp/scrapling/make_request.json
If actually exposed, use make_request with url, method="GET", extraction_type="markdown" only when official Alembic/SQLite transaction or migration documentation is needed. Expected output is source-backed migration compatibility decisions. Fallback: installed package documentation or native web access. Cached schema is not proof of a live connection. Do not install integrations, use unrelated design services, or re-add Antigravity Figma for this database fix.

Verify with disposable storage. Run the new multi-run regression, database and Phase 3 tests, all three earlier diagnostic probes, full backend/frontend suites, Ruff lint/format including worker, and frontend static/build checks. Inspect each exit status; the diagnostic catching an IntegrityError is not a passing regression assertion. Preserve real user data and unrelated processes. Do not inflate timeouts or weaken assertions to obtain green results.

Update verification, decision/workflow status and the review-resolution record. The review saw 151 backend tests and 25 frontend tests pass but independently reproduced H1; passing those tests alone cannot close it. Distinguish automated, API, migration, visual and live-browser evidence. Keep historical reports identifiable. Create a task-owned local commit after verification, no push. Finish with the repair strategy, exact preservation evidence, remaining limitations and scoped PASS/FAIL.
```
