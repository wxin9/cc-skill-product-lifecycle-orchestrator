"""
Task registry — unified task management with sequential IDs and iteration gate checks.

Task ID format:
  PRD-NNN          Product requirement tasks
  ARCH-NNN         Architecture tasks
  ITR-N.CHK-NNN    Iteration check/setup tasks
  ITR-N.DEV-NNN    Iteration development tasks
  ITR-N.TST-NNN    Iteration test tasks (with test_case_ref)

Storage: .lifecycle/tasks.json  (global registry)
         .lifecycle/iter-{n}/tasks.json  (per-iteration view, auto-synced)

Usage:
  python scripts/core/task_registry.py create --category prd --title "Define user roles"
  python scripts/core/task_registry.py update --id PRD-001 --status done
  python scripts/core/task_registry.py gate --iteration 1
  python scripts/core/task_registry.py list [--iteration N] [--status todo|done] [--type dev]
"""
from __future__ import annotations
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

VALID_CATEGORIES = {"prd", "arch", "check", "dev", "test"}
VALID_STATUSES = {"todo", "in_progress", "done", "blocked"}

CATEGORY_PREFIX = {
    "prd": "PRD",
    "arch": "ARCH",
    "check": "CHK",
    "dev": "DEV",
    "test": "TST",
}


# --------------------------------------------------------------------------
# Storage helpers
# --------------------------------------------------------------------------

def _registry_path(project_root: str) -> Path:
    return Path(project_root) / ".lifecycle" / "tasks.json"


def _iter_tasks_path(project_root: str, iteration: int) -> Path:
    return Path(project_root) / ".lifecycle" / f"iter-{iteration}" / "tasks.json"


def _load_registry(project_root: str) -> dict:
    p = _registry_path(project_root)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"tasks": [], "counters": {}}


def _save_registry(project_root: str, registry: dict) -> None:
    p = _registry_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_iter_view(project_root: str, registry: dict, iteration: int) -> None:
    """Write a per-iteration view of tasks to .lifecycle/iter-N/tasks.json."""
    iter_tasks = [t for t in registry["tasks"] if t.get("iteration") == iteration]
    p = _iter_tasks_path(project_root, iteration)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"iteration": iteration, "tasks": iter_tasks}, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# ID generation
# --------------------------------------------------------------------------

def _next_id(registry: dict, category: str, iteration: Optional[int]) -> str:
    counters = registry.setdefault("counters", {})

    if category in ("check", "dev", "test"):
        if iteration is None:
            raise ValueError(f"Iteration number required for category '{category}'")
        key = f"ITR-{iteration}.{CATEGORY_PREFIX[category]}"
    else:
        key = CATEGORY_PREFIX[category]

    n = counters.get(key, 0) + 1
    counters[key] = n

    if category in ("check", "dev", "test"):
        return f"ITR-{iteration}.{CATEGORY_PREFIX[category]}-{n:03d}"
    else:
        return f"{CATEGORY_PREFIX[category]}-{n:03d}"


# --------------------------------------------------------------------------
# Public API: TaskRegistry class
# --------------------------------------------------------------------------

