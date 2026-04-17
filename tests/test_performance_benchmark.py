"""
Performance benchmark tests for Product-Lifecycle v2.1.

Tests verify:
- Checkpoint I/O reduction (target: ≥10x)
- Workflow execution time improvement
- Memory efficiency
"""
import pytest
import tempfile
import time
import os
from pathlib import Path
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.orchestrator import Orchestrator


class TestPerformanceBenchmark:
    """Performance benchmark tests."""

    def test_checkpoint_io_reduction(self, tmp_path):
        """
        Test that checkpoint caching reduces disk I/O.

        Target: ≥10x reduction in disk writes.
        """
        mgr = CheckpointManager(tmp_path)

        # Initialize checkpoint
        mgr.init("test-project", "new-product", "test input")

        # Get initial file modification time
        checkpoint_file = mgr.checkpoint_file
        initial_mtime = os.path.getmtime(checkpoint_file)

        # Perform multiple operations WITHOUT flush
        for i in range(10):
            mgr.record_phase_start(f"phase-{i}")
            mgr.record_phase_complete(f"phase-{i}")

        # File should NOT have been modified (deferred write)
        current_mtime = os.path.getmtime(checkpoint_file)
        assert current_mtime == initial_mtime, "File should not be modified during deferred writes"

        # Flush once
        mgr.flush()

        # File should be modified now
        final_mtime = os.path.getmtime(checkpoint_file)
        assert final_mtime > initial_mtime, "File should be modified after flush"

        # Result: 10 operations = 1 disk write (10x reduction)
        print(f"\n✓ I/O Reduction Test:")
        print(f"  Operations: 10 phase updates")
        print(f"  Disk writes: 1 (after flush)")
        print(f"  Reduction: 10x")

    def test_checkpoint_cache_performance(self, tmp_path):
        """
        Test that cache improves load performance.

        Target: Cache hits should be instant (no disk I/O).
        """
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Measure time for cached loads
        start_time = time.time()
        for _ in range(100):
            checkpoint = mgr.load()
        cached_duration = time.time() - start_time

        # Clear cache
        mgr._cache = None

        # Measure time for disk loads
        start_time = time.time()
        for _ in range(100):
            checkpoint = mgr.load()
        disk_duration = time.time() - start_time

        # Cached loads should be significantly faster
        speedup = disk_duration / cached_duration if cached_duration > 0 else 0

        print(f"\n✓ Cache Performance Test:")
        print(f"  Cached loads (100x): {cached_duration:.4f}s")
        print(f"  Disk loads (100x): {disk_duration:.4f}s")
        print(f"  Speedup: {speedup:.1f}x")

        # Cache should provide at least 2x speedup
        assert speedup >= 2.0, f"Expected ≥2x speedup, got {speedup:.1f}x"

    def test_orchestrator_execution_time(self, tmp_path):
        """
        Test orchestrator execution time improvement.

        Target: Workflow should complete in <1s for basic phases.
        """
        orch = Orchestrator(tmp_path)

        # Measure execution time
        start_time = time.time()
        exit_code = orch.run(intent="new-product", user_input="Test product")
        execution_time = time.time() - start_time

        print(f"\n✓ Orchestrator Execution Time:")
        print(f"  Execution time: {execution_time:.3f}s")
        print(f"  Exit code: {exit_code}")

        # Should complete quickly (<1s for basic phases)
        assert execution_time < 1.0, f"Execution took {execution_time:.3f}s (expected <1s)"

    def test_batch_operations_performance(self, tmp_path):
        """
        Test performance of batch operations.

        Target: Multiple operations should benefit from single flush.
        """
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Measure time for batch operations with deferred write
        start_time = time.time()
        for i in range(50):
            mgr.record_phase_start(f"phase-{i}")
            mgr.record_phase_complete(f"phase-{i}", {"data": f"test-{i}"})
        mgr.flush()
        batch_duration = time.time() - start_time

        print(f"\n✓ Batch Operations Performance:")
        print(f"  Operations: 100 (50 start + 50 complete)")
        print(f"  Time: {batch_duration:.4f}s")
        print(f"  Disk writes: 1 (after flush)")

        # Should complete quickly
        assert batch_duration < 0.1, f"Batch operations took {batch_duration:.4f}s (expected <0.1s)"

    def test_memory_efficiency(self, tmp_path):
        """
        Test memory efficiency of checkpoint cache.

        Target: Cache should not consume excessive memory.
        """
        import sys

        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.init("test-project", "new-product", "test input")

        # Measure checkpoint size in memory
        checkpoint_size = sys.getsizeof(checkpoint)

        # Add some data
        for i in range(10):
            mgr.record_phase_complete(f"phase-{i}", {"data": "x" * 100})

        checkpoint = mgr.load()
        updated_size = sys.getsizeof(checkpoint)

        print(f"\n✓ Memory Efficiency Test:")
        print(f"  Initial checkpoint size: {checkpoint_size} bytes")
        print(f"  Updated checkpoint size: {updated_size} bytes")
        print(f"  Growth: {updated_size - checkpoint_size} bytes")

        # Checkpoint should not grow excessively
        assert updated_size < 10000, f"Checkpoint size {updated_size} bytes (expected <10KB)"

    def test_concurrent_phase_updates(self, tmp_path):
        """
        Test performance of concurrent-like phase updates.

        Target: Multiple rapid updates should be handled efficiently.
        """
        mgr = CheckpointManager(tmp_path)
        mgr.init("test-project", "new-product", "test input")

        # Simulate rapid phase updates
        start_time = time.time()

        phases = [f"phase-{i}" for i in range(20)]
        for phase_id in phases:
            mgr.record_phase_start(phase_id)
            mgr.record_phase_complete(phase_id)

        duration = time.time() - start_time

        print(f"\n✓ Concurrent-like Updates Test:")
        print(f"  Phases: 20")
        print(f"  Time: {duration:.4f}s")
        print(f"  Average per phase: {duration/20*1000:.2f}ms")

        # Should be very fast
        assert duration < 0.05, f"20 phase updates took {duration:.4f}s (expected <0.05s)"


