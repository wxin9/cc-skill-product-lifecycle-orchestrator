"""
Product Lifecycle Orchestrator CLI — v2.3

Breaking Changes:
  - All legacy commands (init, validate, draft, plan, etc.) have been removed
  - Use 'orchestrator run' to start a new workflow
  - Use 'orchestrator resume' to continue from a paused state
  - Use 'orchestrator rollback' to manage rollback points (v2.3)

Usage:
  python -m scripts orchestrator run --intent <intent> --user-input "<input>"
  python -m scripts orchestrator resume --from-phase <phase-id>
  python -m scripts orchestrator status
  python -m scripts orchestrator cancel
  python -m scripts orchestrator rollback --list
  python -m scripts orchestrator rollback --rollback-point-id <id>
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path


# --------------------------------------------------------------------------
# Project root detection
# --------------------------------------------------------------------------

def _find_project_root(start: str = ".") -> Path:
    """Walk up to find .lifecycle/ directory (project root marker)."""
    p = Path(start).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".lifecycle").exists():
            return parent
    print(f"[INFO] No .lifecycle/ directory found upstream, using cwd: {p}")
    return p  # fallback to cwd


def _resolve_project_root(args) -> Path:
    """Resolve explicit --project-root before falling back to cwd discovery."""
    project_root = getattr(args, "project_root", None)
    if project_root:
        return Path(project_root).expanduser().resolve()
    return _find_project_root()


# --------------------------------------------------------------------------
# Orchestrator commands
# --------------------------------------------------------------------------

def cmd_orchestrator_run(args) -> int:
    """Start orchestration workflow."""
    from scripts.core.orchestrator import Orchestrator

    root = _resolve_project_root(args)
    orch = Orchestrator(root)

    if getattr(args, 'from_phase', None):
        from scripts.core.phases import get_phase_by_id, PHASES
        if not get_phase_by_id(args.from_phase):
            valid_ids = ", ".join(p["id"] for p in PHASES)
            print(f"[ERROR] Unknown phase ID: '{args.from_phase}'")
            print(f"  Valid phase IDs: {valid_ids}")
            return 1

    return orch.run(
        intent=args.intent,
        from_phase=args.from_phase,
        user_input=args.user_input
    )


def cmd_orchestrator_resume(args) -> int:
    """Resume orchestration from paused state."""
    from scripts.core.orchestrator import Orchestrator

    root = _resolve_project_root(args)
    orch = Orchestrator(root)

    if getattr(args, 'from_phase', None):
        from scripts.core.phases import get_phase_by_id, PHASES
        if not get_phase_by_id(args.from_phase):
            valid_ids = ", ".join(p["id"] for p in PHASES)
            print(f"[ERROR] Unknown phase ID: '{args.from_phase}'")
            print(f"  Valid phase IDs: {valid_ids}")
            return 1

    return orch.run(
        intent="resume",
        from_phase=args.from_phase,
        user_input=getattr(args, 'user_input', None)
    )


def cmd_orchestrator_status(args) -> int:
    """Show orchestration status."""
    from scripts.core.checkpoint_manager import CheckpointManager

    root = _resolve_project_root(args)

    # Check if project is initialized
    if not (root / ".lifecycle").exists():
        print("Project not initialized")
        return 1

    checkpoint_mgr = CheckpointManager(root)
    checkpoint = checkpoint_mgr.load()

    print("=== Product Lifecycle Orchestrator Status ===\n")
    print(f"Project: {checkpoint.get('project_name', 'Unknown')}")
    print(f"Intent: {checkpoint.get('intent', 'Unknown')}")
    print(f"Status: {checkpoint.get('status', 'Unknown')}")
    print(f"Current Phase: {checkpoint.get('current_phase', 'None')}")
    print(f"\nCompleted Phases ({len(checkpoint.get('completed_phases', []))}):")
    for phase_id in checkpoint.get('completed_phases', []):
        print(f"  ✓ {phase_id}")

    # Check for notification
    notification_file = root / ".lifecycle" / "notification.json"
    if notification_file.exists():
        import json
        try:
            notification = json.loads(notification_file.read_text(encoding="utf-8"))
            print(f"\n⚠ Active Notification:")
            print(f"  Type: {notification.get('type')}")
            print(f"  Phase: {notification.get('phase_name')}")
            print(f"  Message: {notification.get('message')}")
            if notification.get('detail'):
                print(f"  Detail: {notification.get('detail')}")
        except (json.JSONDecodeError, OSError):
            pass

    return 0


def cmd_orchestrator_cancel(args) -> int:
    """Cancel orchestration workflow."""
    from scripts.core.checkpoint_manager import CheckpointManager

    root = _resolve_project_root(args)
    checkpoint_mgr = CheckpointManager(root)
    checkpoint = checkpoint_mgr.load()

    checkpoint["status"] = "cancelled"
    checkpoint["current_phase"] = None
    checkpoint["completed_phases"] = []
    checkpoint["phase_data"] = {}
    checkpoint_mgr.save(checkpoint, immediate=True)
    checkpoint_mgr.clear_notification()

    print("✓ Workflow cancelled")
    return 0


def cmd_orchestrator_rollback(args) -> int:
    """Manage rollback points (v2.3)."""
    from scripts.core.orchestrator import Orchestrator

    root = _resolve_project_root(args)
    orch = Orchestrator(root)

    if args.list:
        # List rollback points
        rollback_points = orch.list_rollback_points()

        if not rollback_points:
            print("No rollback points available")
            return 0

        print("=== Available Rollback Points ===\n")
        for rp in rollback_points:
            print(f"ID: {rp['id']}")
            print(f"  Phase: {rp['phase_id']}")
            print(f"  Timestamp: {rp['timestamp']}")
            print(f"  Description: {rp['description']}")
            print()

        return 0

    elif args.rollback_point_id:
        # Rollback to specific point
        success = orch.rollback_to(args.rollback_point_id)

        if success:
            print(f"\n✓ Successfully rolled back to {args.rollback_point_id}")
            print("You can now resume with: ./orchestrator resume")
            return 0
        else:
            print(f"\n✗ Failed to rollback to {args.rollback_point_id}")
            return 1

    else:
        print("Error: Must specify either --list or --rollback-point-id")
        return 1


# --------------------------------------------------------------------------
# CLI Entry Point
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="python -m scripts",
        description="Product Lifecycle Orchestrator v2.3"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # orchestrator command
    orch_parser = subparsers.add_parser("orchestrator", help="Orchestration engine")
    orch_sub = orch_parser.add_subparsers(dest="orch_cmd", help="Orchestrator commands")

    # orchestrator run
    run_parser = orch_sub.add_parser("run", help="Start orchestration")
    # Collect all valid intents from phases.py dynamically
    from scripts.core.phases import PHASES
    _VALID_INTENTS = set()
    for phase in PHASES:
        for intent in phase.get("intent_triggers", []):
            if intent != "*":
                _VALID_INTENTS.add(intent)
    _VALID_INTENTS.update(["auto", "resume"])
    _VALID_INTENTS = sorted(_VALID_INTENTS)
    run_parser.add_argument(
        "--intent",
        required=False,
        default="auto",
        choices=_VALID_INTENTS,
        metavar="INTENT",
        help=f"User intent. Valid values: {', '.join(_VALID_INTENTS)}. Default: auto (inferred from --user-input)"
    )
    run_parser.add_argument("--user-input", help="Raw user input")
    run_parser.add_argument("--from-phase", help="Start from specific phase")
    run_parser.add_argument("--project-root", help="Project root where Docs/ and .lifecycle/ are read or written")

    # orchestrator resume
    resume_parser = orch_sub.add_parser("resume", help="Resume from paused state")
    resume_parser.add_argument("--from-phase", help="Resume from specific phase")
    resume_parser.add_argument("--user-input", help="User input context for placeholder replacement")
    resume_parser.add_argument("--project-root", help="Project root where Docs/ and .lifecycle/ are read or written")

    # orchestrator status
    status_parser = orch_sub.add_parser("status", help="Show orchestration status")
    status_parser.add_argument("--project-root", help="Project root where Docs/ and .lifecycle/ are read or written")

    # orchestrator cancel
    cancel_parser = orch_sub.add_parser("cancel", help="Cancel workflow")
    cancel_parser.add_argument("--project-root", help="Project root where Docs/ and .lifecycle/ are read or written")

    # orchestrator rollback (v2.3)
    rollback_parser = orch_sub.add_parser("rollback", help="Manage rollback points")
    rollback_parser.add_argument("--project-root", help="Project root where Docs/ and .lifecycle/ are read or written")
    rollback_group = rollback_parser.add_mutually_exclusive_group(required=True)
    rollback_group.add_argument("--list", action="store_true", help="List available rollback points")
    rollback_group.add_argument("--rollback-point-id", help="Rollback to specific point")

    args = parser.parse_args()

    # Route to command handlers
    if args.command == "orchestrator":
        if args.orch_cmd == "run":
            return cmd_orchestrator_run(args)
        elif args.orch_cmd == "resume":
            return cmd_orchestrator_resume(args)
        elif args.orch_cmd == "status":
            return cmd_orchestrator_status(args)
        elif args.orch_cmd == "cancel":
            return cmd_orchestrator_cancel(args)
        elif args.orch_cmd == "rollback":
            return cmd_orchestrator_rollback(args)
        else:
            orch_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
