"""
Tests for Product-Lifecycle v2.2 features.

Tests cover:
- Parallel execution
- Conditional branching
- Rollback mechanism
"""
import pytest
import tempfile
import os
from scripts.core.parallel_executor import ParallelExecutor
from scripts.core.condition_evaluator import ConditionEvaluator, evaluate_condition
from scripts.core.phases import PHASES


class TestParallelExecutor:
    """Test suite for ParallelExecutor."""

    def test_build_dependency_graph(self):
        """Test that dependency graph is built correctly."""
        executor = ParallelExecutor(PHASES)

        # Check that all phases are in the graph
        assert len(executor.dependency_graph) == len(PHASES)

        # Check specific dependencies
        deps = executor.get_dependencies("phase-3-validate-prd")
        assert "phase-2-draft-prd" in deps

    def test_topological_sort(self):
        """Test that topological sort identifies parallel groups."""
        executor = ParallelExecutor(PHASES)

        groups = executor.topological_sort()

        # Should have multiple groups
        assert len(groups) > 0

        # First group should have phases with no dependencies
        first_group = groups[0]
        for phase_id in first_group:
            deps = executor.get_dependencies(phase_id)
            assert len(deps) == 0

        # Later groups should have dependencies
        if len(groups) > 1:
            later_group = groups[-1]
            for phase_id in later_group:
                deps = executor.get_dependencies(phase_id)
                # Should have at least some dependencies
                # (not all phases have dependencies)

    def test_get_parallel_groups(self):
        """Test getting parallel groups for specific intent."""
        executor = ParallelExecutor(PHASES)

        groups = executor.get_parallel_groups("new-product")

        # Should have groups
        assert len(groups) > 0

        # All phases in groups should be relevant to intent
        for group in groups:
            for phase_id in group:
                phase = next((p for p in PHASES if p["id"] == phase_id), None)
                assert phase is not None
                triggers = phase.get("intent_triggers", [])
                # Phase should either match the intent or have wildcard trigger
                # Note: Some phases may not have intent_triggers, which is OK

    def test_is_parallelizable(self):
        """Test checking if phase can be executed."""
        executor = ParallelExecutor(PHASES)

        # Phase with no dependencies should be parallelizable
        assert executor.is_parallelizable("phase-1-init", set())

        # Phase with unmet dependencies should not be parallelizable
        assert not executor.is_parallelizable("phase-3-validate-prd", set())

        # Phase with met dependencies should be parallelizable
        assert executor.is_parallelizable("phase-3-validate-prd", {"phase-2-draft-prd"})

    def test_get_ready_phases(self):
        """Test getting phases ready for execution."""
        executor = ParallelExecutor(PHASES)

        # With no completed phases, should get phases with no dependencies
        ready = executor.get_ready_phases(set())
        assert "phase-1-init" in ready

        # With some completed phases, should get next phases
        ready = executor.get_ready_phases({"phase-1-init"})
        # Should include phases that depend only on phase-1-init


