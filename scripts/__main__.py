"""
product-lifecycle CLI — unified entry point.

Usage:
  python -m scripts <command> [options]

Commands:
  init          Initialize project structure (new or existing)
  validate      Validate PRD or ARCH document clarity
  task          Task management (create / update / list / stats / gate)
  plan          Generate iteration plan from PRD + ARCH
  outline       Test outline management (generate / trace / iter-tests)
  gate          Check iteration gate (all tasks done?)
  change        Handle a change from any node (prd / code / test / iteration)
  status        Show overall project status
  pause         Pause work at current point
  resume        Resume from pause state
  cancel        Cancel the current workflow
"""
from __future__ import annotations
import sys
import json
import argparse
import shutil
import subprocess
import os
from datetime import datetime, timezone
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
# init command
# --------------------------------------------------------------------------

def cmd_init(args) -> int:
    project_path = Path(args.path).resolve()
    project_path.mkdir(parents=True, exist_ok=True)

    lifecycle = project_path / ".lifecycle"
    lifecycle.mkdir(exist_ok=True)
    (lifecycle / "steps").mkdir(exist_ok=True)

    # Check if existing project (has files other than .lifecycle)
    existing_files = [f for f in project_path.iterdir()
                      if f.name not in (".lifecycle", "Docs", ".git")]

    if existing_files and not args.force_new:
        print(f"检测到已有项目文件 ({len(existing_files)} 个)，执行扫描整合模式...")
        return _init_existing(project_path)
    else:
        return _init_new(project_path, args.name or project_path.name)


