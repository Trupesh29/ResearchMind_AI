# ResearchMind AI — Week 1, Phase 1 Implementation Plan

## 1. Executive Summary & Objective

**Phase 1 Goal:** Establish the robust, reproducible project foundation and accessible Apple Modern application shell for ResearchMind AI.

This delivery represents Phase 1 of the two-phase Week 1 breakdown:
- **Phase 1 (This implementation):** Core repository architecture, FastAPI backend foundation, SQLite + Alembic database migrations, core relational models (`users`, `workspaces`, `papers`), idempotent default local user bootstrap, responsive Apple Modern application shell (React + TypeScript + Vite), typed API client with centralized error envelope handling, health/readiness endpoints, environment configuration, reproducible scripts, and ML/generator smoke verification.
- **Phase 2 (Subsequent delivery):** Workspace CRUD management, multi-file PDF upload with binary magic byte validation, duplicate SHA-256 detection, PDF viewer/streaming, and library lifecycle management.
- **Weeks 2–6 (Deferred beyond Week 1):** Ingestion/extraction worker, sentence-aware chunking, hybrid FAISS/BM25 retrieval, RAG Research Assistant, SciCite Model Lab, comparison matrix, experiment extraction, and DOCX reporting.

---

## 2. Specification Reconciliation & Architectural Decisions

1. **Schema Authority & `schema.sql` Reconciliation:**
   - *Finding:* `DATABASE_SCHEMA.md` referenced `schema.sql`, which was not present in the repository root.
   - *Resolution:* Alembic migrations in `backend/migrations/` serve as the primary executable schema authority. In addition, a clean SQL snapshot reflecting the P0 foundational schema (`users`, `workspaces`, `papers`, indexes, triggers) is provided in `backend/schema_p0.sql` to eliminate any ambiguity.
2. **Week 5 Feature Pre-Planning (Experiments, Metrics, Report Jobs):**
   - *Finding:* Older documents tagged experiments and reports as P1, but `WEEKLY_BUILD_PLAN.md` schedules basic experiment extraction and DOCX report jobs for Week 5.
   - *Resolution:* The contracts for `experiments`, `experiment_metrics`, and `reports` are documented in this plan and reserved in the architectural design so future Alembic migrations append cleanly without foreign key conflicts. No premature table creation or fake mocks are implemented in Phase 1.
3. **Storage Directory Unification:**
   - *Finding:* References previously varied between `data/` and `storage/`.
   - *Resolution:* A single root-level `data/` convention is adopted: `data/pdfs/` for uploaded raw files, `data/indexes/` for FAISS/BM25 artifacts, `data/models/` for local cache, and `data/reports/` for generated exports. All storage paths are kept strictly private and outside `frontend/public`.
4. **Worker Boundary:**
   - *Finding:* BackgroundTasks in FastAPI were mentioned in early prototypes, which conflicts with persistent, restartable document processing required for Week 2.
   - *Resolution:* A dedicated `worker/` package boundary is established with shared database and core configuration models, ensuring Week 2 can implement a standalone persistent worker without architectural rewrites.
5. **Readiness vs. Uploaded Status:**
   - *Finding:* Documents must not be marked `ready` upon upload.
   - *Resolution:* Paper statuses follow `uploaded -> processing -> ready | failed`. Phase 1 establishes this lifecycle and validates that search/assistant will only ever query papers with `status = 'ready'`.
6. **Local Identity & Authentication:**
   - *Finding:* Phase 1 is a single-user local application.
   - *Resolution:* Authentication is bypassed via a local identity dependency yielding a seeded default user (`local@researchmind.ai`). If `AUTH_ENABLED=true` is configured without JWT tokens implemented, the system explicitly returns `501 Not Implemented` with an error envelope rather than silently downgrading security.

---

## 3. Directory Layout & Package Boundaries

