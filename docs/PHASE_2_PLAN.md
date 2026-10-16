# ResearchMind AI — Phase 2 Implementation Plan
## Workspace Management & PDF Research Library

**Date:** 2026-10-16  
**Scope:** Week 1 Phase 2 (Foundation & App Shell -> Workspaces & PDF Library)  
**Execution Context:** Local single-user release, SQLite, local `data/pdfs/` storage, zero hosted/paid LLM dependencies.

---

### 1. Scope Decisions & Boundary Definitions

1. **Phase 2 Status Model**:
   - In Week 1 Phase 2, uploaded PDFs transition to and remain at `status = 'uploaded'`.
   - We do **not** enqueue nonexistent Celery/worker jobs, simulate fake background progress to `'processing'` or `'ready'`, or fabricate mock chunking/embeddings.
   - The UI and API truthfully report `uploaded`. Document viewer and library operations work directly on `uploaded` papers.
2. **Batch Upload Contract (`POST /api/papers`)**:
   - Multipart form with `workspace_id` and one or more `files`.
   - Returns HTTP `202 Accepted` with tripartite arrays:
     - `papers`: accepted files, each with `id`, `original_filename`, `status = 'uploaded'`.
     - `duplicates`: duplicate SHA-256 in workspace, with `original_filename` and `existing_paper_id`.
     - `rejected`: invalid files, with `original_filename`, `code`, `message`.
   - All-duplicate or all-rejected batches still return `202 Accepted` with empty `papers`.
   - Request-level errors (missing workspace, foreign workspace, empty files list, whole-request limit exceeded) return standard 4xx error envelope with `request_id`.
3. **Database Schema Authority**:
   - The existing SQLite schema (`models.py`) already defines `User`, `Workspace`, and `Paper` with all required columns, constraints (`uq_workspaces_user_name`, `uq_papers_workspace_sha256`, `check_paper_status_valid`, `check_paper_size_bytes_positive`), and cascade relationships.
   - No schema migrations are required; Alembic drift check remains 0 diffs.
4. **Storage & Path Containment**:
   - Original PDFs are stored under `effective_settings.DATA_DIR / "pdfs" / f"{paper_id}.pdf"`.
   - Generated filenames prevent directory traversal, Windows/Unix path separators, and collision.
   - `storage_path` is an internal column and is **never** exposed in API responses or logs.
   - Temp files during upload are streamed in chunks and cleaned up immediately on validation failure or DB rollback.

---

### 2. Affected Files & Deliverables

| Area | File Path | Purpose |
|---|---|---|
| **Dependencies** | `backend/requirements.txt` | Pin `python-multipart==0.0.32` and `pymupdf==1.28.2`. |
| **Pydantic Schemas** | `backend/app/schemas/workspace.py` | Workspace request/response models with counts. |
| **Pydantic Schemas** | `backend/app/schemas/paper.py` | Paper responses, upload batch response, pagination models. |
| **Services** | `backend/app/services/workspace_service.py` | Workspace DB operations, ownership validation, cascade file removal. |
| **Services** | `backend/app/services/paper_service.py` | Byte streaming, SHA-256 calculation, PyMuPDF validation, file publication/cleanup, range streaming. |
| **API Endpoints** | `backend/app/api/workspaces.py` | CRUD endpoints for `/api/workspaces`. |
| **API Endpoints** | `backend/app/api/papers.py` | Endpoints for `/api/papers`, status, original file streaming (Range 200/206/416), deletion. |
| **API Router** | `backend/app/api/router.py` | Include workspace and paper routers under `/api`. |
| **Frontend API** | `frontend/src/api/client.ts` | Extend `request<T>` for FormData, 204 No Content, and workspace/paper API methods. |
| **Frontend Types** | `frontend/src/api/types.ts` | Type definitions for Workspace, Paper, and Batch upload responses. |
| **UI Components** | `frontend/src/components/workspace/WorkspaceSelector.tsx` | Dropdown for switching/creating/editing workspaces. |
| **UI Components** | `frontend/src/components/workspace/WorkspaceModal.tsx` | Accessible modal for creating and renaming workspaces. |
| **UI Components** | `frontend/src/components/library/UploadDropzone.tsx` | Drag-and-drop & file picker with multi-file feedback. |
| **UI Components** | `frontend/src/components/library/PaperList.tsx` | Paper table with search, status pills, view/delete actions. |
| **UI Components** | `frontend/src/components/library/PdfViewerModal.tsx` | Native browser PDF viewer with fallback download. |
| **UI Components** | `frontend/src/components/ui/ConfirmDialog.tsx` | Accessible confirmation dialog with focus trap. |
| **Pages** | `frontend/src/pages/LibraryPage.tsx` | Connect all components into complete library flow. |
| **Pages** | `frontend/src/pages/DashboardPage.tsx` | Display real workspace and document KPIs. |
| **Backend Tests** | `tests/backend/test_workspaces_api.py` | Workspaces CRUD, ownership, pagination, duplicate conflicts. |
| **Backend Tests** | `tests/backend/test_papers_api.py` | Upload validation, duplicate handling, range requests, storage isolation. |
| **Frontend Tests** | `frontend/src/test/library.test.tsx` | Vitest coverage for upload, search, viewer, and delete dialog. |
| **Browser Runner** | `scripts/run_browser_verification.py` | Verify Phase 2 workspace and library flows in Chrome. |
| **Documentation** | `docs/PHASE_2_VERIFICATION.md` | Verification evidence and requirements mapping. |

