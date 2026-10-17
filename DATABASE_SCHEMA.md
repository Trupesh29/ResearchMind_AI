# DATABASE_SCHEMA.md — ResearchMind AI

**Tables, Relationships, Constraints & ER Diagram**
Derived from TRD v0.1 §5 and the executable `schema.sql` · ORM: SQLAlchemy 2.0 + Alembic · DB: SQLite (dev/MVP) / PostgreSQL (later)

---

## 1. Scope & Source of Truth

This document describes the **relational schema** defined in `schema.sql` (23 tables, 3 views). `schema.sql` is the executable definition; this file explains it. If they ever disagree, fix whichever is wrong and keep both in sync.

Large or variable-shape data (extraction quality, block coordinates, model metrics, comparison matrices, evaluation configs) is serialized to JSON and stored in `TEXT` columns. §5 documents the internal shape of every JSON blob, since that structure is invisible in an ER diagram.

Binary and index artifacts live on the filesystem, not in the database: original PDFs, FAISS index files, BM25 index files, model weights, and exported reports. Tables store only the `*_path` string. See §7 for the path convention.

**Priority tags:** **[P0]** MVP · **[P1]** after MVP · **[P2]** advanced. Create the P0 tables first; the rest can be added by later migrations without changing existing tables.

---

## 2. Entity-Relationship Diagram

### 2.1 Core (P0): ownership, papers, retrieval, answers

```
┌─────────────────────┐
│       users          │
├─────────────────────┤
│ PK id         TEXT   │
│    email      UQ     │
│    password_hash     │
│    display_name      │
│    created_at        │
└──────────┬──────────┘
           │ 1
           │ owns (N)
           ▼
┌─────────────────────┐
│     workspaces       │
├─────────────────────┤
│ PK id                │
│ FK user_id → users   │
│    name   UQ(user,name)│
│    description       │
│    created_at        │
└───┬────────┬────────┬────────────────────┐
    │ 1      │ 1      │ 1                  │ 1
    │        │        │                    │
    ▼ N      ▼ N      ▼ N                  ▼ N
┌─────────┐ ┌────────────────┐ ┌──────────────┐ (see 2.2)
│ papers  │ │embedding_indexes│ │conversations │ comparisons,
├─────────┤ ├────────────────┤ ├──────────────┤ graph_*, reports,
│PK id    │ │PK id            │ │PK id         │ eval_*, research_gaps
│FK workspace_id│FK workspace_id│ │FK workspace_id│
│ sha256  │ │ version         │ │ title        │
│ status  │ │ model_name      │ └──────┬───────┘
│ title.. │ │ dimension       │        │ 1
└─┬──┬──┬─┘ │ chunk_params_json│       │ N
  │  │  │   │ status          │        ▼
  │  │  │   └───────┬────────┘ ┌──────────────┐     ┌─────────────────┐
  │  │  │           │ 1        │   messages    │ N:M │ message_papers  │
  │  │  │           │ N        ├──────────────┤◄───►├─────────────────┤
  │  │  │           ▼          │PK id          │     │PK(message_id,   │
  │  │  │      ┌──────────┐    │FK conversation_id│  │   paper_id)     │
  │  │  └─────►│  chunks  │    │ role, mode    │     └─────────────────┘
  │  │    1:N  ├──────────┤    │ content       │
  │  │         │PK id      │    │ abstained     │
  │  │         │FK paper_id│    └──────┬───────┘
  │  │         │FK embedding_index_id│ │ 1
  │  │         │ page_start/end │      │ N
  │  │         │ section, text  │      ▼
  │  │         │ faiss_id       │ ┌──────────────┐
  │  │         │ is_deleted     │◄┤  citations    │ chunk_id → chunks (SET NULL)
  │  │         └──────────┘      ├──────────────┤ paper_id → papers
  │  │                           │PK id          │
  │  │ 1:N                       │ page_number   │
  │  ▼                           │ excerpt       │
  │ ┌──────────┐                 │ supported     │
  │ │  pages   │                 └──────────────┘
  │ ├──────────┤
  │ │PK id      │
  │ │FK paper_id│
  │ │ page_number│ UQ(paper_id, page_number)
  │ │ flags_json │
  │ └──────────┘
  │ 1:N
  ▼
┌──────────────────┐
│ processing_jobs   │
├──────────────────┤
│PK id              │
│FK paper_id        │
│ stage, status     │
│ attempt, error    │
└──────────────────┘
```

### 2.2 Analysis, evaluation, and Model Lab

