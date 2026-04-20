"""
plan_format_normalizer.py — PLAN.md 格式规范化模块

在生成操作手册之前，确保每个 iter-N/PLAN.md 都符合
iteration_planner.write_iteration_plans() 写出的标准格式。

设计原则：
  - 格式不符合时，优先尝试修复，不静默降级
  - 实在无法自动修复的字段，明确报告哪些字段需要手动填写
  - 对已经符合格式的文件，调用后内容不变

标准 PLAN.md 格式（来自 iteration_planner.write_iteration_plans）：
  # 迭代 N：名称

  **目标：** 用户能够...
  **状态：** planned
  **关联功能：** F01, F02

  ## 端到端验收标准

  ### E2E-1: 描述
  - **入口点：** ...
  - **数据流：** ...
  - **测试用例：** TST-F01-S01

  ## 任务列表

  _（由 `./lifecycle task create` 动态生成）_
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 标准字段的正则模式
# ---------------------------------------------------------------------------

# 标题：# 迭代 N：名称  （N 可以是多位数）
_RE_TITLE = re.compile(r"^#\s+迭代\s+(\d+)[：:]\s*(.+)$", re.MULTILINE)

# **目标：** 内容
_RE_GOAL = re.compile(r"\*\*目标[：:]\*\*\s*(.+)")

# **状态：** 内容
_RE_STATUS = re.compile(r"\*\*状态[：:]\*\*\s*(.+)")

# **关联功能：** 内容
_RE_FEATURES = re.compile(r"\*\*关联功能[：:]\*\*\s*(.+)")

# ## 端到端验收标准 章节
_RE_E2E_SECTION = re.compile(r"^##\s+端到端验收标准", re.MULTILINE)

# ## 任务列表 章节
_RE_TASK_SECTION = re.compile(r"^##\s+任务列表", re.MULTILINE)


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def normalize_plan(plan_path: str | Path, iteration_n: Optional[int] = None) -> dict:
    """
    读取 PLAN.md，检查并修复格式，将结果覆盖写入原文件。

    参数：
      plan_path   — PLAN.md 的完整路径
      iteration_n — 迭代编号（可选，用于推断标题中的 N）

    返回：
    {
        "ok": bool,                    # True = 格式正确（或已修复）
        "fixed_fields": List[str],     # 已自动修复的字段
        "manual_required": List[str],  # 需要用户手动填写的字段（ok=False 时有值）
        "content": str,                # 规范化后的文件内容
        "error": str,                  # 错误信息（ok=False 时有值）
    }
    """
    plan_path = Path(plan_path)

    if not plan_path.exists():
        return _fail(f"文件不存在：{plan_path}", [])

    content = plan_path.read_text(encoding="utf-8", errors="replace")
    original = content
    fixed_fields: list[str] = []
    manual_required: list[str] = []

    # ── 1. 检查并修复标题 ──────────────────────────────────────────────────
    title_match = _RE_TITLE.search(content)
    if not title_match:
        # 尝试从文件名推断迭代号
        n = iteration_n
        if n is None:
            # 尝试从 plan_path 的父目录名推断：iter-3/PLAN.md → 3
            parent_name = plan_path.parent.name
            m = re.match(r"iter-(\d+)", parent_name)
            if m:
                n = int(m.group(1))

        if n is not None:
            # 在文件开头插入标题
            content = f"# 迭代 {n}：（待补充名称）\n\n" + content
            fixed_fields.append(f"title（插入占位标题 '# 迭代 {n}：（待补充名称）'）")
        else:
            manual_required.append("标题（格式：# 迭代 N：名称）")

    # ── 2. 检查并修复 **目标：** ────────────────────────────────────────────
    if not _RE_GOAL.search(content):
        # 在标题下方插入占位
        content = _insert_after_title(
            content,
            "\n**目标：** （待补充：请以「用户能够...」开头描述本迭代价值）\n"
        )
        fixed_fields.append("**目标：**（插入占位符，请修改为实际目标）")

    # ── 3. 检查并修复 **状态：** ────────────────────────────────────────────
    if not _RE_STATUS.search(content):
        content = _insert_after_goal(content, "**状态：** planned\n")
        fixed_fields.append("**状态：**（默认设为 planned）")

    # ── 4. 检查并修复 ## 端到端验收标准 ────────────────────────────────────
    if not _RE_E2E_SECTION.search(content):
        e2e_placeholder = (
            "\n## 端到端验收标准\n\n"
            "> ⚠ 本章节需要手动填写。请按以下格式描述每个验收标准：\n\n"
            "### E2E-1: （功能描述）\n"
            "- **入口点：** （UI 页面 / API 端点 / CLI 命令）\n"
            "- **数据流：** 用户输入 → 处理 → 存储 → 响应\n"
            "- **测试用例：** TST-F01-S01\n"
        )
        if _RE_TASK_SECTION.search(content):
            # 在任务列表之前插入
            content = _RE_TASK_SECTION.sub(e2e_placeholder + "\n## 任务列表", content, count=1)
        else:
            content += e2e_placeholder
        manual_required.append("## 端到端验收标准（已插入模板，需手动填写具体内容）")

    # ── 5. 检查并修复 ## 任务列表 ────────────────────────────────────────────
    if not _RE_TASK_SECTION.search(content):
        content += (
            "\n## 任务列表\n\n"
            "_（由 `./lifecycle task create` 动态生成）_\n"
        )
        fixed_fields.append("## 任务列表（插入标准占位符）")

    # ── 判断是否需要手动干预 ──────────────────────────────────────────────
    # 如果 **目标** 仍然是占位符内容，标记为需要手动填写
    goal_match = _RE_GOAL.search(content)
    if goal_match and "待补充" in goal_match.group(1):
        manual_required.append("**目标：**（需以「用户能够...」开头填写本迭代价值）")

    # 如果标题名称还是占位符
    title_match_new = _RE_TITLE.search(content)
    if title_match_new and "待补充名称" in title_match_new.group(2):
        manual_required.append("标题名称（请将「待补充名称」替换为真实的迭代名称）")

    # ── 写回文件（仅当内容有变化时）────────────────────────────────────────
    if content != original:
        plan_path.write_text(content, encoding="utf-8")

    if manual_required:
        return {
            "ok": False,
            "fixed_fields": fixed_fields,
            "manual_required": manual_required,
            "content": content,
            "error": (
                f"PLAN.md 格式不完整，以下字段需要手动填写：\n"
                + "\n".join(f"  - {f}" for f in manual_required)
                + f"\n文件路径：{plan_path}"
            ),
        }

    return {
        "ok": True,
        "fixed_fields": fixed_fields,
        "manual_required": [],
        "content": content,
        "error": "",
    }


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _fail(error: str, manual_required: list) -> dict:
    return {
        "ok": False,
        "fixed_fields": [],
        "manual_required": manual_required,
        "content": "",
        "error": error,
    }


def _insert_after_title(content: str, text: str) -> str:
    """在第一个 # 标题之后插入文本。"""
    m = re.search(r"^#[^\n]*\n", content, re.MULTILINE)
    if m:
        pos = m.end()
        return content[:pos] + text + content[pos:]
    return text + content


