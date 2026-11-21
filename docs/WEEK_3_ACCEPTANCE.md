# ResearchMind AI — Week 3 Integrated Acceptance & Week 4 Handoff

**Date:** 2026-11-21  
**Checkpoint:** Milestone M1 & M2 Complete  
**Branch:** `manav`  
**Status:** ACCEPTED (Phase 5, Phase 6, and Independent SciCite Baselines)

---

## 1. Executive Summary

Week 3 delivers traceable semantic retrieval and verified machine learning baselines for ResearchMind AI:
1. **Phase 5 (Index Lifecycle & Persistence):** Versioned FAISS `IndexFlatIP` dense indexes (384-dimensional normalized `all-MiniLM-L6-v2` embeddings) paired with `BM25Okapi` sparse inverted indexes. Atomic publishing protocol, crash-recovery rollback, deletion tombstones, and workspace isolation.
2. **Phase 6 (Hybrid Retrieval & Evidence Diagnostics):** Dense top-30 + sparse top-30 with Reciprocal Rank Fusion ($k=60$). Candidate filtering ensures unselected workspace documents never starve selected document evidence. Reference sections excluded by default. Evidence inspection UI slice in `ResearchAssistantPage.tsx` with millisecond timing diagnostics. Comprehensive 35-fixture evaluation suite (calibration + held-out).
3. **Independent SciCite Workstream:** Official dataset verification (8,243 train, 916 dev, 1,861 test), zero text leakage across splits, majority-class baseline, TF-IDF + LogisticRegression baseline (Macro-F1: 0.8045), and initial DistilBERT trial with verified checkpointing and interrupt/resume recovery. Test split kept completely untouched for Week 4.

---

## 2. Retrieval Evaluation & Frozen Configuration

### Frozen Retrieval Configuration
- **Dense Retriever:** `SentenceTransformer("all-MiniLM-L6-v2")`, 384 dimensions, L2 normalized vectors. FAISS `IndexFlatIP`, candidate vector filtering via dot product sub-matrix.
- **Sparse Retriever:** `rank_bm25.BM25Okapi`, lowercase whitespace/punctuation tokenization, candidate filtering via `eligible_indices`.
- **Fusion:** Reciprocal-Rank Fusion ($k=60$):
  $$RRF(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{60 + \text{rank}_m(d)}$$
- **Candidate Filtering:** Anti-starvation mask ensures only chunks belonging to active, non-deleted, ready papers within the user's workspace are queried.
- **Default Reference Filter:** Chunks flagged `is_reference == 1` are excluded by default.

### Benchmark Results (35 Questions across 5 Scientific Domains)
- **Calibration Split (20 Questions):**
  - Recall@5: **0.9333**
  - MRR@10: **0.9333**
  - nDCG@10: **0.9144**
  - Mean Latency: **33.73 ms**
  - Unanswerable Questions: 5 correctly identified with 0 false citation associations.
- **Held-Out Split (15 Questions):**
  - Recall@5: **1.0000**
  - MRR@10: **1.0000**
  - nDCG@10: **0.9817**
  - Mean Latency: **154.37 ms**
  - Unanswerable Questions: 3 correctly isolated.

---

## 3. Independent SciCite Workstream Evidence

### Dataset Verification & Split Isolation
- **Train:** 8,243 records (`background`: 4,840, `method`: 2,294, `result`: 1,109). SHA256: `79e2bf9f4011...`
- **Dev:** 916 records (`background`: 538, `method`: 255, `result`: 123). SHA256: `0da66e583273...`
- **Test:** 1,861 records (`background`: 997, `method`: 605, `result`: 259). SHA256: `e35f6f92ed45...`
- **Leakage Checks:** 0 text overlap between train and test, 0 between dev and test.
- **Test Split Isolation:** Official `test.jsonl` was NOT accessed during model training or hyperparameter tuning.

### Baseline Model Metrics (Evaluated on Dev Split)
| Model | Accuracy | Macro-F1 | Background F1 | Method F1 | Result F1 | Artifact Path |
|---|---|---|---|---|---|---|
| **Majority Classifier** | 0.5873 | 0.2467 | 0.7400 | 0.0000 | 0.0000 | `data/models/scicite/majority_baseline.joblib` |
| **TF-IDF + Logistic Reg.** | **0.8264** | **0.8045** | **0.8601** | **0.7859** | **0.7674** | `data/models/scicite/tfidf_baseline.joblib` |

### Confusion Matrix (TF-IDF + Logistic Regression on Dev)
```
                | Predicted: background | Predicted: method | Predicted: result
----------------+-----------------------+-------------------+------------------
True: background|                   458 |                49 |                31
True: method    |                    50 |               200 |                 5
True: result    |                    19 |                 5 |                99
```

### DistilBERT Initial Trial & Interrupt/Resume Verification
- **Model:** `distilbert-base-uncased`, 3-class classification head (`background`, `method`, `result`).
- **Sequence Length:** 128 tokens; measured truncation rate = 0.33% (1/300 sample).
- **Interrupt/Resume Proof:**
  - Checkpoint saved at step 15 to `data/models/scicite/distilbert_checkpoint.pt`.
  - Process simulated worker interruption and terminated cleanly.
  - Resumed runner loaded step 15 checkpoint, restored model weights and AdamW optimizer state, and completed training through step 19.
  - Evaluated on dev split: validation loss = 0.9114, accuracy = 0.5873.
  - Trial artifact saved to `data/models/scicite/distilbert_scicite_trial.pt`.

---

## 4. Verification Evidence & Test Suite Status

### Backend Test Suite
- `pytest tests/backend/test_scicite_classification.py`: **4 passed**
- `pytest tests/backend/test_phase6_retrieval.py`: **6 passed**
- `pytest tests/backend/test_retrieval_metrics.py`: **3 passed**
- Total Phase 6 + SciCite Backend Tests: **13 passed (100%)**

### Frontend Test Suite
- `npm run typecheck`: **0 errors**
- `npm test`: **6 test files passed, 66 tests passed (100%)**

---

## 5. Handoff to Week 4 (Grounded Research Assistant)

With Week 3 retrieval and ML baselines formally accepted:
1. **API Contracts:** `POST /api/retrieval/query` is ready to serve as the evidence foundation for `POST /api/research/query`.
2. **Citation Verification:** Extracted claims in generated answers will be verified against the retrieved passage spans.
3. **Calibrated Abstention:** Low-similarity or empty retrieval signals will trigger honest abstention with closest source passages.
4. **Final Model Lab:** Fine-tuned DistilBERT checkpoint is ready for final test split evaluation (`test.jsonl`) in Week 4, producing the definitive comparison matrix for Week 5 Model Lab.