class TaskRegistry:
    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def create_task(
        self,
        category: str,
        title: str,
        description: str = "",
        iteration: Optional[int] = None,
        test_case_ref: Optional[str] = None,
        blocked_by: Optional[List[str]] = None,
    ) -> str:
        """Create a task and return its ID."""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Valid: {VALID_CATEGORIES}")

        registry = _load_registry(self.project_root)
        task_id = _next_id(registry, category, iteration)
        now = datetime.now(timezone.utc).isoformat()

        task = {
            "id": task_id,
            "type": category,
            "title": title,
            "description": description,
            "status": "todo",
            "iteration": iteration,
            "test_case_ref": test_case_ref,
            "created_at": now,
            "updated_at": now,
            "blocked_by": blocked_by or [],
        }
        registry["tasks"].append(task)
        _save_registry(self.project_root, registry)

        if iteration is not None:
            _sync_iter_view(self.project_root, registry, iteration)

        return task_id

    def update_status(self, task_id: str, status: str) -> bool:
        """Update a task's status. Returns True if task was found."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {VALID_STATUSES}")

        registry = _load_registry(self.project_root)
        for task in registry["tasks"]:
            if task["id"] == task_id:
                task["status"] = status
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_registry(self.project_root, registry)
                if task.get("iteration"):
                    _sync_iter_view(self.project_root, registry, task["iteration"])
                return True
        return False

    def check_iteration_gate(self, iteration: int) -> dict:
        """
        Check if all tasks in an iteration are done.
        Returns GateResult. Exits with code 1 if blocking tasks exist.
        """
        registry = _load_registry(self.project_root)
        iter_tasks = [t for t in registry["tasks"] if t.get("iteration") == iteration]

        if not iter_tasks:
            return {
                "iteration": iteration,
                "passed": True,
                "total_tasks": 0,
                "done_tasks": 0,
                "blocking_tasks": [],
            }

        blocking = [t for t in iter_tasks if t["status"] not in ("done",)]
        done_count = len(iter_tasks) - len(blocking)

        return {
            "iteration": iteration,
            "passed": len(blocking) == 0,
            "total_tasks": len(iter_tasks),
            "done_tasks": done_count,
            "blocking_tasks": blocking,
        }

    def list_tasks(
        self,
        iteration: Optional[int] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[dict]:
        registry = _load_registry(self.project_root)
        tasks = registry["tasks"]
        if iteration is not None:
            tasks = [t for t in tasks if t.get("iteration") == iteration]
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        if task_type:
            tasks = [t for t in tasks if t["type"] == task_type]
        return tasks

    def get_task(self, task_id: str) -> Optional[dict]:
        registry = _load_registry(self.project_root)
        for task in registry["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def get_stats(self) -> dict:
        registry = _load_registry(self.project_root)
        tasks = registry["tasks"]
        by_status = {}
        by_type = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
            by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        return {
            "total": len(tasks),
            "by_status": by_status,
            "by_type": by_type,
        }

    def reset_iteration_gate(self, iteration: int) -> None:
        """Mark all non-done tasks in iteration as 'todo' to reset gate state."""
        registry = _load_registry(self.project_root)
        for task in registry["tasks"]:
            if task.get("iteration") == iteration and task["status"] == "blocked":
                task["status"] = "todo"
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_registry(self.project_root, registry)
        _sync_iter_view(self.project_root, registry, iteration)

    def move_task_to_iteration(self, task_id: str, new_iteration: int) -> bool:
        """Move a task from one iteration to another."""
        registry = _load_registry(self.project_root)
        for task in registry["tasks"]:
            if task["id"] == task_id:
                old_iter = task.get("iteration")
                task["iteration"] = new_iteration
                # Regenerate ID for new iteration
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_registry(self.project_root, registry)
                if old_iter:
                    _sync_iter_view(self.project_root, registry, old_iter)
                _sync_iter_view(self.project_root, registry, new_iteration)
                return True
        return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_gate_result(result: dict) -> None:
    status = "✓ PASSED" if result["passed"] else "✗ BLOCKED"
    print(f"\n迭代 {result['iteration']} 门控: {status}")
    print(f"  总任务: {result['total_tasks']}  已完成: {result['done_tasks']}")
    if result["blocking_tasks"]:
        print("\n  阻塞任务（未完成）：")
        for t in result["blocking_tasks"]:
            print(f"    [{t['status'].upper():12s}] {t['id']}  {t['title']}")
    print()


def _print_tasks(tasks: List[dict]) -> None:
    if not tasks:
        print("  (无任务)")
        return
    for t in tasks:
        ref = f" → {t['test_case_ref']}" if t.get("test_case_ref") else ""
        print(f"  [{t['status'].upper():11s}] {t['id']:20s} {t['title']}{ref}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product lifecycle task registry")
    parser.add_argument("--root", default=".", help="Project root directory")
    sub = parser.add_subparsers(dest="cmd")

    # create
    cp = sub.add_parser("create", help="Create a task")
    cp.add_argument("--category", required=True, choices=list(VALID_CATEGORIES))
    cp.add_argument("--title", required=True)
    cp.add_argument("--description", default="")
    cp.add_argument("--iteration", type=int)
    cp.add_argument("--test-case-ref")

    # update
    up = sub.add_parser("update", help="Update task status")
    up.add_argument("--id", required=True, dest="task_id")
    up.add_argument("--status", required=True, choices=list(VALID_STATUSES))

    # gate
    gp = sub.add_parser("gate", help="Check iteration gate")
    gp.add_argument("--iteration", required=True, type=int)

    # list
    lp = sub.add_parser("list", help="List tasks")
    lp.add_argument("--iteration", type=int)
    lp.add_argument("--status")
    lp.add_argument("--type", dest="task_type")

    # stats
    sub.add_parser("stats", help="Show task statistics")

    args = parser.parse_args()
    reg = TaskRegistry(args.root)

    if args.cmd == "create":
        tid = reg.create_task(
            args.category,
            args.title,
            args.description,
            args.iteration,
            args.test_case_ref,
        )
        print(f"✓ 创建任务: {tid}")

    elif args.cmd == "update":
        ok = reg.update_status(args.task_id, args.status)
        if ok:
            print(f"✓ {args.task_id} → {args.status}")
        else:
            print(f"✗ 任务未找到: {args.task_id}")
            sys.exit(1)

    elif args.cmd == "gate":
        result = reg.check_iteration_gate(args.iteration)
        _print_gate_result(result)
        sys.exit(0 if result["passed"] else 1)

    elif args.cmd == "list":
        tasks = reg.list_tasks(
            iteration=getattr(args, "iteration", None),
            status=getattr(args, "status", None),
            task_type=getattr(args, "task_type", None),
        )
        print(f"\n任务列表 ({len(tasks)} 条):")
        _print_tasks(tasks)

    elif args.cmd == "stats":
        stats = reg.get_stats()
        print(f"\n任务统计: 总计 {stats['total']}")
        print("  按状态:", stats["by_status"])
        print("  按类型:", stats["by_type"])

    else:
        parser.print_help()
        sys.exit(1)
