# ResearchMind AI — Week 2 Implementation Phases

**Date:** 2026-10-17  
**Status:** Planned; implementation and acceptance evidence are pending.  
**Outcome:** Uploaded PDFs become inspectable, page-linked chunks with honest quality indicators, ready for Week 3 indexing.

Week 1 used implementation Phase 1 for foundation and Phase 2 for the library. Continue with **Phase 3 and Phase 4** below. These implementation numbers differ from the feature-phase numbers in `ROADMAP.md`: both implement roadmap Phase 2, with preparation for roadmap Phase 6. This plan expands Week 2 of `WEEKLY_BUILD_PLAN.md`; it does not change the six-week scope.

## Sequence and time budget

| Implementation phase | Target | Outcome | Review gate |
|---|---|---|---|
| Phase 3 — Persistent processing and PDF extraction | Monday–Tuesday | Recoverable jobs, page/block extraction, metadata provenance, quality flags | Extraction is persisted, traceable, and safe to retry |
| Phase 4 — Sectioning, chunking, and Quality Center | Wednesday–Thursday | Token-safe chunks and a working inspection/reprocessing interface | Users can inspect source-linked output and recover failures |
| Week 2 acceptance | Friday | Integrated fixture demo, recovery checks, SciCite preparation evidence, Week 3 handoff | Record accepted, incomplete, and blocked items with evidence |

These are working targets, not completion claims. Keep SciCite preparation as a separate workstream within the week; do not make ingestion wait for training. If a gate fails, fix or explicitly reschedule it rather than silently removing required scope.

## Entry conditions and shared decisions

- Review the latest Week 1 verification and current checkout. Preserve workspace ownership, batch upload responses, duplicate handling, range streaming, and deletion/quarantine behavior. Existing review reports are historical evidence, not a new verification run.
- Use the existing FastAPI/SQLite/Alembic foundation, shared settings/session factory, and private effective `DATA_DIR`. Implement a standalone local worker under `worker/`; do not put durable jobs in FastAPI `BackgroundTasks`.
- Preserve paper states `uploaded → processing → ready | failed`. A queued upload may remain `uploaded` until claimed. After Week 2 chunking succeeds, the paper remains `processing`, with an explicit “Extraction complete; awaiting indexing” display. No fake embedding jobs, fake vectors, `ready` state, or full-pipeline 100% progress.
- Reconcile proposed schema/API changes against `DATABASE_SCHEMA.md`, `API_SPEC.md`, and executable migrations before coding. Update specifications alongside implementation; paths below identify existing integration points or proposed new modules, not already delivered features.
- Keep originals immutable. Reprocessing versions derived output; retries must not duplicate records. Paper/workspace deletion must prevent an in-flight worker from publishing orphaned results.
- Keep ingestion, question answering, and model training independent. OCR, generated answers, FAISS/BM25 publication, and final classifier training are outside Week 2.

## Phase 3 — Persistent processing and PDF extraction

### User-visible result

A valid uploaded document enters a real processing queue. Its status, extracted pages, metadata sources, and quality warnings can be inspected through the API. Failures are recorded and recoverable without uploading the original again.

### Build scope

