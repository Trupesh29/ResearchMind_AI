# ResearchMind AI — Standalone Processing Worker

This directory houses the standalone background document processing worker for ResearchMind AI.

## Architecture & Responsibilities (Phase 5)

The worker is decoupled from FastAPI's HTTP request lifecycle and executes as a separate, resilient local process.

### Processing Stages (Complete 6-Stage Pipeline)
1. `validating`: Checks physical PDF file presence, size match, `%PDF-` magic bytes, SHA-256 integrity, and document openability.
2. `extracting`: Uses PyMuPDF to extract text, dimensions, rotation, bounding boxes, character counts, metadata provenance, and quality indicators.
3. `sectioning`: Identifies structural sections, headers, and reference zones.
4. `chunking`: Chunks sections into token-bounded semantic units, excluding reference lists and tombstoned fragments.
5. `embedding`: Generates 384-dimensional dense vectors using local `all-MiniLM-L6-v2` with strict sequence limits (256 tokens max) and unit L2 normalization. Caches generation embeddings atomically.
6. `indexing`: Builds paired FAISS FlatIP and BM25 index artifacts in a per-workspace isolated staging directory, serializes publication per workspace, promotes to an immutable versioned directory (`v{version}`), atomically updates database pointers, and transitions the paper status to `ready`.

### Concurrency, Fencing, Leases, and Serialization
- **Short Transactions:** Workers claim a job, commit immediately, run long-running CPU/ML tasks without holding database write locks, and publish results in brief final transactions.
- **Claim Token Fencing:** Each atomic claim generates a unique UUID claim token. Publication strictly verifies that the job's `claim_token` still matches before transitioning status. A slow worker whose lease expired or was superseded cannot publish stale results.
- **Publication Slot Serialization:** Workspace index promotion acquires a cross-process publication slot (`acquire_workspace_publication_slot`) with thread synchronization and atomic directory locking (`.publication_slot`). Only one worker promotes and commits a workspace index version at a time.
- **Compare-And-Swap Version Protection:** Inside the publication slot, workers re-validate version freshness before moving staging artifacts into `v{version}`. If another worker published first, the staging directory is discarded and retried.
- **Heartbeat & Lease Recovery:** Running jobs periodically update `heartbeat_at`. Any worker loop detects abandoned jobs whose heartbeat is older than `--lease-timeout` (default 30s) and automatically re-queues them (up to `--max-retries`, default 3) or transitions them to `failed`.
- **Ownership-Safe Staging Cleanup:** Abandoned staging directories (`v{version}_prep_{build_id}.tmp`) are cleaned up safely using `staging_meta.json` TTL expiration, path-traversal prevention, and never touching active competing workers' staging directories.
- **Artifact Integrity & Fail-Closed Recovery:** Index artifacts (`index.faiss`, `bm25.json`, `manifest.json`) are validated with SHA-256 checksums and DB membership matching. Corrupted, modified, or mismatched artifacts fail closed immediately.
- **Deletion Safety:** Deleting a paper or workspace cascades cleanly. If a worker attempts to publish results for a deleted paper, the publication transaction cleanly aborts without creating orphaned records.

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
