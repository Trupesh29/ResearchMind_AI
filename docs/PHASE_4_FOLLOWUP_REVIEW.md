# Phase 4 follow-up review — fc38b35

Reviewed against `4fcf0e4` on 2026-10-19. No application repair was made in this review.

## Improvements confirmed

The sidebar now uses the correct roadmap mapping (Quality Center 2, Explorer 5, Assistant 4, Model Lab 6), distinguishes active/planned features, and has usable routes. The PDF page argument reaches the viewer URL. The 400/1200-character no-space splitter reproducers now preserve all characters and produce bounded pieces. Unpinned tokenizer fallback is removed. A Load More control and run-bearing cursors were added. Frontend formatting now passes.

## J1 — P1: Production worker still fabricates chunk provenance

`worker/engine.py:711` persists section block IDs but not the new `block_spans`; reconstruction at lines 771 onward does not supply spans. No span field was added to the Section database model. Consequently the actual worker takes `chunking_service.py:213-228`'s proportional fallback, inventing equal-length text regions and interpolated page numbers. Tests that use equal-length blocks or directly supplied spans hide the production failure.

The new disposable probe mirrors that reconstruction with a long page-1 block and short page-2 block. It reports `ALPHA_ONLY_CHUNKS_ATTRIBUTED_TO_PAGE2 2`; one example claims pages 1–2 and blocks a/b despite containing only page-1 evidence. Run `.venv/Scripts/python scripts/review_phase4_followup_probe.py`.

Additionally, `sectioning_service.py:228-236` uniformly scales all offsets when dehyphenation removes characters anywhere in the section. That is not an exact transformation map: a change in one block must not shift unrelated preceding blocks proportionally. Persist/reconstruct true cleaned/raw spans through the stage boundary, remove proportional/nearest-block guesses as factual evidence, and test unequal blocks, sparse page spans and localized dehyphenation through real worker execution.

## J2 — P2: Polling still stops after one transient error

`QualityCenterModal.tsx:180-187` only increments `retryCountRef.current` on a failed poll. Ref changes do not rerun the polling effect, whose dependencies at line 239 stay unchanged; the one-shot timeout has already fired. No retry gets scheduled.

A focused Vitest probe loaded uploaded/queued status, rejected the next request, then advanced 30 seconds: **expected at least 3 calls, received 2**. The reproducer is retained as `scripts/review_phase4_polling.test.tsx.txt`; copy it into `frontend/src/test/phase4-review-probe.test.tsx` to run it, then remove the temporary copy. It is outside test discovery so the existing suite is not intentionally left failing. Schedule the next bounded attempt explicitly after completion/failure, with cancellation on close/switch.

## J3 — P2: Load More and reprocess responses bypass identity guards

`QualityCenterModal.tsx:242-289` lacks the abort controller/request-generation checks used by the initial fetch. If Load More for paper A resolves after switching to B or changing filters, `setChunks(prev => [...prev, ...res.items])` appends A's chunks to the new view. Reprocess can similarly overwrite B's status and trigger A's captured `loadData` callback. Guard all asynchronous paths, not only initial/poll reads; clear filter/action state on identity changes. Add deferred-response tests for pagination, reprocess, close and filter changes, and verify consistent run IDs before merging independently fetched pages/sections/chunks.

## J4 — P2: Rejected tokenizer is cached and accepted on the next call

`chunking_service.py:54-79` assigns `_tokenizer_instance` before validating its sequence limit. After a 128-token tokenizer triggers ValueError, the second `get_tokenizer()` skips validation because the singleton is non-null and returns that same rejected tokenizer. The diagnostic prints `FIRST_INVALID_LOAD_REJECTED True` and `SECOND_INVALID_LOAD_ACCEPTED True`.

Initialize and validate a local candidate before caching it, and clear failures. The broader prior requirement is also incomplete: the code checks tokenizer.model_max_length against a hard-coded 256 rather than resolving the embedding model's usable configuration; chunk records still use constant model name while settings allow a different model, and worker version records retain constants. Either enforce the single supported model/revision explicitly or make the actual resolved identity, effective cap and persisted metadata consistent end to end. Test incompatible settings and repeated failed loads.

## Acceptance evidence and remaining coverage

- Existing frontend suite: **32 passed**. ESLint, Prettier, typecheck and production build passed.
- Previous splitter probe passes its original cases. New follow-up probe confirms J1/J4. Focused polling test fails as described in J2.
- Full backend suite with disposable process-level DATA_DIR/DATABASE_URL: **173 passed**, 122 warnings, 148.39 seconds. Ruff lint/format passed for application code and the added diagnostic.
- Live Chrome command `scripts/run_browser_suite.ps1 -RequirePhase2 -RequirePhase4 -BackendPort 18081 -FrontendPort 15174` exited **1**: eight existing criteria passed, `phase4_quality_center` failed. The runner looks for exact text `Quality Center · Inspection Mode`, but the UI renders a `Quality Center Inspection Guidance` region with different text. It also queries `button[role='tab']`, while the visible tab controls are ordinary buttons without that role. Personally inspected `artifacts/browser_verification/screenshots/desktop_quality_center_modal.png`: the modal and controls are visible, with validating/5% and zero chunks. Thus these failures are selector/semantics mismatches, not proof the controls are absent. Fix the accessibility/selector contract and add real processing evidence; no worker was launched by this harness to populate chunks. The tracked browser summary records this failed run.
- The new Phase 4 browser criterion checks route headings, a guidance banner, modal visibility, tab existence and Escape closure. It does not exercise worker completion, chunk/source correctness, a page >1 PDF jump, pagination, transient retries or late-response isolation. A PASS for that gate must not be presented as full Phase 4 acceptance; extend it with behavioral checks and negative controls.
- Minor scope-copy issue: the planned Explorer page advertises graph/co-citation features rather than roadmap Phase 5 sections/summaries, and Model Lab copy omits the specified SciCite classifier experiment. Align descriptions with ROADMAP.md rather than inventing later-phase scope.

VERDICT: FAIL -- J1–J4 and Phase 4 acceptance coverage remain open. Keep Phase 4 local.