```
papers ──1:N──► summaries            (cache key: paper, type, index, prompt, model)  [P0 basic]
papers ──1:N──► experiments ──1:N──► experiment_metrics                              [P1]
papers ──N:M──► comparisons          (via comparison_papers)                         [P0]
workspaces ──1:N──► graph_nodes ──N:M──► graph_nodes (via graph_edges)               [P2]
workspaces ──1:N──► research_gaps                                                    [P2]
workspaces ──1:N──► eval_questions, eval_runs                                        [P1]
workspaces ──1:N──► reports                                                          [P1]
model_runs   (standalone: global experiment log, no workspace FK)                    [P0]
```

### 2.3 Cardinality summary

| Relationship | Cardinality | FK owner | On delete |
|---|---|---|---|
| `users` → `workspaces` | 1 : N | `workspaces.user_id` | `CASCADE` |
| `workspaces` → `papers` | 1 : N | `papers.workspace_id` | `CASCADE` |
| `workspaces` → `embedding_indexes` | 1 : N (1 active) | `embedding_indexes.workspace_id` | `CASCADE` |
| `papers` → `pages` | 1 : N | `pages.paper_id` | `CASCADE` |
| `papers` → `chunks` | 1 : N | `chunks.paper_id` | `CASCADE` |
| `embedding_indexes` → `chunks` | 1 : N | `chunks.embedding_index_id` | `CASCADE` |
| `papers` → `processing_jobs` | 1 : N | `processing_jobs.paper_id` | `CASCADE` |
| `workspaces` → `conversations` | 1 : N | `conversations.workspace_id` | `CASCADE` |
| `conversations` → `messages` | 1 : N | `messages.conversation_id` | `CASCADE` |
| `messages` ↔ `papers` | N : M | `message_papers` | `CASCADE` both sides |
| `messages` → `citations` | 1 : N | `citations.message_id` | `CASCADE` |
| `chunks` → `citations` | 1 : N | `citations.chunk_id` | `SET NULL` |
| `papers` → `citations` | 1 : N | `citations.paper_id` | `CASCADE` |
| `papers` → `summaries` | 1 : N | `summaries.paper_id` | `CASCADE` |
| `papers` → `experiments` | 1 : N | `experiments.paper_id` | `CASCADE` |
| `experiments` → `experiment_metrics` | 1 : N | `experiment_metrics.experiment_id` | `CASCADE` |
| `comparisons` ↔ `papers` | N : M | `comparison_papers` | `CASCADE` both sides |
| `graph_nodes` ↔ `graph_nodes` | N : M | `graph_edges` | `CASCADE` |

---

## 3. Table Definitions

### 3.1 `users` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | UUID string generated by the app |
| `email` | `TEXT` | `NOT NULL`, `UNIQUE`, `NOCASE` | Login identifier; case-insensitive |
| `password_hash` | `TEXT` | `NOT NULL` | Argon2 or bcrypt hash, never plaintext |
| `display_name` | `TEXT` | nullable | |
| `created_at` | `TEXT` | default current UTC | ISO-8601 |

**Indexes:** the unique constraint on `email` is the lookup path for login.

For a single-user local MVP, create one default user row and skip the login flow; the schema does not change when auth is added later.

### 3.2 `workspaces` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `user_id` | `TEXT` | `NOT NULL`, `FK → users.id` `CASCADE` | Ownership boundary |
| `name` | `TEXT` | `NOT NULL` | |
| `description` | `TEXT` | nullable | |
| `created_at` | `TEXT` | default current UTC | |

**Constraints:** `UNIQUE (user_id, name)`. **Index:** `idx_workspaces_user(user_id)`.

### 3.3 `papers` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `workspace_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `original_filename` | `TEXT` | `NOT NULL` | Display only; never used to build a path |
| `storage_path` | `TEXT` | `NOT NULL` | Server-generated path, see §7 |
| `sha256` | `TEXT` | `NOT NULL` | File hash for duplicate detection |
| `size_bytes` | `INTEGER` | `NOT NULL`, `> 0` | |
| `page_count` | `INTEGER` | `> 0` if set | |
| `title` | `TEXT` | nullable | Extracted or inferred |
| `authors_json` | `TEXT` | valid JSON or NULL | List of author names |
| `publication_year` | `INTEGER` | 1900–2100 if set | |
| `keywords_json` | `TEXT` | valid JSON or NULL | |
| `metadata_source_json` | `TEXT` | valid JSON or NULL | Per field: source + evidence dictionary — see §5.1 |
| `status` | `TEXT` | `uploaded` \| `processing` \| `ready` \| `failed` | Default `uploaded` |
| `current_run_id` | `TEXT` | nullable | Active processing generation run ID |
| `published_run_id` | `TEXT` | nullable | Ingestion generation run ID whose pages/metadata are active |
| `quality_json` | `TEXT` | valid JSON or NULL | Extraction quality summary — see §5.1 |
| `created_at`, `updated_at` | `TEXT` | default current UTC | `updated_at` maintained by trigger |

