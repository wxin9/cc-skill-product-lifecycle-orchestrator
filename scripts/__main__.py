"""
Product-Lifecycle Orchestrator CLI — v2.0

Breaking Changes:
  - All legacy commands (init, validate, draft, plan, etc.) have been removed
  - Use 'orchestrator run' to start a new workflow
  - Use 'orchestrator resume' to continue from a paused state
  - Use 'orchestrator rollback' to manage rollback points (v2.2)

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
    return p  # fallback to cwd


# --------------------------------------------------------------------------
# Orchestrator commands
# --------------------------------------------------------------------------

def cmd_orchestrator_run(args) -> int:
    """Start orchestration workflow."""
    from scripts.core.orchestrator import Orchestrator

    root = _find_project_root()
    orch = Orchestrator(root)

    return orch.run(
        intent=args.intent,
        from_phase=args.from_phase,
        user_input=args.user_input
    )


def cmd_orchestrator_resume(args) -> int:
    """Resume orchestration from paused state."""
    from scripts.core.orchestrator import Orchestrator

    root = _find_project_root()
    orch = Orchestrator(root)

    return orch.run(
        intent="resume",
        from_phase=args.from_phase
    )


def cmd_orchestrator_status(args) -> int:
    """Show orchestration status."""
    from scripts.core.checkpoint_manager import CheckpointManager

    root = _find_project_root()
    checkpoint_mgr = CheckpointManager(root)
    checkpoint = checkpoint_mgr.load()

    print("=== Product-Lifecycle Status ===\n")
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

    root = _find_project_root()
    checkpoint_mgr = CheckpointManager(root)
    checkpoint = checkpoint_mgr.load()

    checkpoint["status"] = "cancelled"
    checkpoint_mgr.save(checkpoint)
    checkpoint_mgr.clear_notification()

    print("✓ Workflow cancelled")
    return 0


def cmd_orchestrator_rollback(args) -> int:
    """Manage rollback points (v2.2)."""
    from scripts.core.orchestrator import Orchestrator

    root = _find_project_root()
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
            print("You can now resume with: python -m scripts orchestrator resume")
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
        description="Product-Lifecycle Orchestrator v2.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # orchestrator command
    orch_parser = subparsers.add_parser("orchestrator", help="Orchestration engine")
    orch_sub = orch_parser.add_subparsers(dest="orch_cmd", help="Orchestrator commands")

    # orchestrator run
    run_parser = orch_sub.add_parser("run", help="Start orchestration")
    run_parser.add_argument("--intent", required=True, help="User intent (e.g., new-product, prd-change)")
    run_parser.add_argument("--user-input", help="Raw user input")
    run_parser.add_argument("--from-phase", help="Start from specific phase")

    # orchestrator resume
    resume_parser = orch_sub.add_parser("resume", help="Resume from paused state")
    resume_parser.add_argument("--from-phase", help="Resume from specific phase")

    # orchestrator status
    status_parser = orch_sub.add_parser("status", help="Show orchestration status")

    # orchestrator cancel
    cancel_parser = orch_sub.add_parser("cancel", help="Cancel workflow")

    # orchestrator rollback (v2.2)
    rollback_parser = orch_sub.add_parser("rollback", help="Manage rollback points")
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
