# ResearchMind AI

> Evidence-first universal research document analyzer with traceable page-level verification, hybrid semantic retrieval, and structured insights.

---

## Overview

ResearchMind AI is designed to analyze academic research papers and technical documents locally with zero loss of provenance. Every factual claim is backed by page-level citations, coordinate-highlighted evidence, and strict abstention when the uploaded evidence does not support an answer.

This repository represents **Week 1, Phase 2: Workspace Management and PDF Research Library** of the six-week development roadmap.

### Key Capabilities in Phase 1 & 2:
- **FastAPI Backend:** Modular API architecture with standardized error envelopes (`API_SPEC.md §2.2`), request correlation IDs, CORS configuration, and structured logging.
- **Relational Persistence (SQLite + Alembic):** Foundational P0 schema for `users`, `workspaces`, and `papers` with cascading foreign keys, uniqueness constraints, and SQLite WAL pragmas.
- **Idempotent Local Identity:** Single-user local bootstrap seeding `local@researchmind.ai` without requiring authentication or exposing passwords.
- **Workspace Management:** Full CRUD operations under `/api/workspaces` with trim/validation, per-user uniqueness, ownership isolation, and live document counts.
- **PDF Research Library:** Multi-file drag & drop upload dropzone, streaming SHA-256 deduplication, PyMuPDF integrity verification, tripartite batch responses (`202 Accepted`), and live search filtering.
- **Original Document Streaming:** HTTP Byte Range streaming (`200 OK`, `206 Partial Content`, `416 Range Not Satisfiable`) on `/api/papers/{id}/file` with safe content-disposition and no server path leakage.
- **Apple Modern Design System (DESIGN.md):** Soft-raised surfaces, dual-shadow elevation, capsule pills, responsive navigation, embedded PDF viewer modal, accessible delete confirmation alertdialogs with focus trapping, and WCAG AA contrast compliance.
- **React 19 + TypeScript + Vite Frontend:** Responsive AppShell with desktop sidebar, mobile drawer, topbar with live health checks, Landing, Dashboard, and Library views.
- **ML Environment Verification:** Standalone smoke check verifying PyTorch (CPU/CUDA fallback), Sentence Transformers (`all-MiniLM-L6-v2`), and FAISS vector index querying.

---

## Directory Structure

```
ResearchMind AI/
├── backend/               # FastAPI application & Alembic migrations
│   ├── app/
│   │   ├── api/           # Endpoints, routers, and dependencies
│   │   ├── core/          # Configuration, logging, and error envelope handlers
│   │   └── db/            # Base, models, session factory, and bootstrap
│   ├── migrations/        # Executable Alembic migration scripts
│   ├── requirements.txt   # Core API dependencies
│   ├── requirements-ml.txt# Heavyweight ML & vector search packages
│   └── schema_p0.sql      # Clean SQL snapshot of foundational tables
├── frontend/              # React 19 + TypeScript + Vite application
│   ├── src/
│   │   ├── api/           # Typed API client and error handling
│   │   ├── app/           # App root and client router
│   │   ├── components/    # Reusable Apple Modern UI & layout components
│   │   ├── pages/         # Landing, Dashboard, Library, and 404 views
│   │   └── styles/        # DESIGN.md design tokens and global styles
│   └── package.json
├── worker/                # Background processing boundary (Week 2)
├── data/                  # Private file storage (excluded from git)
│   ├── pdfs/              # Raw uploaded PDFs
│   ├── indexes/           # FAISS & BM25 indices
│   ├── models/            # Cached model weights
│   └── reports/           # Generated DOCX exports
├── scripts/               # PowerShell setup, startup, and ML check scripts
│   ├── setup_dev.ps1      # Automated setup script
│   ├── start_backend.ps1  # FastAPI launcher (port 8000)
│   ├── start_frontend.ps1 # Vite dev launcher (port 5173)
│   └── ml_smoke_check.py  # Standalone PyTorch/MiniLM/FAISS smoke test
├── tests/                 # Automated test suites
│   └── backend/           # Pytest suite (config, models, bootstrap, APIs)
└── docs/                  # Plans, specifications, and verification evidence
    ├── PHASE_1_PLAN.md    # Detailed Phase 1 planning & specification reconciliation
    └── PHASE_1_VERIFICATION.md # Complete verification log & test results
```

---

## Quickstart & Local Development

### Prerequisites
- **Python:** 3.11 or 3.12 (with `uv` recommended)
- **Node.js:** v18+ or v20+ with `npm`

### 1. Automated Setup
Run the setup script in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
```

Or manually:
```bash
# Backend virtualenv & dependencies
uv venv --python 3.12 .venv
uv pip install -r backend/requirements.txt
uv pip install -r backend/requirements-ml.txt

# Run migrations
.venv/Scripts/alembic -c backend/alembic.ini upgrade head

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Start Servers
In terminal 1 (Backend):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_backend.ps1
# Runs at http://127.0.0.1:8000 (OpenAPI docs at http://127.0.0.1:8000/docs)
```

In terminal 2 (Frontend):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_frontend.ps1
# Runs at http://127.0.0.1:5173
```

---

## Verification Commands

### 1. Run Automated Backend Tests
```bash
.venv/Scripts/pytest -v
```
*Result: 36 passed tests covering config, SQLite foreign key enforcement, table check constraints, Alembic schema drift prevention (with server default and type checks), populated database migration upgrade, cascade deletion, bootstrap idempotency, deep migration-aware ready checks, and error envelopes.*

### 2. Run Python Linter & Formatter
```bash
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
```
*Result: All checks passed with 0 errors and all files correctly formatted.*

### 3. Run Frontend Automated Tests, Linter, Formatter & Build
```bash
cd frontend
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
cd ..
```
*Result: 9 tests passed across 3 test suites with Vitest, clean ESLint and Prettier checks, zero TypeScript errors, and production bundle generated.*

### 4. Run Machine Learning & Vector Search Smoke Check
```bash
.venv/Scripts/python scripts/ml_smoke_check.py
```
*Result: Verifies PyTorch runtime, CPU fallback, SentenceTransformers `all-MiniLM-L6-v2` loading, (3, 384) embedding matrix generation, and FAISS `IndexFlatIP` top-k retrieval.*

---

## Build Boundaries & Next Steps

- **Completed in Phase 1:** Architecture foundation, models, migrations, local user bootstrap, system endpoints, design tokens, responsive app shell, ML smoke tests.
- **Phase 2 (Immediate next phase):** Multi-file PDF upload with binary `%PDF-` validation, size limit checks, SHA-256 deduplication, original PDF streaming, and library CRUD lifecycle.
- **Weeks 2–6:** Document chunking, hybrid retrieval, assistant Q&A, and SciCite Model Lab.
