"""
Checkpoint Manager for Product-Lifecycle Orchestrator.

Manages phase-level workflow state with automatic migration from legacy steps format.
"""
from __future__ import annotations
import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List


class CheckpointManager:
    """
    Manages phase-level workflow state with memory caching and delayed writing.

    Checkpoint file format (.lifecycle/checkpoint.json):
    {
      "version": "2.0",
      "project_name": "xxx",
      "created_at": "2026-04-16T...",
      "updated_at": "2026-04-16T...",
      "current_phase": "phase-3-validate-prd",
      "status": "in_progress" | "paused" | "completed" | "failed",
      "completed_phases": ["phase-0-intent", "phase-1-init", ...],
      "phase_data": {
        "phase-3-validate-prd": {
          "started_at": "...",
          "completed_at": "...",
          "score": 85,
          "artifacts": [...]
        }
      },
      "intent": "new-product",
      "user_input": "我想做一个...",
      "metadata": {}
    }

    Performance Optimization (v2.1):
      - In-memory cache: Reduces disk I/O by caching checkpoint in memory
      - Delayed writing: Only writes to disk when explicitly requested or on destruction
      - Batch operations: Multiple updates in memory, single disk write
    """

    def __init__(self, project_root: Path):
        self.root = Path(project_root).resolve()
        self.checkpoint_file = self.root / ".lifecycle" / "checkpoint.json"
        self.legacy_steps_dir = self.root / ".lifecycle" / "steps"

        # v2.1: In-memory cache
        self._cache: Optional[dict] = None
        self._dirty: bool = False  # Track if cache has unsaved changes

        # v2.2: Thread safety
        self._lock = threading.RLock()

        # v2.1: Register destructor for automatic flush
        import atexit
        atexit.register(self._flush_on_exit)

    def load(self) -> dict:
        """Load checkpoint from cache or disk, migrating from legacy format if needed."""
        with self._lock:  # v2.2: Thread-safe
            # v2.1: Return cached checkpoint if available
            if self._cache is not None:
                return self._cache

            # Load from disk
            if self.checkpoint_file.exists():
                try:
                    self._cache = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
                    # v2.1: Migrate checkpoint version if needed
                    self._cache = self._migrate_checkpoint_version(self._cache)
                    return self._cache
                except (json.JSONDecodeError, OSError) as e:
                    # Corrupted checkpoint, try migration
                    print(f"⚠ Checkpoint corrupted, attempting migration: {e}")
                    self._cache = self._migrate_from_legacy()
                    return self._cache

            # No checkpoint exists, try migration
            if self.legacy_steps_dir.exists():
                self._cache = self._migrate_from_legacy()
                return self._cache

            # Return empty checkpoint
            self._cache = self._create_empty()
            return self._cache

    def save(self, checkpoint: dict, immediate: bool = False):
        """
        Save checkpoint to cache (and optionally to disk).

        Args:
            checkpoint: Checkpoint data to save
            immediate: If True, write to disk immediately. If False, defer until flush().
        """
        with self._lock:  # v2.2: Thread-safe
            # v2.1: Update cache
            self._cache = checkpoint
            self._cache["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._dirty = True

            # Write to disk if immediate mode or if explicitly requested
            if immediate:
                self.flush()

    def init(self, project_name: str, intent: str, user_input: str) -> dict:
        """Initialize a new checkpoint."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = {
                "version": "2.1",
                "project_name": project_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "current_phase": None,
                "status": "initialized",
                "completed_phases": [],
                "phase_data": {},
                "intent": intent,
                "user_input": user_input,
                "metadata": {}
            }
            self.save(checkpoint, immediate=True)  # Write immediately for initialization
            return checkpoint

    def flush(self):
        """Write cached checkpoint to disk (v2.1)."""
        with self._lock:  # v2.2: Thread-safe
            if not self._dirty or self._cache is None:
                return

            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self._dirty = False

    def _flush_on_exit(self):
        """Destructor callback to flush cache on exit (v2.1)."""
        try:
            self.flush()
        except Exception:
            pass  # Silently fail on exit

    def is_phase_completed(self, phase_id: str) -> bool:
        """Check if a phase has been completed (uses cache)."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = self.load()  # This will use cache
            return phase_id in checkpoint.get("completed_phases", [])

    def record_phase_start(self, phase_id: str):
        """Record that a phase has started (updates cache only)."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = self.load()
            if "phase_data" not in checkpoint:
                checkpoint["phase_data"] = {}
            if phase_id not in checkpoint["phase_data"]:
                checkpoint["phase_data"][phase_id] = {}
            checkpoint["phase_data"][phase_id]["started_at"] = datetime.now(timezone.utc).isoformat()
            checkpoint["current_phase"] = phase_id
            checkpoint["status"] = "in_progress"
            self.save(checkpoint)  # Deferred write

    def record_phase_complete(self, phase_id: str, data: Optional[dict] = None):
        """Record that a phase has completed (updates cache only)."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = self.load()
            if phase_id not in checkpoint.get("completed_phases", []):
                if "completed_phases" not in checkpoint:
                    checkpoint["completed_phases"] = []
                checkpoint["completed_phases"].append(phase_id)
            if "phase_data" not in checkpoint:
                checkpoint["phase_data"] = {}
            if phase_id not in checkpoint["phase_data"]:
                checkpoint["phase_data"][phase_id] = {}
            checkpoint["phase_data"][phase_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            if data:
                checkpoint["phase_data"][phase_id].update(data)
            self.save(checkpoint)  # Deferred write

    def record_phase_failed(self, phase_id: str, error: str):
        """Record that a phase has failed (updates cache only)."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = self.load()
            checkpoint["status"] = "failed"
            if "phase_data" not in checkpoint:
                checkpoint["phase_data"] = {}
            if phase_id not in checkpoint["phase_data"]:
                checkpoint["phase_data"][phase_id] = {}
            checkpoint["phase_data"][phase_id]["failed_at"] = datetime.now(timezone.utc).isoformat()
            checkpoint["phase_data"][phase_id]["error"] = error
            self.save(checkpoint, immediate=True)  # Write immediately on failure

    def record_phase_paused(self, phase_id: str, reason: str):
        """Record that a phase is paused waiting for user input (updates cache only)."""
        with self._lock:  # v2.2: Thread-safe
            checkpoint = self.load()
            checkpoint["status"] = "paused"
            if "phase_data" not in checkpoint:
                checkpoint["phase_data"] = {}
            if phase_id not in checkpoint["phase_data"]:
                checkpoint["phase_data"][phase_id] = {}
            checkpoint["phase_data"][phase_id]["paused_at"] = datetime.now(timezone.utc).isoformat()
            checkpoint["phase_data"][phase_id]["pause_reason"] = reason
            self.save(checkpoint, immediate=True)  # Write immediately on pause

    def clear_notification(self):
        """Clear notification file if it exists."""
        notification_file = self.root / ".lifecycle" / "notification.json"
        if notification_file.exists():
            notification_file.unlink()

    # -------------------------------------------------------------------------
    # Rollback Mechanism (v2.2)
    # -------------------------------------------------------------------------

    def create_rollback_point(self, phase_id: str, description: str = "") -> dict:
        """
        Create a rollback point before executing a phase.

        Args:
            phase_id: Phase ID to create rollback point for
            description: Human-readable description

        Returns:
            Rollback point dictionary
        """
        with self._lock:
            checkpoint = self.load()

            # Create rollback point ID
            rollback_id = f"rp-{uuid.uuid4().hex[:8]}"

            # Create file snapshot
            snapshot_dir = self._create_file_snapshot(phase_id)

            rollback_point = {
                "id": rollback_id,
                "phase_id": phase_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": description or f"Before {phase_id}",
                "checkpoint_snapshot": {
                    "current_phase": checkpoint.get("current_phase"),
                    "completed_phases": checkpoint.get("completed_phases", []).copy(),
                    "status": checkpoint.get("status"),
                    "phase_data": checkpoint.get("phase_data", {}).copy()
                },
                "snapshot_dir": str(snapshot_dir) if snapshot_dir else None
            }

            # Add to metadata
            if "metadata" not in checkpoint:
                checkpoint["metadata"] = {}
            if "rollback_points" not in checkpoint["metadata"]:
                checkpoint["metadata"]["rollback_points"] = []

            checkpoint["metadata"]["rollback_points"].append(rollback_point)
            self.save(checkpoint, immediate=True)

            return rollback_point

    def list_rollback_points(self) -> List[dict]:
        """List all available rollback points."""
        with self._lock:
            checkpoint = self.load()
            return checkpoint.get("metadata", {}).get("rollback_points", [])

    def rollback_to(self, rollback_id: str) -> bool:
        """
        Rollback to a specific rollback point.

        Args:
            rollback_id: Rollback point ID

        Returns:
            True if rollback succeeded, False otherwise
        """
        with self._lock:
            checkpoint = self.load()

            # Find rollback point
            rollback_points = checkpoint.get("metadata", {}).get("rollback_points", [])
            rollback_point = None
            for rp in rollback_points:
                if rp["id"] == rollback_id:
                    rollback_point = rp
                    break

            if not rollback_point:
                print(f"❌ Rollback point {rollback_id} not found")
                return False

            # Restore checkpoint state
            snapshot = rollback_point.get("checkpoint_snapshot", {})
            checkpoint["current_phase"] = snapshot.get("current_phase")
            checkpoint["completed_phases"] = snapshot.get("completed_phases", [])
            checkpoint["status"] = snapshot.get("status", "paused")
            checkpoint["phase_data"] = snapshot.get("phase_data", {})

            # Restore file snapshot
            snapshot_dir = rollback_point.get("snapshot_dir")
            if snapshot_dir and Path(snapshot_dir).exists():
                self._restore_file_snapshot(snapshot_dir)

            # Remove rollback points created after this one
            rollback_idx = rollback_points.index(rollback_point)
            checkpoint["metadata"]["rollback_points"] = rollback_points[:rollback_idx + 1]

            self.save(checkpoint, immediate=True)
            print(f"✓ Rolled back to {rollback_point['phase_id']} at {rollback_point['timestamp']}")
            return True

    def _create_file_snapshot(self, phase_id: str) -> Optional[Path]:
        """
        Create a snapshot of project files.

        Args:
            phase_id: Phase ID for snapshot naming

        Returns:
            Path to snapshot directory, or None if no files to snapshot
        """
        snapshot_dir = self.root / ".lifecycle" / "snapshots" / f"{phase_id}-{uuid.uuid4().hex[:8]}"

        # Snapshot Docs/ directory if it exists
        docs_dir = self.root / "Docs"
        if docs_dir.exists():
            snapshot_docs = snapshot_dir / "Docs"
            snapshot_docs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(docs_dir, snapshot_docs)

        # Snapshot .lifecycle/ directory (excluding snapshots/ itself)
        lifecycle_dir = self.root / ".lifecycle"
        if lifecycle_dir.exists():
            snapshot_lifecycle = snapshot_dir / ".lifecycle"
            snapshot_lifecycle.mkdir(parents=True, exist_ok=True)
            for item in lifecycle_dir.iterdir():
                if item.name == "snapshots":
                    continue
                if item.is_file():
                    shutil.copy2(item, snapshot_lifecycle / item.name)
                elif item.is_dir():
                    shutil.copytree(item, snapshot_lifecycle / item.name)

        if snapshot_dir.exists():
            return snapshot_dir
        return None

    def _restore_file_snapshot(self, snapshot_dir: str):
        """
        Restore files from a snapshot.

        Args:
            snapshot_dir: Path to snapshot directory
        """
        snapshot_path = Path(snapshot_dir)
        if not snapshot_path.exists():
            print(f"⚠ Snapshot directory {snapshot_dir} not found")
            return

        # Restore Docs/ directory
        snapshot_docs = snapshot_path / "Docs"
        if snapshot_docs.exists():
            docs_dir = self.root / "Docs"
            if docs_dir.exists():
                shutil.rmtree(docs_dir)
            shutil.copytree(snapshot_docs, docs_dir)

        # Restore .lifecycle/ directory
        snapshot_lifecycle = snapshot_path / ".lifecycle"
        if snapshot_lifecycle.exists():
            lifecycle_dir = self.root / ".lifecycle"
            # Remove current files (but keep snapshots/)
            for item in lifecycle_dir.iterdir():
                if item.name == "snapshots":
                    continue
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

            # Copy snapshot files back
            for item in snapshot_lifecycle.iterdir():
                if item.is_file():
                    shutil.copy2(item, lifecycle_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, lifecycle_dir / item.name)

    def _migrate_checkpoint_version(self, checkpoint: dict) -> dict:
        """
        Migrate checkpoint from old version to new version.

        v2.0 → v2.1: Migrate from 10-phase to 11-phase system (with phase-1-analyze-solution)
        """
        version = checkpoint.get("version", "2.0")

        if version == "2.0":
            # Backup original checkpoint
            backup_file = self.checkpoint_file.with_suffix(".json.bak")
            if not backup_file.exists():  # Don't overwrite existing backup
                try:
                    backup_file.write_text(
                        json.dumps(checkpoint, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    print(f"✓ Checkpoint backed up to {backup_file}")
                except OSError as e:
                    print(f"⚠ Failed to backup checkpoint: {e}")

            # Migrate Phase IDs from v2.0 (10 phases) to v2.1 (11 phases)
            phase_id_map = {
                "phase-1-init": "phase-2-init",
                "phase-2-draft-prd": "phase-3-draft-prd",
                "phase-3-validate-prd": "phase-4-validate-prd",
                "phase-4-arch-interview": "phase-5-arch-interview",
                "phase-5-draft-arch": "phase-6-draft-arch",
                "phase-6-validate-arch": "phase-7-validate-arch",
                "phase-7-test-outline": "phase-8-test-outline",
                "phase-8-iterations": "phase-9-iterations",
                "phase-9-iter-exec": "phase-10-iter-exec",
                "phase-10-change": "phase-11-change"
            }

            # Map completed phases
            old_completed = checkpoint.get("completed_phases", [])
            new_completed = []
            for phase_id in old_completed:
                new_phase_id = phase_id_map.get(phase_id, phase_id)
                new_completed.append(new_phase_id)
            checkpoint["completed_phases"] = new_completed

            # Map current phase
            old_current = checkpoint.get("current_phase")
            if old_current:
                checkpoint["current_phase"] = phase_id_map.get(old_current, old_current)

            # Map phase_data keys
            old_phase_data = checkpoint.get("phase_data", {})
            new_phase_data = {}
            for phase_id, data in old_phase_data.items():
                new_phase_id = phase_id_map.get(phase_id, phase_id)
                new_phase_data[new_phase_id] = data
            checkpoint["phase_data"] = new_phase_data

            # Update version
            checkpoint["version"] = "2.1"

            print(f"✓ Migrated checkpoint from v2.0 to v2.1 ({len(new_completed)} phases)")
            self._dirty = True

        # Validate migrated phase IDs against PHASES registry
        try:
            from .phases import PHASES
            valid_phase_ids = {p["id"] for p in PHASES}

            invalid_completed = [pid for pid in checkpoint["completed_phases"] if pid not in valid_phase_ids]
            if invalid_completed:
                print(f"⚠ Migration warning: Unknown phase IDs in completed_phases: {invalid_completed}")

            current = checkpoint.get("current_phase")
            if current and current not in valid_phase_ids:
                print(f"⚠ Migration warning: Unknown current_phase: {current}")

            invalid_data = [pid for pid in checkpoint.get("phase_data", {}).keys() if pid not in valid_phase_ids]
            if invalid_data:
                print(f"⚠ Migration warning: Unknown phase IDs in phase_data: {invalid_data}")
        except ImportError:
            pass  # Skip validation if PHASES not available

        return checkpoint

    def _create_empty(self) -> dict:
        """Create an empty checkpoint."""
        return {
            "version": "2.1",  # Updated to v2.1
            "project_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "current_phase": None,
            "status": "initialized",
            "completed_phases": [],
            "phase_data": {},
            "intent": "unknown",
            "user_input": "",
            "metadata": {}
        }

    def _migrate_from_legacy(self) -> dict:
        """Migrate from legacy steps/ directory format (stores in cache)."""
        checkpoint = self._create_empty()
        checkpoint["status"] = "migrated"

        if not self.legacy_steps_dir.exists():
            self._cache = checkpoint
            self._dirty = True
            return checkpoint

        print("⚠ Migrating from legacy steps/ format...")

        for step_file in self.legacy_steps_dir.glob("*.json"):
            step_id = step_file.stem
            try:
                step_data = json.loads(step_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            # Map old step_id to new phase_id
            phase_id = self._map_step_to_phase(step_id)
            if phase_id:
                if phase_id not in checkpoint["completed_phases"]:
                    checkpoint["completed_phases"].append(phase_id)
                if "phase_data" not in checkpoint:
                    checkpoint["phase_data"] = {}
                checkpoint["phase_data"][phase_id] = {
                    "migrated_from": step_id,
                    "completed_at": step_data.get("completed_at") or step_data.get("recorded_at")
                }

        # Save migrated checkpoint to cache and disk
        self._cache = checkpoint
        self._dirty = True
        self.flush()  # Write immediately after migration
        print(f"✓ Migrated {len(checkpoint['completed_phases'])} phases from legacy format")
        return checkpoint

    def _map_step_to_phase(self, step_id: str) -> Optional[str]:
        """Map legacy step_id to new phase_id (v2.1 with 11 phases)."""
        mapping = {
            "project-initialized": "phase-2-init",  # Updated for v2.1
            "project-bootstrapped": "phase-2-init",
            "prd-written": "phase-3-draft-prd",
            "prd-drafted": "phase-3-draft-prd",
            "prd-validated": "phase-4-validate-prd",
            "arch-interview-done": "phase-5-arch-interview",
            "arch-designed": "phase-6-draft-arch",
            "arch-doc-written": "phase-6-draft-arch",
            "arch-validated": "phase-7-validate-arch",
            "test-outline-ready": "phase-8-test-outline",
            "test-outline-written": "phase-8-test-outline",
            "iterations-planned": "phase-9-iterations"
        }
        return mapping.get(step_id)
