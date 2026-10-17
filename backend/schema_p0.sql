-- ==============================================================================
-- ResearchMind AI — Phase 1 Schema Snapshot (P0 Foundational Tables)
-- Executable Authority: Alembic migrations located in backend/migrations/
-- ==============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- 1. Users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. Workspaces
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    CONSTRAINT fk_workspaces_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_workspaces_user_name UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_user ON workspaces(user_id);

-- 3. Papers
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
    page_count INTEGER CHECK (page_count IS NULL OR page_count > 0),
    title TEXT,
    authors_json TEXT,
    publication_year INTEGER CHECK (publication_year IS NULL OR (publication_year >= 1900 AND publication_year <= 2100)),
    keywords_json TEXT,
    metadata_source_json TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'ready', 'failed')),
    current_run_id TEXT,
    published_run_id TEXT,
    quality_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT fk_papers_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT uq_papers_workspace_sha256 UNIQUE (workspace_id, sha256)
);

CREATE INDEX IF NOT EXISTS idx_papers_workspace ON papers(workspace_id);
CREATE INDEX IF NOT EXISTS idx_papers_workspace_status ON papers(workspace_id, status);

-- 4. Pages (Phase 3)
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number >= 1),
    char_count INTEGER NOT NULL DEFAULT 0 CHECK (char_count >= 0),
    width REAL,
    height REAL,
    rotation INTEGER,
    extraction_status TEXT NOT NULL DEFAULT 'ok' CHECK (extraction_status IN ('ok', 'partial', 'failed')),
    flags_json TEXT NOT NULL DEFAULT '[]',
    raw_text TEXT,
    blocks_json TEXT,
    created_at TEXT NOT NULL,
    CONSTRAINT fk_pages_paper FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    CONSTRAINT uq_pages_paper_run_page UNIQUE (paper_id, run_id, page_number)
);

CREATE INDEX IF NOT EXISTS ix_pages_paper_id ON pages(paper_id);
CREATE INDEX IF NOT EXISTS ix_pages_run_id ON pages(run_id);

-- 5. Processing Jobs (Phase 3)
CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('validating', 'extracting', 'sectioning', 'chunking', 'embedding', 'indexing', 'ready')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    worker_id TEXT,
    claim_token TEXT,
    claimed_at TEXT,
    heartbeat_at TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    versions_json TEXT,
    created_at TEXT NOT NULL,
    CONSTRAINT fk_jobs_paper FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_processing_jobs_paper_id ON processing_jobs(paper_id);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_run_id ON processing_jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_paper_run ON processing_jobs(paper_id, run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_stage ON processing_jobs(status, stage);
CREATE INDEX IF NOT EXISTS idx_jobs_heartbeat ON processing_jobs(status, heartbeat_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_job_per_paper ON processing_jobs(paper_id) WHERE status IN ('queued', 'running');