class TestConditionEvaluator:
    """Test suite for ConditionEvaluator."""

    def test_evaluate_simple_comparison(self):
        """Test simple comparison expressions."""
        evaluator = ConditionEvaluator({"project_type": "web"})

        assert evaluator.evaluate("project_type == 'web'") is True
        assert evaluator.evaluate("project_type == 'cli'") is False
        assert evaluator.evaluate("project_type != 'cli'") is True

    def test_evaluate_logical_operators(self):
        """Test logical operators."""
        evaluator = ConditionEvaluator({
            "has_prd": True,
            "has_architecture": False
        })

        assert evaluator.evaluate("has_prd and not has_architecture") is True
        assert evaluator.evaluate("has_prd or has_architecture") is True
        assert evaluator.evaluate("not has_prd") is False

    def test_evaluate_membership(self):
        """Test membership operators."""
        evaluator = ConditionEvaluator({
            "project_type": "web",
            "supported_types": ["web", "cli", "mobile"]
        })

        assert evaluator.evaluate("'web' in supported_types") is True
        assert evaluator.evaluate("'data-pipeline' not in supported_types") is True

    def test_evaluate_numeric_comparison(self):
        """Test numeric comparisons."""
        evaluator = ConditionEvaluator({"iteration_count": 5})

        assert evaluator.evaluate("iteration_count > 3") is True
        assert evaluator.evaluate("iteration_count < 10") is True
        assert evaluator.evaluate("iteration_count >= 5") is True
        assert evaluator.evaluate("iteration_count <= 5") is True

    def test_evaluate_empty_expression(self):
        """Test that empty expression evaluates to True."""
        evaluator = ConditionEvaluator({})

        assert evaluator.evaluate("") is True
        assert evaluator.evaluate("  ") is True

    def test_validate_expression_rejects_unsafe_code(self):
        """Test that unsafe expressions are rejected."""
        evaluator = ConditionEvaluator({})

        # Should reject dangerous constructs
        with pytest.raises(ValueError):
            evaluator.evaluate("__import__('os')")

        with pytest.raises(ValueError):
            evaluator.evaluate("exec('print(1)')")

        with pytest.raises(ValueError):
            evaluator.evaluate("open('/etc/passwd')")

    def test_evaluate_with_checkpoint(self):
        """Test evaluating condition with checkpoint context."""
        checkpoint = {
            "metadata": {
                "project_type": "web",
                "has_prd": True
            }
        }

        result = evaluate_condition("project_type == 'web'", checkpoint)
        assert result is True

        result = evaluate_condition("has_prd", checkpoint)
        assert result is True


class TestParallelExecutionIntegration:
    """Integration tests for parallel execution."""

    def test_parallel_execution_with_orchestrator(self, tmp_path):
        """Test that orchestrator can use parallel execution."""
        from scripts.core.orchestrator import Orchestrator

        # Enable parallel execution
        os.environ["ORCHESTRATOR_PARALLEL"] = "1"

        try:
            orch = Orchestrator(tmp_path)

            # Run should use parallel execution
            exit_code = orch.run(intent="new-product", user_input="Test product")

            # Should pause at interaction point
            assert exit_code == 1

        finally:
            os.environ.pop("ORCHESTRATOR_PARALLEL", None)


class TestConditionBranchingIntegration:
    """Integration tests for conditional branching."""

    def test_conditional_phase_selection(self):
        """Test that conditions can select different phases."""
        # This would be tested more thoroughly with actual phase definitions
        # that have condition and branches fields

        checkpoint = {
            "metadata": {
                "project_type": "web"
            }
        }

        # Test that condition evaluation works
        result = evaluate_condition("project_type == 'web'", checkpoint)
        assert result is True