**Constraints:** `UNIQUE (workspace_id, sha256)` — the database itself rejects a duplicate upload to the same workspace.
**Index:** `idx_papers_workspace_status(workspace_id, status)`.

**Status lifecycle:** `uploaded → processing → ready`, or `processing → failed`. A failed paper can be reprocessed; the original PDF is untouched. The paper becomes searchable only when `status = 'ready'`.

### 3.4 `pages` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | UUID string |
| `paper_id` | `TEXT` | `NOT NULL`, `FK → papers.id` `CASCADE` | Indexed |
| `run_id` | `TEXT` | `NOT NULL` | Ingestion generation run UUID |
| `page_number` | `INTEGER` | `NOT NULL`, `>= 1` | 1-based, matches the PDF viewer |
| `char_count` | `INTEGER` | `NOT NULL`, default 0 | Very low counts help detect scans |
| `width` | `REAL` | nullable | Visual page width in PDF points |
| `height` | `REAL` | nullable | Visual page height in PDF points |
| `rotation` | `INTEGER` | nullable | Visual rotation in degrees (0, 90, 180, 270) |
| `extraction_status` | `TEXT` | `ok` \| `partial` \| `failed` | Default `ok` |
| `flags_json` | `TEXT` | `NOT NULL`, valid JSON, default `[]` | e.g. `possible_scan`, `table_unreliable`, `equations_may_be_missing` |
| `raw_text` | `TEXT` | nullable | Extracted textual content of the page |
| `blocks_json` | `TEXT` | valid JSON or NULL | Block coordinates and bounding boxes in visual page frame — see §5.2 |
| `created_at` | `TEXT` | `NOT NULL`, default current UTC | |

**Constraints:** `UNIQUE (paper_id, run_id, page_number)`, `CHECK (page_number >= 1)`, `CHECK (char_count >= 0)`, `CHECK (extraction_status IN ('ok', 'partial', 'failed'))`.
**Index:** `ix_pages_paper_id(paper_id)`, `ix_pages_run_id(run_id)`.

This table is what makes the Quality Center honest: a flagged page is recorded rather than silently treated as understood.

### 3.5 `embedding_indexes` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `workspace_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `version` | `INTEGER` | `NOT NULL`, `>= 1` | |
| `model_name` | `TEXT` | `NOT NULL` | e.g. `all-MiniLM-L6-v2` |
| `dimension` | `INTEGER` | `NOT NULL`, `> 0` | e.g. 384 |
| `chunk_params_json` | `TEXT` | `NOT NULL`, valid JSON | Chunk size, overlap, tokenizer — see §5.3 |
| `faiss_path` | `TEXT` | nullable | |
| `bm25_path` | `TEXT` | nullable | |
| `status` | `TEXT` | `building` \| `active` \| `retired` \| `failed` | Default `building` |
| `created_at` | `TEXT` | default current UTC | |

**Constraints:** `UNIQUE (workspace_id, version)`; a **partial unique index** `uq_embedding_active_per_workspace` allows at most one `active` index per workspace.

**Design note:** Changing the embedding model or chunk parameters creates a **new version** rather than editing the old one. Vectors from different models are never mixed in one index. Once the new version is `active`, the old one becomes `retired` and can be deleted.

### 3.6 `chunks` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `paper_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `embedding_index_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | Chunks belong to one index version |
| `chunk_index` | `INTEGER` | `NOT NULL`, `>= 0` | Order within the paper |
| `page_start`, `page_end` | `INTEGER` | `>= 1`, `page_end >= page_start` | Source location for citations |
| `section` | `TEXT` | `NOT NULL`, default `unknown` | `abstract`, `introduction`, `methodology`, `results`, `references`, … |
| `text` | `TEXT` | `NOT NULL` | |
| `token_count` | `INTEGER` | `NOT NULL`, `> 0` | Counted with the embedder's own tokenizer |
| `faiss_id` | `INTEGER` | nullable | Vector id inside the FAISS index |
| `is_deleted` | `INTEGER` | 0/1, default 0 | Tombstone until the index is rebuilt |
| `created_at` | `TEXT` | default current UTC | |

**Constraints:** `UNIQUE (embedding_index_id, paper_id, chunk_index)`; `UNIQUE (embedding_index_id, faiss_id)`.
**Indexes:** `idx_chunks_paper(paper_id, page_start)`, `idx_chunks_section(paper_id, section)`.

**Retrieval path:** FAISS returns `faiss_id` values; the app maps them to `chunks` rows within the active index, filters out tombstoned rows, and reads `text`, pages, and section for context building and citations. The view `v_active_chunks` encodes that filter.

