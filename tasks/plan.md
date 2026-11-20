# Week 3 implementation plan

Status: planned, not implemented.

The authoritative phase scope, decisions, dependencies, integration points, risks and acceptance gates are in [Week 3 phases](../docs/WEEK_3_PHASES.md). Execution tasks are in [todo.md](todo.md). This preserves the existing project phase-document convention.

Dependency order: accepted ingestion → index contract → embeddings → publication/lifecycle → filtered retrieval → fusion/inspection → evaluation/freeze → Week 4 handoff. Evaluation labeling and SciCite preparation can proceed independently; heavy compute runs should be scheduled separately.

Remaining implementation decisions: exact retrieval-only route, rebuild threshold, crash-recovery protocol, and calibration-derived numeric targets. Resolve and document these at their corresponding task before dependent implementation; none prevents this phase plan.