def _init_new(project_path: Path, project_name: str) -> int:
    """Create standard Docs/ structure for a new project."""
    dirs = [
        "Docs/product/requirements",
        "Docs/product/user_flows",
        "Docs/tech/components",
        "Docs/iterations",
        "Docs/tests/cases",
        "Docs/manual",
    ]
    for d in dirs:
        (project_path / d).mkdir(parents=True, exist_ok=True)

    # Write top-level INDEX.md
    index_content = f"""# {project_name} — 文档索引

> 所有项目文档沉淀在此目录下，按分类管理。

## 文档目录

| 分类 | 路径 | 说明 |
|---|---|---|
| 产品设计 | [product/](product/INDEX.md) | PRD、需求、用户流程 |
| 技术架构 | [tech/](tech/INDEX.md) | 架构文档、组件设计 |
| 迭代规划 | [iterations/](iterations/INDEX.md) | 迭代计划、变更记录 |
| 测试文档 | [tests/](tests/INDEX.md) | 测试大纲、测试用例 |
| 操作手册 | [manual/](manual/MANUAL.md) | 产品操作手册（安装、使用、卸载） |

## 快速状态

运行 `python scripts/__main__.py status` 查看当前进度。
"""
    (project_path / "Docs" / "INDEX.md").write_text(index_content, encoding="utf-8")

    # Write sub-level INDEX stubs
    sub_indexes = {
        "Docs/product/INDEX.md": "# 产品文档\n\n- [PRD.md](PRD.md) — 产品设计文档（待填写）\n",
        "Docs/tech/INDEX.md": "# 技术文档\n\n- [ARCH.md](ARCH.md) — 技术架构文档（待填写）\n",
        "Docs/iterations/INDEX.md": "# 迭代规划\n\n_（待生成）_\n",
        "Docs/tests/INDEX.md": "# 测试文档\n\n- [MASTER_OUTLINE.md](MASTER_OUTLINE.md) — 主测试大纲（待生成）\n",
        "Docs/manual/MANUAL.md": "# 用户操作手册\n\n_（在第一个迭代完成后自动生成）_\n",
    }
    for rel, content in sub_indexes.items():
        p = project_path / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    # Write .lifecycle/config.json
    config = {
        "project_name": project_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_iteration": 0,
        "prd_version": "0.0",
        "arch_version": "0.0",
        "outline_version": "0.0",
        "total_iterations": 0,
    }
    config_path = project_path / ".lifecycle" / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    # Record step
    _record_step(project_path, "project-initialized")

    # Fix 4: Write skill_path and create lifecycle wrapper script
    skill_dir = Path(__file__).parent.parent.resolve()
    skill_path_file = project_path / ".lifecycle" / "skill_path"
    skill_path_file.write_text(str(skill_dir), encoding="utf-8")

    wrapper = project_path / "lifecycle"
    wrapper.write_text(
        "#!/bin/bash\n"
        "SKILL_PATH=\"$(cat \"$(dirname \"$0\")/.lifecycle/skill_path\")\"\n"
        "PYTHONPATH=\"$SKILL_PATH\" python -m scripts \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    print(f"✓ 新项目初始化完成: {project_path}")
    print(f"  创建了 {len(dirs)} 个目录")
    print(f"\n下一步:")
    print(f"  1. 复制模板: cp <skill>/references/doc_templates/prd_template.md {project_path}/Docs/product/PRD.md")
    print(f"  2. 填写 PRD，然后运行: ./lifecycle validate --doc Docs/product/PRD.md")
    return 0


def _init_existing(project_path: Path) -> int:
    """Scan existing project and generate migration plan."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.adapters.project_scanner import scan_project, normalize_structure, execute_migration

    scan = scan_project(str(project_path))
    plan = normalize_structure(scan, str(project_path))

    # Write scan report
    scan_path = project_path / ".lifecycle" / "project_scan.json"
    scan_path.write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 扫描完成: {scan['total_files']} 个文件")
    print(f"  发现文档: {len(scan['detected_docs'])} 个")
    print(f"  技术栈: {scan['inferred_tech_stack']}")

    if plan["conflicts"]:
        print(f"\n⚠ 发现 {len(plan['conflicts'])} 个冲突，需要手动解决:")
        for c in plan["conflicts"]:
            print(f"  - {c}")

    print(f"\n将创建 {len(plan['creates'])} 个目录，整理 {len(plan['moves'])} 个文档")
    print("执行整合（--execute 跳过确认）...")

    result = execute_migration(plan, dry_run=False)
    _init_new(project_path, project_path.name)

    print(f"\n✓ 已有项目整合完成")
    print(f"  扫描报告: .lifecycle/project_scan.json")
    return 0


# --------------------------------------------------------------------------
# validate command
# --------------------------------------------------------------------------

def cmd_validate(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.doc_validator import validate_document

    result = validate_document(args.doc, args.type)
    score = result["score"]
    passed = result["passed"]

    status = "✓ PASSED" if passed else "✗ FAILED"
    print(f"\n文档验证: {status}  (score: {score}/100)")

    if result["issues"]:
        print("\nIssues:")
        for iss in result["issues"]:
            icon = "✗" if iss["severity"] == "error" else "⚠"
            print(f"  {icon} [{iss['field']}] {iss['message']}")

    if result["suggestions"]:
        print("\nSuggestions:")
        for s in result["suggestions"]:
            print(f"  • {s}")

    if passed:
        doc_type = result.get("doc_type", "")
        root = _find_project_root()
        step = "prd-validated" if doc_type == "prd" else None
        if step:
            _record_step(root, "prd-written")
            _record_step(root, "prd-validated")
            print(f"\n✓ 步骤已记录: prd-written, prd-validated")
            # Fix 10: auto-backup PRD snapshot for use by `change prd` without --old
            snapshot_path = root / ".lifecycle" / "prd_snapshot.md"
            doc_content = Path(args.doc).read_text(encoding="utf-8", errors="replace")
            snapshot_path.write_text(doc_content, encoding="utf-8")
            print(f"✓ PRD 快照已保存: .lifecycle/prd_snapshot.md")

    return 0 if passed else 1


# --------------------------------------------------------------------------
# task command
# --------------------------------------------------------------------------

def cmd_task(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.task_registry import TaskRegistry

    root = _find_project_root()
    reg = TaskRegistry(str(root))

    if args.task_cmd == "create":
        tid = reg.create_task(
            args.category,
            args.title,
            getattr(args, "description", ""),
            getattr(args, "iteration", None),
            getattr(args, "test_case_ref", None),
        )
        print(f"✓ 创建任务: {tid}")

    elif args.task_cmd == "update":
        ok = reg.update_status(args.id, args.status)
        print(f"✓ {args.id} → {args.status}" if ok else f"✗ 任务未找到: {args.id}")
        return 0 if ok else 1

    elif args.task_cmd == "list":
        tasks = reg.list_tasks(
            iteration=getattr(args, "iteration", None),
            status=getattr(args, "filter_status", None),
            task_type=getattr(args, "type", None),
        )
        print(f"\n任务列表 ({len(tasks)} 条):")
        for t in tasks:
            ref = f" → {t['test_case_ref']}" if t.get("test_case_ref") else ""
            print(f"  [{t['status'].upper():11s}] {t['id']:22s} {t['title']}{ref}")

    elif args.task_cmd == "stats":
        stats = reg.get_stats()
        print(f"\n任务统计: 总计 {stats['total']}")
        print(f"  按状态: {stats['by_status']}")
        print(f"  按类型: {stats['by_type']}")

    elif args.task_cmd == "gate":
        result = reg.check_iteration_gate(args.iteration)
        status = "✓ PASSED" if result["passed"] else "✗ BLOCKED"
        print(f"\n迭代 {args.iteration} 门控: {status}")
        print(f"  总任务: {result['total_tasks']}  已完成: {result['done_tasks']}")
        if result["blocking_tasks"]:
            print("\n  阻塞任务（未完成）：")
            for t in result["blocking_tasks"]:
                print(f"    [{t['status'].upper():12s}] {t['id']}  {t['title']}")
        return 0 if result["passed"] else 1

    return 0


# --------------------------------------------------------------------------
# plan command
# --------------------------------------------------------------------------

def cmd_plan(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.iteration_planner import plan_iterations, write_iteration_plans, validate_e2e_testable

    root = _find_project_root()
    prd = args.prd or str(root / "Docs/product/PRD.md")
    arch = args.arch or str(root / "Docs/tech/ARCH.md")
    output = args.output or str(root / "Docs/iterations")

    # Gate: require prd-validated
    _require_step(root, "prd-validated", "先完成 PRD 验证（prd-validated）才能生成迭代计划")

    constraints = {}
    if args.constraints:
        try:
            constraints = json.loads(args.constraints)
        except json.JSONDecodeError:
            print("⚠ --constraints 不是有效 JSON，使用默认值")

    iterations = plan_iterations(prd, arch if Path(arch).exists() else None, constraints)
    Path(output).mkdir(parents=True, exist_ok=True)
    write_iteration_plans(iterations, output)

    # Validate E2E testability
    all_valid = True
    for it in iterations:
        result = validate_e2e_testable(it)
        icon = "✓" if result["valid"] else "⚠"
        print(f"  {icon} 迭代 {it['number']}: {it['goal'][:60]}")
        if not result["valid"]:
            all_valid = False
            for issue in result["issues"]:
                print(f"      ⚠ {issue}")

    if all_valid:
        _record_step(root, "iterations-planned")
        print(f"\n✓ 迭代计划已生成: {output}  ({len(iterations)} 个迭代)")
        print(f"✓ 步骤已记录: iterations-planned")
    else:
        print("\n⚠ 部分迭代未通过 E2E 可测验证，请修正后重新生成")
        return 1

    return 0


# --------------------------------------------------------------------------
# outline command
# --------------------------------------------------------------------------

def cmd_outline(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.test_outline import (
        generate_outline, write_outline, trace_impact, generate_iteration_tests, write_iteration_tests
    )

    root = _find_project_root()

    if args.outline_cmd == "generate":
        prd = args.prd or str(root / "Docs/product/PRD.md")
        arch = args.arch or str(root / "Docs/tech/ARCH.md")
        output = args.output or str(root / "Docs/tests/MASTER_OUTLINE.md")

        _require_step(root, "arch-doc-written", "先完成架构文档（arch-doc-written）才能生成测试大纲")

        outline = generate_outline(prd, arch if Path(arch).exists() else None)
        write_outline(outline, output)
        _record_step(root, "test-outline-written")
        print(f"✓ 主测试大纲已生成: {output}")
        print(f"  功能点: {len(outline['entries'])}  测试场景: {outline['total_scenarios']}")

    elif args.outline_cmd == "trace":
        outline = args.outline or str(root / "Docs/tests/MASTER_OUTLINE.md")
        feature_ids = [f.strip() for f in args.features.split(",")]
        affected = trace_impact(feature_ids, outline)
        if affected:
            print(f"受影响的测试用例 ({len(affected)}):")
            for t in affected:
                print(f"  - {t}")
        else:
            print("未找到受影响的测试用例")

    elif args.outline_cmd == "iter-tests":
        outline_path = args.outline or str(root / "Docs/tests/MASTER_OUTLINE.md")
        feature_ids = [f.strip() for f in args.features.split(",")]
        output = args.output or str(root / f"Docs/iterations/iter-{args.iteration}/test_cases.md")
        iter_plan = {"feature_ids": feature_ids}
        outline_data = {"entries": [], "version": "1.0", "generated_at": "", "prd_version": "", "arch_version": "", "total_scenarios": 0}
        cases = generate_iteration_tests(iter_plan, outline_data, args.iteration)
        write_iteration_tests(cases, output, args.iteration)
        n = args.iteration
        _record_step(root, f"iter-{n}-tests-written")
        print(f"✓ 迭代 {n} 测试用例已生成: {output}  ({len(cases)} 个)")

    return 0


# --------------------------------------------------------------------------
# gate command
# --------------------------------------------------------------------------

def cmd_gate(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.task_registry import TaskRegistry

    root = _find_project_root()

    # ── 步骤 1：产物验证（在任务状态检查之前强制运行）────────────────────────
    try:
        from scripts.core.artifact_validator import validate_iteration, print_report
        artifact_report = validate_iteration(root, args.iteration)
        print_report(artifact_report)
        if not artifact_report["passed"]:
            print("✗ 产物验证未通过，gate 阻断。请修复上述问题后重试。")
            return 1
    except ImportError as e:
        print(f"⚠ 无法加载 artifact_validator（跳过产物验证）: {e}")
    except Exception as e:
        print(f"⚠ 产物验证异常（跳过）: {e}")

    # ── 步骤 2：任务状态检查（原有逻辑）──────────────────────────────────────
    reg = TaskRegistry(str(root))
    result = reg.check_iteration_gate(args.iteration)

    status = "✓ PASSED" if result["passed"] else "✗ BLOCKED"
    print(f"\n迭代 {args.iteration} 门控: {status}")
    print(f"  总任务: {result['total_tasks']}  已完成: {result['done_tasks']}")

    if result["passed"]:
        n = args.iteration
        _record_step(root, f"iter-{n}-gate-passed")
        print(f"✓ 步骤已记录: iter-{n}-gate-passed")
        print(f"\n可以进入迭代 {n + 1}")

        # 自动更新操作手册（try/except 不影响 gate 结果）
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from scripts.core.manual_generator import generate_manual
            manual_result = generate_manual(root, n)
            if manual_result["ok"]:
                print(f"✓ 操作手册已更新: {manual_result['path']}")
            else:
                print(f"⚠ 操作手册更新失败（不影响迭代门控）:\n  {manual_result['error']}")
        except Exception as e:
            print(f"⚠ 操作手册更新异常（不影响迭代门控）: {e}")
    else:
        print("\n未完成任务：")
        for t in result["blocking_tasks"]:
            print(f"  [{t['status'].upper():11s}] {t['id']}  {t['title']}")
        print(f"\n当前迭代未完成，无法进入下一迭代。")

    return 0 if result["passed"] else 1


# --------------------------------------------------------------------------
# change command — handle changes from any of the 4 nodes
# --------------------------------------------------------------------------

def cmd_change(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.change_detector import (
        detect_prd_diff, cascade_impact, cascade_from_code_change
    )
    from scripts.core.task_registry import TaskRegistry

    root = _find_project_root()
    reg = TaskRegistry(str(root))

    node = args.node  # prd | code | test | iteration

    if node == "prd":
        old_prd = args.old or ""
        new_prd = args.new or str(root / "Docs/product/PRD.md")

        # Fix 10: use auto-saved snapshot when --old not provided
        if not old_prd:
            snapshot = root / ".lifecycle" / "prd_snapshot.md"
            if snapshot.exists():
                old_prd = str(snapshot)
                print(f"ℹ 使用 PRD 快照作为旧版本: .lifecycle/prd_snapshot.md")
            else:
                print("⚠ 未找到 PRD 快照（请先运行 validate 生成快照），也未提供 --old 参数")
                print("  请先运行: ./lifecycle validate --doc Docs/product/PRD.md")
                print("  或手动指定: ./lifecycle change prd --old <旧版路径>")
                return 1
        outline = str(root / "Docs/tests/MASTER_OUTLINE.md")

        change_report = detect_prd_diff(old_prd, new_prd)
        impact = cascade_impact(change_report, outline)

        # Write impact report
        impact_path = root / ".lifecycle" / "CHANGE_IMPACT.md"
        impact_path.write_text(impact["summary_md"], encoding="utf-8")

        # Auto-create downstream tasks
        for item in impact["impact_items"]:
            if item["type"] == "arch":
                reg.create_task("arch", f"[变更] {item['description']}")
            elif item["action_required"] in ("regenerate", "update"):
                # Find current iteration
                config = _load_config(root)
                cur_iter = config.get("current_iteration", 1)
                if item["type"] == "test":
                    reg.create_task("test", f"[变更] 重新验证 {item['id']}", iteration=cur_iter, test_case_ref=item["id"])

        print(f"✓ 变更影响报告已生成: .lifecycle/CHANGE_IMPACT.md")
        print(f"\n变更摘要: {change_report['summary']}")
        print(f"受影响测试: {len(impact['affected_tests'])} 个")
        print(f"受影响迭代: {impact['affected_iterations']}")
        if impact["needs_arch_update"]:
            print("⚠ 技术架构文档需要同步更新")

        # Reset prd-validated step so user re-validates new PRD
        _reset_step(root, "prd-validated")
        print("\n⚠ prd-validated 已重置，请重新验证更新后的 PRD")

    elif node == "code":
        components = [c.strip() for c in args.components.split(",")]
        outline = str(root / "Docs/tests/MASTER_OUTLINE.md")
        impact = cascade_from_code_change(components, outline)

        # Create test tasks for affected tests
        config = _load_config(root)
        cur_iter = config.get("current_iteration", 1) + 1
        for tst_id in impact["affected_tests"]:
            reg.create_task("test", f"[代码变更] 重新验证 {tst_id}", iteration=cur_iter, test_case_ref=tst_id)

        impact_path = root / ".lifecycle" / "CODE_CHANGE_IMPACT.md"
        impact_path.write_text(impact["summary_md"], encoding="utf-8")
        print(f"✓ 代码变更影响报告: .lifecycle/CODE_CHANGE_IMPACT.md")
        print(f"受影响测试用例: {len(impact['affected_tests'])} 个")
        if impact["affected_tests"]:
            print(f"已自动创建迭代 {cur_iter} 的测试任务")

        # Reset gate for impacted iterations
        if impact["affected_tests"]:
            reg.reset_iteration_gate(cur_iter)
            print(f"⚠ 迭代 {cur_iter} 门控已重置，需重新通过验证")

    elif node == "test":
        failure_type = args.failure_type  # bug | gap | wrong-test
        test_id = args.test_id

        if failure_type == "bug":
            config = _load_config(root)
            cur_iter = config.get("current_iteration", 1)
            tid = reg.create_task("dev", f"[Bug修复] 测试失败: {test_id}", iteration=cur_iter)
            print(f"✓ 已创建 Bug 修复任务: {tid}")
            print(f"  修复完成后运行: python -m scripts change code --components <module>")

        elif failure_type == "gap":
            tid = reg.create_task("prd", f"[需求遗漏] {test_id} 暴露了未覆盖的需求场景")
            print(f"✓ 已创建 PRD 变更任务: {tid}")
            print(f"  请修改 PRD 后运行: python -m scripts change prd --new Docs/product/PRD.md")

        elif failure_type == "wrong-test":
            print(f"请修改 {test_id} 对应的测试用例文件")
            print(f"修改后运行: python -m scripts outline trace --features <feature_id>")
            print(f"确认无其他测试受到连带影响")

    elif node == "iteration":
        from scripts.core.iteration_planner import rebalance_iterations
        # Read current iteration plans (simplified — from .lifecycle)
        print(f"迭代变更处理：请手动编辑 Docs/iterations/iter-{args.from_iter}/PLAN.md")
        print(f"变更后运行: python -m scripts gate --iteration {args.from_iter} 重新验证门控")

    return 0


# --------------------------------------------------------------------------
# test-record command — record test case execution results
# --------------------------------------------------------------------------

def cmd_test_record(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.artifact_validator import record_test_result, list_test_results

    root = _find_project_root()

    if getattr(args, "list_results", False):
        summary = list_test_results(str(root), args.iteration)
        if not summary["exists"]:
            print(f"迭代 {args.iteration} 尚无测试执行记录")
            print(f"  使用: ./lifecycle test-record --iteration {args.iteration} --test-id <TST-ID> --status pass/fail")
        else:
            print(f"\n迭代 {args.iteration} 测试执行状态（{summary['total']} 条记录）:")
            print(f"  pass: {summary['pass_count']}  fail: {summary['fail_count']}")
            print()
            for r in summary["results"]:
                icon = "✓" if r["status"] == "pass" else "✗"
                res_note = f"  [{r.get('resolution', '')}]" if r["status"] == "fail" else ""
                task_ref = f" ({r.get('task_ref', '')})" if r.get("task_ref") else ""
                print(f"  {icon} {r['test_id']}{task_ref}{res_note}")
        return 0

    # 写入模式：--test-id 和 --status 为必填
    if not getattr(args, "test_id", None):
        print("✗ 写入模式需要 --test-id 参数")
        return 1
    if not getattr(args, "status", None):
        print("✗ 写入模式需要 --status 参数（pass 或 fail）")
        return 1

    result = record_test_result(
        root=str(root),
        iteration_n=args.iteration,
        test_id=args.test_id,
        status=args.status,
        task_ref=getattr(args, "task_ref", "") or "",
        resolution=getattr(args, "resolution", "") or "",
        notes=getattr(args, "notes", "") or "",
    )

    if result["ok"]:
        icon = "✓" if args.status == "pass" else "✗"
        print(f"{icon} 测试记录已{result['action']}: {args.test_id} → {args.status}")
        print(f"  文件: .lifecycle/iter-{args.iteration}/test_results.json")
    else:
        print(f"✗ 记录失败: {result['error']}")
        return 1

    return 0


# --------------------------------------------------------------------------
# manual command — generate/update the user operations manual
# --------------------------------------------------------------------------

def cmd_manual(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.manual_generator import generate_manual

    root = _find_project_root()

    # 自动检测最高已完成迭代
    iteration_n = getattr(args, "iteration", None)
    if iteration_n is None:
        # 从已完成的步骤中推断最高迭代
        steps_dir = root / ".lifecycle" / "steps"
        max_iter = 0
        if steps_dir.exists():
            for step_file in steps_dir.glob("iter-*-gate-passed.json"):
                m = __import__("re").match(r"iter-(\d+)-gate-passed", step_file.stem)
                if m:
                    max_iter = max(max_iter, int(m.group(1)))
        iteration_n = max_iter

    print(f"生成操作手册（基于迭代 1 至 {iteration_n}）...")
    result = generate_manual(str(root), iteration_n)

    if result["ok"]:
        print(f"✓ 操作手册已生成: {result['path']}")
        if result["warnings"]:
            for w in result["warnings"]:
                print(f"  ⚠ {w}")
    else:
        print(f"✗ 生成失败:\n{result['error']}")
        return 1

    return 0


# --------------------------------------------------------------------------
# status command
# --------------------------------------------------------------------------

def cmd_status(args) -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.task_registry import TaskRegistry

    root = _find_project_root()
    config = _load_config(root)

    print(f"\n{'='*50}")
    print(f"  product-lifecycle 项目仪表盘")
    print(f"{'='*50}")
    print(f"项目: {config.get('project_name', root.name)}")
    print(f"目录: {root}")

    # ── Step progress ──
    steps_dir = root / ".lifecycle" / "steps"
    completed_steps = []
    if steps_dir.exists():
        completed_steps = sorted(s.stem for s in steps_dir.glob("*.json"))

    workflow_phases = [
        ("project-initialized", "项目初始化"),
        ("prd-written", "PRD 编写"),
        ("prd-validated", "PRD 验证"),
        ("arch-doc-written", "架构文档"),
        ("test-outline-written", "测试大纲"),
        ("iterations-planned", "迭代规划"),
    ]
    print(f"\n── 工作流进度 ──")
    current_phase = "未开始"
    for step_id, label in workflow_phases:
        done = step_id in completed_steps
        icon = "✓" if done else "○"
        print(f"  {icon} {label}")
        if done:
            current_phase = label

    # Show iteration-level steps
    cur_iter = config.get("current_iteration", 0)
    if cur_iter > 0:
        for i in range(1, cur_iter + 1):
            iter_steps = [
                (f"iter-{i}-tests-written", "测试用例"),
                (f"iter-{i}-gate-passed", "门控通过"),
            ]
            all_done = all(s in completed_steps for s, _ in iter_steps)
            print(f"\n  迭代 {i}: {'✅ 完成' if all_done else '🔄 进行中'}")
            for step_id, label in iter_steps:
                done = step_id in completed_steps
                print(f"    {'✓' if done else '○'} {label}")

    # ── Document completeness ──
    print(f"\n── 文档状态 ──")
    docs = [
        ("Docs/product/PRD.md", "PRD", "prd"),
        ("Docs/tech/ARCH.md", "ARCH", "arch"),
        ("Docs/tests/MASTER_OUTLINE.md", "测试大纲", "test_outline"),
    ]
    for rel_path, label, doc_type in docs:
        full_path = root / rel_path
        if full_path.exists():
            from scripts.core.doc_validator import validate_document
            result = validate_document(str(full_path), doc_type)
            score = result["score"]
            bar = _progress_bar(score, 100)
            status = "✓" if result["passed"] else "✗"
            print(f"  {status} {label:8s} {bar} {score}/100")
        else:
            print(f"  — {label:8s} 未创建")

    # ── Task progress ──
    reg = TaskRegistry(str(root))
    stats = reg.get_stats()
    total = stats["total"]
    print(f"\n── 任务概览 ──")
    if total > 0:
        by_status = stats["by_status"]
        done = by_status.get("done", 0)
        in_prog = by_status.get("in_progress", 0)
        todo = by_status.get("todo", 0)
        blocked = by_status.get("blocked", 0)
        bar = _progress_bar(done, total)
        print(f"  进度: {bar} {done}/{total}")
        print(f"  完成: {done}  进行中: {in_prog}  待办: {todo}  阻塞: {blocked}")

        # Per-iteration breakdown
        if cur_iter > 0:
            print(f"\n── 迭代任务明细 ──")
            for i in range(1, cur_iter + 1):
                iter_tasks = reg.list_tasks(iteration=i)
                if iter_tasks:
                    iter_done = sum(1 for t in iter_tasks if t["status"] == "done")
                    iter_total = len(iter_tasks)
                    bar = _progress_bar(iter_done, iter_total)
                    print(f"  迭代 {i}: {bar} {iter_done}/{iter_total}")
    else:
        print(f"  暂无任务")

    # ── Pause state ──
    pause_file = root / ".lifecycle" / "pause_state.json"
    if pause_file.exists():
        pause = json.loads(pause_file.read_text(encoding="utf-8"))
        print(f"\n⏸ 已暂停: {pause.get('reason', '')} ({pause.get('paused_at', '')})")

    print()
    return 0


def _progress_bar(current: int, total: int, width: int = 20) -> str:
    """Render a text progress bar like [████████░░░░░░░░░░░░]."""
    if total <= 0:
        return f"[{'░' * width}]"
    filled = int(width * current / total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


# --------------------------------------------------------------------------
# pause command
# --------------------------------------------------------------------------

def cmd_pause(args) -> int:
    root = _find_project_root()
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.core.task_registry import TaskRegistry

    reg = TaskRegistry(str(root))
    incomplete = reg.list_tasks(status="todo") + reg.list_tasks(status="in_progress")
    config = _load_config(root)

    pause_state = {
        "paused_at": datetime.now(timezone.utc).isoformat(),
        "current_phase": args.phase or "unknown",
        "current_iteration": config.get("current_iteration", 0),
        "reason": args.reason or "",
        "pending_cascade_items": [],
        "incomplete_task_ids": [t["id"] for t in incomplete],
    }

    pause_path = root / ".lifecycle" / "pause_state.json"
    pause_path.write_text(json.dumps(pause_state, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write cancel file to stop step enforcement
    (root / ".lifecycle" / ".skill-cancel").touch()

    print(f"✓ 项目已暂停")
    print(f"  未完成任务: {len(incomplete)} 个")
    print(f"  暂停原因: {args.reason}")
    print(f"\n恢复: python -m scripts resume")
    return 0


# --------------------------------------------------------------------------
# resume command
# --------------------------------------------------------------------------

def cmd_resume(args) -> int:
    root = _find_project_root()
    pause_path = root / ".lifecycle" / "pause_state.json"
    cancel_flag = root / ".lifecycle" / ".skill-cancel"

    if not pause_path.exists():
        print("没有找到暂停状态，项目未暂停。")
        return 0

    pause = json.loads(pause_path.read_text(encoding="utf-8"))

    # Remove cancel flag
    if cancel_flag.exists():
        cancel_flag.unlink()

    print(f"✓ 从暂停状态恢复")
    print(f"  暂停时间: {pause.get('paused_at', '')}")
    print(f"  暂停原因: {pause.get('reason', '')}")
    print(f"  中断阶段: {pause.get('current_phase', 'unknown')}")
    print(f"  待完成任务: {pause.get('incomplete_task_ids', [])}")
    print(f"\n运行 `python -m scripts status` 查看完整状态")

    # Archive pause state
    archive = root / ".lifecycle" / "pause_state.archived.json"
    pause_path.rename(archive)
    return 0


# --------------------------------------------------------------------------
# cancel command
# --------------------------------------------------------------------------

def cmd_cancel(args) -> int:
    root = _find_project_root()
    cancel_path = root / ".lifecycle" / ".skill-cancel"
    cancel_path.touch()

    cancel_state = {
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "reason": args.reason or "",
    }
    (root / ".lifecycle" / "cancel_state.json").write_text(
        json.dumps(cancel_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✓ 工作流已取消。所有后续步骤门控将优雅退出。")
    return 0


# --------------------------------------------------------------------------
# step command — proxy to step_enforcer.py (Fix 5)
# --------------------------------------------------------------------------

def cmd_step(args) -> int:
    """Delegate to step_enforcer.py, using skill_path from .lifecycle."""
    root = _find_project_root()

    # Locate step_enforcer.py via .lifecycle/skill_path or __file__
    skill_path_file = root / ".lifecycle" / "skill_path"
    if skill_path_file.exists():
        skill_dir = Path(skill_path_file.read_text(encoding="utf-8").strip())
    else:
        skill_dir = Path(__file__).parent.parent.resolve()

    enforcer = skill_dir / "scripts" / "step_enforcer.py"
    if not enforcer.exists():
        print(f"✗ 找不到 step_enforcer.py: {enforcer}")
        return 1

    step_args = args.step_args or []
    cmd = [sys.executable, str(enforcer)] + step_args
    env = {**os.environ, "PYTHONPATH": str(skill_dir)}
    result = subprocess.run(cmd, cwd=str(root), env=env)
    return result.returncode


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

def _record_step(root: Path, step_id: str) -> None:
    steps_dir = root / ".lifecycle" / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    step_file = steps_dir / f"{step_id}.json"
    step_file.write_text(
        json.dumps({"id": step_id, "recorded_at": datetime.now(timezone.utc).isoformat()},
                   ensure_ascii=False),
        encoding="utf-8",
    )


def _require_step(root: Path, step_id: str, message: str) -> None:
    step_file = root / ".lifecycle" / "steps" / f"{step_id}.json"
    cancel_file = root / ".lifecycle" / ".skill-cancel"
    if cancel_file.exists():
        return  # graceful exit
    if not step_file.exists():
        print(f"✗ 步骤未完成: {step_id}")
        print(f"  {message}")
        sys.exit(1)


def _reset_step(root: Path, step_id: str) -> None:
    step_file = root / ".lifecycle" / "steps" / f"{step_id}.json"
    if step_file.exists():
        step_file.unlink()


def _load_config(root: Path) -> dict:
    config_path = root / ".lifecycle" / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


# --------------------------------------------------------------------------
# Argument parser
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts",
        description="product-lifecycle — 产品全环节管理 CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p = sub.add_parser("init", help="初始化项目结构")
    p.add_argument("--path", default=".", help="项目目录")
    p.add_argument("--name", help="项目名称")
    p.add_argument("--force-new", action="store_true", help="强制新建模式（即使有已有文件）")

    # validate
    p = sub.add_parser("validate", help="验证文档清晰度")
    p.add_argument("--doc", required=True, help="文档路径")
    p.add_argument("--type", choices=["prd", "arch", "test_outline", "auto"], default="auto")

    # task
    p = sub.add_parser("task", help="任务管理")
    ts = p.add_subparsers(dest="task_cmd")
    tp = ts.add_parser("create"); tp.add_argument("--category", required=True, choices=["prd","arch","check","dev","test"]); tp.add_argument("--title", required=True); tp.add_argument("--description", default=""); tp.add_argument("--iteration", type=int); tp.add_argument("--test-case-ref", dest="test_case_ref")
    tu = ts.add_parser("update"); tu.add_argument("--id", required=True); tu.add_argument("--status", required=True, choices=["todo","in_progress","done","blocked"])
    tl = ts.add_parser("list"); tl.add_argument("--iteration", type=int); tl.add_argument("--status", dest="filter_status"); tl.add_argument("--type")
    ts.add_parser("stats")
    tg = ts.add_parser("gate"); tg.add_argument("--iteration", required=True, type=int)

    # plan
    p = sub.add_parser("plan", help="生成迭代计划")
    p.add_argument("--prd", help="PRD 路径（默认 Docs/product/PRD.md）")
    p.add_argument("--arch", help="架构文档路径")
    p.add_argument("--output", help="输出目录（默认 Docs/iterations）")
    p.add_argument("--constraints", help="约束 JSON，如 {\"max_features_per_iter\": 3}")

    # outline
    p = sub.add_parser("outline", help="测试大纲管理")
    os_ = p.add_subparsers(dest="outline_cmd")
    og = os_.add_parser("generate"); og.add_argument("--prd"); og.add_argument("--arch"); og.add_argument("--output")
    ot = os_.add_parser("trace"); ot.add_argument("--outline"); ot.add_argument("--features", required=True, help="逗号分隔的功能 ID，如 F01,F02")
    oi = os_.add_parser("iter-tests"); oi.add_argument("--outline"); oi.add_argument("--features", required=True); oi.add_argument("--iteration", required=True, type=int); oi.add_argument("--output")

    # gate
    p = sub.add_parser("gate", help="检查迭代门控")
    p.add_argument("--iteration", required=True, type=int)

    # change
    p = sub.add_parser("change", help="处理变更（任意节点）")
    p.add_argument("node", choices=["prd", "code", "test", "iteration"], help="变更发生的节点")
    p.add_argument("--old", help="[prd] 旧版 PRD 路径")
    p.add_argument("--new", help="[prd] 新版 PRD 路径")
    p.add_argument("--components", help="[code] 逗号分隔的修改组件名")
    p.add_argument("--test-id", dest="test_id", help="[test] 失败的测试用例 ID")
    p.add_argument("--failure-type", dest="failure_type", choices=["bug","gap","wrong-test"], help="[test] 失败类型")
    p.add_argument("--from-iter", dest="from_iter", type=int, help="[iteration] 来源迭代")
    p.add_argument("--to-iter", dest="to_iter", type=int, help="[iteration] 目标迭代")

    # test-record
    p = sub.add_parser("test-record", help="记录测试用例执行结果")
    p.add_argument("--iteration", required=True, type=int, help="迭代编号")
    p.add_argument("--test-id", dest="test_id", default=None, help="测试用例 ID（如 TST-F01-S01）")
    p.add_argument("--status", choices=["pass", "fail"], default=None, help="执行结果")
    p.add_argument("--task-ref", dest="task_ref", default="", help="对应任务 ID（可选，如 ITR-1.TST-001）")
    p.add_argument("--resolution", default="", help="[fail 时必填] 说明如何处理该失败")
    p.add_argument("--notes", default="", help="备注（可选）")
    p.add_argument("--list", dest="list_results", action="store_true", help="列出当前迭代所有测试执行记录")

    # manual
    p = sub.add_parser("manual", help="生成/更新用户操作手册")
    p.add_argument("--iteration", type=int, help="基于的最高迭代号（默认自动检测）")

    # status
    sub.add_parser("status", help="查看项目整体状态")

    # pause
    p = sub.add_parser("pause", help="暂停当前工作流")
    p.add_argument("--reason", default="", help="暂停原因")
    p.add_argument("--phase", default="", help="当前所处阶段")

    # resume
    sub.add_parser("resume", help="从暂停状态恢复")

    # cancel
    p = sub.add_parser("cancel", help="取消工作流")
    p.add_argument("--reason", default="")

    # step (Fix 5: proxy to step_enforcer.py)
    p = sub.add_parser("step", help="步骤状态管理（代理 step_enforcer.py）")
    p.add_argument("step_args", nargs=argparse.REMAINDER,
                   help="传给 step_enforcer 的参数，如 status / record <step-id> / require <step-id>")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    cmd_map = {
        "init": cmd_init,
        "validate": cmd_validate,
        "task": cmd_task,
        "plan": cmd_plan,
        "outline": cmd_outline,
        "gate": cmd_gate,
        "change": cmd_change,
        "test-record": cmd_test_record,
        "manual": cmd_manual,
        "status": cmd_status,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "cancel": cmd_cancel,
        "step": cmd_step,
    }

    if args.command is None:
        parser.print_help()
        return 0

    fn = cmd_map.get(args.command)
    if fn is None:
        parser.print_help()
        return 1

    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
