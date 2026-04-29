"""
Parallel Executor for Product Lifecycle Orchestrator.

Enables parallel execution of independent phases using topological sorting
and thread pool execution.
"""
from __future__ import annotations
from typing import List, Dict, Set, Tuple
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class ParallelExecutor:
    """
    Executes independent phases in parallel using dependency graph analysis.

    Features:
      - Builds dependency graph from phase definitions
      - Uses topological sort to identify parallel execution groups
      - Executes phases in parallel using ThreadPoolExecutor
      - Thread-safe checkpoint updates
    """

    def __init__(self, phases: List[dict]):
        """
        Initialize ParallelExecutor with phase definitions.

        Args:
            phases: List of PhaseDefinition dicts
        """
        self.phases = phases
        self.phase_map: Dict[str, dict] = {p["id"]: p for p in phases}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.reverse_graph: Dict[str, Set[str]] = {}

        # Build dependency graphs
        self._build_dependency_graph()

    # -------------------------------------------------------------------------
    # Dependency Graph Construction
    # -------------------------------------------------------------------------

    def _build_dependency_graph(self):
        """Build forward and reverse dependency graphs."""
        # Initialize graphs
        for phase in self.phases:
            phase_id = phase["id"]
            self.dependency_graph[phase_id] = set()
            self.reverse_graph[phase_id] = set()

        # Add edges
        for phase in self.phases:
            phase_id = phase["id"]
            depends_on = phase.get("depends_on", [])

            # Forward graph: phase -> phases it depends on
            self.dependency_graph[phase_id].update(depends_on)

            # Reverse graph: phase -> phases that depend on it
            for dep_id in depends_on:
                if dep_id in self.reverse_graph:
                    self.reverse_graph[dep_id].add(phase_id)

    def get_dependencies(self, phase_id: str) -> Set[str]:
        """Get phases that this phase depends on."""
        return self.dependency_graph.get(phase_id, set())

    def get_dependents(self, phase_id: str) -> Set[str]:
        """Get phases that depend on this phase."""
        return self.reverse_graph.get(phase_id, set())

    # -------------------------------------------------------------------------
    # Topological Sort
    # -------------------------------------------------------------------------

    def topological_sort(self, start_phases: List[str] = None) -> List[List[str]]:
        """
        Perform topological sort to identify parallel execution groups.

        Returns groups of phases that can be executed in parallel.
        Each group contains phases with no dependencies on each other.

        Args:
            start_phases: Optional list of starting phases (default: all phases)

        Returns:
            List of phase groups, where each group can be executed in parallel.
            Groups are ordered by dependency (group 0 must complete before group 1, etc.)

        Example:
            >>> executor = ParallelExecutor(phases)
            >>> groups = executor.topological_sort()
            >>> for group in groups:
            ...     print(f"Parallel group: {group}")
            ["phase-2-init"]
            ["phase-3-draft-prd"]
            ["phase-4-product-spec"]
        """
        if start_phases is None:
            # Start with all phases
            phases_to_process = set(self.phase_map.keys())
        else:
            # Start with specified phases and their dependents
            phases_to_process = set(start_phases)
            queue = deque(start_phases)

            while queue:
                phase_id = queue.popleft()
                for dependent in self.get_dependents(phase_id):
                    if dependent not in phases_to_process:
                        phases_to_process.add(dependent)
                        queue.append(dependent)

        # Kahn's algorithm for topological sort with level tracking
        in_degree = {}
        for phase_id in phases_to_process:
            # Count dependencies within the subset
            deps = self.get_dependencies(phase_id) & phases_to_process
            in_degree[phase_id] = len(deps)

        # Group phases by their level (parallel execution groups)
        groups = []
        remaining = set(phases_to_process)

        while remaining:
            # Find all phases with in_degree 0 (no unmet dependencies)
            current_group = [
                phase_id for phase_id in remaining
                if in_degree[phase_id] == 0
            ]

            if not current_group:
                # Circular dependency detected
                raise ValueError(
                    f"Circular dependency detected among phases: {remaining}"
                )

            # Add current group to result
            groups.append(sorted(current_group))  # Sort for deterministic order

            # Remove processed phases and update in_degree
            for phase_id in current_group:
                remaining.remove(phase_id)
                for dependent in self.get_dependents(phase_id):
                    if dependent in remaining:
                        in_degree[dependent] -= 1

        return groups

    def get_parallel_groups(self, intent: str = None) -> List[List[str]]:
        """
        Get parallel execution groups for a specific intent.

        Args:
            intent: Filter phases by intent trigger (optional)

        Returns:
            List of parallel execution groups
        """
        # Filter phases by intent if specified
        if intent:
            relevant_phases = [
                p["id"] for p in self.phases
                if intent in p.get("intent_triggers", []) or "*" in p.get("intent_triggers", [])
            ]
            return self.topological_sort(relevant_phases)
        else:
            return self.topological_sort()

    # -------------------------------------------------------------------------
    # Parallel Execution
    # -------------------------------------------------------------------------

    def execute_parallel(
        self,
        phase_group: List[str],
        executor_func,
        max_workers: int = 4
    ) -> Dict[str, dict]:
        """
        Execute a group of phases in parallel.

        Args:
            phase_group: List of phase IDs to execute in parallel
            executor_func: Function to execute for each phase (phase_id) -> result
            max_workers: Maximum number of parallel workers

        Returns:
            Dict mapping phase_id to execution result
        """
        results = {}

        if len(phase_group) == 1:
            # Single phase, no need for parallel execution
            phase_id = phase_group[0]
            results[phase_id] = executor_func(phase_id)
        else:
            # Multiple phases, execute in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all phases
                future_to_phase = {
                    executor.submit(executor_func, phase_id): phase_id
                    for phase_id in phase_group
                }

                # Collect results
                for future in as_completed(future_to_phase):
                    phase_id = future_to_phase[future]
                    try:
                        results[phase_id] = future.result()
                    except Exception as e:
                        results[phase_id] = {
                            "status": "failed",
                            "error": str(e)
                        }

        return results

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def is_parallelizable(self, phase_id: str, completed_phases: Set[str]) -> bool:
        """
        Check if a phase can be executed (all dependencies met).

        Args:
            phase_id: Phase ID to check
            completed_phases: Set of completed phase IDs

        Returns:
            True if all dependencies are satisfied
        """
        dependencies = self.get_dependencies(phase_id)
        return dependencies.issubset(completed_phases)

    def get_ready_phases(self, completed_phases: Set[str]) -> List[str]:
        """
        Get all phases that are ready to execute (dependencies met).

        Args:
            completed_phases: Set of completed phase IDs

        Returns:
            List of phase IDs ready for execution
        """
        ready = []
        for phase_id, deps in self.dependency_graph.items():
            if phase_id not in completed_phases and deps.issubset(completed_phases):
                ready.append(phase_id)
        return sorted(ready)

    def visualize_dependency_graph(self) -> str:
        """
        Generate ASCII visualization of dependency graph.

        Returns:
            ASCII art representation of the graph
        """
        lines = ["Dependency Graph:", "=" * 50]

        for phase_id in sorted(self.phase_map.keys()):
            deps = self.get_dependencies(phase_id)
            if deps:
                lines.append(f"{phase_id} -> {', '.join(sorted(deps))}")
            else:
                lines.append(f"{phase_id} -> (no dependencies)")

        return "\n".join(lines)