def _insert_after_goal(content: str, text: str) -> str:
    """在 **目标：** 行之后插入文本。"""
    m = _RE_GOAL.search(content)
    if m:
        end = content.index("\n", m.start()) + 1
        return content[:end] + text + content[end:]
    return content + "\n" + text


def _insert_before_section(content: str, section_re: re.Pattern, text: str) -> str:
    """在某个 ## 章节之前插入文本。"""
    m = section_re.search(content)
    if m:
        return content[:m.start()] + text + content[m.start():]
    return content + text


# ---------------------------------------------------------------------------
# 批量规范化：处理所有迭代的 PLAN.md
# ---------------------------------------------------------------------------

def normalize_all_plans(root: str | Path, max_iteration: int) -> dict:
    """
    对 iter-1 到 iter-max_iteration 的所有 PLAN.md 执行规范化。

    返回：
    {
        "all_ok": bool,
        "results": {
            "iter-N": {"ok": bool, "fixed_fields": [...], "manual_required": [...], "error": "..."}
        }
    }
    """
    root = Path(root).resolve()
    results: dict = {}
    all_ok = True

    for n in range(1, max_iteration + 1):
        plan_path = root / "Docs" / "iterations" / f"iter-{n}" / "PLAN.md"
        if not plan_path.exists():
            results[f"iter-{n}"] = {
                "ok": False,
                "fixed_fields": [],
                "manual_required": [],
                "error": f"文件不存在：{plan_path}",
            }
            all_ok = False
            continue

        r = normalize_plan(plan_path, iteration_n=n)
        results[f"iter-{n}"] = {
            "ok": r["ok"],
            "fixed_fields": r["fixed_fields"],
            "manual_required": r["manual_required"],
            "error": r["error"],
        }
        if not r["ok"]:
            all_ok = False

    return {"all_ok": all_ok, "results": results}


# ---------------------------------------------------------------------------
# CLI 入口（便于独立调试）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python plan_format_normalizer.py <PLAN.md路径> [迭代号]")
        sys.exit(1)

    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else None
    result = normalize_plan(path, n)

    print(f"ok              : {result['ok']}")
    if result["fixed_fields"]:
        print(f"fixed_fields    : {result['fixed_fields']}")
    if result["manual_required"]:
        print(f"manual_required : {result['manual_required']}")
        print(f"\n✗ 错误：\n{result['error']}")
    else:
        print("✓ 格式规范化完成")
