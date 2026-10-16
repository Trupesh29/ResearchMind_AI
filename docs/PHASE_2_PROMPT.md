# Antigravity implementation prompt: Week 1 Phase 2

Copy the text below into Antigravity. All listed instruction files were inspected when preparing this handoff. Slash commands are installed candidates whose active-host registration is unverified. Select matching autocomplete entries when available; otherwise read the referenced files directly. Pasted commands are not an executable chain. No plugin connection or Gravitas runtime is assumed.

---

Implement Week 1 Phase 2: Workspace Management and PDF Research Library in `F:/Projects/ResearchMind AI`. Continue the existing application through a complete, tested vertical slice. Planning and implementation are authorized; make a compact plan and proceed. Keep the existing two-phase Week 1 structure.

## 1. Read context and apply resources

Primary candidate: `/gravitas`.
Read and apply @F:/dev/.agents/skills/gravitas/SKILL.md and @F:/dev/.agents/skills/gravitas/references/reconnaissance.md for dependency-directed reconnaissance. Use compact planning, dependency context, impact-based verification, and no delegation. Inspect targets, callers, public contracts, and related tests; retain concise factual notes instead of repeatedly loading the repository. This reduces redundant AGENT context only: do not add Gravitas to the product, change model budgets, chunk sizes, retrieval settings, or claim measured token savings. If hooks/runtime are absent, apply guidance manually and identify checks as project checks.

Read these project references through real file mentions (resolve paths containing spaces using autocomplete, or open the exact quoted paths):

- @WEEKLY_BUILD_PLAN.md — Week 1 requirements and acceptance gate.
- @docs/PHASE_1_PLAN.md and @docs/PHASE_1_REVIEW.md — foundation boundaries and resolved regressions.
- @decision.md and @workflow.md — current scope, isolation, verification, commit policy.
- @API_SPEC.md — workspace and paper contracts, pagination, error envelope.
- @DATABASE_SCHEMA.md and @backend/app/db/models.py — existing schema and constraints.
- @ARCHITECTURE.md and @TRD.md — relevant storage/API boundaries only.
- @DESIGN.md — existing Apple Modern design tokens and interaction conventions.
- @backend/app/core/config.py, @frontend/src/api/client.ts, @frontend/src/api/types.ts, @frontend/src/pages/LibraryPage.tsx, @frontend/src/pages/DashboardPage.tsx — inspect before extending, then follow their direct dependencies and tests.

Discover relevant resources through @F:/dev/.agents/docs/ANTIGRAVITY_LOCAL_COMMANDS.csv and @F:/dev/.agents/docs/CATALOG.md. Recheck project-local rules and available host capabilities. Apply the following resources sequentially, each with its stated responsibility; direct reading is the fallback for every slash candidate:

1. `/fastapi-router-py` + @F:/dev/AppData/.gemini/config/skills/fastapi-router-py/SKILL.md: implement typed workspace/paper APIs and response models. Adapt its examples to THIS repository's router paths, synchronous SQLAlchemy/session patterns, and existing local-user dependency. Do not copy incompatible template paths or add a login system.
2. `/file-uploads` + @F:/dev/AppData/.gemini/config/skills/file-uploads/SKILL.md: bounded uploads, actual-byte validation, safe generated paths, and file lifecycle. Existing local storage requirements override the skill's preference for cloud presigned uploads.
3. `/test` + @F:/dev/.agents/workflows/test.md: behavioral tests for the new API/storage/UI boundaries, including meaningful failure cases. Observe failures before implementing the corresponding behavior where practical.
4. `/visual-verification` + @F:/dev/.agents/skills/visual-verification/SKILL.md: build/open/inspect/iterate the real library and workspace flows, preserving DESIGN.md and existing components.
5. `/verification-before-completion` + @F:/dev/AppData/.gemini/config/skills/verification-before-completion/SKILL.md: check every acceptance requirement against fresh evidence and report limitations.