### 3.7 `processing_jobs` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | UUID string |
| `paper_id` | `TEXT` | `NOT NULL`, `FK → papers.id` `CASCADE` | Indexed |
| `run_id` | `TEXT` | `NOT NULL` | Generation run UUID |
| `stage` | `TEXT` | `validating` \| `extracting` \| `sectioning` \| `chunking` \| `embedding` \| `indexing` \| `ready` | Pipeline stage |
| `status` | `TEXT` | `queued` \| `running` \| `succeeded` \| `failed` | Default `queued` |
| `attempt` | `INTEGER` | `>= 1`, default 1 | Retries increment this |
| `worker_id` | `TEXT` | nullable | Claiming worker process identifier |
| `claim_token` | `TEXT` | nullable | Fencing token to prevent stale workers from publishing |
| `claimed_at` | `TEXT` | nullable | ISO-8601 timestamp of worker claim |
| `heartbeat_at` | `TEXT` | nullable | ISO-8601 timestamp for worker lease renewal |
| `error_message` | `TEXT` | nullable | Shown in the Quality Center |
| `started_at` | `TEXT` | nullable | ISO-8601 timestamp when job execution began |
| `finished_at` | `TEXT` | nullable | ISO-8601 timestamp when job finished |
| `versions_json` | `TEXT` | valid JSON or NULL | Extractor and model versions used — see §5.3 |
| `created_at` | `TEXT` | `NOT NULL`, default current UTC | |

**Constraints:** `CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))`, `CHECK (stage IN ('validating', 'extracting', 'sectioning', 'chunking', 'embedding', 'indexing', 'ready'))`, `CHECK (attempt >= 1)`, partial unique index `uq_active_job_per_paper` on `(paper_id) WHERE status IN ('queued', 'running')`.
**Indexes:** `ix_processing_jobs_paper_id(paper_id)`, `ix_processing_jobs_run_id(run_id)`, `idx_jobs_paper_run(paper_id, run_id)`, `idx_jobs_status_stage(status, stage)`, `idx_jobs_heartbeat(status, heartbeat_at)`, `uq_active_job_per_paper`.

One row per stage per attempt gives the processing history the Quality Center displays and lets a failed run resume from the failing stage. Heartbeats and claim tokens ensure robust distributed lease fencing on SQLite.

### 3.8 `conversations`, `messages`, `message_papers` [P0]

**`conversations`**

| Column | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` |
| `workspace_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` |
| `title` | `TEXT` | nullable |
| `created_at` | `TEXT` | default current UTC |

**`messages`**

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `conversation_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `role` | `TEXT` | `user` \| `assistant` | |
| `mode` | `TEXT` | `paper_only` \| `multi_paper` \| `simple` \| `general` | Answer mode used |
| `content` | `TEXT` | `NOT NULL` | |
| `standalone_query` | `TEXT` | nullable | Rewritten follow-up query, for debugging |
| `abstained` | `INTEGER` | 0/1, default 0 | Evidence was insufficient |
| `uncertainties_json` | `TEXT` | valid JSON or NULL | List of uncertainty notices |
| `timings_json` | `TEXT` | valid JSON or NULL | Per-stage latency — see §5.4 |
| `created_at` | `TEXT` | default current UTC | |

**`message_papers`** — composite `PRIMARY KEY (message_id, paper_id)`, both `FK` `CASCADE`. Records which papers were selected for a question.

**Indexes:** `idx_conversations_workspace(workspace_id, created_at)`, `idx_messages_conversation(conversation_id, created_at)`.

### 3.9 `citations` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `message_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `paper_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `chunk_id` | `TEXT` | `FK → chunks.id` `SET NULL` | May become NULL after reindexing |
| `page_number` | `INTEGER` | `NOT NULL`, `>= 1` | |
| `excerpt` | `TEXT` | `NOT NULL` | Stored copy of the supporting text |
| `claim_text` | `TEXT` | nullable | The claim this source supports |
| `supported` | `INTEGER` | 0/1, default 0 | Passed verification |
| `score` | `REAL` | nullable | Retrieval or entailment score |
| `created_at` | `TEXT` | default current UTC | |

**Indexes:** `idx_citations_message(message_id)`, `idx_citations_paper(paper_id, page_number)`.

**Design note:** A citation stores its own `excerpt` and `page_number`. If chunks are rebuilt under a new index version, `chunk_id` becomes NULL but old answers still show their evidence and the PDF viewer can still jump to the page.

### 3.10 `summaries` [P0 basic]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `paper_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `summary_type` | `TEXT` | `simple` \| `technical` \| `methodology` \| `results` \| `critical` | |
| `content` | `TEXT` | `NOT NULL` | |
| `citations_json` | `TEXT` | valid JSON or NULL | |
| `embedding_index_id` | `TEXT` | `FK` `SET NULL` | |
| `prompt_version`, `model_name` | `TEXT` | `NOT NULL` | |
| `created_at` | `TEXT` | default current UTC | |

