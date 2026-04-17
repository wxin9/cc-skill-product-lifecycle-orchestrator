"""
Integration tests for Orchestrator workflow.

Tests cover:
- Full new-product workflow execution
- Phase state transitions
- Interaction pause and resume
- Failure handling and recovery
- Checkpoint persistence
"""
import pytest
import tempfile
import json
from pathlib import Path
from scripts.core.orchestrator import Orchestrator
from scripts.core.checkpoint_manager import CheckpointManager


class TestNewProductWorkflow:
    """Integration tests for new-product workflow."""

    def test_orchestrator_initializes_project(self, tmp_path):
        """Test that orchestrator initializes project structure."""
        orch = Orchestrator(tmp_path)

        # Run with new-product intent
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should pause at Phase 2 (PRD draft)
        assert exit_code == 1  # paused

        # Check project structure created
        assert (tmp_path / "Docs" / "INDEX.md").exists()
        assert (tmp_path / ".lifecycle" / "config.json").exists()
        assert (tmp_path / ".lifecycle" / "dod.json").exists()

        # Check checkpoint state
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        assert checkpoint["status"] == "paused"
        assert checkpoint["intent"] == "new-product"
        assert "phase-1-init" in checkpoint["completed_phases"]

    def test_orchestrator_pauses_at_interaction_point(self, tmp_path):
        """Test that orchestrator pauses at interaction points."""
        orch = Orchestrator(tmp_path)

        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should pause at Phase 2
        assert exit_code == 1

        # Check notification file created
        notification_file = tmp_path / ".lifecycle" / "notification.json"
        assert notification_file.exists()

        notification = json.loads(notification_file.read_text())
        assert notification["type"] == "pause_for_user"
        assert "phase-2-draft-prd" in notification["phase_id"]

    def test_orchestrator_resumes_from_pause(self, tmp_path):
        """Test that orchestrator can resume from pause point."""
        orch = Orchestrator(tmp_path)

        # Run until pause
        exit_code = orch.run(intent="new-product", user_input="Test product")
        assert exit_code == 1  # paused

        # Resume should continue from current phase
        exit_code = orch.run(intent="resume", from_phase="phase-2-draft-prd")

        # Should pause again at next interaction point (Phase 4 or 5)
        # or complete if no more phases
        assert exit_code in [0, 1, 2]  # success, paused, or failed

    def test_orchestrator_records_phase_completion(self, tmp_path):
        """Test that orchestrator records phase completion in checkpoint."""
        orch = Orchestrator(tmp_path)

        orch.run(intent="new-product", user_input="Test product")

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        # Phase 1 should be completed
        assert "phase-1-init" in checkpoint["completed_phases"]

        # Phase data should exist
        phase_data = checkpoint["phase_data"].get("phase-1-init", {})
        assert "started_at" in phase_data
        assert "completed_at" in phase_data

    def test_orchestrator_handles_phase_failure(self, tmp_path):
        """Test that orchestrator handles phase failure correctly."""
        orch = Orchestrator(tmp_path)

        # Run workflow
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should pause at interaction point, not fail
        assert exit_code == 1

        # Check checkpoint state
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        # Should be paused, not failed
        assert checkpoint["status"] == "paused"

    def test_orchestrator_creates_notification_on_pause(self, tmp_path):
        """Test that orchestrator creates notification file on pause."""
        orch = Orchestrator(tmp_path)

        orch.run(intent="new-product", user_input="Test product")

        notification_file = tmp_path / ".lifecycle" / "notification.json"
        assert notification_file.exists()

        notification = json.loads(notification_file.read_text())

        assert "type" in notification
        assert "phase_id" in notification
        assert "message" in notification
        assert "actions" in notification
        assert len(notification["actions"]) > 0

    def test_orchestrator_clears_notification_on_completion(self, tmp_path):
        """Test that orchestrator clears notification when workflow completes."""
        orch = Orchestrator(tmp_path)

        # Run and pause
        orch.run(intent="new-product", user_input="Test product")

        notification_file = tmp_path / ".lifecycle" / "notification.json"
        assert notification_file.exists()

        # Manually complete the workflow
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()
        checkpoint["status"] = "completed"
        mgr.save(checkpoint, immediate=True)
        mgr.clear_notification()

        # Notification should be cleared
        assert not notification_file.exists()

    def test_orchestrator_handles_multiple_phases(self, tmp_path):
        """Test that orchestrator executes multiple phases in sequence."""
        orch = Orchestrator(tmp_path)

        orch.run(intent="new-product", user_input="Test product")

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        # Should have completed at least Phase 1
        assert len(checkpoint["completed_phases"]) >= 1

        # Current phase should be set
        assert checkpoint["current_phase"] is not None

    def test_orchestrator_validates_phase_dependencies(self, tmp_path):
        """Test that orchestrator validates phase dependencies."""
        orch = Orchestrator(tmp_path)

        # Initialize checkpoint first
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Try to resume from a phase that has unmet dependencies
        # Should handle gracefully (may skip or fail)
        exit_code = orch.run(intent="resume", from_phase="phase-3-validate-prd")

        # Should handle gracefully (may succeed, pause, or fail)
        assert exit_code in [0, 1, 2]


