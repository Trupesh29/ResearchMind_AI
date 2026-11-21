# ResearchMind AI — Week 4 Implementation Phases

**Date:** 2026-10-21  
**Status:** In progress  
**Outcome:** Grounded Research Assistant delivering verified, cited answers with honest abstention and interactive PDF navigation, alongside reproducible fine-tuned SciCite classification.

---

## Roadmap-to-Week Mapping

Week 4 implements roadmap **Phase 4** (Evidence-grounded assistant, citation verification, and calibrated abstention) and completes the independent **Phase 6** fine-tuning and evaluation workstream.

---

## Schedule & Phases

| Phase | Focus | Deliverable | Gate |
|---|---|---|---|
| Phase 7 | Assistant API & Grounding Engine | `POST /research/query`, query rewriting, untrusted prompt framing, DB conversation persistence | Multi-paper selection constraints, untrusted prompt boundaries, no hallucinated source IDs |
| Phase 8 | Citation Verification & Calibrated Abstention | Semantic claim verification, NLI / rule judge, explicit abstention with closest passages | 0 unsupported claims rendered; abstention on unanswerable fixtures |
| Phase 9 | Assistant UI & Split Workspace | Split PDF/chat layout, interactive citation jump with page/block focus, keyboard navigation | Responsive at 1440px/768px/375px; citation clicks navigate to correct source page |
| Independent Model Work | SciCite Fine-Tuned Model & Final Evaluation | DistilBERT fine-tuning evaluation on held-out test split, confusion matrix, artifact persistence | Untouched test split; reproducible macro-F1 and confusion matrix saved |
| Week 4 Acceptance | Full assistant and model validation | Comprehensive backend test suite, browser acceptance run, Week 5 handoff documentation | Verified citations, working abstention, stored model evaluation runs |

---

## Phase 7 — Assistant API & Grounding Engine

**User result:** Users can submit research queries scoped to explicitly selected ready papers in their workspace.

1. **Endpoint & Contract:**
   - `POST /api/research/query` (or `/research/query` via API router).
   - Validates workspace ownership and selected papers (must be in `ready` state).
   - Request schema: `workspace_id`, `query`, `selected_paper_ids: list[str]`, `mode: "concise" | "detailed" | "comparison"`, optional `conversation_id`.
   - Standalone query rewriter transforms conversational follow-ups into explicit queries without leaking past selections.
2. **Untrusted Prompt Assembly:**
   - Retrieved passages are enclosed within strict untrusted boundary delimiters (`<source id="...">...</source>`).
   - Strict instructions prevent system prompt override, prompt injections, and knowledge fabrication.
   - Preserves source metadata (paper ID, title, section, page start/end, chunk ID).
3. **Conversational Storage:**
   - Conversations and messages persisted in SQLite database (`conversations` and `messages` tables).
   - Traceable links between assistant messages, retrieved passages, and citations.

---

## Phase 8 — Citation Verification & Calibrated Abstention

**User result:** Every statement in an answer has verifiable source backing; questions with insufficient evidence trigger explicit abstention.

1. **Claim Extraction & Citation Verification:**
   - Parse generated claims and cited source IDs.
   - Check numerical values, measurements, entities, and factual assertions against source text.
   - Filter out or flag any statement not supported by retrieved chunks.
2. **Calibrated Abstention:**
   - When maximum evidence relevance or factual support falls below threshold, output honest abstention.
   - Provide the closest relevant passages rather than guessing.
   - Zero hallucinated source IDs or invented papers.

---

## Phase 9 — Assistant UI & Split Workspace

**User result:** Seamless split-screen workspace with chat interface and live PDF viewer with citation jump.

1. **Layout & Interaction:**
   - Desktop: Side-by-side split screen (PDF Viewer + Chat Panel).
   - Tablet & Mobile: Tabbed/drawer layout preserving conversation state.
   - Citation clicks immediately jump the PDF viewer to the cited page and highlight the relevant section/block.
2. **Accessible States:**
   - Loading skeletons, streaming/non-streaming feedback, error recovery, empty conversation states.
   - Full keyboard accessibility and WCAG contrast compliance.

---

## Independent SciCite Final Evaluation

- Evaluate fine-tuned DistilBERT checkpoint against the official held-out SciCite test split.
- Generate and persist confusion matrix, accuracy, macro-F1, per-class metrics (`method`, `background`, `result`).
- Persist model metadata for consumption by the Week 5 Model Lab.

---

## Friday Acceptance Gate

1. Grounded query responses contain only verifiable claims with accurate page citations.
2. Unanswerable queries reliably trigger honest abstention.
3. PDF viewer jumps to cited page on citation pill click.
4. Final SciCite test evaluation metrics saved and verifiable via API.