class TestRealWorldScenarios:
    """Real-world scenario performance tests."""

    def test_full_workflow_performance(self, tmp_path):
        """
        Test performance of full workflow execution.

        Simulates: new-product workflow with multiple phases.
        """
        orch = Orchestrator(tmp_path)

        # Measure full workflow execution
        start_time = time.time()

        # Run until first pause
        exit_code = orch.run(intent="new-product", user_input="Performance test product")

        # Record time
        workflow_time = time.time() - start_time

        # Check checkpoint
        mgr = CheckpointManager(tmp_path)
        checkpoint = mgr.load()

        print(f"\n✓ Full Workflow Performance:")
        print(f"  Workflow time: {workflow_time:.3f}s")
        print(f"  Completed phases: {len(checkpoint['completed_phases'])}")
        print(f"  Status: {checkpoint['status']}")

        # Should complete quickly
        assert workflow_time < 2.0, f"Workflow took {workflow_time:.3f}s (expected <2s)"
        assert len(checkpoint['completed_phases']) >= 1

    def test_resume_performance(self, tmp_path):
        """
        Test performance of resume operation.

        Simulates: resuming workflow from checkpoint.
        """
        orch = Orchestrator(tmp_path)

        # Initial run
        orch.run(intent="new-product", user_input="Test product")

        # Measure resume time
        start_time = time.time()
        exit_code = orch.run(intent="resume", from_phase="phase-2-draft-prd")
        resume_time = time.time() - start_time

        print(f"\n✓ Resume Performance:")
        print(f"  Resume time: {resume_time:.3f}s")
        print(f"  Exit code: {exit_code}")

        # Resume should be fast
        assert resume_time < 1.0, f"Resume took {resume_time:.3f}s (expected <1s)"


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([__file__, "-v", "-s"])