1. **Persistent jobs and migrations.** Add page storage and stage-attempt history with paper ownership, run/generation identity, timestamps, extractor/configuration versions, and sanitized errors. Add uniqueness and foreign-key constraints. Define queued/running/succeeded/failed transitions, atomic job claiming, bounded retries, and a lease/heartbeat or equivalent recovery mechanism that cannot reclaim a live worker's job.
2. **Upload and worker integration.** Persist the first validation job with the accepted paper transaction; keep duplicate/rejection behavior intact. Support existing `uploaded` papers through reprocess. Provide a documented worker startup command and graceful shutdown. Commit completed stages atomically and resume only from valid checkpoints after restart.
3. **Page/block extraction.** Use the existing PyMuPDF dependency to extract selectable text, page dimensions, rotation/coordinate convention, stable block identifiers, bounding boxes, one-based page numbers, and character counts. Preserve raw extracted text so cleaned output remains auditable. Test multi-column reading order; surface limitations rather than claiming perfect layout understanding.
4. **Metadata provenance.** Extract title, authors, year, and keywords where available. Store whether each value came from PDF metadata, visible text, or inference; retain supporting page/block evidence for text-derived values. Missing values stay absent; filenames and heuristics must not masquerade as reported metadata.
5. **Quality outcomes.** Persist page/document flags for possible scans, unreliable tables, and potentially missing equations, with the reason and affected page. Treat these as heuristic warnings. An all-image/no-usable-text document must show an unsupported-text outcome rather than successful analysis; a partially readable document retains usable pages and explicit warnings. Corrupt uploads remain rejected by upload validation; post-upload read failures become recorded processing failures.
6. **Inspection and retry API.** Extend `/api/papers/{id}/status`; implement pages, page-block inspection, and `POST /api/papers/{id}/reprocess` using existing envelope/ownership conventions. Return `409` for an already queued or running ingestion run. Expose actual stage history and conservative progress estimates, never private paths or document content in logs.

### Main integration points

| Area | Changes |
|---|---|
| Persistence | `backend/app/db/models.py`, new Alembic migration(s), shared session/configuration |
| Worker | New worker entrypoint, claim/recovery loop, validation and extraction stage handlers |
| Services/API | Existing paper service/router/schemas; new processing and extraction services |
| Operations | Worker startup script, worker README, configuration and troubleshooting instructions |
| Verification | Backend job, migration, extraction, ownership, retry, and deletion fixtures/tests |

### Phase 3 acceptance gate

- Fresh and existing Week 1 databases migrate successfully; check Alembic metadata/drift and preserve existing papers/files.
- A text PDF produces the expected page count and stable page/block coordinates. Compare selected blocks against the original PDF, including a rotated or multi-column fixture.
- Kill/restart the worker during extraction: it recovers without duplicate pages or stage outputs. Two workers cannot publish the same attempt concurrently.
- Retry a controlled failure; verify attempt history and unchanged original-file hash. Deleting a paper/workspace while work is running leaves no resurrected records or published orphan output.
- Foreign-workspace requests fail consistently. Scan-like, partial-text, table-heavy, and corrupt inputs receive the intended outcomes with readable reasons.
- Save commands, fixture IDs, results, unresolved defects, and the tested revision before beginning dependent Phase 4 integration.

## Phase 4 — Sectioning, chunking, and Quality Center

### User-visible result

A user opens the Quality Center, follows real stage history, inspects extracted pages and chunks against the original PDF, understands warnings and metadata provenance, and requests reprocessing. Completed extraction is visibly awaiting Week 3 indexing.

### Build scope

1. **Cleaning and sectioning.** Remove repeated headers/footers conservatively, repair line-wrap hyphenation, and detect common/numbered headings. Retain raw-to-cleaned block mappings. Use `unknown` for nonstandard sections; preserve reference text for inspection while marking it excluded from the default answer index. Do not remove legitimate body text merely because it repeats.
2. **Token-safe chunking.** Apply the project's approximately 200-token baseline and 20% target overlap using the configured MiniLM tokenizer. Prefer sentence boundaries; split oversized sentences with a documented fallback. Count the exact final embedding input including special tokens, verify the configured model limit at runtime, and prohibit silent truncation. Store measured token counts, model/tokenizer revision, chunk parameters, and source page/block spans. Missing tokenizer assets cause an actionable failure, never a character-count substitute.
3. **Pre-index storage decision.** The current schema specification requires `chunks.embedding_index_id` before Week 3 indexes exist. Use versioned ingestion chunks independent of index membership, with a later explicit index-to-chunk mapping; reconcile this design in the schema/API documentation and migrations. Do not create a fake active index or weaken readiness to satisfy the old relationship. Record the immutable ingestion generation that Week 3 will consume.
4. **Inspection contracts.** Implement the specified chunk inspection endpoint with pagination and page/section filters, bringing its older P1 designation into Week 2 scope. Include stable IDs, text, token counts, section, page range, and block references. Expose section inspection as needed without implementing Week 5 summaries/Explorer. Select only a consistent generation of pages/chunks; failed replacement runs must not mix old and new output.
5. **Quality Center UI.** Extend existing typed API utilities and navigation with a Quality Center view. Show actual processing history, errors, page flags, metadata provenance, section/chunk counts, and source-page links. Provide loading, empty, partial, failed, worker-unavailable, and awaiting-indexing states. Stop polling completed Week 2 work, resume on reprocess, and cancel stale requests when switching papers/workspaces or unmounting.
6. **Reprocessing and accessibility.** Add retry/reprocess feedback and conflict handling. Use existing design tokens and responsive patterns. Verify keyboard access, focus return, readable status/error announcements, narrow-screen inspection, and original PDF navigation. Do not claim coordinate highlighting unless it is implemented and visually verified.

