#!/usr/bin/env python3
"""
Step Enforcer — portable step verification template for generated skills.

Copy this file to <your-skill>/scripts/step_enforcer.py and:
  1. Fill in the STEPS list below with your skill's step definitions.
  2. Add gate calls in your SKILL.md before each phase:
       python scripts/step_enforcer.py require <step-id>
  3. Record each step after completing it:
       python scripts/step_enforcer.py record <step-id>

Cancel protocol:
  If the user says "Cancel" or "取消" in conversation, the SKILL.md should
  instruct Claude to write a .skill-cancel flag file:
       touch .skill-cancel
  All subsequent require/record calls will detect this flag and exit(0)
  gracefully instead of enforcing steps.

Dependency: Python 3.8+ stdlib only. No external packages required.
Usage:
    python scripts/step_enforcer.py require <step-id>
    python scripts/step_enforcer.py record <step-id> [--data '{"key": "val"}']
    python scripts/step_enforcer.py status
    python scripts/step_enforcer.py cancel-check
    python scripts/step_enforcer.py reset <step-id>   # remove a checkpoint
"""

# =============================================================================
# CUSTOMIZATION: Replace this list with your skill's actual steps.
# Each step: {"id": str, "description": str, "required": bool}
# "required": True  → require/record will enforce this step
# "required": False → informational only (still tracked, but require won't fail)
# =============================================================================
STEPS = [
    # Phase 1: Project Initialization
    {"id": "project-initialized",   "description": "项目结构初始化完成（Docs/ + .lifecycle/）",     "required": True},
    # Phase 2: PRD
    {"id": "prd-written",           "description": "产品设计文档（PRD）初稿完成",                    "required": True},
    {"id": "prd-validated",         "description": "PRD 清晰度验证通过（score ≥ 70）",              "required": True},
    # Phase 4: Architecture
    {"id": "arch-interview-done",   "description": "架构访谈完成，用户预期已记录",                    "required": True},
    {"id": "arch-doc-written",      "description": "技术架构文档（ARCH.md）完成",                    "required": True},
    # Phase 5: Test Outline
    {"id": "test-outline-written",  "description": "主测试大纲（MASTER_OUTLINE.md）生成完成",        "required": True},
    # Phase 6: Iteration Planning
    {"id": "iterations-planned",    "description": "迭代计划完成，所有迭代通过 E2E 可测验证",         "required": True},
    # Phase 7: Iteration execution (N is a placeholder — actual IDs use iter-1, iter-2, etc.)
    {"id": "iter-1-tasks-created",  "description": "迭代 1 任务已创建（CHK/DEV/TST 编号）",          "required": False},
    {"id": "iter-1-tests-written",  "description": "迭代 1 测试用例已生成",                           "required": False},
    {"id": "iter-1-gate-passed",    "description": "迭代 1 门控验证通过（所有任务完成）",              "required": False},
    {"id": "iter-2-tasks-created",  "description": "迭代 2 任务已创建",                               "required": False},
    {"id": "iter-2-tests-written",  "description": "迭代 2 测试用例已生成",                           "required": False},
    {"id": "iter-2-gate-passed",    "description": "迭代 2 门控验证通过",                              "required": False},
    {"id": "iter-3-tasks-created",  "description": "迭代 3 任务已创建",                               "required": False},
    {"id": "iter-3-tests-written",  "description": "迭代 3 测试用例已生成",                           "required": False},
    {"id": "iter-3-gate-passed",    "description": "迭代 3 门控验证通过",                              "required": False},
    {"id": "iter-4-tasks-created",  "description": "迭代 4 任务已创建",                               "required": False},
    {"id": "iter-4-tests-written",  "description": "迭代 4 测试用例已生成",                           "required": False},
    {"id": "iter-4-gate-passed",    "description": "迭代 4 门控验证通过",                              "required": False},
    {"id": "iter-5-tasks-created",  "description": "迭代 5 任务已创建",                               "required": False},
    {"id": "iter-5-tests-written",  "description": "迭代 5 测试用例已生成",                           "required": False},
    {"id": "iter-5-gate-passed",    "description": "迭代 5 门控验证通过",                              "required": False},
    {"id": "iter-6-tasks-created",  "description": "迭代 6 任务已创建",                               "required": False},
    {"id": "iter-6-tests-written",  "description": "迭代 6 测试用例已生成",                           "required": False},
    {"id": "iter-6-gate-passed",    "description": "迭代 6 门控验证通过",                              "required": False},
]
# =============================================================================

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

CANCEL_FILE = Path(".lifecycle/.skill-cancel")
STEPS_DIR = Path(".lifecycle/steps")


def _step_file(step_id):
    # type: (str) -> Path
    return STEPS_DIR / "{}.json".format(step_id)


def _valid_ids():
    # type: () -> set
    return {s["id"] for s in STEPS}


def _is_required(step_id):
    # type: (str) -> bool
    for s in STEPS:
        if s["id"] == step_id:
            return s.get("required", True)
    return True  # unknown step → treat as required


