"""
artifact_validator.py — 产物存在性与完整性验证器

在 ./lifecycle gate 执行时被强制调用，验证每个迭代的产物是否
真实存在且质量达标。纯代码驱动，不依赖大模型判断。

4 层验证架构：
  Layer 1：基础文档存在性    → 阻断
  Layer 2：迭代专属产物      → 阻断
  Layer 3：测试执行记录      → 阻断
  Layer 4：架构覆盖检查      → 警告（不阻断）

返回结构：
{
    "passed": bool,
    "iteration": int,
    "layers": {
        "layer1": {"passed": bool, "checks": [CheckResult, ...]},
        "layer2": {"passed": bool, "checks": [CheckResult, ...]},
        "layer3": {"passed": bool, "checks": [CheckResult, ...]},
        "layer4": {"passed": bool, "warnings": [str, ...]},
    },
    "blocking_failures": [str, ...],   # 导致阻断的具体原因
    "warnings": [str, ...],             # 非阻断性警告
    "summary": str,                     # 一句话汇总
}

CheckResult = {
    "name": str,        # 检查项名称
    "passed": bool,
    "detail": str,      # 失败时的具体原因；通过时简短说明
}
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def validate_iteration(root: str | Path, iteration_n: int) -> dict:
    """
    对迭代 N 运行完整的产物验证。

    参数：
      root        — 项目根目录（含 .lifecycle/ 和 Docs/）
      iteration_n — 要验证的迭代编号（≥ 1）

    返回：见模块 docstring 中的结构定义
    """
    root = Path(root).resolve()
    blocking_failures: list[str] = []
    warnings: list[str] = []

    # ── Layer 1：基础文档存在性 ──────────────────────────────────────────────
    l1 = _check_layer1(root)

    # ── Layer 2：迭代专属产物 ────────────────────────────────────────────────
    l2 = _check_layer2(root, iteration_n)

    # ── Layer 3：测试执行记录 ────────────────────────────────────────────────
    l3 = _check_layer3(root, iteration_n)

    # ── Layer 4：架构覆盖检查（警告，不阻断）──────────────────────────────────
    l4 = _check_layer4(root, iteration_n)

    # 汇总阻断性失败
    for layer_key, layer_result in [("layer1", l1), ("layer2", l2), ("layer3", l3)]:
        for chk in layer_result["checks"]:
            if not chk["passed"]:
                blocking_failures.append(f"[{layer_key.upper()}] {chk['name']}: {chk['detail']}")

    warnings.extend(l4["warnings"])

    passed = len(blocking_failures) == 0

    if passed:
        summary = f"迭代 {iteration_n} 产物验证通过（{_count_checks(l1, l2, l3)} 项检查）"
    else:
        summary = f"迭代 {iteration_n} 产物验证失败（{len(blocking_failures)} 项阻断，{len(warnings)} 项警告）"

    return {
        "passed": passed,
        "iteration": iteration_n,
        "layers": {
            "layer1": l1,
            "layer2": l2,
            "layer3": l3,
            "layer4": l4,
        },
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "summary": summary,
    }


def _count_checks(*layers) -> int:
    total = 0
    for layer in layers:
        total += len(layer.get("checks", []))
    return total


# ---------------------------------------------------------------------------
# Layer 1：基础文档存在性
# ---------------------------------------------------------------------------

def _check_layer1(root: Path) -> dict:
    """PRD、ARCH、MASTER_OUTLINE 是否存在且有实质内容。"""
    checks = []

    # PRD.md
    prd_path = root / "Docs" / "product" / "PRD.md"
    checks.append(_check_file_exists_and_nonempty(
        prd_path,
        name="PRD.md 存在且非空",
        min_bytes=500,
        hint="请先运行: ./lifecycle validate --doc Docs/product/PRD.md --type prd"
    ))

    # ARCH.md
    arch_path = root / "Docs" / "tech" / "ARCH.md"
    checks.append(_check_file_exists_and_nonempty(
        arch_path,
        name="ARCH.md 存在且非空",
        min_bytes=300,
        hint="请先运行: ./lifecycle validate --doc Docs/tech/ARCH.md --type arch"
    ))

    # MASTER_OUTLINE.md — 必须包含有效 TST-ID
    outline_path = root / "Docs" / "tests" / "MASTER_OUTLINE.md"
    if not outline_path.exists():
        checks.append(_fail(
            "MASTER_OUTLINE.md 存在且含测试场景",
            f"文件不存在: {outline_path}。请先运行: ./lifecycle outline generate"
        ))
    else:
        content = outline_path.read_text(encoding="utf-8", errors="replace")
        tst_ids = re.findall(r"TST-[A-Z0-9]+-S\d+", content)
        if not tst_ids:
            checks.append(_fail(
                "MASTER_OUTLINE.md 存在且含测试场景",
                f"MASTER_OUTLINE.md 存在但未找到任何 TST-Fxx-Sxx 格式的测试场景 ID。"
                f"请重新生成: ./lifecycle outline generate"
            ))
        else:
            checks.append(_ok(
                "MASTER_OUTLINE.md 存在且含测试场景",
                f"包含 {len(set(tst_ids))} 个测试场景 ID"
            ))

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks}


# ---------------------------------------------------------------------------
# Layer 2：迭代专属产物
# ---------------------------------------------------------------------------

def _check_layer2(root: Path, n: int) -> dict:
    """迭代 N 的 PLAN.md、test_cases.md、TST-ID 交叉引用。"""
    checks = []
    iter_dir = root / "Docs" / "iterations" / f"iter-{n}"

    # PLAN.md 存在且含目标字段
    plan_path = iter_dir / "PLAN.md"
    if not plan_path.exists():
        checks.append(_fail(
            f"iter-{n}/PLAN.md 存在",
            f"文件不存在: {plan_path}。请先运行: ./lifecycle plan"
        ))
    else:
        content = plan_path.read_text(encoding="utf-8", errors="replace")
        has_goal = bool(re.search(r"\*\*目标[：:]\*\*\s*.{5,}", content))
        has_e2e = bool(re.search(r"##\s*端到端验收标准", content))
        if not has_goal:
            checks.append(_fail(
                f"iter-{n}/PLAN.md 含目标字段",
                "PLAN.md 缺少 **目标：** 字段或内容过短。"
                "请补全后重新运行 plan_format_normalizer。"
            ))
        elif not has_e2e:
            checks.append(_fail(
                f"iter-{n}/PLAN.md 含E2E验收标准",
                "PLAN.md 缺少 '## 端到端验收标准' 章节。"
                "请补全后重新运行 plan_format_normalizer。"
            ))
        else:
            checks.append(_ok(
                f"iter-{n}/PLAN.md 存在且完整",
                "含目标字段和E2E验收标准"
            ))

    # test_cases.md 存在且有实质内容
    tc_path = iter_dir / "test_cases.md"
    if not tc_path.exists():
        checks.append(_fail(
            f"iter-{n}/test_cases.md 存在",
            f"文件不存在: {tc_path}。"
            f"请先运行: ./lifecycle outline iter-tests --features <F01,...> --iteration {n}"
        ))
    else:
        content = tc_path.read_text(encoding="utf-8", errors="replace")
        # 去掉空行和注释后，检查实质行数
        real_lines = [l for l in content.splitlines()
                      if l.strip() and not l.strip().startswith(">")
                      and l.strip() != "_（由 `./lifecycle task create` 动态生成）_"]
        tst_ids_in_tc = re.findall(r"TST-[A-Z0-9]+-S\d+", content)

        if len(real_lines) < 5:
            checks.append(_fail(
                f"iter-{n}/test_cases.md 有实质内容",
                f"test_cases.md 内容过少（{len(real_lines)} 行有效内容），疑似空占位符。"
                f"请重新生成: ./lifecycle outline iter-tests --features <F01,...> --iteration {n}"
            ))
        elif not tst_ids_in_tc:
            checks.append(_fail(
                f"iter-{n}/test_cases.md 含 TST-ID",
                "test_cases.md 存在但未找到任何 TST-Fxx-Sxx 格式的测试用例 ID。"
                "文件可能是手动创建的占位符，请重新生成。"
            ))
        else:
            checks.append(_ok(
                f"iter-{n}/test_cases.md 存在且有实质内容",
                f"含 {len(set(tst_ids_in_tc))} 个测试用例 ID"
            ))

    # TST 任务的 test_case_ref 交叉验证：引用的 ID 必须在 MASTER_OUTLINE 中真实存在
    outline_path = root / "Docs" / "tests" / "MASTER_OUTLINE.md"
    tasks_path = root / ".lifecycle" / "tasks.json"

    if outline_path.exists() and tasks_path.exists():
        outline_content = outline_path.read_text(encoding="utf-8", errors="replace")
        valid_tst_ids = set(re.findall(r"TST-[A-Z0-9]+-S\d+", outline_content))

        try:
            tasks_data = json.loads(tasks_path.read_text(encoding="utf-8"))
            tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
        except Exception:
            tasks = []

        iter_tst_tasks = [
            t for t in tasks
            if t.get("iteration") == n and t.get("type") in ("test", "tst")
            and t.get("test_case_ref")
        ]

        orphan_refs = [
            t["test_case_ref"] for t in iter_tst_tasks
            if t["test_case_ref"] not in valid_tst_ids
        ]

        if orphan_refs:
            checks.append(_fail(
                "TST 任务 test_case_ref 交叉验证",
                f"以下测试任务引用的 TST-ID 在 MASTER_OUTLINE.md 中不存在：{orphan_refs}。"
                "可能是测试大纲未更新，请重新生成: ./lifecycle outline generate"
            ))
        else:
            ref_count = len(iter_tst_tasks)
            if ref_count > 0:
                checks.append(_ok(
                    "TST 任务 test_case_ref 交叉验证",
                    f"{ref_count} 个测试任务的引用均在 MASTER_OUTLINE.md 中有效"
                ))

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks}


# ---------------------------------------------------------------------------
# Layer 3：测试执行记录
# ---------------------------------------------------------------------------

def _check_layer3(root: Path, n: int) -> dict:
    """
    .lifecycle/iter-N/test_results.json 必须存在，且：
      - 本迭代所有 ITR-N.TST-xxx 任务都有对应的执行记录
      - 没有 status=fail 且缺少 resolution 字段的条目
    """
    checks = []
    results_path = root / ".lifecycle" / f"iter-{n}" / "test_results.json"

    # 检查文件是否存在
    if not results_path.exists():
        checks.append(_fail(
            f"iter-{n} 测试执行记录文件存在",
            f"缺少 .lifecycle/iter-{n}/test_results.json。\n"
            f"  请在执行每个测试用例后运行:\n"
            f"    ./lifecycle test-record --iteration {n} --test-id <TST-ID> --status pass/fail"
        ))
        # 文件不存在，无法继续后续检查
        return {"passed": False, "checks": checks}

    # 解析文件
    try:
        results_data = json.loads(results_path.read_text(encoding="utf-8"))
        results_list = results_data.get("results", [])
    except Exception as e:
        checks.append(_fail(
            f"iter-{n} 测试执行记录文件可解析",
            f".lifecycle/iter-{n}/test_results.json 格式错误: {e}"
        ))
        return {"passed": False, "checks": checks}

    recorded_test_ids = {r.get("test_id", "") for r in results_list}

    # 读取本迭代的 TST 任务，检查每个都有执行记录
    tasks_path = root / ".lifecycle" / "tasks.json"
    try:
        tasks_data = json.loads(tasks_path.read_text(encoding="utf-8"))
        tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
    except Exception:
        tasks = []

    iter_tst_tasks = [
        t for t in tasks
        if t.get("iteration") == n and t.get("type") in ("test", "tst")
    ]

    # 找出 done 状态的 TST 任务里，test_case_ref 没有执行记录的
    missing_records = []
    for t in iter_tst_tasks:
        ref = t.get("test_case_ref", "")
        if t.get("status") == "done" and ref and ref not in recorded_test_ids:
            missing_records.append(f"{t['id']} (test_case_ref={ref})")

    if missing_records:
        checks.append(_fail(
            "所有完成的 TST 任务有执行记录",
            f"以下已标记为 done 的测试任务缺少执行记录（未在 test_results.json 中找到）：\n"
            + "\n".join(f"    - {m}" for m in missing_records)
            + f"\n  请运行: ./lifecycle test-record --iteration {n} --test-id <TST-ID> --status pass/fail"
        ))
    elif iter_tst_tasks:
        checks.append(_ok(
            "所有完成的 TST 任务有执行记录",
            f"{len(iter_tst_tasks)} 个测试任务均有执行记录"
        ))

    # 检查 fail 状态是否都有 resolution
    unresolved_fails = [
        r for r in results_list
        if r.get("status") == "fail" and not r.get("resolution", "").strip()
    ]
    if unresolved_fails:
        fail_ids = [r.get("test_id", "?") for r in unresolved_fails]
        checks.append(_fail(
            "所有 fail 的测试用例有 resolution",
            f"以下测试用例标记为 fail 但缺少 resolution（说明如何处理该失败）：{fail_ids}。\n"
            f"  请运行: ./lifecycle test-record --iteration {n} --test-id <TST-ID> "
            f"--status fail --resolution \"已创建 ITR-{n}.DEV-xxx 修复\""
        ))
    else:
        if results_list:
            fail_count = sum(1 for r in results_list if r.get("status") == "fail")
            pass_count = sum(1 for r in results_list if r.get("status") == "pass")
            checks.append(_ok(
                "所有 fail 的测试用例有 resolution",
                f"pass: {pass_count}, fail（已解决）: {fail_count}"
            ))

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks}


# ---------------------------------------------------------------------------
# Layer 4：架构覆盖检查（警告，不阻断）
# ---------------------------------------------------------------------------

def _check_layer4(root: Path, n: int) -> dict:
    """
    检查本迭代的 feature_ids 是否在 ARCH.md 中有对应的描述。
    仅产出警告，不阻断 gate。
    """
    warnings: list[str] = []

    plan_path = root / "Docs" / "iterations" / f"iter-{n}" / "PLAN.md"
    arch_path = root / "Docs" / "tech" / "ARCH.md"

    if not plan_path.exists() or not arch_path.exists():
        return {"passed": True, "warnings": warnings}

    plan_content = plan_path.read_text(encoding="utf-8", errors="replace")
    arch_content = arch_path.read_text(encoding="utf-8", errors="replace")

    # 提取本迭代的 feature_ids（格式：F01, F02 ...）
    feat_match = re.search(r"\*\*关联功能[：:]\*\*\s*(.+)", plan_content)
    if not feat_match:
        return {"passed": True, "warnings": warnings}

    feature_ids = [f.strip() for f in feat_match.group(1).split(",") if f.strip()]

    # 在 ARCH.md 里查找每个 feature_id 是否有对应引用
    # 也查找对应的功能名称（从 MASTER_OUTLINE 或 PRD 提取）
    outline_path = root / "Docs" / "tests" / "MASTER_OUTLINE.md"
    feature_names: dict[str, str] = {}
    if outline_path.exists():
        outline_content = outline_path.read_text(encoding="utf-8", errors="replace")
        for fid in feature_ids:
            m = re.search(rf"##\s+{re.escape(fid)}\s+[—-]\s+(.+)", outline_content)
            if m:
                feature_names[fid] = m.group(1).strip()

    for fid in feature_ids:
        fname = feature_names.get(fid, "")
        # 检查 ARCH.md 中是否提到了该功能 ID 或功能名称
        found_id = bool(re.search(re.escape(fid), arch_content))
        found_name = fname and bool(re.search(re.escape(fname[:10]), arch_content))

        if not found_id and not found_name:
            hint = f"({fname})" if fname else ""
            warnings.append(
                f"功能 {fid}{hint} 在 ARCH.md 中未找到对应引用。"
                f"如果该功能有新的数据模型/API，请更新 Docs/tech/ARCH.md。"
            )

    return {"passed": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# 打印报告（供 cmd_gate 调用）
# ---------------------------------------------------------------------------

def print_report(report: dict) -> None:
    """将验证报告打印为人类可读格式。"""
    n = report["iteration"]
    print(f"\n{'─' * 55}")
    print(f"  产物验证报告 — 迭代 {n}")
    print(f"{'─' * 55}")

    layer_labels = {
        "layer1": "Layer 1  基础文档存在性",
        "layer2": "Layer 2  迭代专属产物",
        "layer3": "Layer 3  测试执行记录",
        "layer4": "Layer 4  架构覆盖检查（警告）",
    }

    for layer_key, label in layer_labels.items():
        layer = report["layers"][layer_key]
        checks = layer.get("checks", [])
        layer_warnings = layer.get("warnings", [])

        layer_ok = layer["passed"]
        icon = "✓" if layer_ok else "✗"
        print(f"\n  {icon} {label}")

        for chk in checks:
            c_icon = "  ✓" if chk["passed"] else "  ✗"
            print(f"    {c_icon} {chk['name']}")
            if not chk["passed"]:
                # 缩进打印失败详情
                for line in chk["detail"].splitlines():
                    print(f"         {line}")

        for w in layer_warnings:
            print(f"    ⚠ {w}")

    print(f"\n{'─' * 55}")
    if report["passed"]:
        print(f"  ✓ {report['summary']}")
    else:
        print(f"  ✗ {report['summary']}")
        print(f"\n  阻断原因（共 {len(report['blocking_failures'])} 项）：")
        for i, reason in enumerate(report["blocking_failures"], 1):
            print(f"    {i}. {reason}")
    print(f"{'─' * 55}\n")


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _check_file_exists_and_nonempty(
    path: Path, name: str, min_bytes: int = 100, hint: str = ""
) -> dict:
    if not path.exists():
        detail = f"文件不存在: {path}"
        if hint:
            detail += f"\n  {hint}"
        return _fail(name, detail)

    size = path.stat().st_size
    if size < min_bytes:
        detail = (
            f"文件存在但内容过少（{size} 字节，最小要求 {min_bytes} 字节），"
            f"疑似空占位符: {path}"
        )
        if hint:
            detail += f"\n  {hint}"
        return _fail(name, detail)

    return _ok(name, f"{size} 字节")


def _ok(name: str, detail: str = "") -> dict:
    return {"name": name, "passed": True, "detail": detail}


def _fail(name: str, detail: str) -> dict:
    return {"name": name, "passed": False, "detail": detail}


# ---------------------------------------------------------------------------
# 辅助：写入测试结果记录（供 cmd_test_record 调用）
# ---------------------------------------------------------------------------

def record_test_result(
    root: str | Path,
    iteration_n: int,
    test_id: str,
    status: str,
    task_ref: str = "",
    resolution: str = "",
    notes: str = "",
) -> dict:
    """
    向 .lifecycle/iter-N/test_results.json 写入或更新一条测试执行记录。

    参数：
      root        — 项目根目录
      iteration_n — 迭代编号
      test_id     — 测试用例 ID（如 TST-F01-S01）
      status      — "pass" 或 "fail"
      task_ref    — 对应的任务 ID（如 ITR-1.TST-001，可选）
      resolution  — fail 时的处理说明（fail 时必填）
      notes       — 备注（可选）

    返回：{"ok": bool, "error": str}
    """
    root = Path(root).resolve()

    if status not in ("pass", "fail"):
        return {"ok": False, "error": f"status 必须是 'pass' 或 'fail'，得到: {status!r}"}

    if status == "fail" and not resolution.strip():
        return {
            "ok": False,
            "error": "测试失败时必须提供 --resolution 说明（如何处理该失败，例如：已创建修复任务 ITR-N.DEV-xxx）"
        }

    results_dir = root / ".lifecycle" / f"iter-{iteration_n}"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "test_results.json"

    # 读取现有数据
    if results_path.exists():
        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"iteration": iteration_n, "results": []}
    else:
        data = {"iteration": iteration_n, "results": []}

    results_list: list[dict] = data.get("results", [])

    # 查找是否已有同 test_id 的记录（更新）
    existing_idx = next(
        (i for i, r in enumerate(results_list) if r.get("test_id") == test_id), None
    )

    entry = {
        "test_id": test_id,
        "task_ref": task_ref,
        "status": status,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    if status == "fail":
        entry["resolution"] = resolution

    if existing_idx is not None:
        results_list[existing_idx] = entry
        action = "更新"
    else:
        results_list.append(entry)
        action = "新增"

    data["results"] = results_list
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    results_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "error": "", "action": action}


def list_test_results(root: str | Path, iteration_n: int) -> dict:
    """读取并返回迭代 N 的测试执行状态摘要。"""
    root = Path(root).resolve()
    results_path = root / ".lifecycle" / f"iter-{iteration_n}" / "test_results.json"

    if not results_path.exists():
        return {
            "exists": False,
            "results": [],
            "pass_count": 0,
            "fail_count": 0,
            "total": 0,
        }

    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
        results = data.get("results", [])
    except Exception:
        results = []

    pass_count = sum(1 for r in results if r.get("status") == "pass")
    fail_count = sum(1 for r in results if r.get("status") == "fail")

    return {
        "exists": True,
        "results": results,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": len(results),
    }


# ---------------------------------------------------------------------------
# CLI 入口（便于独立调试）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    report = validate_iteration(root, n)
    print_report(report)
    sys.exit(0 if report["passed"] else 1)
