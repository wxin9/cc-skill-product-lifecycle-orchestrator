"""
Product Lifecycle Orchestrator.

Orchestrates phase execution with state machine, interaction pauses,
and failure handling.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Literal, TypedDict

# Import new components
from scripts.core.phases import PHASES, PhaseDefinition, get_phase_by_id, get_phases_by_intent
from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.command_executor import CommandExecutor
from scripts.core.parallel_executor import ParallelExecutor


# ---------------------------------------------------------------------------
# Notification Types
# ---------------------------------------------------------------------------

class Notification(TypedDict, total=False):
    """Notification structure."""
    type: Literal["pause_for_user", "validation_failed", "dod_failed", "error"]
    phase_id: str
    phase_name: str
    message: str
    detail: Optional[str]
    timestamp: str
    actions: List[str]
    # Validation-failure enrichment fields (optional)
    score: int
    threshold: int
    issues: List[dict]
    suggestions: List[str]
    artifacts: List[str]
    expected_files: List[str]
    dod_results: List[dict]


# ---------------------------------------------------------------------------
# Orchestrator Class
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Product Lifecycle Orchestrator orchestration engine.

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
            0 = success or expected pause waiting for user input
            2 = failed (requires manual intervention)
        """
        # Auto-resolve intent from user_input when intent is "auto"
        if intent == "auto":
            if user_input:
                try:
                    from scripts.core.intent_resolver import IntentResolver
                    resolved_intents, explanation = IntentResolver.resolve(user_input)
                    if resolved_intents:
                        intent = resolved_intents[0]
                        print(f"[ORCHESTRATOR] Auto-resolved intent: '{intent}' ({explanation})")
                    else:
                        intent = "new-product"
                        print(f"[ORCHESTRATOR] Could not resolve intent from input, defaulting to 'new-product'")
                except Exception as e:
                    intent = "new-product"
                    print(f"[ORCHESTRATOR] Intent resolution error ({e}), defaulting to 'new-product'")
            else:
                intent = "new-product"
                print(f"[ORCHESTRATOR] No user_input provided for auto intent, defaulting to 'new-product'")

        # v2.2: Check if parallel execution is enabled
        import os
        parallel_enabled = os.environ.get("ORCHESTRATOR_PARALLEL", "0") == "1"

        # 1. Load or initialize checkpoint
        checkpoint = self.checkpoint_mgr.load()

        # Always update intent and user_input if provided
        if intent not in ["resume", "status"]:
            # Warn if overwriting an in-progress workflow
            existing_status = checkpoint.get("status")
            if existing_status in ["in_progress", "paused"]:
                print(f"[ORCHESTRATOR] ⚠ Workflow is currently '{existing_status}'. "
                      f"Running again will update intent to '{intent}' and continue from current phase.")
            checkpoint["intent"] = intent
            if user_input:
                checkpoint["user_input"] = user_input
            self.checkpoint_mgr.save(checkpoint)

        # Update user_input if provided on resume (for placeholder replacement)
        if intent == "resume" and user_input is not None:
            checkpoint["user_input"] = user_input
            self.checkpoint_mgr.save(checkpoint)

        # Initialize new workflow if needed
        if checkpoint.get("status") == "initialized":
            project_name = self.root.name
            self.checkpoint_mgr.init(project_name, intent, user_input or "")
            checkpoint = self.checkpoint_mgr.load()

        # Phase 0 (intent recognition) is resolved implicitly by the --intent flag.
        # Mark it as completed so Phase 1 (which depends on it) can proceed.
        if intent not in ["resume", "status"] and not self.checkpoint_mgr.is_phase_completed("phase-0-intent"):
            self.checkpoint_mgr.record_phase_complete(
                "phase-0-intent",
                {"auto_completed": True, "reason": "intent resolved from --intent flag", "intent": intent}
            )
            checkpoint = self.checkpoint_mgr.load()

        # Resume must continue the original workflow intent from checkpoint.
        # Treating "resume" as its own intent pulls every phase into the path,
        # including unrelated change phases.
        active_intent = checkpoint.get("intent", "new-product") if intent == "resume" else intent

        # 2. Determine starting phase
        if from_phase:
            start_phase_id = from_phase
        elif checkpoint.get("current_phase"):
            start_phase_id = checkpoint["current_phase"]
        else:
            # Resolve intent to get entry point
            start_phase_id = self._resolve_entry_point(active_intent, user_input)

        # 3. Build execution path
        if parallel_enabled:
            # v2.2: Use parallel execution groups
            execution_groups = self._build_parallel_execution_path(start_phase_id, active_intent)
            return self._execute_parallel_groups(execution_groups, checkpoint)
        else:
            # v2.0/v2.1: Sequential execution
            execution_path = self._build_execution_path(start_phase_id, active_intent)
            return self._execute_sequential(execution_path, checkpoint)

    # ------------------------------------------------------------------
    # Execution Methods
    # ------------------------------------------------------------------

    def _execute_sequential(self, execution_path: List[str], checkpoint: dict) -> int:
        """Execute phases sequentially (v2.0/v2.1 mode)."""
        for phase_id in execution_path:
            checkpoint = self.checkpoint_mgr.load()
            phase = get_phase_by_id(phase_id)
            if not phase:
                return self._fail(f"Unknown phase: {phase_id}")

            # Check dependencies (skip deps not in current execution path for change intents)
            if not self._check_dependencies(phase, relevant_phase_ids=set(execution_path)):
                return self._fail(f"Phase {phase_id} dependencies not satisfied: {phase['depends_on']}")

            # Record phase start
            self.checkpoint_mgr.record_phase_start(phase_id)

            # Auto-create rollback point before each phase (C4 fix)
            try:
                self.checkpoint_mgr.create_rollback_point(phase_id, f"Before {phase['name']}")
                self._trim_rollback_points(max_keep=5)
            except Exception:
                pass  # Rollback point creation is best-effort

            # Detect if this is a resume scenario (phase is currently paused)
            is_resuming = (
                checkpoint.get("phase_data", {}).get(phase_id, {}).get("pause_reason") is not None
                or (checkpoint.get("current_phase") == phase_id and checkpoint.get("status") == "paused")
            )

            # Execute phase
            result = self._execute_phase(phase, checkpoint, skip_pause=is_resuming)

            if result["status"] == "paused":
                # Interaction pause
                self.checkpoint_mgr.record_phase_paused(phase_id, result.get("reason"))
                self._notify_pause(phase, result.get("reason"))
                return 0

            elif result["status"] == "failed":
                # Failure handling
                self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))

                if phase["on_failure"] == "pause":
                    # Use dod_failed notification type for iteration gate phase
                    if phase_id == "phase-12-iter-exec":
                        self._notify_dod_failure(phase, result.get("error"), result.get("data"))
                    else:
                        self._notify_failure(phase, result.get("error"), result.get("data"))
                    return 2
                elif phase["on_failure"] == "retry":
                    # Retry logic
                    for attempt in range(phase["max_retries"]):
                        print(f"\n[ORCHESTRATOR] Retry attempt {attempt + 1}/{phase['max_retries']}")
                        result = self._execute_phase(phase, checkpoint)
                        if result["status"] == "completed":
                            break
                    else:
                        self._notify_failure(phase, "Max retries exhausted", None)
                        return 2
                elif phase["on_failure"] == "skip":
                    print(f"[ORCHESTRATOR] Skipping failed phase: {phase_id}")
                    continue

            # Phase completed
            self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))
            checkpoint = self.checkpoint_mgr.load()

            # Increment iteration counter only when iter-exec phase succeeds
            if phase_id == "phase-12-iter-exec" and result.get("status") == "completed":
                _cp = self.checkpoint_mgr.load()
                meta = _cp.setdefault("metadata", {})
                meta["current_iteration"] = meta.get("current_iteration", 1) + 1
                self.checkpoint_mgr.save(_cp)
                checkpoint = self.checkpoint_mgr.load()  # refresh in-memory copy

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
        if not groups:
            print("[WARN] No phases to execute in parallel path")
            cp = self.checkpoint_mgr.load()
            cp["status"] = "completed"
            self.checkpoint_mgr.save(cp, immediate=True)
            self.checkpoint_mgr.clear_notification()
            return 0

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
                    checkpoint = self.checkpoint_mgr.load()  # Reload for fresh state
                    result = self._execute_phase(phase, checkpoint)

                    if result["status"] == "failed":
                        self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))
                        self._notify_failure(phase, result.get("error"), result.get("data"))
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
                            self._notify_failure(phase, result.get("error"), result.get("data"))
                            return 2

            # Handle interaction phases (must be sequential)
            for phase_id in interaction_phases:
                phase = get_phase_by_id(phase_id)

                if not self._check_dependencies(phase):
                    return self._fail(f"Phase {phase_id} dependencies not satisfied")

                self.checkpoint_mgr.record_phase_start(phase_id)
                checkpoint = self.checkpoint_mgr.load()  # Reload for fresh state
                result = self._execute_phase(phase, checkpoint)

                if result["status"] == "paused":
                    self.checkpoint_mgr.record_phase_paused(phase_id, result.get("reason"))
                    self._notify_pause(phase, result.get("reason"))
                    return 0
                elif result["status"] == "failed":
                    self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))
                    self._notify_failure(phase, result.get("error"), result.get("data"))
                    return 2
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
        checkpoint: dict,
        skip_pause: bool = False
    ) -> dict:
        """
        Execute a single phase.

        Execution order:
          0. Evaluate condition (if any) — skip phase if condition is False
          1. Apply execution mode.
             - prepare_then_pause: command → pause → resume artifact validation.
             - pause_then_command: pause → resume command → validation.
             - auto_command: command → validation.
          2. Check interaction pause (if auto=False and pause_for set and not resuming)
          3. Artifact validation (if specified)
          4. Document validation (if specified)

        Args:
            phase: Phase definition
            checkpoint: Current checkpoint state
            skip_pause: If True, skip pause check (used when resuming from paused phase)

        Returns:
            {"status": "completed" | "paused" | "failed", "error": str | None, "data": dict | None}
        """
        phase_id = phase["id"]
        print(f"\n[ORCHESTRATOR] Executing Phase {phase['order']}: {phase['name']}")
        print(f"  Description: {phase['description']}")
        execution_mode = self._execution_mode(phase)

        # 0. Evaluate condition (M1 fix: ConditionEvaluator now wired in)
        if phase.get("condition"):
            try:
                from scripts.core.condition_evaluator import evaluate_condition
                if not evaluate_condition(phase["condition"], checkpoint):
                    print(f"  ⏭ Condition not met, skipping phase: {phase['condition']}")
                    return {
                        "status": "completed",
                        "error": None,
                        "data": {"skipped": True, "reason": "condition_not_met"}
                    }
            except Exception as e:
                print(f"  ⚠ Condition evaluation error (proceeding): {e}")

        if (
            execution_mode == "pause_then_command"
            and not phase["auto"]
            and phase["pause_for"]
            and not skip_pause
        ):
            return {
                "status": "paused",
                "reason": phase["pause_for"],
                "error": None,
                "data": None
            }

        # 1. Execute command when needed. For prepare_then_pause phases, the command
        # generated review material before the pause; on resume we validate the user's
        # artifact instead of regenerating and overwriting it.
        should_run_command = bool(phase["command"])
        if skip_pause and execution_mode == "prepare_then_pause":
            should_run_command = False

        if should_run_command:
            # Prepare command arguments
            cmd_args = dict(phase.get("command_args") or {})

            # Replace placeholders
            for key, value in cmd_args.items():
                if isinstance(value, str):
                    if value == "{project_name}":
                        cmd_args[key] = checkpoint.get("project_name", self.root.name)
                    elif value == "{user_description}":
                        cmd_args[key] = checkpoint.get("user_input", "")
                    elif value == "{intent}":
                        cmd_args[key] = checkpoint.get("intent", "new-product")
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

        # 2. Check if interaction pause is required (after command)
        if (
            execution_mode != "pause_then_command"
            and not phase["auto"]
            and phase["pause_for"]
            and not skip_pause
        ):
            return {
                "status": "paused",
                "reason": phase["pause_for"],
                "error": None,
                "data": None
            }

        # 3. Artifact validation (if specified)
        if phase["artifacts"]:
            validation = self._validate_artifacts(phase)
            if not validation["passed"]:
                error_msg = f"Artifact validation failed: {validation['failures']}"
                # For command=None phases (pure interaction), add exit guidance
                if phase["command"] is None:
                    artifact_list = ", ".join(a["path"] for a in phase["artifacts"])
                    error_msg += (
                        f"\n\nRequired files: {artifact_list}"
                        f"\nOptions:"
                        f"\n  1. Create the required files and run: ./orchestrator resume --from-phase {phase_id}"
                        f"\n  2. Cancel the workflow: ./orchestrator cancel"
                    )
                return {
                    "status": "failed",
                    "error": error_msg,
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

    def _execution_mode(self, phase: PhaseDefinition) -> str:
        """Return the phase execution mode."""
        explicit = phase.get("execution_mode")  # type: ignore[attr-defined]
        if explicit:
            return explicit
        if phase["auto"]:
            return "auto_command"
        if phase["pause_for"]:
            return "prepare_then_pause"
        return "auto_command"

    def _build_execution_path(self, start_phase_id: str, intent: str) -> List[str]:
        """
        Build execution path (phase sequence).

        Rules:
          1. Start from start_phase (if specified)
          2. Sort by order
          3. Only include intent-relevant phases
          4. Skip completed phases (unless change intent or paused phase)
        """
        # Get all relevant phases
        relevant_phases = get_phases_by_intent(intent)

        # Sort by order
        relevant_phases = sorted(relevant_phases, key=lambda p: p["order"])

        # Build path
        path = []
        checkpoint = self.checkpoint_mgr.load()
        completed = set(checkpoint.get("completed_phases", []))
        paused_phase = checkpoint.get("current_phase") if checkpoint.get("status") == "paused" else None

        # Track whether we've reached the start_phase
        reached_start = (start_phase_id is None)  # If no start specified, begin from start

        # Warn if user explicitly resumed to an already-completed phase
        if start_phase_id and start_phase_id in completed:
            next_phase = None
            for p in relevant_phases:
                if p["id"] == start_phase_id:
                    reached_start = True
                elif reached_start and p["id"] not in completed:
                    next_phase = p["id"]
                    break
            if next_phase:
                print(f"[ORCHESTRATOR] ⚠ Phase '{start_phase_id}' already completed. Resuming from '{next_phase}'.")
            else:
                print(f"[ORCHESTRATOR] ⚠ Phase '{start_phase_id}' already completed. All phases done.")

        for phase in relevant_phases:
            # Skip phases before start_phase_id
            if not reached_start:
                if phase["id"] == start_phase_id:
                    reached_start = True
                else:
                    continue  # Skip this phase

            # Change intents don't skip completed phases
            if intent in ["prd-change", "code-change", "test-failure", "bug-fix", "gap"]:
                path.append(phase["id"])
            elif phase["id"] == paused_phase:
                # Paused phase must be included (needs resume validation)
                path.append(phase["id"])
            elif phase["id"] not in completed:
                path.append(phase["id"])

        return path

    def _check_dependencies(self, phase: PhaseDefinition, relevant_phase_ids: set = None) -> bool:
        """Check if phase dependencies are satisfied.

        If relevant_phase_ids is provided (from execution_path), dependencies that are NOT
        in the current execution path are treated as optional — they pass if already completed,
        but don't block execution if not. This allows change intents (prd-change, code-change)
        to run on projects where some prerequisite phases were never part of their workflow.
        """
        for dep_id in phase["depends_on"]:
            # Skip deps outside current execution path (change intent scenario)
            if relevant_phase_ids and dep_id not in relevant_phase_ids:
                continue
            if not self.checkpoint_mgr.is_phase_completed(dep_id):
                return False
        return True

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
        """Send pause notification with artifact paths so the model knows what to create."""
        # Extract artifact paths for the model to know what files it should produce
        artifact_paths = [a["path"] for a in phase.get("artifacts", [])]

        notification: Notification = {
            "type": "pause_for_user",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
            "message": f"Phase {phase['name']} paused",
            "detail": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifact_paths,
            "expected_files": artifact_paths,
            "actions": [
                f"完成用户交互后，运行: ./orchestrator resume --from-phase {phase['id']}",
                f"取消流程: ./orchestrator cancel"
            ]
        }
        self._write_notification(notification)

    def _notify_failure(self, phase: PhaseDefinition, error: str, data: Optional[dict] = None):
        """Send failure notification, enriched with validator details when available."""
        notification: Notification = {
            "type": "validation_failed",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
            "message": f"Phase {phase['name']} failed",
            "detail": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions": [
                f"修复问题后，运行: ./orchestrator resume --from-phase {phase['id']}",
                f"查看详细日志: cat .lifecycle/notification.json"
            ]
        }
        # Enrich with validator result when available (Phase 4 PRD validation, Phase 7 ARCH validation)
        if data and isinstance(data, dict):
            if "score" in data:
                notification["score"] = data["score"]
                notification["threshold"] = 70
            if "issues" in data:
                notification["issues"] = data["issues"]
            if "suggestions" in data:
                notification["suggestions"] = data["suggestions"]
        self._write_notification(notification)

    def _notify_dod_failure(self, phase: PhaseDefinition, error: str, data: Optional[dict] = None):
        """Send DoD-specific failure notification with per-rule results."""
        dod_results = []
        if data and isinstance(data, dict):
            dod_results = data.get("dod_results", data.get("results", []))

        notification: Notification = {
            "type": "dod_failed",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
            "message": f"DoD check failed for {phase['name']}",
            "detail": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dod_results": dod_results,
            "actions": [
                f"修复 DoD 失败项后，运行: ./orchestrator resume --from-phase {phase['id']}",
                f"查看详细结果: cat .lifecycle/notification.json"
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
        # Print validator score and issues if available
        if "score" in notification:
            print(f"\nValidation Score: {notification['score']}/{notification.get('threshold', 70)} (threshold: {notification.get('threshold', 70)})")
        if notification.get("issues"):
            print("\nIssues:")
            for iss in notification["issues"]:
                icon = "✗" if iss.get("severity") == "error" else "⚠"
                print(f"  {icon} [{iss.get('field', '?')}] {iss.get('message', '')}")
        if notification.get("suggestions"):
            print("\nSuggestions:")
            for s in notification["suggestions"]:
                print(f"  • {s}")
        # Print artifact paths when pausing for user interaction
        if notification.get("artifacts"):
            print("\nExpected files to create:")
            for path in notification["artifacts"]:
                print(f"  📄 {path}")
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

    def _trim_rollback_points(self, max_keep: int = 5):
        """Keep only the most recent N rollback points, deleting older ones."""
        checkpoint = self.checkpoint_mgr.load()
        rollback_points = checkpoint.get("metadata", {}).get("rollback_points", [])
        if len(rollback_points) > max_keep:
            # Sort by timestamp, keep newest max_keep
            rollback_points.sort(key=lambda rp: rp.get("timestamp", ""), reverse=True)
            to_remove = rollback_points[max_keep:]
            rollback_points = rollback_points[:max_keep]
            # Update checkpoint
            checkpoint.setdefault("metadata", {})["rollback_points"] = rollback_points
            self.checkpoint_mgr.save(checkpoint)
            # Remove snapshot directories for trimmed points
            for rp in to_remove:
                # Use the snapshot_dir field stored in the rollback point
                snapshot_dir = rp.get("snapshot_dir")
                if snapshot_dir:
                    import shutil
                    snapshot_path = Path(snapshot_dir)
                    if snapshot_path.exists() and snapshot_path.is_dir():
                        shutil.rmtree(snapshot_path)

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