**Constraints:** `UNIQUE (paper_id, summary_type, embedding_index_id, prompt_version, model_name)`. This is the **cache key**: change the index, prompt, or model and the summary is regenerated instead of reused.

### 3.11 `comparisons`, `comparison_papers` [P0 for two papers]

**`comparisons`:** `id`, `workspace_id` (`FK` `CASCADE`), `title`, `dimensions_json` (`NOT NULL`, valid JSON), `result_json` (`NOT NULL`, valid JSON — see §5.5), `created_at`.
**`comparison_papers`:** composite `PRIMARY KEY (comparison_id, paper_id)`, both `FK` `CASCADE`.

### 3.12 `experiments`, `experiment_metrics` [P1]

**`experiments`** — one row per experiment reported in a paper.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PK` | |
| `paper_id` | `TEXT NOT NULL FK CASCADE` | |
| `name`, `task`, `model`, `dataset` | `TEXT` | |
| `n_samples` | `INTEGER` | |
| `training_config_json` | `TEXT` (valid JSON) | |
| `hardware`, `evaluation_method`, `baseline`, `limitations` | `TEXT` | |
| `source_page` | `INTEGER` (`>= 1`) | |
| `source_section` | `TEXT` | |
| `source_chunk_id` | `TEXT FK SET NULL` | |
| `extraction_version` | `TEXT NOT NULL` | Extractor and prompt version |
| `created_at` | `TEXT` | |

**Indexes:** `idx_experiments_paper(paper_id)`, `idx_experiments_dataset(dataset)`.

**`experiment_metrics`** — one row per reported metric.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `experiment_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` | |
| `metric_name` | `TEXT` | `NOT NULL` | `accuracy`, `f1`, `latency_ms`, `bandwidth_gbps`, … |
| `value_numeric` | `REAL` | nullable | For sorting and charts |
| `value_text` | `TEXT` | nullable | The value exactly as written in the paper |
| `unit` | `TEXT` | nullable | |
| `verified` | `INTEGER` | 0/1, default 0 | Value found verbatim in the source chunk |
| `source_page` | `INTEGER` | `>= 1` if set | |
| `source_chunk_id` | `TEXT` | `FK` `SET NULL` | |

**Check:** `verified = 0 OR value_text IS NOT NULL` — a metric cannot be marked verified without the stored original text.
**Indexes:** `idx_metrics_experiment(experiment_id)`, `idx_metrics_name(metric_name)`.

**"Not Reported" rule:** A value the paper does not give is stored as NULL, never guessed. The view `v_experiment_results` shows it as the literal text `Not Reported`.

### 3.13 `graph_nodes`, `graph_edges`, `research_gaps` [P2]

**`graph_nodes`:** `id`, `workspace_id` (`FK` `CASCADE`), `node_type` (`paper` \| `author` \| `topic` \| `algorithm` \| `dataset` \| `experiment` \| `finding` \| `technology`), `label`, `paper_id` (`FK` `CASCADE`, nullable), `properties_json`. `UNIQUE (workspace_id, node_type, label)`.

**`graph_edges`:** `id`, `workspace_id`, `source_id` and `target_id` (`FK → graph_nodes` `CASCADE`), `relation` (`uses` \| `evaluates` \| `cites` \| `solves` \| `supports` \| `potentially_contradicts` \| `mentions`), `evidence_chunk_id` (`FK` `SET NULL`), `confidence` (0–1). **Check:** `source_id <> target_id`. **Indexes:** on `source_id` and `target_id`.

**`research_gaps`:** `id`, `workspace_id`, `gap_text` (`NOT NULL`), `research_question`, `reasoning`, `is_hypothesis` (**locked to 1** by a `CHECK`), `evidence_json` (`NOT NULL`, valid JSON), `created_at`.

**Design note:** `is_hypothesis = 1` is enforced by the database. A generated gap can never be stored as if it were a paper-supported finding, and a gap found in the uploaded corpus is not proof that nobody else has studied the topic.

### 3.14 `model_runs` [P0]

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | |
| `name` | `TEXT` | `NOT NULL` | |
| `task` | `TEXT` | `NOT NULL` | e.g. `citation_intent` |
| `base_model` | `TEXT` | `NOT NULL` | e.g. `distilbert-base-uncased` |
| `dataset` | `TEXT` | `NOT NULL` | e.g. `allenai/scicite` |
| `run_type` | `TEXT` | `fine_tuned` \| `baseline` | Default `fine_tuned` |
| `device` | `TEXT` | nullable | `cuda`, `mps`, `cpu` |
| `seed` | `INTEGER` | nullable | For reproducibility |
| `hyperparams_json` | `TEXT` | `NOT NULL`, valid JSON | See §5.6 |
| `metrics_json` | `TEXT` | valid JSON or NULL | See §5.6 |
| `artifact_path` | `TEXT` | nullable | Weights, tokenizer, config directory |
| `status` | `TEXT` | `running` \| `completed` \| `failed` | Default `running` |
| `started_at` | `TEXT` | default current UTC | |
| `finished_at` | `TEXT` | nullable | |

**Index:** `idx_model_runs_task(task, started_at)`.

`model_runs` has **no workspace or user FK** on purpose: a training run is a global experiment log, not user data. Baselines (majority class, TF-IDF + logistic regression) are stored in the same table with `run_type = 'baseline'`, so Model Lab can compare them to the fine-tuned model with one query.

### 3.15 `eval_questions`, `eval_runs` [P1]

**`eval_questions`:** `id`, `workspace_id` (`FK` `CASCADE`), `question` (`NOT NULL`), `answerable` (0/1, default 1; **0 marks an abstention test**), `gold_json` (see §5.7), `created_at`.
**`eval_runs`:** `id`, `workspace_id`, `config_json` (`NOT NULL`), `metrics_json`, `n_questions`, `created_at`.

### 3.16 `reports` [P1]

| Column | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` |
| `workspace_id` | `TEXT` | `NOT NULL`, `FK` `CASCADE` |
| `report_type` | `TEXT` | `paper_summary` \| `literature_review` \| `experiment_evidence` \| `research_gaps` \| `technical_analysis` \| `model_evaluation` |
| `params_json` | `TEXT` | valid JSON or NULL |
| `format` | `TEXT` | `pdf` \| `docx` \| `csv` |
| `file_path` | `TEXT` | nullable |
| `status` | `TEXT` | `pending` \| `ready` \| `failed` (default `pending`) |
| `created_at` | `TEXT` | default current UTC |

