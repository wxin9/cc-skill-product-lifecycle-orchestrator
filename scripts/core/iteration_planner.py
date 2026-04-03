"""
Iteration planner — plans iterations from architecture + PRD features.

Rules:
  1. Every iteration MUST be E2E testable (full stack from UI/API to DB).
  2. Goal is described as "用户能够…" (user-centric, not module-centric).
  3. Each iteration has explicit E2E acceptance criteria.
  4. An iteration cannot depend on another iteration that isn't planned yet.

Usage:
  python scripts/core/iteration_planner.py plan --prd PRD.md --arch ARCH.md --output Docs/iterations/
  python scripts/core/iteration_planner.py validate --plan-dir Docs/iterations/iter-1/
  python scripts/core/iteration_planner.py rebalance --plan-dir Docs/iterations/ --move TASK_ID --to-iter 2
"""
from __future__ import annotations
import re
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# --------------------------------------------------------------------------
# E2E testability validation
# --------------------------------------------------------------------------

def validate_e2e_testable(iteration: dict) -> dict:
    """
    Validate that an iteration is truly E2E testable.

    Requirements:
    - Must have at least one E2E acceptance criterion
    - Each criterion must have an entry_point (UI page, API endpoint, or CLI cmd)
    - Each criterion must describe a data_flow
    - Goal must be user-centric ("用户能够…" or "User can…")

    Returns: {'valid': bool, 'issues': List[str]}
    """
    issues: List[str] = []

    # Check goal phrasing
    goal = iteration.get("goal", "")
    if not re.search(r"(用户能|用户可以|User can|用户将能)", goal, re.IGNORECASE):
        issues.append(
            f"迭代目标应以「用户能够」开头，描述用户价值而非技术实现。"
            f"当前: 「{goal[:60]}」"
        )

    # Check E2E criteria
    criteria = iteration.get("e2e_criteria", [])
    if not criteria:
        issues.append("迭代缺少端到端验收标准（e2e_criteria）")
    else:
        for i, crit in enumerate(criteria):
            if not crit.get("entry_point"):
                issues.append(f"E2E 标准 {i+1} 缺少入口点（entry_point：UI页面/API端点/CLI命令）")
            if not crit.get("data_flow"):
                issues.append(f"E2E 标准 {i+1} 缺少数据流描述（data_flow：输入→处理→存储→响应）")

    # Check feature coverage
    if not iteration.get("feature_ids"):
        issues.append("迭代没有关联任何功能点（feature_ids 为空）")

    return {"valid": len(issues) == 0, "issues": issues}


# --------------------------------------------------------------------------
# Feature grouping heuristics
# --------------------------------------------------------------------------

def _group_features_into_iterations(
    features: List[dict],
    constraints: dict,
) -> List[List[dict]]:
    """
    Group features into iterations such that each group is E2E testable.

    Strategy:
    - Iter 1: Core auth + minimal viable flow (always first)
    - Subsequent iters: Logical feature clusters
    - Max features per iteration: constraints.get('max_features_per_iter', 3)
    """
    max_per_iter = constraints.get("max_features_per_iter", 3)
    min_viable = constraints.get("min_viable_iteration", 1)

    if not features:
        return []

    groups: List[List[dict]] = []

    # Try to identify auth/login features for iter 1
    auth_features = [
        f for f in features
        if re.search(r"(登录|注册|认证|auth|login|register|sign.?in)", f["feature_name"], re.IGNORECASE)
    ]
    other_features = [f for f in features if f not in auth_features]

    if auth_features:
        # Iter 1: auth + first core feature (to make E2E testable)
        iter1 = auth_features[:2]
        if other_features and len(iter1) < min_viable + 1:
            iter1.append(other_features.pop(0))
        groups.append(iter1)
    else:
        # No auth: iter 1 = first max_per_iter features
        groups.append(other_features[:max_per_iter])
        other_features = other_features[max_per_iter:]

    # Remaining features: chunk by max_per_iter
    for i in range(0, len(other_features), max_per_iter):
        chunk = other_features[i:i + max_per_iter]
        if chunk:
            groups.append(chunk)

    return groups


