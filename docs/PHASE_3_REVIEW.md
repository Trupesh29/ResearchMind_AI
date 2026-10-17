# Phase 3 independent review

Reviewed 2026-10-18: `fea8fce`, compared with accepted Phase 2 checkpoint `4058b2d`. Application code was not changed during this review.

## Publication state

Live `git ls-remote origin refs/heads/manav refs/heads/main` returned `4058b2d144f827ce341fe9045943ff573b2f0a9b` for both branches. Phase 2 is already published. Its acceptance report includes normal/delayed browser checks and an independent negative search control. No additional push is necessary. Phase 3 must remain local pending correction and review.

## Findings

### R1 — P1: Job claiming and fencing are read-then-write races

`worker/engine.py:130-164` selects a queued ORM object, then updates it by primary key without a queued-state compare-and-swap or write lock covering selection. Two independent sessions synchronized immediately before the UPDATE both returned a claim for the same job with different tokens (`CLAIM_WINNERS 2 DISTINCT_TOKENS 2`). Recovery and heartbeat updates also check state before unconditional ORM writes; publication checks the token separately from the writes it is intended to protect. Use transactional ownership checks and affected-row validation so stale readers cannot reclaim, heartbeat, or publish over a newer owner. Test actual overlapping transactions, including recovery/publication interleavings.

### R2 — P1: Healthy long-running extraction loses its lease

`worker/engine.py:298-313` sends a heartbeat only before and after the synchronous `extract_pdf()` call. Another worker can reclaim a healthy extraction after the default 30 seconds, repeat the work, and ultimately exhaust retries. Validation has no heartbeat during hashing either. Renew ownership throughout expensive work using a safe independent session or bounded cooperative progress, and stop/discard work when ownership is lost. Verify extraction lasting longer than a lease alongside another polling worker, plus actual process termination and restart. This finding is from code inspection; a wall-clock long-extraction test was not run in this review.

### R3 — P1: Concurrent reprocess requests create competing generations

`backend/app/services/processing_service.py:66-87` separately checks for active jobs and inserts a new run, without a database-enforced active-run invariant. Synchronizing two independent sessions before the paper UPDATE produced two successful service responses and two active runs (`REPROCESS_ACCEPTED ['processing', 'processing'] ACTIVE_RUNS 2`). The older generation can overwrite pages/metadata after a newer run, while status picks a run by job creation time. Serialize run admission and enforce the invariant in storage; return 409 for the loser. Fence publication by the current run, and associate published pages with their ingestion generation.

### R4 — P2: Public processing errors leak storage paths

`worker/engine.py:220` persists the complete missing-file path; raw exceptions at lines 239 and 310 can also include private details. `processing_service.py:126-148` returns those strings in public stage/error fields. A disposable missing-file probe returned `PDF file not found at storage path: F:\dev\temp\<temporary-directory>\missing.pdf`. Use stable public error codes/messages and sanitized diagnostics. Test missing files, permission errors, and parser failures through the HTTP status endpoint, including nested history.

### R5 — P2: Rotated page dimensions and block coordinates use different frames

`backend/app/services/extraction_service.py:145-175` stores rotated `page.rect` dimensions alongside unrotated extraction coordinates. A 612×792 page rotated 90 degrees returned width=792, height=612, but block bounds `[72.0, 688.17, 290.9, 703.29]`, extending beyond that height. Define a consistent intrinsic or transformed frame and expose any needed transform/crop offset. Verify 0/90/180/270-degree and cropped-page overlays visually. The review reproduced inconsistent geometry but did not run a browser overlay audit.

### R6 — P2: Metadata heuristics are promoted to reported facts without evidence

`backend/app/services/extraction_service.py:309-327` treats an arbitrary short second block as authors and PDF file creation date as publication year. A creation date is not necessarily the publication date; headings/body prose can satisfy the author heuristic. `sources` stores only strings and cannot provide the required page/block support. Preserve uncertain values as inferred or absent, retain evidence for text-derived fields, and distinguish file metadata from publication facts. Ensure reprocessing does not retain stale values with newly replaced provenance. This finding is based on the code paths, not a broad metadata benchmark.

### R7 — P2: Completion evidence overstates the exercised behavior

`docs/PHASE_3_VERIFICATION.md` describes a conditional SQL claim update and `WorkerFencingViolation`, neither implemented as described. `test_worker_atomic_claim_and_fencing` invokes workers sequentially and manually ages timestamps; it does not prove simultaneous claiming or kill/restart recovery. Recovery overwrites the existing attempt row rather than retaining per-attempt history. The reported PASS cannot establish the Phase 3 acceptance gate. Preserve historical reports but correct their current status, implement missing attempt history, add real concurrent/subprocess checks, and record source-coordinate inspection with actual artifacts. Do not infer visual verification from synthetic bounding-box assertions.

## Fresh verification

- Backend suite: 140 passed, 90 warnings, 74.82 seconds. Process-level DATA_DIR/DATABASE_URL were redirected to disposable storage as an extra guard.
- Ruff lint and format: passed, including `worker`; 44 files already formatted.
- Independent SQLite/PyMuPDF probes: confirmed R1, R3, R4, R5. Run `.venv/Scripts/python scripts/review_phase3_probe.py`; it uses temporary storage and synchronized real SQL operations. It is a review diagnostic that prints observations, not an acceptance test: exit 0 does not imply correct product behavior. R3's first diagnostic attempt synchronized too late, after a write lock; moving the barrier before the first write produced the valid two-run reproduction above.
- Frontend: 25 tests passed; ESLint, Prettier, TypeScript, and Vite build passed. Test output includes the existing jsdom scrollTo limitation. Live browser, clean dependency installation, long-running heartbeat, and actual worker kill/restart checks were not run in this review.

VERDICT: FAIL -- Phase 3 concurrency, lease liveness, generation isolation, error privacy, provenance, and evidence gates remain unmet. Phase 2 remains accepted and already published.