**Index:** `idx_reports_workspace(workspace_id, created_at)`.

---

## 4. Views and Triggers

| Object | Purpose |
|---|---|
| `v_active_chunks` | Chunks that are searchable now: index `status = 'active'` and `is_deleted = 0` |
| `v_citation_details` | Citations joined with paper titles, for the evidence drawer and PDF viewer |
| `v_experiment_results` | Experiments joined with metrics; missing values shown as `Not Reported` |
| `trg_papers_updated` | Sets `papers.updated_at` on every update |

SQLite does not fire a trigger from its own update unless `recursive_triggers` is on (it is off by default), so `trg_papers_updated` does not loop. If you turn on recursive triggers, rewrite it.

---

## 5. JSON Blob Schemas (the "invisible" part of the schema)

The database only checks that these columns contain **valid JSON** (`json_valid`). Their internal shape is enforced by Pydantic models at the API boundary. Treat the examples below as the contract, and bump a version field if a shape ever changes.

### 5.1 `papers.quality_json`, `papers.metadata_source_json`

```json
// quality_json
{
  "readable_pages": 16,
  "flagged_pages": 2,
  "possible_scan_pages": [3],
  "table_unreliable_pages": [11, 12],
  "total_chars": 58210,
  "chunk_count": 214
}

// metadata_source_json: how each field was obtained
{ "title": "pdf", "authors": "pdf", "publication_year": "inferred", "keywords": "inferred" }
```

### 5.2 `pages.flags_json`, `pages.blocks_json`

```json
// flags_json
["table_unreliable", "equations_may_be_missing"]

// blocks_json: coordinates in PDF points (top-left origin), used to highlight cited passages
[
  {
    "id": "p1_b0",
    "bbox": [54.0, 72.0, 558.0, 114.5],
    "text": "Deep Learning for Scientific Document Processing",
    "block_type": "text"
  }
]
```

### 5.3 `embedding_indexes.chunk_params_json`, `processing_jobs.versions_json`

```json
// chunk_params_json
{
  "chunk_tokens": 200,
  "overlap_pct": 20,
  "tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
  "sentence_aware": true,
  "exclude_sections": ["references"]
}

// versions_json
{ "extractor": "pymupdf 1.24.x", "embedder": "all-MiniLM-L6-v2", "pipeline": "0.1.0" }
```

### 5.4 `messages.uncertainties_json`, `messages.timings_json`

```json
// uncertainties_json
["The paper does not report memory latency.", "Page 11 table could not be extracted reliably."]

// timings_json (milliseconds)
{ "rewrite": 0, "dense": 12, "bm25": 5, "rerank": 140, "generate": 1820, "verify": 260 }
```