def _build_e2e_criteria(features: List[dict], has_ui: bool) -> List[dict]:
    """Build E2E acceptance criteria for a group of features."""
    criteria = []
    entry_type = "界面" if has_ui else "API"

    for feat in features[:2]:  # Top 2 features get explicit E2E criteria
        criteria.append({
            "description": f"用户能够完整使用「{feat['feature_name']}」功能",
            "entry_point": f"{entry_type}入口：{feat['feature_name']}页面/端点",
            "data_flow": "用户操作 → 前端校验 → API 调用 → 业务逻辑 → 数据库读写 → 响应返回 → 界面更新",
            "test_case_refs": [f"TST-{feat['feature_id']}-S01"],
        })

    return criteria


# --------------------------------------------------------------------------
# Public: plan_iterations
# --------------------------------------------------------------------------

def plan_iterations(
    prd_path: str,
    arch_path: Optional[str] = None,
    constraints: Optional[dict] = None,
) -> List[dict]:
    """
    Generate iteration plan from PRD and ARCH documents.

    Args:
        prd_path: Path to PRD.md
        arch_path: Path to ARCH.md (optional)
        constraints: dict with keys:
            max_features_per_iter (default 3)
            min_viable_iteration (default 1)

    Returns:
        List of Iteration dicts.
    """
    from .test_outline import _extract_prd_features  # reuse

    constraints = constraints or {}
    features = _extract_prd_features(prd_path)

    has_ui = True
    if arch_path and Path(arch_path).exists():
        arch_text = Path(arch_path).read_text(encoding="utf-8", errors="replace")
        has_ui = bool(re.search(r"(前端|UI|界面|web|React|Vue|HTML|frontend)", arch_text, re.IGNORECASE))

    feature_groups = _group_features_into_iterations(features, constraints)
    iterations: List[dict] = []

    for i, group in enumerate(feature_groups, 1):
        feature_ids = [f["feature_id"] for f in group]
        feature_names = [f["feature_name"] for f in group]
        goal = "用户能够" + "、".join(feature_names[:2])
        if len(feature_names) > 2:
            goal += f" 以及 {len(feature_names)-2} 个相关功能"

        e2e_criteria = _build_e2e_criteria(group, has_ui)
        dependencies = list(range(1, i))  # depends on all previous iterations

        iterations.append({
            "number": i,
            "name": f"迭代 {i}：{feature_names[0]}",
            "goal": goal,
            "feature_ids": feature_ids,
            "e2e_criteria": e2e_criteria,
            "task_ids": [],  # populated later by task_registry
            "dependencies": dependencies,
            "status": "planned",
        })

    return iterations


# --------------------------------------------------------------------------
# Public: rebalance_iterations
# --------------------------------------------------------------------------

def rebalance_iterations(
    iterations: List[dict],
    move_feature_id: str,
    from_iter: int,
    to_iter: int,
) -> dict:
    """
    Move a feature from one iteration to another and return the rebalanced list
    plus a summary of what changed.

    Returns: {'iterations': [...], 'changes': [...], 'warnings': [...]}
    """
    changes: List[str] = []
    warnings: List[str] = []

    source = next((it for it in iterations if it["number"] == from_iter), None)
    target = next((it for it in iterations if it["number"] == to_iter), None)

    if not source:
        return {"iterations": iterations, "changes": [], "warnings": [f"迭代 {from_iter} 不存在"]}
    if not target:
        return {"iterations": iterations, "changes": [], "warnings": [f"迭代 {to_iter} 不存在"]}

    if move_feature_id not in source["feature_ids"]:
        return {"iterations": iterations, "changes": [], "warnings": [f"功能 {move_feature_id} 不在迭代 {from_iter} 中"]}

    # Check: won't leave source empty
    if len(source["feature_ids"]) == 1:
        warnings.append(f"警告：迭代 {from_iter} 将变为空，请考虑合并或删除该迭代")

    source["feature_ids"].remove(move_feature_id)
    target["feature_ids"].append(move_feature_id)
    changes.append(f"功能 {move_feature_id} 从迭代 {from_iter} 移入迭代 {to_iter}")

    # Check E2E validity of both affected iterations
    src_valid = validate_e2e_testable(source)
    tgt_valid = validate_e2e_testable(target)

    if not src_valid["valid"]:
        for issue in src_valid["issues"]:
            warnings.append(f"迭代 {from_iter} 调整后可能无法 E2E 测试: {issue}")
    if not tgt_valid["valid"]:
        for issue in tgt_valid["issues"]:
            warnings.append(f"迭代 {to_iter} 调整后可能无法 E2E 测试: {issue}")

    return {"iterations": iterations, "changes": changes, "warnings": warnings}