```
ResearchMind AI/
├── .gitignore
├── README.md
├── docs/
│   ├── PHASE_1_PLAN.md
│   └── PHASE_1_VERIFICATION.md
├── data/                  # Private storage (excluded from git)
│   ├── pdfs/
│   ├── indexes/
│   ├── models/
│   └── reports/
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── schema_p0.sql
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── system.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── errors.py
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── session.py
│   │       ├── bootstrap.py
│   │       └── models.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial_core_schema.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── app/
│       │   ├── App.tsx
│       │   └── routes.tsx
│       ├── api/
│       │   ├── client.ts
│       │   └── types.ts
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppShell.tsx
│       │   │   ├── Sidebar.tsx
│       │   │   ├── Topbar.tsx
│       │   │   └── MobileNav.tsx
│       │   └── ui/
│       │       ├── Button.tsx
│       │       ├── Badge.tsx
│       │       ├── Card.tsx
│       │       └── StatusPill.tsx
│       ├── pages/
│       │   ├── LandingPage.tsx
│       │   ├── DashboardPage.tsx
│       │   ├── LibraryPage.tsx
│       │   └── NotFoundPage.tsx
│       ├── styles/
│       │   ├── tokens.css
│       │   ├── globals.css
│       │   └── components.css
│       └── types/
│           └── index.ts
├── worker/
│   └── README.md
├── scripts/
│   ├── setup_dev.ps1
│   ├── start_backend.ps1
│   ├── start_frontend.ps1
│   └── ml_smoke_check.py
└── tests/
    ├── backend/
    │   ├── conftest.py
    │   ├── test_config.py
    │   ├── test_database.py
    │   ├── test_bootstrap.py
    │   └── test_system_api.py
    └── frontend/
        └── smoke.test.ts
```

---

## 4. Database Contracts & Relational Models (P0)

### 4.1 Implemented Tables
- **`users`**
  - `id`: TEXT (UUID4 primary key)
  - `email`: TEXT UNIQUE NOT NULL (NOCASE)
  - `password_hash`: TEXT NOT NULL
  - `display_name`: TEXT NULL
  - `created_at`: TEXT NOT NULL (ISO-8601 UTC)
- **`workspaces`**
  - `id`: TEXT (UUID4 primary key)
  - `user_id`: TEXT NOT NULL, FK -> `users.id` ON DELETE CASCADE
  - `name`: TEXT NOT NULL
  - `description`: TEXT NULL
  - `created_at`: TEXT NOT NULL (ISO-8601 UTC)
  - *Constraints:* UNIQUE(`user_id`, `name`), Index on `user_id`
- **`papers`**
  - `id`: TEXT (UUID4 primary key)
  - `workspace_id`: TEXT NOT NULL, FK -> `workspaces.id` ON DELETE CASCADE
  - `original_filename`: TEXT NOT NULL
  - `storage_path`: TEXT NOT NULL
  - `sha256`: TEXT NOT NULL
  - `size_bytes`: INTEGER NOT NULL (> 0)
  - `page_count`: INTEGER NULL
  - `title`: TEXT NULL
  - `authors_json`: TEXT NULL (JSON array of strings)
  - `publication_year`: INTEGER NULL
  - `keywords_json`: TEXT NULL (JSON array of strings)
  - `metadata_source_json`: TEXT NULL (JSON dictionary)
  - `status`: TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'ready', 'failed'))
  - `quality_json`: TEXT NULL (JSON summary)
  - `created_at`: TEXT NOT NULL (ISO-8601 UTC)
  - `updated_at`: TEXT NOT NULL (ISO-8601 UTC)
  - *Constraints:* UNIQUE(`workspace_id`, `sha256`), Index on (`workspace_id`, `status`)

### 4.2 SQLite Pragmas
- `PRAGMA foreign_keys = ON;`
- `PRAGMA journal_mode = WAL;`
- `PRAGMA busy_timeout = 5000;`