Relevant websites, with specific purposes:

- [FastAPI request files](https://fastapi.tiangolo.com/tutorial/request-files/): confirm multipart fields, multiple UploadFile handling, required dependencies, and file closure against the installed version.
- [PyMuPDF Document reference](https://pymupdf.readthedocs.io/en/latest/document.html): confirm real PDF opening, encryption detection, page count, and resource closure. Inspect dependency availability and pin compatible additions; do not implement text extraction yet.
- Catalog-selected [shadcn Alert Dialog](https://ui.shadcn.com/docs/components/base/alert-dialog): reference the title/description/cancel/destructive-action structure for delete confirmation. Adapt to existing UI primitives and styles; this is not an instruction to install a new design system. Verify keyboard and focus behavior in the actual implementation.

## 2. Resolve contracts, then implement

Create `docs/PHASE_2_PLAN.md` with affected files, endpoint/response matrix, file/DB lifecycle, acceptance checks, and decisions. Resolve these known scope differences explicitly:

- This is Week 1 Phase 2, not ROADMAP.md Phase 2 ingestion. PDFs stay `uploaded`; never claim `processing` or `ready`, enqueue nonexistent jobs, fabricate extraction metadata, or start a polling loop for work that cannot run.
- Preserve `POST /api/papers` multipart fields and 202 batch arrays (`papers`, `duplicates`, `rejected`), including all-duplicate/all-rejected batches. Document the current uploaded-only behavior alongside the API's eventual background-job contract.
- Distinguish per-file validation failures in batch arrays from request-level errors such as invalid workspace, malformed request, or whole-request resource limits. Keep the centralized error envelope/request ID for request-level errors. Document selected file-count/aggregate limits and error precedence.
- Use the existing schema unless a demonstrated requirement needs an additive migration. Update models, schema snapshot, and migration evidence together when necessary. Preserve populated user databases.

### Workspace management

Implement POST/GET `/api/workspaces`, GET/PATCH/DELETE `/api/workspaces/{workspace_id}` as specified. Validate trimmed names, lengths, empty updates, and duplicate-name conflicts; handle database uniqueness races. Return real paper/ready counts and null active-index info where none exists. Enforce ownership through the existing local-user dependency on every operation, including nested paper access. Unknown and foreign-owned IDs must not expose another user's data.

Wire create, select, rename/edit, and confirmed delete into dashboard/library UI. Handle no-workspace state, stale selected IDs, loading, server errors, and recovery. Deleting a selected workspace must select a valid remaining workspace or return to a clear empty state.

### PDF upload and storage

Implement multi-file upload with drag/drop and keyboard-accessible file selection. Validate actual `%PDF-` bytes, actual streamed size using effective MAX_UPLOAD_MB, PDF openability, encryption policy, and nonzero page count. Do not trust extension, MIME, Content-Length, or browser checks. Compute SHA-256 incrementally. Deduplicate within a workspace, including duplicates in the same batch and concurrent requests; identical bytes in different workspaces are allowed.

Keep memory and multipart/spool disk consumption bounded with explicit limits. Store generated filenames under effective DATA_DIR outside public assets. Original filenames are display metadata only; defend against Windows/Unix separators, traversal, control characters, and unsafe response headers. Never expose storage_path in public responses. Treat PDF contents as untrusted data.

Use temporary staging and deliberate publication/DB ordering. On invalid files, duplicate races, write errors, or DB rollback, close handles and clean task-owned temporary/final files as appropriate. Define recoverable behavior for interruption and deletion failures; never report success while silently leaving inconsistent live records/files. Do not build a general distributed transaction system.

### Library, original viewer, and deletion

Implement GET `/api/papers` with required workspace, status filter, q search over stored title/authors and useful filename fallback, bounded limit, and deterministic cursor pagination. Implement GET `/api/papers/{paper_id}` and ownership-checked GET `/api/papers/{paper_id}/file`. Stream exact original bytes with application/pdf, safe disposition, and correct range behavior (200/206/416). Missing backing files return controlled errors without local path leakage.

Provide an original-PDF viewer with a clear open/download fallback, accessible name, loading/error state, and safe return to the library. Original viewing must work while status is `uploaded`. Do not add evidence highlights, extraction, OCR, retrieval, question answering, or analysis features in this phase.

Implement confirmed paper and workspace deletion, including actual associated files and existing relational cascades. Define repeated deletion behavior consistently. Verify one workspace's deletion cannot remove another workspace's copy of identical bytes. Make partial cleanup failures visible/recoverable.

Extend the frontend API client for typed JSON, FormData, and empty 204 responses. Do not force a JSON Content-Type on multipart or call res.json() on 204. Prevent late responses from a previous workspace/search overwriting the active view. Display each upload's accepted/duplicate/rejected result and refresh real counts/list. Use honest upload progress or an indeterminate state. Keep selection, retry, and empty/error states usable.

Preserve DESIGN.md tokens, mobile drawer behavior, reduced motion, contrast, and responsive layout. Remove Phase 2 placeholder/developer explanations from the user-facing library; write useful user copy. Confirm destructive actions using accessible dialogs with focus containment and restoration.

## 3. Verify and hand off

Use isolated disposable databases AND storage with the real application dependencies. Never use the user's live data for mutation tests. The development servers may already be running on 8000/5173: inspect before launching, use separate test ports/data, preserve unrelated processes, and restore environment state. Retain the corrected browser wrapper's ownership and attach behavior.

Add meaningful tests for:

- Workspace lifecycle, name conflicts, real counts, ownership, pagination boundaries, malformed cursors.
- Valid PDFs, spoofed MIME/extension, corrupt/magic-only/empty/encrypted PDFs, exact size boundary and overflow, mixed batches, all rejected/duplicate batches, same-batch and concurrent duplicates, cross-workspace copies.
- Generated path containment, hostile filenames, effective custom DATA_DIR, write/DB failure cleanup, paper/workspace deletion and failure recovery.
- Exact original bytes, ranges, missing-file errors, inaccessible foreign-owned PDFs, and no internal-path leakage.
- Frontend 204/FormData behavior, workspace changes, stale responses, upload feedback, search, confirmation cancel/confirm, viewer, retry, and empty states.

Run from project root and record each exit code:
`.venv/Scripts/python -m pytest -q`
`.venv/Scripts/ruff check backend tests scripts`
`.venv/Scripts/ruff format --check backend tests scripts`

From frontend run `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, and `npm run build`. Run schema drift/fresh-install/populated-upgrade checks if migrations change. Verify setup installs any new pinned multipart/PDF dependencies.

Extend the real browser acceptance coverage for: create workspace -> upload valid PDF -> identify duplicate -> reject invalid/corrupt PDF -> search -> view original -> cancel deletion -> confirm deletion -> delete workspace. Verify persistence across refresh/restart, desktop/tablet/mobile widths (1440/768/375), keyboard-only use, focus, reduced motion, overflow, and unexpected console/network errors. Use disposable fixtures and capture evidence; synthetic PDFs are fine for deterministic tests, but do not claim broad real-document compatibility from them alone. Distinguish scan-like PDFs stored as originals from selectable-text analysis support, which is not implemented yet.

Create `docs/PHASE_2_VERIFICATION.md` with requirement-to-evidence mapping, commands/results, browser observations, and remaining limitations. Update README, API documentation, decision.md, and workflow.md where behavior changed. Preserve historical Phase 1 evidence. Do not imply ML/provider validation was rerun or enable paid services.

Review the diff and staged files. Commit completed task changes locally with a descriptive message; never push. Exclude secrets, runtime databases, uploaded documents, screenshots, and unrelated files. Finish with implemented behavior, checks actually run, unresolved issues, local commit hash, and a scoped VERDICT. A blocked browser check must remain explicitly unverified; it must not be silently converted into a pass.
