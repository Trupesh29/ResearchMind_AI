# ResearchMind AI — Standalone Processing Worker

This directory houses the standalone background document processing worker for ResearchMind AI.

## Architecture & Responsibilities (Phase 3)

The worker is decoupled from FastAPI's HTTP request lifecycle and executes as a separate, resilient local process.

### Processing Stages
- **Implemented in Phase 3:**
  1. `validating`: Checks physical PDF file presence, size match, `%PDF-` magic bytes, SHA-256 integrity, and document openability.
  2. `extracting`: Uses PyMuPDF to extract text, dimensions, rotation, bounding boxes, character counts, metadata provenance, and quality indicators.
- **Phase 3 Boundary:**
  - Processing stops after extraction. The paper remains in `status = "processing"` with stage `extracting` (progress 0.5) awaiting Phase 4 sectioning.
  - Phase 4 will implement `sectioning` and `chunking`.
  - Week 3 will implement `embedding`, `indexing`, and eventual `ready` transition.

### Concurrency, Fencing, and Leases
- **Short Transactions:** Workers claim a job, commit immediately, parse the PDF without holding database write locks, and publish results in a brief final transaction.
- **Claim Token Fencing:** Each atomic claim generates a unique UUID claim token. Publication strictly verifies that the job's `claim_token` still matches before writing pages or transitioning status. A slow worker whose lease expired cannot publish stale results.
- **Heartbeat & Lease Recovery:** Running jobs periodically update `heartbeat_at`. Any worker loop detects abandoned jobs whose heartbeat is older than `--lease-timeout` (default 30s) and automatically re-queues them (up to `--max-retries`, default 3) or transitions them to `failed`.
- **Deletion Safety:** Deleting a paper or workspace deletes associated `processing_jobs` via `ON DELETE CASCADE`. If a worker attempts to publish results for a deleted paper, the publication transaction cleanly aborts without creating orphaned pages or resurrecting the document.

---

## Worker Execution

Run the worker from the project root using the Python virtual environment:

### Continuous Polling Mode (Default)
```powershell
.venv\Scripts\python -m worker.main
```

### Options and Flags
- `--poll-interval <float>`: Queue polling interval in seconds (default: `1.0`).
- `--lease-timeout <int>`: Heartbeat expiration threshold in seconds (default: `30`).
- `--max-retries <int>`: Maximum retry attempts for failed/recovered stages (default: `3`).
- `--worker-id <str>`: Explicit worker instance name (defaults to `hostname-pid-uuid`).
- `--once`: Process a single available job pass and exit immediately (ideal for deterministic tests, CI, and batch runner orchestration).
- `-v, --verbose`: Enable detailed DEBUG logging.

### Example: Single Pass Execution
```powershell
.venv\Scripts\python -m worker.main --once
```

### Graceful Shutdown
The worker intercepts `SIGINT` (Ctrl+C) and `SIGTERM`. Upon receiving a termination signal, it requests a stop, finishes the current processing step, and exits cleanly.