---

### 3. API Contract & Response Matrix

#### Workspaces
- `POST /api/workspaces` -> `201 Created` (`WorkspaceDetail`) | `400 INVALID_REQUEST` | `409 NAME_CONFLICT`
- `GET /api/workspaces` -> `200 OK` (`WorkspaceListResponse` with cursor)
- `GET /api/workspaces/{id}` -> `200 OK` (`WorkspaceDetail` with counts & active_index=null) | `404 NOT_FOUND`
- `PATCH /api/workspaces/{id}` -> `200 OK` (`WorkspaceDetail`) | `400 INVALID_REQUEST` | `404 NOT_FOUND` | `409 NAME_CONFLICT`
- `DELETE /api/workspaces/{id}` -> `204 No Content` | `404 NOT_FOUND`

#### Papers
- `POST /api/papers` -> `202 Accepted` (`PaperUploadBatchResponse` with `papers`, `duplicates`, `rejected`) | `400 INVALID_REQUEST` | `404 NOT_FOUND`
- `GET /api/papers?workspace_id=...&status=...&q=...&limit=...&cursor=...` -> `200 OK` (`PaperListResponse`) | `404 NOT_FOUND`
- `GET /api/papers/{id}` -> `200 OK` (`PaperResponse`) | `404 NOT_FOUND`
- `GET /api/papers/{id}/status` -> `200 OK` (`PaperStatusResponse`: status='uploaded', progress=0.0) | `404 NOT_FOUND`
- `GET /api/papers/{id}/file` -> `200 OK` or `206 Partial Content` (PDF binary stream) | `404 NOT_FOUND` | `416 Range Not Satisfiable`
- `DELETE /api/papers/{id}` -> `204 No Content` | `404 NOT_FOUND`

---

### 4. Implementation Steps

1. **Schemas & Services**:
   - Create `backend/app/schemas/workspace.py` and `backend/app/schemas/paper.py`.
   - Implement `backend/app/services/workspace_service.py` for workspace CRUD and ownership verification.
   - Implement `backend/app/services/paper_service.py` for PDF byte validation (`%PDF-`), streaming SHA-256 calculation, PyMuPDF inspection (encrypted, pages > 0), range streaming, and atomic publishing.
2. **API Routers**:
   - Implement `backend/app/api/workspaces.py` and `backend/app/api/papers.py`.
   - Connect to `backend/app/api/router.py`.
3. **Backend Tests**:
   - Write comprehensive tests in `tests/backend/test_workspaces_api.py` and `tests/backend/test_papers_api.py`.
   - Execute Pytest suite and verify all pass.
4. **Frontend API & Components**:
   - Update `client.ts` to support FormData and 204 No Content; add API methods.
   - Update `types.ts` with workspace and paper types.
   - Build accessible UI components: `WorkspaceSelector`, `WorkspaceModal`, `UploadDropzone`, `PaperList`, `PdfViewerModal`, `ConfirmDialog`.
   - Wire into `LibraryPage.tsx` and update `DashboardPage.tsx`.
5. **Frontend Tests & Production Build**:
   - Run Vitest tests (`npm test`).
   - Run lint, typecheck, format check, and production build.
6. **Live Browser Acceptance Verification**:
   - Extend `scripts/run_browser_verification.py` to test workspace creation, PDF upload, duplicate rejection, viewer opening, and deletion.
   - Execute verification suite via `scripts/run_browser_suite.ps1`.
7. **Documentation & Local Commit**:
   - Create `docs/PHASE_2_VERIFICATION.md`.
   - Update `decision.md` and `workflow.md`.
   - Commit locally on branch `manav` (no push).
