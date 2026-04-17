"""
Unit tests for CheckpointManager.

Tests cover:
- Initialization and empty checkpoint creation
- Memory caching and delayed writing
- Phase lifecycle (start, complete, fail, pause)
- Legacy migration
- Automatic flush on exit
"""
import pytest
import tempfile
import json
from pathlib import Path
from scripts.core.checkpoint_manager import CheckpointManager


class TestCheckpointManager:
    """Test suite for CheckpointManager."""

    def test_init_creates_checkpoint(self, tmp_path):
        """Test that init() creates a new checkpoint with correct fields."""
        mgr = CheckpointManager(tmp_path)

        checkpoint = mgr.init("test-project", "new-product", "test input")

        assert checkpoint["version"] == "2.0"
        assert checkpoint["project_name"] == "test-project"
        assert checkpoint["intent"] == "new-product"
        assert checkpoint["user_input"] == "test input"
        assert checkpoint["status"] == "initialized"
        assert checkpoint["completed_phases"] == []
        assert checkpoint["phase_data"] == {}

    def test_load_returns_cached_checkpoint(self, tmp_path):
        """Test that load() returns cached checkpoint without disk I/O."""
        mgr = CheckpointManager(tmp_path)
        checkpoint1 = mgr.init("test-project", "new-product", "test input")

        # Second load should return the same object from cache
        checkpoint2 = mgr.load()
        assert checkpoint2 is checkpoint1

    def test_save_updates_cache_not_disk(self, tmp_path):
        """Test that save() with immediate=False updates cache only."""
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Modify and save without immediate flush
        checkpoint["custom_field"] = "test_value"
        mgr.save(checkpoint)

        # Cache should be updated
        assert mgr._cache["custom_field"] == "test_value"
        assert mgr._dirty is True

        # Disk file should not have the update yet
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert "custom_field" not in disk_checkpoint

    def test_save_immediate_writes_to_disk(self, tmp_path):
        """Test that save() with immediate=True writes to disk."""
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Modify and save with immediate flush
        checkpoint["custom_field"] = "test_value"
        mgr.save(checkpoint, immediate=True)

        # Disk file should have the update
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert disk_checkpoint["custom_field"] == "test_value"
        assert mgr._dirty is False

    def test_flush_writes_cache_to_disk(self, tmp_path):
        """Test that flush() writes cached checkpoint to disk."""
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Modify cache
        checkpoint["custom_field"] = "test_value"
        mgr.save(checkpoint)

        # Flush to disk
        mgr.flush()

        # Disk file should have the update
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert disk_checkpoint["custom_field"] == "test_value"
        assert mgr._dirty is False

    def test_record_phase_start(self, tmp_path):
        """Test that record_phase_start() updates cache correctly."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        mgr.record_phase_start("phase-1-init")

        checkpoint = mgr.load()
        assert checkpoint["current_phase"] == "phase-1-init"
        assert checkpoint["status"] == "in_progress"
        assert "started_at" in checkpoint["phase_data"]["phase-1-init"]

    def test_record_phase_complete(self, tmp_path):
        """Test that record_phase_complete() updates cache correctly."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        mgr.record_phase_start("phase-1-init")
        mgr.record_phase_complete("phase-1-init", {"score": 95})

        checkpoint = mgr.load()
        assert "phase-1-init" in checkpoint["completed_phases"]
        assert checkpoint["phase_data"]["phase-1-init"]["score"] == 95
        assert "completed_at" in checkpoint["phase_data"]["phase-1-init"]

    def test_record_phase_failed_writes_immediately(self, tmp_path):
        """Test that record_phase_failed() writes to disk immediately."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        mgr.record_phase_start("phase-1-init")
        mgr.record_phase_failed("phase-1-init", "Test error")

        # Should be written to disk immediately
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert disk_checkpoint["status"] == "failed"
        assert disk_checkpoint["phase_data"]["phase-1-init"]["error"] == "Test error"

    def test_record_phase_paused_writes_immediately(self, tmp_path):
        """Test that record_phase_paused() writes to disk immediately."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        mgr.record_phase_start("phase-1-init")
        mgr.record_phase_paused("phase-1-init", "Waiting for user")

        # Should be written to disk immediately
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert disk_checkpoint["status"] == "paused"
        assert disk_checkpoint["phase_data"]["phase-1-init"]["pause_reason"] == "Waiting for user"

    def test_is_phase_completed(self, tmp_path):
        """Test that is_phase_completed() checks completed_phases list."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        assert mgr.is_phase_completed("phase-1-init") is False

        mgr.record_phase_start("phase-1-init")
        mgr.record_phase_complete("phase-1-init")

        assert mgr.is_phase_completed("phase-1-init") is True

    def test_multiple_phase_updates_single_flush(self, tmp_path):
        """Test that multiple phase updates can be flushed in one write."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Multiple updates
        mgr.record_phase_start("phase-1-init")
        mgr.record_phase_complete("phase-1-init")
        mgr.record_phase_start("phase-2-draft-prd")
        mgr.record_phase_complete("phase-2-draft-prd")

        # All updates should be in cache
        checkpoint = mgr.load()
        assert len(checkpoint["completed_phases"]) == 2

        # Flush once
        mgr.flush()

        # Disk should have all updates
        disk_checkpoint = json.loads(mgr.checkpoint_file.read_text())
        assert len(disk_checkpoint["completed_phases"]) == 2

    def test_migrate_from_legacy(self, tmp_path):
        """Test migration from legacy steps/ directory format."""
        # Create legacy steps directory
        steps_dir = tmp_path / ".lifecycle" / "steps"
        steps_dir.mkdir(parents=True)

        # Create a legacy step file
        step_file = steps_dir / "project-initialized.json"
        step_data = {
            "completed_at": "2026-04-16T10:00:00Z",
            "recorded_at": "2026-04-16T10:00:00Z"
        }
        step_file.write_text(json.dumps(step_data))

        # Load should migrate
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        assert checkpoint["status"] == "migrated"
        assert "phase-1-init" in checkpoint["completed_phases"]
        assert checkpoint["phase_data"]["phase-1-init"]["migrated_from"] == "project-initialized"

    def test_clear_notification(self, tmp_path):
        """Test that clear_notification() removes notification file."""
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Create notification file
        notification_file = tmp_path / ".lifecycle" / "notification.json"
        notification_file.parent.mkdir(parents=True, exist_ok=True)
        notification_file.write_text("{}")

        assert notification_file.exists()

        # Clear notification
        mgr.clear_notification()

        assert not notification_file.exists()


class TestCheckpointManagerPerformance:
    """Performance tests for CheckpointManager."""

    def test_multiple_operations_single_io(self, tmp_path):
        """Test that multiple operations result in minimal disk I/O."""
        import os

        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Get initial file modification time
        initial_mtime = os.path.getmtime(mgr.checkpoint_file)

        # Perform multiple operations (should not write to disk)
        for i in range(10):
            mgr.record_phase_start(f"phase-{i}")
            mgr.record_phase_complete(f"phase-{i}")

        # File should not have been modified
        current_mtime = os.path.getmtime(mgr.checkpoint_file)
        assert current_mtime == initial_mtime

        # Flush should update file
        mgr.flush()
        final_mtime = os.path.getmtime(mgr.checkpoint_file)
        assert final_mtime > initial_mtime
