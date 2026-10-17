# Phase 2 review — e5367c9

Reviewed 2026-10-17. Phase 2 is not accepted for publication yet. These are findings against the committed implementation, not changes to application code.

## Findings

1. **P1 — Browser mutation tests use the real default database/storage.** `scripts/run_browser_suite.ps1:97` launches the application without overriding DATA_DIR or DATABASE_URL. The newly added lifecycle at `scripts/run_browser_verification.py:784` creates/uploads/deletes using that server, including in attach mode. Separate ports isolate processes, not data. Its fixed `Browser E2E Workspace` name can collide with an existing workspace; the name-presence check is not proof that this run created it. Provision disposable migrated storage/database for owned verification servers, require a verified disposable target for mutation tests in attach mode, and track only resources created by the run. Do not delete by a pre-existing display name. Static finding; the destructive suite was deliberately not rerun against live data.

2. **P1 — Upload limits run after multipart spooling.** `backend/app/api/papers.py:24` declares `files: list[UploadFile] = File(...)`, so FastAPI parses the body before the service checks MAX_UPLOAD_MB. The installed Starlette parser spools file parts without a file-byte limit; its max_part_size check applies to non-file fields. No application aggregate receive limit or deliberate batch count limit exists. A very large file can exhaust temporary disk before being rejected. Enforce bounded incoming bytes before/during parsing, including streams without Content-Length, and document request-level versus per-file limits. Static finding verified against the installed parser; no disk-exhaustion test was run.

3. **P2 — Failed database writes orphan published PDFs.** `backend/app/services/paper_service.py:230-278` moves the PDF into final storage, then only compensates for IntegrityError. An OperationalError/other persistence failure leaves the final file behind; finally only removes the old temporary path. Disposable reproduction with Session.commit raising OperationalError returned 500, left one final PDF, and persisted zero Paper rows. Also distinguish a committed row followed by refresh failure from a pre-commit failure; blindly unlinking after every exception would corrupt committed data. Only report a duplicate when a real winning row exists.

4. **P2 — Failed physical deletion still returns success.** `backend/app/services/paper_service.py:345-357` and `workspace_service.py:214-229` commit row deletion before unlink, then log and swallow unlink errors. With a simulated Windows file lock, DELETE returned 204, metadata GET returned 404, and the original PDF remained on disk. The retry cannot locate it through the deleted row. Implement visible/recoverable cleanup semantics for paper and workspace deletion; merely returning 500 after losing all cleanup state is insufficient.

5. **P2 — Unicode original filenames cannot be viewed.** `backend/app/api/papers.py:171,182` interpolates the original Unicode name directly into Content-Disposition. Uploading `研究.pdf` succeeds, but GET of its original returned HTTP 500 because response headers cannot encode it as Latin-1. Use standards-compatible disposition encoding and quoted-name escaping for both full and partial responses; cover non-Latin names and quotes.

6. **P2 — Valid ranges extending past EOF are rejected.** `backend/app/api/papers.py:146` rejects any end greater than or equal to file size. A request `bytes=0-(size+100)` reproduced 416, although the start is satisfiable and the end should be clipped. See [RFC 9110 section 14.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-14.1.2). Test open-ended/suffix/overshooting ranges, truly unsatisfiable ranges, and malformed or very large numeric inputs. Prefer the installed framework's tested range response where it meets the contract.

7. **P2 — Pagination is discarded by the UI.** `frontend/src/pages/LibraryPage.tsx:56,90` requests only the first 100 workspaces/papers and ignores next_cursor. PaperList has no next-page/load-more action. Older papers cannot be browsed, and older workspaces cannot be selected; DashboardPage also totals only its first 100 workspaces. Consume pagination and distinguish page counts from total counts. Static finding; add >100-item UI/API regressions.

8. **P2 — Late mutations restore an obsolete workspace.** `frontend/src/pages/LibraryPage.tsx:153-165,177-187` captures selectedWorkspace when upload/deletion starts, then calls loadWorkspaces(oldId) on completion. The workspace selector remains usable while uploading. Switch from A to B during a slow upload to A and its completion forces selection back to A; the paper request counter cannot prevent this separate workspace mutation. Scope mutation results/count refreshes to their origin while preserving the user's latest selection/search; invalidate reads when selection clears and ignore stale workspace fetches. Static async-flow finding; add deferred-promise tests.

## Verification and coverage limits

- Fresh backend suite: 99 passed, 55 deprecation warnings, 53.98 seconds.
- Fresh frontend suite: 16 passed in 4 files; JSDOM reports its existing scrollTo limitation.
- Ruff lint and format (35 files), ESLint, Prettier, TypeScript, and production build passed.
- Four disposable reproducers confirmed findings 3–6. They asserted the observed buggy behavior to capture evidence; they are not passing acceptance tests. The temporary probe file was removed after execution. Real project storage was guarded by the existing fixture.
- No fresh full browser, clean-install, ML, or provider run. Historical browser evidence does not cover new dialog keyboard interaction, persistence after restart, cleanup failures, or the pagination/race cases above.
- The browser evaluator correctly rejects runner_exception; that tested behavior is not a finding. Missing Phase 2 results should nevertheless be required for a Phase 2 acceptance verdict rather than silently treated as a Phase 1-only pass.
- Correct documentation overclaims during repair: actual storage is DATA_DIR/pdfs/{id}.pdf, not DATA_DIR/workspaces/{workspace_id}; actual name limit is 255, not 100; search currently has no debounce. Avoid blanket '100% verified' claims.

## Publication checkpoint

At the user's explicit request, created remote `main` at `24eadea004b968c3be839874a65db4a743ff2190`, the final reviewed Phase 1 checkpoint. Verified using `git ls-remote --heads origin`. Remote `manav` remains at `51e3071`. Neither Phase 2 handoff `fc6e0fa` nor implementation `e5367c9` was pushed. Phase 2 publication remains gated on completed implementation and fresh acceptance/review.

VERDICT: FAIL — Phase 2 findings above remain unresolved.
