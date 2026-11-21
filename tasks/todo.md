# ResearchMind AI — Execution Checklist (Weeks 3–6)

Status: In progress (Milestone M1 completed, Milestone M2 active).

---

## Week 3: Phase 5 & Phase 6 (Indexes, Retrieval, and Evaluation)

| Done | Task | Depends on | Verification / acceptance |
|---|---|---|---|
| [x] | 5.1 Ingestion handoff & runtime prerequisites | Phase 4 | Embedding model and FAISS environment verified |
| [x] | 5.2 Index manifest & membership schema | 5.1 | `EmbeddingIndex` and `IndexChunk` models and migrations |
| [x] | 5.3 Batch MiniLM embeddings | 5.2 | Pinned model, finite normalized vectors, sequence bounds |
| [x] | 5.4 Paired FAISS + BM25 snapshot | 5.3 | Coherent snapshot build from identical eligible chunk manifest |
| [x] | 5.5 Atomic publication & crash recovery | 5.4 | Atomic slot rename, fencing token validation, recoverability |
| [x] | 5.6 Delete/reprocess invalidation | 5.5 | Immediate query tombstone filtering, rebuild threshold |
| [x] | 5.7 Stage/status/retry integration | 5.5 | Real worker, Quality Center UI progress, race guards |
| [x] | Checkpoint: Phase 5 acceptance | 5.6, 5.7 | Recorded in `PHASE_5_VERIFICATION.md` (Commit `10dba89`) |
| [x] | 6.1 Define retrieval-only API contract | 5.2 | `POST /api/retrieval/query` route, schemas, workspace ownership |
| [x] | 6.2 Filtered candidate retrieval (Dense + Sparse) | 6.1 | Anti-starvation candidate filtering on selected papers, reference exclusion |
| [x] | 6.3 Reciprocal-Rank Fusion (RRF k=60) & diagnostics | 6.2 | Stable deduplication, raw & fused scores, timings, provenance |
| [x] | 6.4 Minimal evidence inspection UI | 6.3 | Source navigation, selection race protection, keyboard/narrow screen |
| [x] | 6.5 Evaluation fixtures (30–50 labeled queries) | 5.1 | Varied docs, unanswerable questions, split calibration / held-out |
| [x] | 6.6 Metric evaluation CLI (Recall@5, MRR, nDCG@10) | 6.3, 6.5 | Hand-verified metric calculations, latency measurement |
| [x] | 6.7 Baseline comparison & configuration freeze | 6.6 | Dense vs BM25 vs Hybrid evaluation reports |
| [x] | S1 Verify SciCite readiness | Independent | Data splits, labels (`method`, `background`, `result`), leakage checks |
| [x] | S2 Train majority & TF-IDF baselines | S1 | Training-only fit, validation metrics & confusion matrix |
| [x] | S3 Initial DistilBERT trial & resume check | S1 | Checkpoint, validation curves, interrupt/resume verified |
| [x] | Checkpoint: Week 3 acceptance | 6.4, 6.7, S3 | Real-worker demo evidence, metrics saved, Week 4 handoff |

---

## Week 4: Grounded Research Assistant & Classifier Acceptance

| Done | Task | Depends on | Verification / acceptance |
|---|---|---|---|
| [x] | 7.1 Assistant API & query rewriting | Week 3 | `POST /api/research/query`, conversation persistence, untrusted context framing |
| [x] | 8.1 Citation verification engine | 7.1 | Grounding check against source chunks, extraction of numerical/factual claims |
| [x] | 8.2 Calibrated abstention | 8.1 | Honest abstention on unanswerable queries with closest evidence |
| [x] | 9.1 Assistant UI & split workspace | 7.1, 8.2 | Side-by-side PDF/chat view, citation click jumps to PDF page |
| [x] | S4 Final SciCite evaluation on held-out test split | S3 | Final accuracy, macro-F1, confusion matrix persisted |
| [x] | Checkpoint: Week 4 acceptance | 9.1, S4 | Verified citations, working abstention, recorded model run |

---

## Week 5: Research Intelligence & Model Lab

| Done | Task | Depends on | Verification / acceptance |
|---|---|---|---|
| [x] | 10.1 Research Explorer & multi-style summaries | Week 4 | Simple, technical, methodology, results summaries with citations |
| [x] | 11.1 Two-paper comparison matrix | 10.1 | Comparative table with per-cell citations and non-comparable states |
| [x] | 12.1 Experiment intelligence extraction | 10.1 | Extracted conditions, measures, units, and source provenance |
| [x] | 13.1 Report Studio (DOCX generation) | 10.1, 11.1, 12.1 | Server-side docx export, status polling, authenticated download |
| [x] | 14.1 Model Lab UI | S4 | Real confusion matrix, learning curves, and baseline comparison |
| [x] | Checkpoint: Week 5 acceptance | 13.1, 14.1 | Exported DOCX verified, comparison verified, experiment records verified |

---

## Week 6: Hardening, Packaging & Release

| Done | Task | Depends on | Verification / acceptance |
|---|---|---|---|
| [ ] | 15.1 Security audit & path isolation | Week 5 | Path traversal guards, prompt injection defense, CORS verification |
| [ ] | 16.1 Comprehensive E2E regression suite | 15.1 | 250+ backend and frontend tests passing with 0 regressions |
| [ ] | 17.1 Accessibility & visual polish | 16.1 | WCAG 2.2 AA compliance, 1440/768/375px responsive checks |
| [ ] | 18.1 Performance profiling | 16.1 | RAM <= 4GB, retrieval < 100ms, batch throughput verified |
| [ ] | 19.1 Local deployment packaging & final demo | 18.1 | Single-command launch, user guide, final release report in `docs/RELEASE_WEEK_6.md` |
| [ ] | Checkpoint: Final Six-Week Release | 19.1 | Six-week MVP fully accepted |