### 4.3 Reserved Future Schemas (Week 5 Contracts)
- `experiments`: `(id PK, paper_id FK -> papers CASCADE, name, description, baseline_name, dataset_name, sample_size, created_at)`
- `experiment_metrics`: `(id PK, experiment_id FK -> experiments CASCADE, metric_name, metric_value, unit, confidence_interval, created_at)`
- `reports`: `(id PK, workspace_id FK -> workspaces CASCADE, title, status, report_type, file_path, created_at)`

---

## 5. Backend Foundation & API Contracts

### 5.1 Base Path & Headers
- Prefix: `/api`
- Request correlation: `X-Request-ID` attached to all requests and responses.

### 5.2 Standard Error Envelope (API_SPEC.md §2.2)
```json
{
  "error": {
    "code": "STRING_ENUM",
    "message": "Human readable explanation",
    "details": {},
    "request_id": "req_uuid"
  }
}
```

### 5.3 System Endpoints
1. `GET /api/health`
   - Returns `{ "status": "ok" }`
2. `GET /api/ready`
   - Returns `{ "status": "ready" | "degraded", "database": "connected", "storage": "writable", "ml_ready": boolean, "generator": { "provider": "...", "configured": boolean } }`
3. `GET /api/config/public`
   - Returns `{ "max_upload_mb": 25, "auth_enabled": false, "environment": "development", "api_version": "0.1.0" }`

---

## 6. Frontend & Design System Integration (DESIGN.md)

### 6.1 Theme & Tokens
- **Palette:** `--canvas: #F5F5F7`, `--ink: #1D1D1F`, `--gray-400: #AAAAAA`, `--blue: #007AFF`, `--blue-action: #0071E3`, `--blue-text: #0066CC`
- **Elevation:** Soft-raised dual shadows with top-left light source:
  - `--raise-1: -3px -3px 8px rgba(255,255,255,0.95), 3px 3px 10px rgba(174,174,192,0.32);`
  - `--raise-2: -6px -6px 16px rgba(255,255,255,0.95), 8px 8px 20px rgba(174,174,192,0.32);`
  - `--inset-1: inset 2px 2px 5px rgba(174,174,192,0.32), inset -2px -2px 5px rgba(255,255,255,0.95);`
- **Shapes:** Capsule pills (`border-radius: 999px`) for interactive buttons, chips, badges.
- **Typography:** System Apple font stack with tabular figures for numbers.

### 6.2 Routes & Components
- `/` -> Minimal Product Landing Page (clean Apple-style hero, declarative benefit, "Open Workspace" entry point).
- `/dashboard` -> Main Workspace Shell (honest metrics: 0 papers uploaded, quick actions, setup guidance).
- `/library` -> Library Shell (empty state explaining Phase 2 upload lifecycle).
- `*` -> 404 Route with clear recovery navigation.

---

## 7. Task Checklist & Verification Strategy

- [x] Create project directories and `.gitignore`.
- [x] Configure Python backend with dependencies, SQLite session, Alembic migrations, and P0 models.
- [x] Implement default local-user bootstrap and local user dependency.
- [x] Implement API routers, request ID middleware, centralized error handling, and health/ready endpoints.
- [x] Configure React/TypeScript/Vite frontend with DESIGN.md tokens and accessible components.
- [x] Implement Landing, Dashboard, Library, and 404 views with typed API integration.
- [x] Create ML smoke check script (`scripts/ml_smoke_check.py`) testing PyTorch, MiniLM, and FAISS.
- [x] Write backend unit & integration tests covering config, migrations, bootstrap, constraints, schema drift, and error envelopes.
- [x] Add frontend automated test suites (Vitest), linters (ESLint, Ruff), and formatters (Prettier, Ruff format).
- [x] Complete code review remediation for all 7 defect areas (models registered in env.py, table check constraints, isolated test environments, anchored scripts, accessible modal focus traps, truthful status reporting).
- [x] Verify clean completion evidence in `docs/PHASE_1_VERIFICATION.md`.