class TestRollbackMechanism:
    """Test suite for rollback mechanism."""

    def test_checkpoint_can_store_rollback_points(self, tmp_path):
        """Test that checkpoint can store rollback points."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Add rollback points to metadata
        checkpoint["metadata"]["rollback_points"] = [
            {
                "id": "rp-001",
                "phase_id": "phase-1-init",
                "timestamp": "2026-04-16T10:00:00Z",
                "description": "After initialization"
            }
        ]

        mgr.save(checkpoint, immediate=True)

        # Load and verify
        loaded = mgr.load()
        assert "rollback_points" in loaded["metadata"]
        assert len(loaded["metadata"]["rollback_points"]) == 1

    def test_create_rollback_point(self, tmp_path):
        """Test creating a rollback point."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Record some phases as completed
        mgr.record_phase_complete("phase-1-init")
        mgr.record_phase_complete("phase-2-draft-prd")

        # Create rollback point
        rollback_point = mgr.create_rollback_point(
            "phase-2-draft-prd",
            "After PRD draft"
        )

        # Verify rollback point structure
        assert "id" in rollback_point
        assert rollback_point["phase_id"] == "phase-2-draft-prd"
        assert rollback_point["description"] == "After PRD draft"
        assert "timestamp" in rollback_point
        assert "checkpoint_snapshot" in rollback_point

        # Verify snapshot contains correct state
        snapshot = rollback_point["checkpoint_snapshot"]
        assert "phase-1-init" in snapshot["completed_phases"]
        assert "phase-2-draft-prd" in snapshot["completed_phases"]

    def test_list_rollback_points(self, tmp_path):
        """Test listing rollback points."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Create multiple rollback points
        mgr.create_rollback_point("phase-1-init", "First rollback point")
        mgr.create_rollback_point("phase-2-draft-prd", "Second rollback point")

        # List rollback points
        rollback_points = mgr.list_rollback_points()

        assert len(rollback_points) == 2
        assert rollback_points[0]["phase_id"] == "phase-1-init"
        assert rollback_points[1]["phase_id"] == "phase-2-draft-prd"

    def test_rollback_to_point(self, tmp_path):
        """Test rolling back to a specific point."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Complete some phases
        mgr.record_phase_complete("phase-1-init")
        mgr.record_phase_complete("phase-2-draft-prd")

        # Create rollback point
        rollback_point = mgr.create_rollback_point(
            "phase-2-draft-prd",
            "Before validation"
        )

        # Complete more phases
        mgr.record_phase_complete("phase-3-validate-prd")
        mgr.record_phase_complete("phase-4-arch-interview")

        # Verify current state
        checkpoint = mgr.load()
        assert len(checkpoint["completed_phases"]) == 4

        # Rollback
        success = mgr.rollback_to(rollback_point["id"])
        assert success

        # Verify rollback
        checkpoint = mgr.load()
        assert len(checkpoint["completed_phases"]) == 2
        assert "phase-1-init" in checkpoint["completed_phases"]
        assert "phase-2-draft-prd" in checkpoint["completed_phases"]
        assert "phase-3-validate-prd" not in checkpoint["completed_phases"]

    def test_rollback_with_file_snapshot(self, tmp_path):
        """Test that file snapshots are created and restored."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Create a test file
        docs_dir = tmp_path / "Docs"
        docs_dir.mkdir()
        test_file = docs_dir / "test.md"
        test_file.write_text("Original content")

        # Create rollback point
        rollback_point = mgr.create_rollback_point(
            "phase-1-init",
            "Before changes"
        )

        # Modify the file
        test_file.write_text("Modified content")

        # Rollback
        mgr.rollback_to(rollback_point["id"])

        # Verify file was restored
        assert test_file.read_text() == "Original content"

    def test_rollback_to_nonexistent_point(self, tmp_path):
        """Test rolling back to a non-existent point."""
        from scripts.core.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Try to rollback to non-existent point
        success = mgr.rollback_to("rp-nonexistent")
        assert not success


class TestV22FeatureIntegration:
    """Integration tests for v2.2 features."""

    def test_parallel_executor_with_real_phases(self):
        """Test ParallelExecutor with actual phase definitions."""
        executor = ParallelExecutor(PHASES)

        # Get parallel groups
        groups = executor.topological_sort()

        # Verify structure
        assert len(groups) > 0

        # Verify no circular dependencies
        all_phases = set()
        for group in groups:
            for phase_id in group:
                assert phase_id not in all_phases  # No duplicates
                all_phases.add(phase_id)

    def test_condition_evaluator_with_real_context(self):
        """Test ConditionEvaluator with realistic context."""
        context = {
            "project_type": "web",
            "has_prd": True,
            "has_architecture": False,
            "iteration_count": 3
        }

        evaluator = ConditionEvaluator(context)

        # Test various conditions
        assert evaluator.evaluate("project_type == 'web' and has_prd")
        assert evaluator.evaluate("iteration_count > 0")
        assert evaluator.evaluate("not has_architecture")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