### 5.5 `comparisons.dimensions_json`, `comparisons.result_json`

```json
// dimensions_json
["objective", "methodology", "dataset", "metrics", "results", "limitations"]

// result_json
{
  "papers": ["paper-id-1", "paper-id-2"],
  "cells": {
    "dataset": {
      "paper-id-1": { "text": "SciCite", "citation_ids": ["c1"] },
      "paper-id-2": { "text": "Not reported", "citation_ids": [] }
    }
  },
  "warnings": [
    { "dimension": "results", "type": "non_comparable",
      "reason": "Different datasets and hardware reported." }
  ]
}
```

### 5.6 `model_runs.hyperparams_json`, `model_runs.metrics_json`

```json
// hyperparams_json (DistilBERT / SciCite example)
{
  "max_seq_length": 128,
  "per_device_batch_size": 4,
  "gradient_accumulation_steps": 4,
  "learning_rate": 3e-5,
  "weight_decay": 0.01,
  "epochs": 3,
  "warmup_ratio": 0.06,
  "fp16": true
}

// metrics_json (shape only; values come from real runs)
{
  "accuracy": 0.0,
  "macro_f1": 0.0,
  "per_class": { "background": {"precision":0.0,"recall":0.0,"f1":0.0},
                 "method":     {"precision":0.0,"recall":0.0,"f1":0.0},
                 "result":     {"precision":0.0,"recall":0.0,"f1":0.0} },
  "confusion_matrix": [[0,0,0],[0,0,0],[0,0,0]],
  "loss_curve": { "train": [], "val": [] },
  "training_time_sec": 0.0,
  "inference_ms_per_example": 0.0,
  "misclassified_examples": []
}
```

The zeros are placeholders for shape only. Every number the app displays must come from a stored run.

### 5.7 `eval_questions.gold_json`, `eval_runs.config_json`, `eval_runs.metrics_json`

```json
// gold_json
[ { "paper_id": "…", "pages": [7, 8] } ]

// config_json
{ "retrieval": "hybrid", "reranker": true, "chunk_tokens": 200,
  "embedder": "all-MiniLM-L6-v2", "top_k": 6 }

// metrics_json
{ "recall_at_5": 0.0, "mrr": 0.0, "ndcg_at_10": 0.0,
  "latency_ms": { "p50": 0, "p95": 0 },
  "citation_correctness": 0.0, "faithfulness": 0.0, "abstention_accuracy": 0.0 }
```

---

## 6. What's *Not* in the Schema (Gaps & Recommendations)

| Missing | Impact | Recommendation |
|---|---|---|
| **No refresh-token / session table** | A single token cannot be revoked before it expires. | Add `refresh_tokens` (or a blocklist) when real auth is built. |
| **No annotations / notes table** | The PRD mentions user annotations; they cannot be saved yet. | Add `annotations(id, paper_id, page_number, bbox_json, note, created_at)` in a P1 migration. |
| **No audit or LLM-usage log** | You cannot track API cost per user or per query. | Add `llm_calls(id, message_id, provider, model, input_tokens, output_tokens, cost, created_at)` once a hosted LLM is chosen. |
| **No full-text index table** | BM25 lives in a file, outside transactional control. | Keep BM25 as a file for the MVP. Consider SQLite FTS5 or PostgreSQL full-text later so keyword search and deletes stay consistent with the database. |
| **No workspace sharing** | Everything is single-owner. | Add `workspace_members(workspace_id, user_id, role)` later. Existing tables are unaffected. |
| **Deleting a paper deletes its citations** | Old answers lose evidence from a deleted paper. | This is intentional (the source is gone). The UI should show "source removed" for answers whose citations disappeared. |
| **`updated_at` only on `papers`** | Other tables do not record changes. | Add it where needed through migrations. |
| **Vector data outside the database** | FAISS files can drift from `chunks` after crashes or deletes. | Run a consistency check job that compares `chunks.faiss_id` with the index size, and rebuild on mismatch. |
| **No migration history yet** | `schema.sql` is a one-time snapshot. | Make Alembic the source of truth from the first commit; keep `schema.sql` as a reference export. |

---

## 7. File Storage Path Convention (referenced by `*_path` columns)

Every `*_path` value is generated by the server, never accepted from client input. The user's filename is stored only as display text.

```
data/pdfs/{workspace_id}/{paper_id}.pdf                     → papers.storage_path
data/indexes/{workspace_id}/v{version}/faiss.index          → embedding_indexes.faiss_path
data/indexes/{workspace_id}/v{version}/bm25.pkl             → embedding_indexes.bm25_path
data/models/{run_id}/                                       → model_runs.artifact_path
data/reports/{workspace_id}/{report_id}.{pdf|docx|csv}      → reports.file_path
```

