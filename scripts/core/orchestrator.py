"""
Product-Lifecycle Orchestrator.

Orchestrates phase execution with state machine, interaction pauses,
and failure handling.
"""
from __future__ import annotations
import sys
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Literal, TypedDict

# Import new components
from scripts.core.phases import PHASES, PhaseDefinition, get_phase_by_id, get_phases_by_intent
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.intent_resolver import IntentResolver, IntentType
from scripts.core.command_executor import CommandExecutor
from scripts.core.parallel_executor import ParallelExecutor
from scripts.core.condition_evaluator import evaluate_condition


# ---------------------------------------------------------------------------
# Notification Types
# ---------------------------------------------------------------------------

class Notification(TypedDict):
    """Notification structure."""
    type: Literal["pause_for_user", "validation_failed", "dod_failed", "error"]
    phase_id: str
    phase_name: str
    message: str
    detail: Optional[str]
    timestamp: str
    actions: List[str]


# ---------------------------------------------------------------------------
# Orchestrator Class
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Product-Lifecycle orchestration engine.

    Responsibilities:
      1. Select execution path based on intent
      2. Execute phases in order, managing state transitions
      3. Pause at interaction points and notify model
      4. Handle failures (validation, DoD)
      5. Support resume from checkpoint
    """

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        self.checkpoint_mgr = CheckpointManager(self.root)
        self.command_executor = CommandExecutor(self.root)
        self.parallel_executor = ParallelExecutor(PHASES)  # v2.2: Parallel execution
        self.notification_file = self.root / ".lifecycle" / "notification.json"

    # ------------------------------------------------------------------
    # Main Entry: run
    # ------------------------------------------------------------------

    def run(
        self,
        intent: str,
        from_phase: Optional[str] = None,
        user_input: Optional[str] = None
    ) -> int:
        """
        Execute orchestration workflow.

        Args:
            intent: User intent (e.g., "new-product", "prd-change")
            from_phase: Resume from specific phase (None = start from beginning or checkpoint)
            user_input: Raw user input (for intent resolution)

        Returns:
            0 = success
            1 = paused waiting for user input
            2 = failed (requires manual intervention)
        """
        # v2.2: Check if parallel execution is enabled
        import os
        parallel_enabled = os.environ.get("ORCHESTRATOR_PARALLEL", "0") == "1"

        # 1. Load or initialize checkpoint
        checkpoint = self.checkpoint_mgr.load()

        # Always update intent and user_input if provided
        if intent not in ["resume", "status"]:
            checkpoint["intent"] = intent
            if user_input:
                checkpoint["user_input"] = user_input
            self.checkpoint_mgr.save(checkpoint)

        # Initialize new workflow if needed
        if checkpoint.get("status") == "initialized":
            project_name = self.root.name
            self.checkpoint_mgr.init(project_name, intent, user_input or "")
            checkpoint = self.checkpoint_mgr.load()

        # 2. Determine starting phase
        if from_phase:
            start_phase_id = from_phase
        elif checkpoint.get("current_phase"):
            start_phase_id = checkpoint["current_phase"]
        else:
            # Resolve intent to get entry point
            start_phase_id = self._resolve_entry_point(intent, user_input)

        # 3. Build execution path
        if parallel_enabled:
            # v2.2: Use parallel execution groups
            execution_groups = self._build_parallel_execution_path(start_phase_id, intent)
            return self._execute_parallel_groups(execution_groups, checkpoint)
        else:
            # v2.0/v2.1: Sequential execution
            execution_path = self._build_execution_path(start_phase_id, intent)
            return self._execute_sequential(execution_path, checkpoint)

    # ------------------------------------------------------------------
    # Execution Methods
    # ------------------------------------------------------------------

    def _execute_sequential(self, execution_path: List[str], checkpoint: dict) -> int:
        """Execute phases sequentially (v2.0/v2.1 mode)."""
        for phase_id in execution_path:
            phase = get_phase_by_id(phase_id)
            if not phase:
                return self._fail(f"Unknown phase: {phase_id}")

            # Check dependencies
            if not self._check_dependencies(phase):
                return self._fail(f"Phase {phase_id} dependencies not satisfied: {phase['depends_on']}")

            # Record phase start
            self.checkpoint_mgr.record_phase_start(phase_id)

            # Execute phase
            result = self._execute_phase(phase, checkpoint)

            if result["status"] == "paused":
                # Interaction pause
                self.checkpoint_mgr.record_phase_paused(phase_id, result.get("reason"))
                self._notify_pause(phase, result.get("reason"))
                return 1

            elif result["status"] == "failed":
                # Failure handling
                self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))

                if phase["on_failure"] == "pause":
                    self._notify_failure(phase, result.get("error"))
                    return 2
                elif phase["on_failure"] == "retry":
                    # Retry logic
                    for attempt in range(phase["max_retries"]):
                        print(f"\n[ORCHESTRATOR] Retry attempt {attempt + 1}/{phase['max_retries']}")
                        result = self._execute_phase(phase, checkpoint)
                        if result["status"] == "completed":
                            break
                    else:
                        self._notify_failure(phase, "Max retries exhausted")
                        return 2
                elif phase["on_failure"] == "skip":
                    print(f"[ORCHESTRATOR] Skipping failed phase: {phase_id}")
                    continue

            # Phase completed
            self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))

        # All phases completed
        checkpoint = self.checkpoint_mgr.load()
        checkpoint["status"] = "completed"
        self.checkpoint_mgr.save(checkpoint, immediate=True)  # Flush on completion
        self.checkpoint_mgr.clear_notification()

        print("\n[ORCHESTRATOR] ✓ All phases completed successfully")
        return 0

    def _build_parallel_execution_path(self, start_phase_id: str, intent: str) -> List[List[str]]:
        """Build parallel execution groups (v2.2)."""
        # Get parallel groups from ParallelExecutor
        groups = self.parallel_executor.get_parallel_groups(intent)

        # Filter out already completed phases
        checkpoint = self.checkpoint_mgr.load()
        completed = set(checkpoint.get("completed_phases", []))

        # Find groups that need to be executed
        filtered_groups = []
        start_found = False

        for group in groups:
            # Skip groups before start_phase
            if not start_found:
                if start_phase_id in group:
                    start_found = True
                else:
                    continue

            # Filter out completed phases from group
            pending = [pid for pid in group if pid not in completed]
            if pending:
                filtered_groups.append(pending)

        return filtered_groups

    def _execute_parallel_groups(self, groups: List[List[str]], checkpoint: dict) -> int:
        """Execute phase groups in parallel (v2.2)."""
        for group in groups:
            print(f"\n[ORCHESTRATOR] Executing parallel group: {group}")

            # Check if group has interaction phases
            interaction_phases = []
            auto_phases = []

            for phase_id in group:
                phase = get_phase_by_id(phase_id)
                if not phase:
                    return self._fail(f"Unknown phase: {phase_id}")

                if not phase["auto"] and phase["pause_for"]:
                    interaction_phases.append(phase_id)
                else:
                    auto_phases.append(phase_id)

            # Execute auto phases in parallel
            if auto_phases:
                if len(auto_phases) == 1:
                    # Single phase, execute directly
                    phase_id = auto_phases[0]
                    phase = get_phase_by_id(phase_id)

                    if not self._check_dependencies(phase):
                        return self._fail(f"Phase {phase_id} dependencies not satisfied")

                    self.checkpoint_mgr.record_phase_start(phase_id)
                    result = self._execute_phase(phase, checkpoint)

                    if result["status"] == "failed":
                        self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))
                        self._notify_failure(phase, result.get("error"))
                        return 2

                    self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))
                else:
                    # Multiple phases, execute in parallel
                    results = self.parallel_executor.execute_parallel(
                        auto_phases,
                        lambda pid: self._execute_phase_wrapper(pid, checkpoint)
                    )

                    # Check results
                    for phase_id, result in results.items():
                        if result["status"] == "failed":
                            phase = get_phase_by_id(phase_id)
                            self._notify_failure(phase, result.get("error"))
                            return 2

            # Handle interaction phases (must be sequential)
            for phase_id in interaction_phases:
                phase = get_phase_by_id(phase_id)

                if not self._check_dependencies(phase):
                    return self._fail(f"Phase {phase_id} dependencies not satisfied")

                self.checkpoint_mgr.record_phase_start(phase_id)
                result = self._execute_phase(phase, checkpoint)

                if result["status"] == "paused":
                    self.checkpoint_mgr.record_phase_paused(phase_id, result.get("reason"))
                    self._notify_pause(phase, result.get("reason"))
                    return 1
                elif result["status"] == "failed":
                    self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))
                    self._notify_failure(phase, result.get("error"))
                    return 2

                self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))

        # All phases completed
        checkpoint = self.checkpoint_mgr.load()
        checkpoint["status"] = "completed"
        self.checkpoint_mgr.save(checkpoint, immediate=True)
        self.checkpoint_mgr.clear_notification()

        print("\n[ORCHESTRATOR] ✓ All phases completed successfully")
        return 0

    def _execute_phase_wrapper(self, phase_id: str, checkpoint: dict) -> dict:
        """Wrapper for parallel phase execution."""
        phase = get_phase_by_id(phase_id)
        if not phase:
            return {"status": "failed", "error": f"Unknown phase: {phase_id}", "data": None}

        if not self._check_dependencies(phase):
            return {"status": "failed", "error": "Dependencies not satisfied", "data": None}

        self.checkpoint_mgr.record_phase_start(phase_id)
        result = self._execute_phase(phase, checkpoint)

        if result["status"] == "completed":
            self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))
        elif result["status"] == "failed":
            self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))

        return result

    def _execute_phase(
        self,
        phase: PhaseDefinition,
        checkpoint: dict
    ) -> dict:
        """
        Execute a single phase.

        Returns:
            {"status": "completed" | "paused" | "failed", "error": str | None, "data": dict | None}
        """
        phase_id = phase["id"]
        print(f"\n[ORCHESTRATOR] Executing Phase {phase['order']}: {phase['name']}")
        print(f"  Description: {phase['description']}")

        # 1. Check if interaction is required
        if not phase["auto"] and phase["pause_for"]:
            # Pause for user interaction
            return {
                "status": "paused",
                "reason": phase["pause_for"],
                "error": None,
                "data": None
            }

        # 2. Execute command (if specified)
        if phase["command"]:
            # Prepare command arguments
            cmd_args = phase.get("command_args") or {}

            # Replace placeholders
            for key, value in cmd_args.items():
                if isinstance(value, str):
                    if value == "{project_name}":
                        cmd_args[key] = checkpoint.get("project_name", self.root.name)
                    elif value == "{user_description}":
                        cmd_args[key] = checkpoint.get("user_input", "")
                    elif value == "{current_iteration}":
                        cmd_args[key] = str(checkpoint.get("metadata", {}).get("current_iteration", 1))
                    elif value == "{change_type}":
                        cmd_args[key] = checkpoint.get("intent", "prd")

            # Execute command
            print(f"  Executing command: {phase['command']}")
            result = self.command_executor.execute(phase["command"], cmd_args)

            if not result["success"]:
                return {
                    "status": "failed",
                    "error": result.get("error", "Command execution failed"),
                    "data": result.get("data")
                }

            print(f"  ✓ Command completed: {result['message']}")

        # 3. Artifact validation (if specified)
        if phase["artifacts"]:
            validation = self._validate_artifacts(phase)
            if not validation["passed"]:
                return {
                    "status": "failed",
                    "error": f"Artifact validation failed: {validation['failures']}",
                    "data": None
                }

        # 4. Document validation (if specified)
        if phase["validation_type"]:
            validation = self._validate_document(phase)
            if not validation["passed"]:
                return {
                    "status": "failed",
                    "error": f"Document validation failed: {validation['error']}",
                    "data": validation.get("data")
                }

        return {"status": "completed", "error": None, "data": None}

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _resolve_entry_point(self, intent: str, user_input: Optional[str]) -> str:
        """Resolve starting phase based on intent."""
        # Get phases triggered by this intent
        phases = get_phases_by_intent(intent)
        if not phases:
            return "phase-0-intent"

        # Find first incomplete phase
        for phase in sorted(phases, key=lambda p: p["order"]):
            if not self.checkpoint_mgr.is_phase_completed(phase["id"]):
                return phase["id"]

        # All phases complete, start from beginning
        return phases[0]["id"]

    def _build_execution_path(self, start_phase_id: str, intent: str) -> List[str]:
        """
        Build execution path (phase sequence).

        Rules:
          1. Start from start_phase
          2. Sort by order
          3. Only include intent-relevant phases
          4. Skip completed phases (unless change intent)
        """
        # Get all relevant phases
        relevant_phases = get_phases_by_intent(intent)

        # Sort by order
        relevant_phases = sorted(relevant_phases, key=lambda p: p["order"])

        # Build path
        path = []
        checkpoint = self.checkpoint_mgr.load()
        completed = set(checkpoint.get("completed_phases", []))

        for phase in relevant_phases:
            # Change intents don't skip completed phases
            if intent in ["prd-change", "code-change", "test-failure", "bug-fix", "gap"]:
                path.append(phase["id"])
            elif phase["id"] not in completed:
                path.append(phase["id"])

        return path

    def _check_dependencies(self, phase: PhaseDefinition) -> bool:
        """Check if phase dependencies are satisfied."""
        for dep_id in phase["depends_on"]:
            if not self.checkpoint_mgr.is_phase_completed(dep_id):
                return False
        return True

    def _run_command(self, command: str, args: Optional[dict], checkpoint: dict) -> int:
        """Execute lifecycle command via subprocess."""
        # Build command line
        cmd_parts = [sys.executable, "-m", "scripts", command]

        if args:
            for key, value in args.items():
                # Replace placeholders
                if isinstance(value, str):
                    if value == "{project_name}":
                        value = checkpoint.get("project_name", self.root.name)
                    elif value == "{user_description}":
                        value = checkpoint.get("user_input", "")
                    elif value == "{current_iteration}":
                        value = str(checkpoint.get("metadata", {}).get("current_iteration", 1))
                    elif value == "{change_type}":
                        value = checkpoint.get("intent", "prd")

                cmd_parts.append(f"--{key}")
                if value is not True:  # Handle flag arguments
                    cmd_parts.append(str(value))

        print(f"  Running: {' '.join(cmd_parts)}")

        # Execute
        result = subprocess.run(cmd_parts, cwd=str(self.root))
        return result.returncode

    def _validate_artifacts(self, phase: PhaseDefinition) -> dict:
        """Validate phase artifacts."""
        failures = []

        for artifact in phase["artifacts"]:
            artifact_path = self.root / artifact["path"]

            # Check existence
            if not artifact_path.exists():
                failures.append(f"Missing: {artifact['path']}")
                continue

            # Check size
            content = artifact_path.read_bytes()
            if len(content) < artifact["min_bytes"]:
                failures.append(
                    f"Too small: {artifact['path']} ({len(content)} < {artifact['min_bytes']} bytes)"
                )

        return {
            "passed": len(failures) == 0,
            "failures": failures
        }

    def _validate_document(self, phase: PhaseDefinition) -> dict:
        """Validate document using doc_validator."""
        # Import doc_validator
        try:
            from scripts.core.doc_validator import validate_document
        except ImportError:
            print("  ⚠ doc_validator not available, skipping document validation")
            return {"passed": True, "error": None}

        # Determine document path
        if phase["command_args"] and "doc" in phase["command_args"]:
            doc_path = self.root / phase["command_args"]["doc"]
        else:
            return {"passed": True, "error": None}

        if not doc_path.exists():
            return {"passed": False, "error": f"Document not found: {doc_path}"}

        # Validate
        doc_type = phase["validation_type"]
        result = validate_document(str(doc_path), doc_type)

        return {
            "passed": result.get("passed", False),
            "error": result.get("error") if not result.get("passed") else None,
            "data": result
        }

    # ------------------------------------------------------------------
    # Notification Mechanism
    # ------------------------------------------------------------------

    def _notify_pause(self, phase: PhaseDefinition, reason: str):
        """Send pause notification."""
        notification: Notification = {
            "type": "pause_for_user",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
            "message": f"Phase {phase['name']} paused",
            "detail": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions": [
                f"完成用户交互后，运行: python -m scripts orchestrator resume --from-phase {phase['id']}",
                f"取消流程: python -m scripts orchestrator cancel"
            ]
        }
        self._write_notification(notification)

    def _notify_failure(self, phase: PhaseDefinition, error: str):
        """Send failure notification."""
        notification: Notification = {
            "type": "validation_failed",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
            "message": f"Phase {phase['name']} failed",
            "detail": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions": [
                f"修复问题后，运行: python -m scripts orchestrator resume --from-phase {phase['id']}",
                f"查看详细日志: cat .lifecycle/notification.json"
            ]
        }
        self._write_notification(notification)

    def _write_notification(self, notification: Notification):
        """Write notification file and print to stdout."""
        self.notification_file.parent.mkdir(parents=True, exist_ok=True)
        self.notification_file.write_text(
            json.dumps(notification, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # Print to stdout for model
        print(f"\n{'='*70}")
        print(f"[ORCHESTRATOR] {notification['type'].upper()}")
        print(f"{'='*70}")
        print(f"Phase: {notification['phase_name']}")
        print(f"Message: {notification['message']}")
        if notification.get("detail"):
            print(f"Detail: {notification['detail']}")
        print("\nActions:")
        for action in notification["actions"]:
            print(f"  - {action}")
        print(f"{'='*70}\n")

    def _fail(self, message: str) -> int:
        """Quick failure."""
        print(f"\n[ORCHESTRATOR ERROR] {message}")
        return 2

    # ------------------------------------------------------------------
    # Rollback Mechanism (v2.2)
    # ------------------------------------------------------------------

    def create_rollback_point(self, phase_id: str, description: str = "") -> dict:
        """
        Create a rollback point for the current phase.

        Args:
            phase_id: Phase ID to create rollback point for
            description: Human-readable description

        Returns:
            Rollback point dictionary
        """
        return self.checkpoint_mgr.create_rollback_point(phase_id, description)

    def list_rollback_points(self) -> list:
        """List all available rollback points."""
        return self.checkpoint_mgr.list_rollback_points()

    def rollback_to(self, rollback_id: str) -> bool:
        """
        Rollback to a specific rollback point.

        Args:
            rollback_id: Rollback point ID

        Returns:
            True if rollback succeeded, False otherwise
        """
        return self.checkpoint_mgr.rollback_to(rollback_id)
