# Week 3 execution checklist

All items are pending. Acceptance criteria and integration points are defined in [Week 3 phases](../docs/WEEK_3_PHASES.md). Split any item exceeding one focused session into smaller tasks before implementation.

| Done | Task | Depends on | Verification / acceptance |
|---|---|---|---|
| [x] | 5.1 Confirm ingestion handoff and runtime prerequisites | Accepted Phase 4 | Record generation, tokenizer/config revisions and actual embedding/FAISS smoke result |
| [x] | 5.2 Define index manifest and membership migration | 5.1 | Fresh/populated migration checks; explicit compatible-version contract |
| [x] | 5.3 Embed one accepted generation | 5.2 | Exact token-limit checks; finite normalized vectors; idempotent retry |
| [x] | Checkpoint: embedding contract | 5.3 | Inspect vector membership against original chunk/source IDs |
| [x] | 5.4 Build paired FAISS/BM25 snapshot | 5.3 | Both reload with identical eligible manifest; failures leave prior version intact |
| [x] | 5.5 Publish and recover index versions | 5.4 | Crash-boundary and concurrent-build tests; ready only after valid publication |
| [x] | 5.6 Integrate delete/reprocess invalidation | 5.5 | Stale worker cannot publish; deleted/superseded source unavailable immediately |
| [x] | 5.7 Expose stage/status/retry behavior | 5.5 | Real-worker browser states; coherent progress; existing UI race regressions pass |
| [x] | Checkpoint: Phase 5 acceptance | 5.6, 5.7 | Save migration, lifecycle, backend and browser evidence separately |
| [ ] | 6.1 Define retrieval-only API contract | 5.2 | Route, ownership, readiness, bounds and error cases documented |
| [ ] | 6.2 Retrieve selected-scope dense/sparse candidates | Phase 5, 6.1 | Isolation, reference exclusion, starvation and deletion negative controls |
| [ ] | 6.3 Fuse and return traceable evidence | 6.2 | Hand-checked RRF, stable deduplication, source spans and version diagnostics |
| [ ] | Checkpoint: retrieval service | 6.3 | Selected ready documents only; no ranking-as-confidence claim |
| [ ] | 6.4 Build minimal evidence inspection UI | 6.3 | Live source navigation, slow-response selection race, keyboard/narrow screen checks |
| [ ] | 6.5 Label and split evaluation fixtures | 5.1 | 30–50 questions, at least five documents, 5–10 unanswerable cases; immutable split manifest |
| [ ] | 6.6 Implement and validate metric CLI | 6.3, 6.5 | Hand-calculated metric cases, stale-label rejection, explicit denominators/cutoffs |
| [ ] | 6.7 Compare baselines and freeze configuration | 6.6 | Calibration targets fixed before held-out run; quality/latency reports saved |
| [ ] | S1 Verify SciCite readiness | Independent | Dataset rights/revisions, splits, labels and leakage checks recorded |
| [ ] | S2 Run majority and TF-IDF baselines | S1 | Training-only fit; actual validation metrics and configurations saved |
| [ ] | S3 Run initial DistilBERT trial and resume check | S1 | Checkpoint, validation curves, device/memory/timing and resume evidence; test untouched |
| [ ] | Checkpoint: Week 3 acceptance and Week 4 handoff | 6.4, 6.7, S2, S3 | Save reviewed revision, real-worker/browser/recovery evidence and separate classifier status; list incomplete gates honestly |

Optional reranker follows 6.7 only if schedule permits; it must earn inclusion through measured quality/cost evidence. Classifier blockers do not prevent independent retrieval acceptance.