Because every path contains a `workspace_id` that resolves to a `user_id`, ownership is checked in the data layer before any path is built or any file is served.

---

## 8. Type Mapping: SQLite (dev) vs PostgreSQL (later)

| Schema type | SQLite | PostgreSQL | Notes |
|---|---|---|---|
| UUID `TEXT` ids | `TEXT` | `uuid` | Convert with a migration; keep app-generated UUIDs |
| `TEXT` JSON columns | `TEXT` + `json_valid` | `jsonb` | Drop `json_valid` checks; add GIN indexes only if you query inside the JSON |
| Timestamps (`TEXT`) | ISO-8601 text | `timestamptz` | Store UTC; avoid naive datetimes |
| 0/1 flags (`INTEGER`) | `INTEGER` | `boolean` | `abstained`, `supported`, `verified`, `is_deleted`, `answerable` |
| `COLLATE NOCASE` (email) | supported | not supported | Use `citext` or a unique index on `lower(email)` |
| Partial unique index | supported | supported | Works unchanged |
| `REAL` | `REAL` | `double precision` | |
| Triggers | SQL trigger | plpgsql function + trigger | Rewrite `trg_papers_updated` |
| Foreign keys | Off unless `PRAGMA foreign_keys = ON` | Always enforced | **Set the PRAGMA on every SQLite connection** |

**Migration risk:** SQLite's relaxed typing lets bad data slip through during development that PostgreSQL will reject. Run the test suite against a local PostgreSQL container well before deployment.

---

## 9. Query Patterns in Practice

| Use case | Query shape |
|---|---|
| List a workspace's papers | `SELECT * FROM papers WHERE workspace_id = :wid ORDER BY created_at DESC` (uses `idx_papers_workspace_status`) |
| Duplicate check on upload | `SELECT id FROM papers WHERE workspace_id = :wid AND sha256 = :hash` (unique index) |
| Resolve search hits to text | `SELECT * FROM v_active_chunks WHERE embedding_index_id = :iid AND faiss_id IN (:ids)` |
| Restrict search to selected papers | Add `AND paper_id IN (:paper_ids)` |
| Evidence for one answer | `SELECT * FROM v_citation_details WHERE message_id = :mid ORDER BY page_number` |
| Experiment table with gaps shown | `SELECT * FROM v_experiment_results WHERE paper_id IN (:ids)` |
| Compare baseline vs fine-tuned | `SELECT run_type, metrics_json FROM model_runs WHERE task = 'citation_intent' AND status = 'completed'` |
| Ownership check (any resource) | Resolve up to `workspaces.user_id = :current_user` — papers, chunks, citations, and everything else have no direct `user_id` |

On SQLite, reading a value inside a JSON column needs `json_extract()` or loading it in Python. On PostgreSQL, use `jsonb` operators (`->>`).

---

## 10. Summary Table

| Table | Rows represent | Depends on | Referenced by | Priority |
|---|---|---|---|---|
| `users` | An account | — | `workspaces` | P0 |
| `workspaces` | One research project | `users` | most tables | P0 |
| `papers` | One uploaded PDF and its metadata | `workspaces` | pages, chunks, jobs, citations, summaries, experiments, graph nodes | P0 |
| `pages` | One PDF page and its extraction flags | `papers` | — | P0 |
| `embedding_indexes` | One (model, chunking) index version | `workspaces` | `chunks`, `summaries` | P0 |
| `chunks` | One searchable passage with page range | `papers`, `embedding_indexes` | citations, experiments, graph edges | P0 |
| `processing_jobs` | One pipeline stage attempt | `papers` | — | P0 |
| `conversations` | A chat thread | `workspaces` | `messages` | P0 |
| `messages` | One user or assistant turn | `conversations` | citations, message_papers | P0 |
| `message_papers` | Papers selected for a message | `messages`, `papers` | — | P0 |
| `citations` | One piece of supporting evidence | `messages`, `papers`, `chunks` | — | P0 |
| `summaries` | A cached summary | `papers`, `embedding_indexes` | — | P0 |
| `comparisons` / `comparison_papers` | A saved comparison and its papers | `workspaces`, `papers` | — | P0 |
| `model_runs` | One training or baseline run | — | — | P0 |
| `experiments` / `experiment_metrics` | Extracted experiments and their metrics | `papers`, `chunks` | — | P1 |
| `eval_questions` / `eval_runs` | Labeled questions and evaluation results | `workspaces` | — | P1 |
| `reports` | One generated export | `workspaces` | — | P1 |
| `graph_nodes` / `graph_edges` | Knowledge-graph entities and relations | `workspaces`, `papers`, `chunks` | — | P2 |
| `research_gaps` | A generated gap hypothesis | `workspaces` | — | P2 |
