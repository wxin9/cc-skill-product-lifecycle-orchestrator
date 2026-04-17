"""
Integration tests for rollback CLI commands.
"""
import pytest
import tempfile
import os
from pathlib import Path


class TestRollbackCLI:
    """Integration tests for rollback CLI commands."""

    def test_list_empty_rollback_points(self, tmp_path):
        """Test listing rollback points when none exist."""
        from scripts.core.orchestrator import Orchestrator

        orch = Orchestrator(tmp_path)
        orch.checkpoint_mgr.init("test-project", "new-product", "test input")

        rollback_points = orch.list_rollback_points()
        assert len(rollback_points) == 0

    def test_create_and_list_rollback_points(self, tmp_path):
        """Test creating and listing rollback points."""
        from scripts.core.orchestrator import Orchestrator

        orch = Orchestrator(tmp_path)
        orch.checkpoint_mgr.init("test-project", "new-product", "test input")

        # Create rollback points
        rp1 = orch.create_rollback_point("phase-1-init", "First checkpoint")
        rp2 = orch.create_rollback_point("phase-2-draft-prd", "Second checkpoint")

        # List rollback points
        rollback_points = orch.list_rollback_points()

        assert len(rollback_points) == 2
        assert rollback_points[0]["id"] == rp1["id"]
        assert rollback_points[1]["id"] == rp2["id"]

    def test_rollback_via_cli(self, tmp_path):
        """Test rollback via CLI command."""
        from scripts.core.orchestrator import Orchestrator
        from scripts.core.checkpoint_manager import CheckpointManager

        orch = Orchestrator(tmp_path)
        orch.checkpoint_mgr.init("test-project", "new-product", "test input")

        # Complete some phases
        orch.checkpoint_mgr.record_phase_complete("phase-1-init")
        orch.checkpoint_mgr.record_phase_complete("phase-2-draft-prd")

        # Create rollback point
        rp = orch.create_rollback_point("phase-2-draft-prd", "Before validation")

        # Complete more phases
        orch.checkpoint_mgr.record_phase_complete("phase-3-validate-prd")

        # Verify state before rollback
        checkpoint = orch.checkpoint_mgr.load()
        assert len(checkpoint["completed_phases"]) == 3

        # Rollback via CLI
        success = orch.rollback_to(rp["id"])
        assert success

        # Verify state after rollback
        checkpoint = orch.checkpoint_mgr.load()
        assert len(checkpoint["completed_phases"]) == 2

    def test_rollback_with_file_restoration(self, tmp_path):
        """Test that rollback restores files correctly."""
        from scripts.core.orchestrator import Orchestrator

        orch = Orchestrator(tmp_path)
        orch.checkpoint_mgr.init("test-project", "new-product", "test input")

        # Create test files
        docs_dir = tmp_path / "Docs"
        docs_dir.mkdir()
        prd_file = docs_dir / "PRD.md"
        prd_file.write_text("# Original PRD\n\nThis is the original content.")

        # Create rollback point
        rp = orch.create_rollback_point("phase-2-draft-prd", "After PRD draft")

        # Modify file
        prd_file.write_text("# Modified PRD\n\nThis is modified content.")

        # Verify modification
        assert "Modified" in prd_file.read_text()

        # Rollback
        success = orch.rollback_to(rp["id"])
        assert success

        # Verify restoration
        content = prd_file.read_text()
        assert "Original" in content
        assert "Modified" not in content

    def test_rollback_removes_later_rollback_points(self, tmp_path):
        """Test that rollback removes rollback points created after it."""
        from scripts.core.orchestrator import Orchestrator

        orch = Orchestrator(tmp_path)
        orch.checkpoint_mgr.init("test-project", "new-product", "test input")

        # Create multiple rollback points
        rp1 = orch.create_rollback_point("phase-1-init", "First")
        rp2 = orch.create_rollback_point("phase-2-draft-prd", "Second")
        rp3 = orch.create_rollback_point("phase-3-validate-prd", "Third")

        # Verify all 3 exist
        rollback_points = orch.list_rollback_points()
        assert len(rollback_points) == 3

        # Rollback to rp2
        orch.rollback_to(rp2["id"])

        # Verify rp3 was removed
        rollback_points = orch.list_rollback_points()
        assert len(rollback_points) == 2
        assert rp1["id"] in [rp["id"] for rp in rollback_points]
        assert rp2["id"] in [rp["id"] for rp in rollback_points]
        assert rp3["id"] not in [rp["id"] for rp in rollback_points]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
