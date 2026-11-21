# ResearchMind AI — Week 6 Implementation Phases

**Date:** 2026-10-23  
**Status:** Planned  
**Outcome:** Production-hardened, fully tested, accessible, and locally deployable ResearchMind AI MVP with comprehensive verification evidence and documentation.

---

## Roadmap-to-Week Mapping

Week 6 delivers roadmap **Phase 7** (Testing, security hardening, performance profiling, documentation, and local deployment packaging) culminating in the final Six-Week Local MVP release.

---

## Schedule & Phases

| Phase | Focus | Deliverable | Gate |
|---|---|---|---|
| Phase 15 | Security Hardening & Input Sanitization | Path traversal guards, SQL injection audits, CORS lockdown, untrusted input isolation | Clean security audit, no path escape, strict schema validation |
| Phase 16 | Comprehensive E2E Testing & Edge Cases | Full regression test suite (250+ tests), corrupt/scanned PDF handling, prompt injection defense | 100% test pass rate across backend and frontend |
| Phase 17 | Accessibility & UI Refinement | WCAG 2.2 AA audit, keyboard navigation, focus indicators, responsive layouts (1440/768/375px) | Zero critical accessibility violations, keyboard-navigable |
| Phase 18 | Performance Profiling & Resource Benchmarking | Latency profiling for 20-page document ingestion, hybrid retrieval, and report generation | Verified operation within 4GB RAM local constraints |
| Phase 19 | Local Deployment Packaging & Release Demo | CLI startup scripts, health check endpoints, offline model cache validation, user guide | Single-command launch, clean first-time user journey |
| Week 6 Acceptance | Final Local MVP Sign-off | `docs/RELEASE_WEEK_6.md`, verification artifacts, demo walkthrough | All 6-week MVP acceptance criteria completely fulfilled |

---

## Phase 15 — Security Hardening & Input Sanitization

1. **Storage & Path Safety:**
   - Prevent directory traversal in PDF streaming, DOCX download, and workspace file handlers.
   - Enforce workspace isolation boundaries; reject cross-workspace access attempts.
2. **Prompt Injection & LLM Security:**
   - Strict structural separation between system prompts, user instructions, and document text.
   - Neutralize prompt injection attempts embedded in uploaded research PDFs.
3. **CORS & Environment:**
   - Strict CORS origins, secure headers, and clean credential isolation.

---

## Phase 16 — Comprehensive E2E Testing & Edge Cases

1. **Automated Test Matrix:**
   - Ingestion: malformed PDFs, password-protected PDFs, scanned pages, huge files.
   - Retrieval: multi-paper isolation, reference section exclusion, zero-result queries.
   - Assistant: unsupported claim detection, honest abstention, citation mapping.
   - Reports: corrupt data recovery, stale report invalidation upon document deletion.
2. **Regression Guarantees:**
   - Zero test regressions; clean pytest and vitest execution.

---

## Phase 17 — Accessibility & Visual Polish

1. **WCAG 2.2 AA Compliance:**
   - Contrast ratio >= 4.5:1 for standard text, >= 3:1 for large text and UI components.
   - Visible keyboard focus rings on all interactive elements.
   - ARIA live regions for async indexing, query generation, and export jobs.
2. **Responsive Verification:**
   - Flawless rendering at 1440px desktop, 768px tablet, and 375px mobile viewports.

---

## Phase 18 — Performance Profiling & Hardware Budget

1. **Local Budget:**
   - Max memory usage <= 4GB RAM (CPU-only execution compatible).
   - Index query latency < 100ms for hybrid retrieval over 1,000 chunks.
   - Batch ingestion throughput profiled and documented.

---

## Phase 19 — Packaging & Final Acceptance

1. **One-Command Setup:**
   - Verified virtual environment setup, model caching scripts, and database initialization.
2. **Release Documentation:**
   - Comprehensive user manual, architecture guide, and operational troubleshooting runbook.
   - Final release audit documented in `docs/RELEASE_WEEK_6.md`.
