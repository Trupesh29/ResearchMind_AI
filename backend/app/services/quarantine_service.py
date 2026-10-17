"""
Quarantine and Durable Storage Recovery Service for ResearchMind AI.

Manages physical document file lifecycle during deletions and rollbacks:
- Stages files into `.trash/` with durable metadata (`.meta.json`) before database commit.
- On commit success: bounds retry to purge quarantined files; on lock failure, preserves
  durable `committed_pending_purge` state for asynchronous or restart reconciliation.
- On commit rollback: attempts restoration; if restoration rename fails, preserves
  durable `rollback_pending_restoration` state, truthfully reports failure, and allows
  live records to serve bytes from quarantine fallback.
- Reconciles quarantine ledger on startup and on-demand, cleanly distinguishing live rows
  (restoration) from committed deletions (purge) while strictly preserving foreign/unrelated files.
"""

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.models import Paper

logger = logging.getLogger("researchmind.quarantine")


def _get_trash_dir(base_storage_dir: Path) -> Path:
    trash_dir = base_storage_dir / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    return trash_dir


def _save_meta(meta_path: Path, data: dict[str, Any]) -> None:
    temp_meta = meta_path.with_suffix(".tmp_meta")
    temp_meta.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_meta.replace(meta_path)


def _load_meta(meta_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to read quarantine metadata at {meta_path}: {exc}")
        return None


def stage_file_for_deletion(
    original_path: Path,
    entity_type: str,
    paper_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> tuple[Path, Path]:
    """
    Moves original_path into .trash with a unique quarantine ID and durable .meta.json ledger.
    Raises OSError if staging rename fails (leaving original_path untouched).
    """
    trash_dir = _get_trash_dir(original_path.parent)
    quarantine_id = f"del_{entity_type}_{paper_id}_{uuid.uuid4().hex[:8]}"
    staged_path = trash_dir / f"{quarantine_id}.tmp"
    meta_path = trash_dir / f"{quarantine_id}.meta.json"

    meta_data = {
        "quarantine_id": quarantine_id,
        "entity_type": entity_type,
        "paper_id": paper_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "original_path": str(original_path.resolve()),
        "staged_path": str(staged_path.resolve()),
        "state": "staged",
        "retry_count": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "last_error": None,
    }
    _save_meta(meta_path, meta_data)

    try:
        original_path.rename(staged_path)
    except OSError as exc:
        meta_path.unlink(missing_ok=True)
        raise exc

    return staged_path, meta_path


def mark_committed_deletion(meta_path: Path) -> None:
    """Updates quarantine metadata state to committed_pending_purge."""
    data = _load_meta(meta_path)
    if data:
        data["state"] = "committed_pending_purge"
        _save_meta(meta_path, data)


def mark_rollback_failed(meta_path: Path, error_message: str) -> None:
    """Updates quarantine metadata state to rollback_pending_restoration."""
    data = _load_meta(meta_path)
    if data:
        data["state"] = "rollback_pending_restoration"
        data["last_error"] = error_message
        data["retry_count"] = data.get("retry_count", 0) + 1
        _save_meta(meta_path, data)


def purge_quarantined_file(staged_path: Path, meta_path: Path, max_retries: int = 3) -> bool:
    """
    Attempts bounded retries to unlink quarantined file and its metadata.
    Returns True if successfully deleted (or already absent), False if all attempts fail.
    """
    for attempt in range(max_retries):
        try:
            if staged_path.exists():
                staged_path.unlink()
            meta_path.unlink(missing_ok=True)
            return True
        except OSError as exc:
            data = _load_meta(meta_path)
            if data:
                data["retry_count"] = data.get("retry_count", 0) + 1
                data["last_error"] = str(exc)
                data["state"] = "committed_pending_purge"
                _save_meta(meta_path, data)
            if attempt < max_retries - 1:
                time.sleep(0.05)
    return False


def restore_quarantined_file(staged_path: Path, original_path: Path, meta_path: Path) -> bool:
    """
    Attempts to rename staged_path back to original_path on rollback.
    Returns True on success (removing metadata), False on failure (recording durable state).
    """
    try:
        if staged_path.exists():
            original_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.rename(original_path)
        meta_path.unlink(missing_ok=True)
        return True
    except OSError as exc:
        logger.error(f"Failed to restore staged file {staged_path} to {original_path}: {exc}")
        mark_rollback_failed(meta_path, str(exc))
        return False


def get_quarantine_fallback_path(
    trash_dir: Path,
    paper_id: str,
    user_id: str | None = None,
) -> Path | None:
    """
    Searches quarantine ledger for any staged or rollback-failed file belonging to a live paper.
    Allows live records with recoverable staged bytes to serve downloads/views.
    """
    if not trash_dir.exists():
        return None

    for meta_path in trash_dir.glob("*.meta.json"):
        data = _load_meta(meta_path)
        if not data:
            continue
        if data.get("paper_id") == paper_id and data.get("state") in (
            "staged",
            "rollback_pending_restoration",
        ):
            if user_id is not None:
                meta_user = data.get("user_id")
                if meta_user is not None and meta_user != user_id:
                    continue
            staged_p = Path(data.get("staged_path", ""))
            if staged_p.exists():
                return staged_p
    return None


def find_adoptable_quarantine(
    trash_dir: Path,
    paper_id: str,
    user_id: str,
) -> tuple[Path, Path, Path] | None:
    """
    Finds an existing quarantined file belonging to a live paper owned by user_id
    that is in 'staged' or 'rollback_pending_restoration' state where staged_path exists.
    Returns (original_path, staged_path, meta_path) or None.
    If metadata lacks user_id, updates metadata to persist user_id.
    """
    if not trash_dir.exists():
        return None

    for meta_path in trash_dir.glob("*.meta.json"):
        data = _load_meta(meta_path)
        if not data:
            continue
        if data.get("paper_id") == paper_id and data.get("state") in (
            "staged",
            "rollback_pending_restoration",
        ):
            meta_user = data.get("user_id")
            # If metadata explicitly has a different user_id, do not adopt
            if meta_user is not None and meta_user != user_id:
                continue

            staged_p = Path(data.get("staged_path", ""))
            original_p = Path(data.get("original_path", ""))
            if staged_p.exists():
                # Persist owner in metadata if it was missing or different
                if meta_user != user_id:
                    data["user_id"] = user_id
                    _save_meta(meta_path, data)
                return original_p, staged_p, meta_path
    return None


def update_ledger_ownership(
    meta_path: Path,
    user_id: str,
    workspace_id: str | None = None,
) -> None:
    """Updates ledger metadata with verified user_id and optional workspace_id."""
    data = _load_meta(meta_path)
    if data:
        data["user_id"] = user_id
        if workspace_id:
            data["workspace_id"] = workspace_id
        _save_meta(meta_path, data)


def find_pending_purges(
    trash_dir: Path,
    paper_id: str,
    user_id: str | None = None,
) -> list[tuple[Path, Path]]:
    """
    Returns list of (staged_path, meta_path) for paper_id in committed_pending_purge state.
    Strictly verifies user ownership. Old ownerless ledgers without user_id are NOT returned
    to prevent unauthorized purges merely from possession of a resource ID.
    """
    results = []
    if not trash_dir.exists() or not user_id:
        return results

    for meta_path in trash_dir.glob("*.meta.json"):
        data = _load_meta(meta_path)
        if not data:
            continue
        if (
            data.get("paper_id") == paper_id
            and data.get("user_id") == user_id
            and data.get("state")
            in (
                "committed_deletion",
                "committed_pending_purge",
            )
        ):
            staged_p = Path(data.get("staged_path", ""))
            results.append((staged_p, meta_path))
    return results


def find_pending_purges_by_workspace(
    trash_dir: Path,
    workspace_id: str,
    user_id: str | None = None,
) -> list[tuple[Path, Path]]:
    """
    Returns list of (staged_path, meta_path) for workspace_id in committed_pending_purge state.
    Strictly verifies user ownership. Old ownerless ledgers without user_id are NOT returned
    to prevent unauthorized purges merely from possession of a resource ID.
    """
    results = []
    if not trash_dir.exists() or not user_id:
        return results

    for meta_path in trash_dir.glob("*.meta.json"):
        data = _load_meta(meta_path)
        if not data:
            continue
        if (
            data.get("workspace_id") == workspace_id
            and data.get("user_id") == user_id
            and data.get("state")
            in (
                "committed_deletion",
                "committed_pending_purge",
            )
        ):
            staged_p = Path(data.get("staged_path", ""))
            results.append((staged_p, meta_path))
    return results


def reconcile_quarantine(trash_dir: Path, db: Session) -> dict[str, int]:
    """
    Reconciles all quarantine ledger entries:
    - If paper exists in database: staged file belongs to live row -> attempts restoration back to original_path.
    - If paper does not exist in database: committed deletion -> attempts purge of staged file.
    - Strictly preserves unrelated files (files lacking valid .meta.json ledger).
    Returns dictionary with counts: {"purged": N, "restored": N, "failed_purge": N, "failed_restore": N}.
    """
    stats = {"purged": 0, "restored": 0, "failed_purge": 0, "failed_restore": 0}
    if not trash_dir.exists():
        return stats

    # Only process files accompanied by valid .meta.json files
    for meta_path in list(trash_dir.glob("*.meta.json")):
        data = _load_meta(meta_path)
        if not data:
            continue

        paper_id = data.get("paper_id")
        staged_path = Path(data.get("staged_path", ""))
        original_path = Path(data.get("original_path", ""))

        # Check if the paper row is alive in DB
        live_paper = db.query(Paper).filter(Paper.id == paper_id).first() if paper_id else None

        if live_paper:
            # LIVE paper: must restore original file!
            if staged_path.exists():
                restored = restore_quarantined_file(staged_path, original_path, meta_path)
                if restored:
                    stats["restored"] += 1
                else:
                    stats["failed_restore"] += 1
            else:
                meta_path.unlink(missing_ok=True)
        else:
            # COMMITTED deletion: must purge physical file!
            purged = purge_quarantined_file(staged_path, meta_path, max_retries=2)
            if purged:
                stats["purged"] += 1
            else:
                stats["failed_purge"] += 1

    return stats
