# Independent Phase 4 review — 1cf85bf

Reviewed against `7c95eb0` on 2026-10-18. Application code was not changed. Phase 3 publication was verified live: both origin/manav and origin/main resolve to `6de34b3d9903227df7fd9b8cf7c46cc4427129ce`. Phase 4 remains local.

## Sidebar phases and navigation

The roadmap feature phases and implementation checkpoints use different numbering. `docs/WEEK_2_PHASES.md:7` explicitly maps implementation Phases 3/4 to roadmap Phase 2. Do not change Quality Center to Phase 4 while keeping Assistant's roadmap Phase 4 in the same unexplained badge system.

| Feature | Roadmap phase | Current screenshot | Assessment |
|---|---|---|---|
| Quality Center | 2 | Phase 2 | Roadmap number correct; available through the new library modal, but sidebar route is broken |
| Research Explorer | 5 | Phase 5 | Correct roadmap number; still planned |
| Assistant | 4 | Phase 4 | Correct roadmap number; still planned |
| Model Lab | 6 | Phase 3 | Incorrect; training starts earlier but feature belongs to roadmap Phase 6 |

Use clear availability labels for end users, with roadmap timing separately identified if retained. Implemented actions must navigate somewhere usable; planned entries should not lead to 404. Dashboard copy also still claims the already-implemented library will activate in Week 1 Phase 2.

## Findings

### P4-01 — P1: Oversized no-space text is truncated and can loop indefinitely

`backend/app/services/chunking_service.py:139-142` returns only `sentence[:1000]` for an oversized single word/no-space sequence. At lines 211-221, a still-oversized unit is replaced by the same splitter result and retried without advancing. With the locally cached real MiniLM tokenizer, 400 repetitions of `研` produce a single unchanged 402-token unit. This makes the inner loop repeat indefinitely. With 1,200 repetitions, the splitter discards 200 characters and returns 1,002 tokens, still above the cap. The active heartbeat can keep this stuck worker's lease alive.

Reproduce safely using `scripts/review_phase4_probe.py`; it checks the failing splitter/progress precondition without entering the infinite loop. Replace character truncation with lossless, offset-aware bounded splitting and prove strict progress on no-whitespace Unicode, punctuation and long identifiers. Include a process-level timeout regression for the full chunker.

### P4-02 — P1: Chunk source references describe the entire section

`chunking_service.py:244-253` assigns all section block IDs and the full section page span to every chunk. A two-page probe produces an Alpha-only first chunk labeled with both Alpha/page1 and Beta/page2 blocks; the Beta-only last chunk likewise claims page1. Page filters and source links therefore give misleading evidence. `SectionResult` also has no cleaned-text offset map to recover each chunk's real source range.

Carry source offsets through cleaning, splitting and overlap. Attribute only contributing blocks/pages to each chunk and retain enough raw-to-cleaned mapping to verify transformed excerpts. Do not claim exact geometric highlighting from a section-wide block list.

### P4-03 — P2: Tokenizer provenance and limit are not verified at runtime

`chunking_service.py:45-66` tries a pinned revision, then silently loads an unpinned local cache. Output rows and worker version records nevertheless always claim the constant revision/name. The configured model may also differ while the recorded name and hard-coded 256 cap remain MiniLM's. Preserve the verified revision or fail actionably; record the actual resolved assets and derive/validate the usable limit from the corresponding model configuration. Tests must exercise pinned-load failure and incompatible configuration, not merely compare output to constants.

### P4-04 — P2: Sidebar has a wrong phase and Quality Center goes to 404

`frontend/src/components/layout/Sidebar.tsx:55-84` retains Model Lab Phase 3 and routes Quality Center to `/quality`, while `frontend/src/app/App.tsx:77-97` only implements `/`, `/dashboard` and `/library`. The new Quality Center is only a library modal. Correct the mapping above and route the sidebar through a usable paper-selection/inspection flow; do not advertise broken routes as available features. Verify the shared desktop/mobile navigation and stale dashboard promises.

### P4-05 — P2: View Page discards the requested page number

`QualityCenterModal.tsx:700` passes `chunk.page_start`, but `LibraryPage.tsx:534-537` accepts only the paper and discards that argument. `PdfViewerModal.tsx:216-217` loads the plain file URL. A chunk on page 5 opens the PDF at its default page. Propagate the requested page to the viewer and verify actual PDF navigation, not just that a mocked callback was called.

### P4-06 — P2: Polling stops for queued uploads and after a transient failure

`QualityCenterModal.tsx:166-183` polls only `status === processing`; the API deliberately returns `uploaded/queued` for newly queued validation. Opening inspection before a worker claims that job never schedules another read. A failed polling request also leaves statusData unchanged, so the timer effect does not schedule a replacement. The modal has no abort/invalidation cleanup for in-flight requests on close and does not reset old paper data before switching.

Poll queued/running stages based on pipeline state, reschedule bounded transient-error retries, stop at awaiting-indexing/failure, and cancel/invalidate requests on identity/filter/visibility changes. Cover deferred cross-paper responses and recovery, not only initial render.

### P4-07 — P2: Pagination is incomplete and can switch generations mid-list

The modal requests `limit: 100` at line 126 and discards `next_cursor`, so chunks after the first 100 cannot be inspected and local text search misses them. The API cursor (`processing_service.py:554-567`) is only a chunk index; each request chooses the then-current published run. Publishing B between pages of A silently returns B's continuation. Implement UI pagination and a cursor bound to paper/generation/filter context, with consistent rejection or snapshot behavior across publication changes. Keep page/section/source results aligned to a verified generation.

## Verification and reporting gaps

- The standalone probe reproduced P4-01 and P4-02 with the real locally cached tokenizer; it makes no network request and modifies no user data.
- Frontend: 30 tests passed; ESLint, typecheck and build passed. **Prettier failed** for `src/api/client.ts`, `src/components/library/QualityCenterModal.tsx`, and `src/test/quality-center.test.tsx`.
- Ruff lint and formatting passed, including the diagnostic (58 files).
- Backend full suite with disposable process-level DATA_DIR/DATABASE_URL: **166 passed**, 122 warnings, 152.65 seconds. These passing tests do not cover the reproduced splitter/provenance failures.
- The implementation's browser report only runs the existing eight library criteria; the browser runner has no Phase 4 changes. It does not establish Quality Center source navigation, polling recovery, pagination, or responsive acceptance. No fresh Phase 4 browser acceptance was performed in this review.
- The current report's zero-truncation and exact-source claims are contradicted by the probe. Correct completion claims and add new-feature browser evidence after repairs.

VERDICT: FAIL -- P4-01 through P4-07 and verification gaps remain. Keep Phase 4 local.
