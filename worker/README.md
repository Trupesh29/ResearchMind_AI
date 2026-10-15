# ResearchMind AI — Worker Boundary

This directory houses the entrypoint and task orchestration for background document processing jobs scheduled for **Week 2**.

## Architecture & Responsibilities (Week 2):
- **Job States:** `validating` → `extracting` → `sectioning` → `chunking` → `embedding` → `ready`
- **Recovery:** Polling SQLite for unprocessed/interrupted processing jobs on worker start.
- **Independence:** Decoupled from the synchronous FastAPI HTTP request lifecycle. Uses shared database models from `backend.app.db.models`.
- **No BackgroundTasks:** Not tied to the FastAPI web process lifespan to ensure resilience against server reloads.