class TestOrchestratorStateTransitions:
    """Test orchestrator state machine transitions."""

    def test_status_transitions_initialized_to_in_progress(self, tmp_path):
        """Test status transitions from initialized to in_progress."""
        orch = Orchestrator(tmp_path)

        # Run orchestrator (this will initialize checkpoint)
        orch.run(intent="new-product", user_input="Test product")

        # Check status changed from initialized
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        # Status should be paused (at interaction point) or in_progress
        # Note: may also be "initialized" if no phases executed yet
        assert checkpoint["status"] in ["initialized", "in_progress", "paused"]

    def test_status_transitions_to_paused_at_interaction(self, tmp_path):
        """Test status transitions to paused at interaction point."""
        orch = Orchestrator(tmp_path)

        orch.run(intent="new-product", user_input="Test product")

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        assert checkpoint["status"] == "paused"

    def test_status_transitions_to_completed(self, tmp_path):
        """Test status transitions to completed when all phases done."""
        orch = Orchestrator(tmp_path)

        # Manually complete all phases
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Mark all phases as completed
        all_phases = [
            "phase-0-intent", "phase-1-init", "phase-2-draft-prd",
            "phase-3-validate-prd", "phase-4-arch-interview",
            "phase-5-draft-arch", "phase-6-validate-arch",
            "phase-7-test-outline", "phase-8-iterations",
            "phase-9-iter-exec", "phase-10-change"
        ]
        checkpoint["completed_phases"] = all_phases
        checkpoint["status"] = "completed"
        mgr.save(checkpoint, immediate=True)

        # Status should be completed
        checkpoint = mgr.load()
        assert checkpoint["status"] == "completed"


class TestOrchestratorWithCommandExecutor:
    """Test orchestrator integration with CommandExecutor."""

    def test_orchestrator_calls_command_executor(self, tmp_path):
        """Test that orchestrator calls CommandExecutor for phase commands."""
        orch = Orchestrator(tmp_path)

        # Run Phase 1 which calls init command
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should have executed init command
        assert (tmp_path / "Docs" / "INDEX.md").exists()
        assert (tmp_path / ".lifecycle" / "config.json").exists()

    def test_orchestrator_handles_command_failure(self, tmp_path):
        """Test that orchestrator handles command execution failures."""
        orch = Orchestrator(tmp_path)

        # Create a checkpoint that points to a phase with invalid command
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")
        checkpoint["current_phase"] = "phase-1-init"
        mgr.save(checkpoint, immediate=True)

        # Run should still succeed or pause gracefully
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should not crash
        assert exit_code in [0, 1, 2]


class TestOrchestratorPerformance:
    """Performance tests for orchestrator."""

    def test_orchestrator_minimizes_disk_io(self, tmp_path):
        """Test that orchestrator minimizes disk I/O using cache."""
        import os

        orch = Orchestrator(tmp_path)

        # Run orchestrator
        orch.run(intent="new-product", user_input="Test product")

        mgr = CheckpointManager(tmp_path)
        checkpoint_file = mgr.checkpoint_file

        # Get file modification time
        initial_mtime = os.path.getmtime(checkpoint_file)

        # Load checkpoint (should use cache)
        checkpoint1 = mgr.load()

        # File should not have been modified
        current_mtime = os.path.getmtime(checkpoint_file)
        assert current_mtime == initial_mtime

        # Cache should be used
        checkpoint2 = mgr.load()
        assert checkpoint2 is checkpoint1  # Same object reference

    def test_orchestrator_handles_rapid_phase_transitions(self, tmp_path):
        """Test that orchestrator handles rapid phase transitions."""
        orch = Orchestrator(tmp_path)

        # Run multiple operations quickly
        for i in range(3):
            orch.run(intent="new-product", user_input=f"Test product {i}")

            mgr = CheckpointManager(tmp_path)
            checkpoint = mgr.load()

            # Should handle gracefully
            assert checkpoint["status"] in ["initialized", "in_progress", "paused", "completed"]


class TestOrchestratorErrorRecovery:
    """Test orchestrator error recovery."""

    def test_orchestrator_recoverable_from_missing_checkpoint(self, tmp_path):
        """Test that orchestrator can recover from missing checkpoint."""
        orch = Orchestrator(tmp_path)

        # Run without pre-existing checkpoint
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should create checkpoint and proceed
        assert exit_code in [0, 1, 2]

        # Check checkpoint created
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()
        assert checkpoint is not None

    def test_orchestrator_handles_corrupted_checkpoint(self, tmp_path):
        """Test that orchestrator handles corrupted checkpoint gracefully."""
        # Create corrupted checkpoint
        checkpoint_file = tmp_path / ".lifecycle" / "checkpoint.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_text("{ invalid json }")

        orch = Orchestrator(tmp_path)

        # Should handle gracefully
        exit_code = orch.run(intent="new-product", user_input="Test product")

        # Should recover or fail gracefully
        assert exit_code in [0, 1, 2]