### Main integration points

| Area | Changes |
|---|---|
| Processing | New sectioning/chunking services and worker stage handlers |
| Persistence | Generation-aware chunk storage, provenance, migration/schema updates |
| API | Paper inspection/status contracts, typed chunk and section responses |
| Frontend | `frontend/src/api/`, new Quality Center page/components, existing app routing/navigation |
| Verification | Token-limit/provenance fixtures, frontend state tests, live browser acceptance |

### Phase 4 acceptance gate

- Normal, long-sentence, multi-page, heading-free, and references-heavy fixtures produce nonempty usable chunks where text exists. Every final embedding input fits the verified tokenizer limit without truncation.
- Inspect representative chunks against source pages/blocks; cleanup and overlap preserve provenance. Unknown sections remain honest and reference chunks are marked excluded from default retrieval.
- Reprocessing is idempotent and generation-consistent, including restart, repeated requests, and deletion during chunking. Original-file hashes remain unchanged.
- In the browser, upload → inspect stages → open page/chunk evidence → see warnings → retry a controlled failure works with keyboard and narrow-screen layouts. Polling must not display stale results from another paper.
- Completed Week 2 output remains `processing` and clearly awaits indexing. No analysis action treats it as ready.
- Run affected backend/frontend tests, lint, formatting, type checking, production build, migration checks, and browser acceptance; record each layer separately.

## Independent Week 2 preparation

**SciCite readiness:** verify dataset availability, license/access terms, official splits, label mapping, label distributions, dependencies, and available device memory. Record dataset/model revisions and seed. Run a small training smoke test using training data and validation only; save configuration, timing, memory observations, and checkpoint evidence. Keep the held-out test split untouched. Schedule heavy training separately from ingestion on the local machine. Dataset/model-download or hardware blockers must be recorded without blocking document inspection; baselines/trials remain Week 3 and final results Week 4.

**Week 5 extraction sample:** select a small versioned sample from at least five varied documents, including reliable text, simple tables, missing fields, and unreliable tables. Label source passages/pages, task/method, evidence/material, conditions, measure, raw value/unit, and limitations where reported. Preserve null/`Not Reported` cases and documents with no experiments. Record source/license and fixture hashes; save labels for later field-level and numeric-correctness evaluation. This prepares evaluation data, not the Week 5 extractor implementation.

## Friday acceptance and Week 3 handoff

Deliver a verification record containing the tested revision, fixture manifest, exact commands, automated results, browser evidence, manually checked provenance samples, recovery results, and limitations. Keep ordinary PDFs, multi-column/rotated pages, scans, mixed text/image pages, unreliable tables/equations, corrupt inputs, duplicate uploads, and embedded prompt instructions represented. Treat PDF text as untrusted data throughout.

The Week 3 handoff must identify the accepted ingestion generation, tokenizer/configuration versions, chunk IDs and source mappings, reference exclusions, unresolved quality warnings, retry/recovery commands, and the planned index-membership contract. Week 3 owns embedding, FAISS/BM25 construction, atomic index publication, retrieval evaluation, and the transition to `ready`.

Phase completion requires evidence for its acceptance gate. This document authorizes no completion claim, application implementation, or publication by itself.
