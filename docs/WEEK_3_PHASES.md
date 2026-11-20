# ResearchMind AI — Week 3 Implementation Phases

**Date:** 2026-10-20  
**Status:** Planned; no Week 3 implementation or acceptance claimed.  
**Outcome:** Selected ready documents return traceable evidence through measured hybrid retrieval, with reproducible initial classifier experiments.

Continue the implementation numbering with **Phase 5 and Phase 6**. Both implement roadmap feature Phase 3; the independent SciCite work prepares roadmap feature Phase 6. These numbers must not replace the feature labels in the sidebar. This expands the existing six-week schedule without moving assistant generation into Week 3.

## Starting evidence and entry gate

- Current checkout: `480e78e`, documenting acceptance of application checkpoint `63fde59`. `PHASE_4_REVIEW_63fde59.md` records 200 backend tests, 48 frontend tests, and 9/9 browser criteria passing. These are recorded prior results, not tests rerun for this plan. Older files named “latest” do not supersede this newer review.
- The worker currently publishes a chunk bundle using `published_run_id`; extraction completion still awaits semantic indexing. Preserve exact chunk/page/block provenance and the accepted Quality Center race protections.
- Before implementation, verify the accepted generation, tokenizer revision/configuration, migrations, and effective private storage paths. Confirm SciCite preparation and Week 5 extraction-label preparation separately; Phase 4 application acceptance alone does not prove those workstreams complete.
- Reconcile `DATABASE_SCHEMA.md` and `API_SPEC.md` against executable models/migrations. A job-stage enum or documented endpoint is not evidence that indexing or retrieval works.

## Schedule

| Work | Target | Deliverable | Gate |
|---|---|---|---|
| Phase 5 — Embeddings and index lifecycle | Monday–Tuesday | Versioned workspace FAISS/BM25 indexes and real ready transition | Publication, restart, reprocess and deletion safety |
| Phase 6 — Hybrid retrieval and evaluation | Wednesday–Thursday | Selected-document search, evidence diagnostics and measured baselines | Isolation, provenance and evaluation correctness |
| Independent SciCite work | Bounded sessions during the week | Majority/TF-IDF baselines and first DistilBERT validation trial | Reproducible artifacts; test split untouched |
| Integrated acceptance | Friday | Real-worker demo, saved metrics, failure recovery and Week 4 handoff | Evidence for every required gate |

Targets are estimates. If lifecycle repairs overrun, drop the optional reranker first and record remaining work honestly. Training does not gate document retrieval; avoid concurrent GPU training and embedding on the documented 4 GB machine.

## Phase 5 — Embeddings and index lifecycle

**User result:** An extracted document becomes ready only after its matching evidence is searchable in a successfully published index. Failed builds remain recoverable.

1. **Index contract and migration.** Define immutable workspace index versions, explicit index-to-chunk/vector membership, ingestion run identity, model/tokenizer revisions, dimension, normalization, build configuration, file checksums and active-version pointer. Keep pre-index chunks independent of index membership. Define building/active/failed/retired states and migrations for existing databases. One version contains compatible embeddings only.
2. **Embedding path.** Extend the persistent worker after chunk publication. Use the configured MiniLM model, normalized vectors, bounded batches and CPU fallback. Revalidate the exact final embedding input against its tokenizer limit, including special tokens. Reject nonfinite vectors, dimension mismatches and incompatible chunk/model revisions. Retrying must not duplicate membership or vectors.
3. **Workspace snapshot and publication.** Build FAISS and BM25 from the same eligible chunk manifest in a new immutable artifact directory. Validate both artifacts before a transactional active-pointer/ready-state update. Coordinate filesystem writes and DB commit through a documented crash-recovery protocol; do not assume a cross-system atomic transaction. Serialize or compare-and-swap competing workspace builds so one upload cannot overwrite another's membership.
4. **Lifecycle integration.** Resume valid embedding/indexing checkpoints after worker restart. Retain the last valid index on build failure, but never serve old or deleted generations as current. Reprocessing makes that paper unavailable to retrieval until the replacement generation publishes; unaffected ready papers remain usable. Exclude deleted sources immediately at query time, record durable tombstones and rebuild at a documented threshold. Recheck liveness/generation before publication. Wire invalidation for existing derived outputs and specify the contract for later summaries/conversations.
5. **Status and recovery.** Extend the existing API and Quality Center with actual embedding/indexing stages, awaiting-indexing, failure/retry and ready states. Reconcile the existing chunk-stage `progress = 1.0` convention with full-pipeline progress in both API and UI. Preserve cancellation, coherent generation snapshots and reprocess conflict handling. Define zero-eligible-chunk behavior explicitly; do not claim searchable success for an empty document.

**Integration points:** `backend/app/db/models.py`, new migrations and index/embedding services, `backend/app/services/processing_service.py`, `worker/engine.py`, existing paper/status schemas, typed frontend API and Quality Center. Proposed new files are implementation work, not existing capabilities.

**Phase 5 gate:**

- Fresh and populated databases migrate without losing original files or accepted chunks. A real worker produces loadable FAISS/BM25 artifacts with matching IDs, versions and counts; a ready document has valid membership.
- Inject failures before artifact completion, before pointer switch, and after commit; restart and verify recoverable state with no partial publication. Test competing uploads/builds and stale workers.
- Delete/reprocess during embedding, build and query. Neither retrieval path returns deleted or superseded evidence; unaffected papers remain usable. Original hashes remain unchanged.
- Verify status and retry in the browser with the real worker, plus focused backend tests and affected frontend lint/format/type/build checks. Save evidence by verification layer.

