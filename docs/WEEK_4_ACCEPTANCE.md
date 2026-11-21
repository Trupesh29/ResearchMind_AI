# ResearchMind AI — Week 4 Integrated Acceptance & Week 5 Handoff

**Date:** 2026-11-21  
**Checkpoint:** Milestone M3 Complete  
**Branch:** `manav`  
**Status:** ACCEPTED (Grounded Research Assistant, Citation Verification, Split Workspace, and SciCite Test Split Acceptance)

---

## 1. Executive Summary

Week 4 completes the Grounded Research Assistant and final SciCite model evaluation:
1. **Grounded Research Assistant API (`POST /api/research/query`):**
   - Untrusted XML framing (`<source id="...">...</source>`) preventing prompt breakout and hallucinations.
   - Conversational thread context management with scoped standalone query rewriting.
   - Persistent `conversations` and `messages` tables via Alembic migration `0012_add_assistant_conversations_and_messages.py`.
2. **Citation Verification & Calibrated Abstention:**
   - Strict claim-level citation markers (`[1]`, `[2]`).
   - Claim verification ensuring citations directly match retrieved evidence text and metadata.
   - Calibrated honest abstention when evidence is insufficient or completely absent (tested with unanswerable queries such as Martian conditions), providing clear reasoning rather than fabricating facts.
3. **Split Workspace UI (`ResearchAssistantPage.tsx`):**
   - Left pane: Synchronized PDF document viewer with page navigation, zoom, and cited quote highlight cards.
   - Right pane: Grounded conversational chat with thread switcher, honest abstention banner, and interactive citation pills jumping the PDF viewer to the exact cited page.
4. **Final SciCite Evaluation on Held-Out Test Split:**
   - 1,861 unseen test samples evaluated using frozen TF-IDF + Logistic Regression model.
   - **Test Accuracy:** **0.8162** (81.62%)
   - **Macro-F1:** **0.7977** (79.77%)
   - **Weighted F1:** **0.8190**
   - Zero test data leakage verified across train, dev, and test sets.

---

## 2. API Contract & Implementation

### Endpoint: `POST /api/research/query`
- **Request:**
  ```json
  {
    "workspace_id": "...",
    "query": "What is the primary contribution?",
    "conversation_id": "optional-uuid",
    "selected_paper_ids": ["..."],
    "citation_style": "inline",
    "abstention_threshold": 0.015
  }
  ```
- **Response:**
  ```json
  {
    "answer": "...",
    "conversation_id": "...",
    "citations": [
      {
        "citation_id": 1,
        "paper_id": "...",
        "paper_title": "...",
        "page_number": 1,
        "section_title": "...",
        "chunk_id": "...",
        "quote": "..."
      }
    ],
    "abstained": false,
    "abstention_reason": null,
    "evidence_count": 5
  }
  ```

### Conversations Lifecycle:
- `GET /api/research/conversations?workspace_id=...` — list active threads.
- `GET /api/research/conversations/{id}` — load full conversation with message history.
- `DELETE /api/research/conversations/{id}` — delete conversation thread.

---

## 3. SciCite Final Test Split Evaluation

Evaluated with `scripts/evaluate_scicite.py --baseline tfidf --split test`:
- **Sample Count:** 1,861
- **Overall Accuracy:** 0.8162 (81.62%)
- **Macro-F1:** 0.7977
- **Micro-F1:** 0.8162
- **Weighted-F1:** 0.8190

### Per-Class Performance
| Class | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| `background` | 0.8782 | 0.8024 | **0.8386** | 997 |
| `method` | 0.8319 | 0.8182 | **0.8250** | 605 |
| `result` | 0.6310 | 0.8649 | **0.7296** | 259 |

### Test Confusion Matrix
```
                 | Predicted: background | Predicted: method | Predicted: result
-----------------+-----------------------+-------------------+------------------
True: background |                   800 |                92 |               105
True: method     |                    84 |               495 |                26
True: result     |                    27 |                 8 |               224
```

---

## 4. Verification & Test Evidence

- **Backend Assistant Suite:** `pytest tests/backend/test_week4_assistant.py` → **5/5 passed (11.73s)**.
  - `test_query_rewriting_and_prompt_framing`: verified prompt framing and conversational rewriting.
  - `test_assistant_grounded_query_success`: verified citations, conversation creation, and response schema.
  - `test_calibrated_abstention_on_unanswerable_query`: verified honest abstention without hallucinated citations.
  - `test_conversation_lifecycle_and_persistence`: verified listing, retrieval, and deletion of threads.
  - `test_scicite_test_split_evaluation_integrity`: verified held-out test evaluation report integrity.
- **Frontend Vitest Suite:** `npm test -- --run` → **7 test files, 69/69 passed (15.86s)**.
- **TypeScript & Lint:** Clean compile, 0 diagnostics.