def _check_cancel():
    # type: () -> None
    """If .skill-cancel exists, print a message and exit(0)."""
    if CANCEL_FILE.exists():
        print("[enforcer] Workflow cancelled by user. Exiting gracefully.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Public API (usable as a library)
# ---------------------------------------------------------------------------

def record(step_id, data=None):
    # type: (str, dict) -> Path
    """
    Record that a step has been completed.

    Creates a JSON checkpoint file under .skill-steps/.
    Returns the path of the created file.

    Raises:
        ValueError: If step_id is not in STEPS.
    """
    if step_id not in _valid_ids():
        raise ValueError("Unknown step '{}'. Valid IDs: {}".format(
            step_id, sorted(_valid_ids())
        ))

    STEPS_DIR.mkdir(exist_ok=True)
    checkpoint = {
        "step": step_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "data": data or {},
    }
    path = _step_file(step_id)
    path.write_text(json.dumps(checkpoint, indent=2))
    return path


def check(step_id):
    # type: (str) -> bool
    """Return True if the step checkpoint file exists."""
    return _step_file(step_id).exists()


def require(step_id):
    # type: (str) -> dict
    """
    Verify a step is complete. Exits with code 1 if not.

    Returns the checkpoint data dict on success.
    """
    _check_cancel()

    if not _is_required(step_id):
        return {}  # optional step — never blocks

    if not check(step_id):
        print("\n[enforcer] HALT: Required step '{}' has NOT been recorded.".format(step_id))
        print("  Expected: {}".format(_step_file(step_id)))
        print("\n  Complete this step, then record it:")
        print("    python scripts/step_enforcer.py record {}".format(step_id))
        sys.exit(1)

    try:
        return json.loads(_step_file(step_id).read_text())
    except (ValueError, OSError):
        return {}


def status():
    # type: () -> None
    """Print the completion status of all steps."""
    _check_cancel()

    print("[enforcer] Step Status")
    print("=" * 50)
    for step in STEPS:
        sid = step["id"]
        done = check(sid)
        req_label = "" if step.get("required", True) else " (optional)"
        if done:
            try:
                data = json.loads(_step_file(sid).read_text())
                ts = data.get("completed_at", "?")[:19].replace("T", " ")
            except (ValueError, OSError):
                ts = "?"
            print("  \u2713 {}{}  [{}]".format(sid, req_label, ts))
        else:
            print("  \u25cb {}{}".format(sid, req_label))

    total = len(STEPS)
    done_count = sum(1 for s in STEPS if check(s["id"]))
    print()
    print("Progress: {}/{} steps completed".format(done_count, total))
    if CANCEL_FILE.exists():
        print("(Workflow cancelled — .skill-cancel is set)")


def reset(step_id):
    # type: (str) -> None
    """Remove a step checkpoint (allows re-running that step)."""
    path = _step_file(step_id)
    if path.exists():
        path.unlink()
        print("[enforcer] Reset step: {}".format(step_id))
    else:
        print("[enforcer] Step '{}' was not recorded (nothing to reset).".format(step_id))


def cancel_check():
    # type: () -> None
    """
    Check for the cancel flag and exit(0) if set.

    Call this at the start of any long-running phase so a user-initiated
    cancel (touch .skill-cancel) is respected promptly.
    """
    _check_cancel()
    print("[enforcer] No cancel flag detected. Continuing.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "require":
        if len(sys.argv) < 3:
            print("Usage: step_enforcer.py require <step-id>")
            sys.exit(1)
        require(sys.argv[2])
        print("[enforcer] \u2713 Step '{}' verified.".format(sys.argv[2]))

    elif cmd == "record":
        if len(sys.argv) < 3:
            print("Usage: step_enforcer.py record <step-id> [--data '{...}']")
            sys.exit(1)
        step_id = sys.argv[2]
        data = {}
        if "--data" in sys.argv:
            idx = sys.argv.index("--data")
            if idx + 1 < len(sys.argv):
                try:
                    data = json.loads(sys.argv[idx + 1])
                except json.JSONDecodeError as e:
                    print("[enforcer] ERROR: --data is not valid JSON: {}".format(e))
                    sys.exit(1)
        try:
            path = record(step_id, data)
            print("[enforcer] \u2713 Recorded '{}' \u2192 {}".format(step_id, path))
        except ValueError as e:
            print("[enforcer] ERROR: {}".format(e))
            sys.exit(1)

    elif cmd == "status":
        status()

    elif cmd == "cancel-check":
        cancel_check()

    elif cmd == "reset":
        if len(sys.argv) < 3:
            print("Usage: step_enforcer.py reset <step-id>")
            sys.exit(1)
        reset(sys.argv[2])

    else:
        _usage()
        sys.exit(1)


def _usage():
    print("Usage: step_enforcer.py <command> [args]")
    print("Commands:")
    print("  require <step-id>               Fail (exit 1) if step not recorded")
    print("  record <step-id> [--data JSON]  Record step as completed")
    print("  status                          Show all step completions")
    print("  cancel-check                    Exit 0 if .skill-cancel exists")
    print("  reset <step-id>                 Remove a step checkpoint")
    print()
    print("Defined steps:")
    for s in STEPS:
        req = "required" if s.get("required", True) else "optional"
        print("  {:30s} {}  [{}]".format(s["id"], s["description"], req))


if __name__ == "__main__":
    main()