## Phase 6 — Hybrid retrieval and evaluation

**User result:** A query over explicitly selected documents returns relevant passages with paper, section, page/block references and diagnostic scores. Answer generation remains Week 4.

1. **Retrieval-only contract.** Add a documented endpoint and typed schemas consistent with existing envelopes and ownership checks; finalize its route before coding. Require nonempty selected paper IDs belonging to the workspace. Reject mixed foreign/not-ready selections rather than silently broadening scope. Define no-active-index, building, unavailable-model and empty-result behavior. Bound query length, selection count and result limits.
2. **Filtered candidate retrieval.** Search only the active snapshot and eligible selected generations. Return dense top-30 and BM25 top-30 within that selected scope, excluding reference chunks by default. Filtering a workspace top-30 after search is insufficient: use a selected subset or a verified expansion strategy so unrelated papers cannot starve selected evidence.
3. **Fusion and evidence.** Deduplicate by stable chunk identity and combine ranks with reciprocal-rank fusion, `k=60`, returning up to 20 passages. Preserve raw scores, per-path ranks, fused score, source text/page/block spans, run/index/model versions and timings. Specify deterministic tie handling. Recheck deletion/generation eligibility before returning results. RRF scores are ranking values, not confidence probabilities.
4. **Inspection slice.** Provide a minimal retrieval diagnostics view using existing components, with selected papers, query, passages, source-page navigation, timing and explicit empty/error states. Keep Assistant and Explorer feature labels intact; do not imply generated answers exist. Guard late responses after selection/workspace changes. Validate keyboard use and narrow-screen layouts.
5. **Evaluation fixtures and CLI.** Version 30–50 labeled questions across at least five varied documents, including 5–10 unanswerable questions. Record document hashes/rights, selected scope, relevant source spans and graded relevance where required. Resolve labels to the tested ingestion generation; fail on stale labels. Separate calibration and held-out sets before tuning. Save Recall@5, MRR (with explicit cutoff), nDCG@10 and latency with counts, denominators, seed/configuration, hardware and index revision. Report unanswerable cases separately; do not assign them fabricated relevant chunks or treat low rank as a calibrated abstention.
6. **Comparison and freeze.** Run BM25-only, dense-only and hybrid on identical inputs. Report quality plus cold/warm latency and memory observations. Set numeric quality/latency targets from calibration results before the held-out evaluation; retain regressions and failures. Evaluate a cross-encoder only if time remains and measured gains justify cost. Freeze the chosen configuration and record honest pass/fail results; do not keep tuning on the held-out set.

**Integration points:** new retrieval service/router/schemas, API router registration, small frontend diagnostics view, proposed evaluation CLI and versioned fixture labels. Existing `scripts/ml_smoke_check.py` can check runtime prerequisites but cannot establish retrieval acceptance.

**Phase 6 gate:**

- Known-answer fixtures return expected source passages; default results exclude references. Multi-workspace, unselected-paper, stale-generation and deleted-paper negative controls pass in both paths and fused results.
- Test selection starvation explicitly: many irrelevant/unselected workspace chunks must not crowd out the selected document's relevant passage. Verify stable fusion and metric calculations against small hand-calculated fixtures.
- Live browser flow: upload → real indexing → ready → select papers → retrieve → open the correct source page. Switching selection during a slow request cannot display the previous selection's evidence.
- Save all three baseline runs, separate calibration/held-out reports, limitations and the frozen retrieval configuration. No quality claim without measured evidence.

## Independent SciCite workstream

- Confirm official dataset access/license, immutable dataset/model revisions, split hashes, label mapping/distributions and duplicates/leakage checks. Reuse verified Week 2 preparation when available; record missing preparation explicitly.
- Fit majority-class and TF-IDF/logistic-regression baselines on training data only. Fit vocabulary on training data; use validation for selection. Save configuration, macro-F1, accuracy, per-class metrics and confusion matrices from actual runs.
- Run the first DistilBERT trial with a recorded seed, small batches and approximately 128-token inputs; measure truncation and memory. Save validation curves, checkpoint, duration and device configuration. Test interruption/resume once and reserve time for a failed-run recovery.
- Keep the official test split untouched until Week 4 final evaluation. Training remains CLI-driven; Model Lab UI stays Week 5. No paper upload triggers training.

## Friday acceptance and Week 4 handoff

Produce a verification record with tested revision, fixture hashes, exact commands, migration/recovery evidence, test counts, browser artifacts, manual provenance checks, evaluation outputs and outstanding issues. Keep ordinary, multi-column, partial/scanned, reference-heavy, long and prompt-instruction-bearing PDFs represented; document text is untrusted input.

The handoff must contain the active index manifest, chunk/source contract, frozen retrieval settings, calibration/held-out separation, measured quality/latency, selected-document protections, restart/rebuild commands and classifier artifacts. Week 4 owns generation, claim verification, calibrated abstention, conversations and final classifier evaluation. Generation must wait for retrieval acceptance; classifier completion is tracked separately.

## Scope and resources

This is a planning change only. No application implementation, training, paid service, external upload or publication is included. No new MCP capability is required. Applied the installed `att-addy-agent-skills-planning-and-task-breakdown` instruction file for dependency ordering and verifiable slices; this does not claim native Codex commands or verified Antigravity menu registration. Retain the project convention of phase documents under `docs/`; `tasks/plan.md` links here and `tasks/todo.md` tracks the execution checklist.