# --------------------------------------------------------------------------
# Write iteration plan to Docs/
# --------------------------------------------------------------------------

def write_iteration_plans(iterations: List[dict], output_dir: str) -> None:
    """Write each iteration plan to Docs/iterations/iter-N/PLAN.md"""
    base = Path(output_dir)

    # Write INDEX.md
    index_lines = [
        "# 迭代规划总览",
        "",
        f"**总迭代数：** {len(iterations)}",
        "",
        "| 迭代 | 名称 | 功能点 | 状态 |",
        "|---|---|---|---|",
    ]
    for it in iterations:
        feat_str = ", ".join(it["feature_ids"])
        index_lines.append(f"| {it['number']} | {it['name']} | {feat_str} | {it['status']} |")
    index_lines += ["", "---", ""]
    for it in iterations:
        index_lines.append(f"- [迭代 {it['number']}](iter-{it['number']}/PLAN.md) — {it['goal']}")

    (base / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    # Write each iteration
    for it in iterations:
        iter_dir = base / f"iter-{it['number']}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        plan_lines = [
            f"# 迭代 {it['number']}：{it['name']}",
            "",
            f"**目标：** {it['goal']}",
            f"**状态：** {it['status']}",
            f"**关联功能：** {', '.join(it['feature_ids'])}",
        ]
        if it["dependencies"]:
            plan_lines.append(f"**依赖迭代：** {', '.join(str(d) for d in it['dependencies'])}")

        plan_lines += ["", "## 端到端验收标准", ""]
        for j, crit in enumerate(it.get("e2e_criteria", []), 1):
            plan_lines += [
                f"### E2E-{j}: {crit['description']}",
                f"- **入口点：** {crit.get('entry_point', 'TBD')}",
                f"- **数据流：** {crit.get('data_flow', 'TBD')}",
                f"- **测试用例：** {', '.join(crit.get('test_case_refs', []))}",
                "",
            ]

        plan_lines += [
            "## 任务列表",
            "",
            "_（由 `python scripts/__main__.py task create` 自动填充）_",
            "",
        ]

        (iter_dir / "PLAN.md").write_text("\n".join(plan_lines), encoding="utf-8")

        # Create empty CHANGE_LOG.md
        (iter_dir / "CHANGE_LOG.md").write_text(
            f"# 迭代 {it['number']} 变更记录\n\n_（暂无变更）_\n",
            encoding="utf-8",
        )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Iteration planner")
    sub = parser.add_subparsers(dest="cmd")

    plan_p = sub.add_parser("plan", help="Generate iteration plan")
    plan_p.add_argument("--prd", required=True)
    plan_p.add_argument("--arch", default="")
    plan_p.add_argument("--output", default="Docs/iterations")
    plan_p.add_argument("--max-features", type=int, default=3)

    val_p = sub.add_parser("validate", help="Validate an iteration for E2E testability")
    val_p.add_argument("--plan-json", required=True, help="Iteration JSON file")

    args = parser.parse_args()

    if args.cmd == "plan":
        constraints = {"max_features_per_iter": args.max_features}
        iters = plan_iterations(args.prd, args.arch or None, constraints)
        Path(args.output).mkdir(parents=True, exist_ok=True)
        write_iteration_plans(iters, args.output)
        print(f"✓ 迭代计划已生成: {args.output}")
        for it in iters:
            valid = validate_e2e_testable(it)
            status = "✓" if valid["valid"] else "⚠"
            print(f"  {status} 迭代 {it['number']}: {it['goal'][:50]}")
            for issue in valid["issues"]:
                print(f"    ⚠ {issue}")

    elif args.cmd == "validate":
        data = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
        result = validate_e2e_testable(data)
        if result["valid"]:
            print("✓ 迭代通过 E2E 可测验证")
        else:
            print("✗ 迭代未通过 E2E 可测验证:")
            for issue in result["issues"]:
                print(f"  - {issue}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)
