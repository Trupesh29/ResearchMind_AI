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
    quality_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT fk_papers_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT uq_papers_workspace_sha256 UNIQUE (workspace_id, sha256)
);

CREATE INDEX IF NOT EXISTS idx_papers_workspace ON papers(workspace_id);
CREATE INDEX IF NOT EXISTS idx_papers_workspace_status ON papers(workspace_id, status);
