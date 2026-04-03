"""
Test outline manager — master test outline + impact tracing.

Master outline maps: feature_id → scenarios → test cases (TST-{F}-{S})

Impact tracing:
  Given changed feature IDs or component names, returns all affected TST-* IDs
  so they can be scheduled for re-run or regeneration.

Usage:
  python scripts/core/test_outline.py generate --prd PRD.md --arch ARCH.md --output MASTER_OUTLINE.md
  python scripts/core/test_outline.py trace --outline MASTER_OUTLINE.md --features F01,F02
  python scripts/core/test_outline.py iter-tests --outline MASTER_OUTLINE.md --iter-plan PLAN.md --output test_cases.md
"""
from __future__ import annotations
import re
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# --------------------------------------------------------------------------
# Helpers — feature extraction
# --------------------------------------------------------------------------

def _extract_prd_features(prd_path: str) -> List[dict]:
    """
    Extract features from PRD.md using strong matching only.

    Supported formats (in priority order):
      1. ### F01 — 功能名称       (recommended)
      2. ### REQ-001 功能名称     (legacy)

    If neither format is found, raises SystemExit with a friendly error.
    No loose heading fallback — format mismatch is surfaced, not silently swallowed.

    Returns list of {feature_id, feature_name, description, prd_ref}.
    """
    content = Path(prd_path).read_text(encoding="utf-8", errors="replace")
    features = []

    # Priority 1: ### F01 — 功能名称 (recommended format)
    fid_pattern = re.compile(r"^###\s+(F(\d+))\s*[—\-–]\s*(.+)", re.MULTILINE)
    fid_matches = list(fid_pattern.finditer(content))

    if fid_matches:
        for m in fid_matches:
            raw_fid = m.group(1)          # e.g. "F01" or "F1"
            num = int(m.group(2))
            fid = f"F{num:02d}"           # normalize to F01, F02, ...
            fname = m.group(3).strip()
            # Extract body: text between this heading and the next ### heading
            start = m.end()
            next_heading = re.search(r"^###\s+", content[start:], re.MULTILINE)
            body = content[start: start + next_heading.start()].strip() if next_heading else content[start:].strip()
            features.append({
                "feature_id": fid,
                "feature_name": fname,
                "description": body,
                "prd_ref": f"PRD-{raw_fid}",
            })
        return features

    # Priority 2: ### REQ-001 功能名称 (legacy compat)
    req_pattern = re.compile(r"^###\s+(REQ-(\d+))\s+(.+)", re.MULTILINE | re.IGNORECASE)
    req_matches = list(req_pattern.finditer(content))

    if req_matches:
        for i, m in enumerate(req_matches):
            fid = f"F{(i+1):02d}"
            fname = m.group(3).strip()
            start = m.end()
            next_heading = re.search(r"^###\s+", content[start:], re.MULTILINE)
            body = content[start: start + next_heading.start()].strip() if next_heading else content[start:].strip()
            features.append({
                "feature_id": fid,
                "feature_name": fname,
                "description": body,
                "prd_ref": m.group(1).upper(),
            })
        return features

    # Strong match failed — report error and exit
    print(
        "\n错误：无法从 PRD 提取功能点。\n"
        "请确保核心功能章节使用以下格式之一：\n"
        "  ### F01 — 功能名称（推荐）\n"
        "  ### REQ-001 功能名称\n"
        "\n当前 PRD 中没有找到以上格式的功能定义。\n"
        f"请检查文件：{prd_path}\n",
        file=sys.stderr,
    )
    sys.exit(1)


def _extract_arch_context(arch_path: Optional[str]) -> dict:
    """
    Extract architectural context to guide scenario generation.
    Returns hints about backend APIs, async tasks, data models, external deps.
    """
    ctx = {
        "has_ui": True,
        "has_async_tasks": False,
        "has_external_deps": False,
        "has_file_io": False,
        "has_db": False,
        "api_endpoints": [],        # list of "METHOD /path" strings
        "tech_keywords": [],
    }
    if not arch_path or not Path(arch_path).exists():
        return ctx

    text = Path(arch_path).read_text(encoding="utf-8", errors="replace")
    ctx["has_ui"] = bool(re.search(r"(前端|UI|界面|web|React|Vue|HTML|frontend)", text, re.IGNORECASE))
    ctx["has_async_tasks"] = bool(re.search(r"(Celery|异步|队列|Worker|任务队列|async task|background)", text, re.IGNORECASE))
    ctx["has_external_deps"] = bool(re.search(r"(外部系统|第三方|External|REST API|SDK|平台对接)", text, re.IGNORECASE))
    ctx["has_file_io"] = bool(re.search(r"(文件|上传|下载|导入|导出|Excel|PDF|CSV|upload|download|export)", text, re.IGNORECASE))
    ctx["has_db"] = bool(re.search(r"(数据库|PostgreSQL|MySQL|MongoDB|SQLite|ORM|数据模型)", text, re.IGNORECASE))

    # Extract API endpoints mentioned in arch doc
    ctx["api_endpoints"] = re.findall(r"(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)", text, re.IGNORECASE)

    return ctx


def _generate_scenarios_for_feature(
    feature: dict,
    has_ui: bool = True,
    arch_context: Optional[dict] = None,
) -> List[dict]:
    """
    Generate comprehensive test scenarios for a feature.

    Coverage dimensions:
      1. UI E2E happy path (if has_ui)
      2. UI E2E error path (if has_ui)
      3. Backend API happy path
      4. Backend API error/validation path
      5. Data integrity / persistence
      6. Async task completion (if arch has async)
      7. External dependency failure (if arch has external deps)
      8. File I/O edge cases (if feature involves file operations)
      9. Permission/auth (if feature name suggests it)
    """
    fname = feature["feature_name"]
    desc = feature.get("description", "")
    ctx = arch_context or {"has_ui": has_ui, "has_async_tasks": False,
                           "has_external_deps": False, "has_file_io": False, "has_db": False}
    scenarios = []
    sid = 0

    # ── Dimension 1: UI E2E Happy Path ──
    if ctx.get("has_ui", has_ui):
        sid += 1
        scenarios.append({
            "id": f"S{sid:02d}",
            "description": f"[UI] 正常使用「{fname}」",
            "steps": [
                f"(Given) 用户已登录并进入「{fname}」功能页面",
                "(When) 输入有效数据并提交",
                "(When) 系统处理请求并返回结果",
                "(Then) 页面展示成功反馈",
                "(Then) 数据在页面上正确显示",
            ],
            "expected": f"「{fname}」功能正常运行，界面反馈及时，数据正确展示",
            "e2e": True,
            "layer_entry": "ui",
        })

    # ── Dimension 2: UI E2E Error Path ──
    if ctx.get("has_ui", has_ui):
        sid += 1
        scenarios.append({
            "id": f"S{sid:02d}",
            "description": f"[UI] 「{fname}」异常输入处理",
            "steps": [
                f"(Given) 用户在「{fname}」页面",
                "(When) 输入无效或缺失数据并提交",
                "(Then) 前端校验拦截或后端返回错误",
                "(Then) 页面显示清晰错误提示，不丢失已填内容",
            ],
            "expected": "系统显示清晰错误提示，不造成数据损坏，用户可修正后重试",
            "e2e": True,
            "layer_entry": "ui",
        })

    # ── Dimension 3: Backend API Happy Path ──
    sid += 1
    scenarios.append({
        "id": f"S{sid:02d}",
        "description": f"[API] 「{fname}」接口正常调用",
        "steps": [
            "(Given) 系统已启动，测试数据已准备",
            f"(When) 发送有效请求到「{fname}」相关 API 端点",
            "(Then) 返回 200/201 状态码和正确响应体",
            "(Then) 数据库中记录正确创建/更新",
        ],
        "expected": "API 返回正确响应，数据持久化成功",
        "e2e": True,
        "layer_entry": "api",
    })

    # ── Dimension 4: Backend API Validation ──
    sid += 1
    scenarios.append({
        "id": f"S{sid:02d}",
        "description": f"[API] 「{fname}」接口参数校验",
        "steps": [
            "(Given) 系统已启动",
            "(When) 发送缺失必填字段或非法参数的请求",
            "(Then) 返回 400/422 状态码和错误详情",
            "(Then) 数据库无脏数据写入",
        ],
        "expected": "API 返回 4xx 错误码和可理解的错误信息，不产生部分写入",
        "e2e": True,
        "layer_entry": "api",
    })

    # ── Dimension 5: Data Integrity ──
    if ctx.get("has_db", True):
        sid += 1
        scenarios.append({
            "id": f"S{sid:02d}",
            "description": f"[DATA] 「{fname}」数据完整性",
            "steps": [
                "(Given) 系统有已存在的相关数据",
                f"(When) 执行「{fname}」的创建/更新/删除操作",
                "(Then) 验证关联数据的一致性（外键、级联）",
                "(Then) 验证并发操作不产生数据冲突",
            ],
            "expected": "数据操作保持引用完整性，无孤立记录或级联异常",
            "e2e": False,
            "layer_entry": "api",
        })

    # ── Dimension 6: Async Task ──
    if ctx.get("has_async_tasks"):
        async_keywords = r"(验证|分析|生成|报告|推送|同步|批量|连通|检查|导入|导出|计算)"
        if re.search(async_keywords, fname + desc, re.IGNORECASE):
            sid += 1
            scenarios.append({
                "id": f"S{sid:02d}",
                "description": f"[ASYNC] 「{fname}」异步任务完成与超时",
                "steps": [
                    f"(Given) 用户触发「{fname}」的异步操作",
                    "(When) 任务提交到队列并开始执行",
                    "(Then) 轮询/回调显示任务进度",
                    "(Then) 任务完成后结果正确写入数据库",
                    "(Then) 验证任务超时时的友好提示",
                ],
                "expected": "异步任务正常完成并回写结果；超时时给出明确反馈，不进入死循环",
                "e2e": True,
                "layer_entry": "api",
            })

    # ── Dimension 7: External Dependency Failure ──
    if ctx.get("has_external_deps"):
        ext_keywords = r"(推送|对接|同步|上报|平台|外部|第三方|MCP|知识库)"
        if re.search(ext_keywords, fname + desc, re.IGNORECASE):
            sid += 1
            scenarios.append({
                "id": f"S{sid:02d}",
                "description": f"[EXT] 「{fname}」外部服务不可用时的降级",
                "steps": [
                    "(Given) 外部依赖服务不可达或返回错误",
                    f"(When) 用户触发「{fname}」中依赖外部服务的操作",
                    "(Then) 系统捕获异常并给出友好提示",
                    "(Then) 本地数据不受影响，操作可重试",
                ],
                "expected": "外部服务故障时系统优雅降级，不崩溃，不丢数据",
                "e2e": True,
                "layer_entry": "api",
            })

    # ── Dimension 8: File I/O ──
    if ctx.get("has_file_io"):
        file_keywords = r"(导入|导出|上传|下载|报告|Excel|文件|CSV|YAML|JSON)"
        if re.search(file_keywords, fname + desc, re.IGNORECASE):
            sid += 1
            scenarios.append({
                "id": f"S{sid:02d}",
                "description": f"[FILE] 「{fname}」文件操作边界",
                "steps": [
                    "(Given) 准备各种格式/大小的测试文件",
                    f"(When) 使用「{fname}」处理空文件/超大文件/错误格式文件",
                    "(Then) 空文件和错误格式返回清晰错误",
                    "(Then) 正常文件处理结果正确",
                ],
                "expected": "文件操作对边界情况有明确的错误处理，中文文件名不乱码",
                "e2e": True,
                "layer_entry": "api",
            })

    # ── Dimension 9: Permission / Auth ──
    if re.search(r"(权限|角色|登录|用户|授权|管理员|认证|auth)", fname + desc, re.IGNORECASE):
        sid += 1
        scenarios.append({
            "id": f"S{sid:02d}",
            "description": f"[AUTH] 「{fname}」权限控制",
            "steps": [
                "(Given) 以无权限或未认证用户身份发起请求",
                f"(When) 访问「{fname}」的受保护资源",
                "(Then) 系统返回 401/403 并拒绝访问",
                "(Then) 无敏感数据泄露",
            ],
            "expected": "系统拒绝无权限访问并返回适当错误码",
            "e2e": True,
            "layer_entry": "api",
        })

    return scenarios


# --------------------------------------------------------------------------
# Public: generate_outline
# --------------------------------------------------------------------------

def generate_outline(
    prd_path: str,
    arch_path: Optional[str] = None,
    prd_version: str = "1.0",
    arch_version: str = "1.0",
) -> dict:
    """
    Generate a MasterOutline from PRD (and optionally ARCH).

    Uses architecture context to generate multi-dimensional test scenarios:
    UI E2E, Backend API, Data Integrity, Async Tasks, External Deps, File I/O, Auth.

    Returns MasterOutline dict.
    """
    features = _extract_prd_features(prd_path)
    arch_ctx = _extract_arch_context(arch_path)

    entries: List[dict] = []
    total_scenarios = 0

    for feat in features:
        scenarios = _generate_scenarios_for_feature(feat, arch_ctx.get("has_ui", True), arch_ctx)
        total_scenarios += len(scenarios)
        entries.append({
            "feature_id": feat["feature_id"],
            "feature_name": feat["feature_name"],
            "prd_ref": feat["prd_ref"],
            "scenarios": scenarios,
        })

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prd_version": prd_version,
        "arch_version": arch_version,
        "entries": entries,
        "total_scenarios": total_scenarios,
    }


# --------------------------------------------------------------------------
# Public: write_outline (to markdown)
# --------------------------------------------------------------------------

def write_outline(outline: dict, output_path: str) -> None:
    """Write MasterOutline to MASTER_OUTLINE.md with coverage matrix."""
    lines = [
        "# 主测试大纲 (Master Test Outline)",
        "",
        f"**版本：** {outline['version']}  |  **生成时间：** {outline['generated_at']}",
        f"**基于 PRD 版本：** {outline['prd_version']}  |  **架构版本：** {outline['arch_version']}",
        f"**总测试场景数：** {outline['total_scenarios']}",
        "",
        "> 此文件是测试追溯的权威来源。任何需求或代码变更后，",
        "> 请通过 `python scripts/__main__.py outline trace` 找出受影响的测试用例。",
        "",
        "---",
        "",
        "## 测试覆盖矩阵",
        "",
        "| 功能 ID | 功能名称 | 场景数 | UI | API | DATA | ASYNC | EXT | FILE | AUTH |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    # Build coverage matrix
    for entry in outline["entries"]:
        fid = entry["feature_id"]
        fname = entry["feature_name"]
        sc_count = len(entry["scenarios"])
        dims = {"UI": 0, "API": 0, "DATA": 0, "ASYNC": 0, "EXT": 0, "FILE": 0, "AUTH": 0}
        for sc in entry["scenarios"]:
            desc = sc.get("description", "")
            for dim in dims:
                if f"[{dim}]" in desc:
                    dims[dim] += 1
        row = f"| {fid} | {fname} | {sc_count} |"
        for dim in dims:
            row += f" {'✓' if dims[dim] else '—'} |"
        lines.append(row)

    lines += ["", "---", ""]

    for entry in outline["entries"]:
        fid = entry["feature_id"]
        fname = entry["feature_name"]
        prd_ref = entry["prd_ref"]
        lines += [
            f"## {fid} — {fname}",
            f"**PRD 来源：** `{prd_ref}`",
            "",
        ]
        for sc in entry["scenarios"]:
            tst_id = f"TST-{fid}-{sc['id']}"
            e2e_badge = " `[E2E]`" if sc.get("e2e") else ""
            entry_badge = f" `[{sc.get('layer_entry', 'api').upper()}]`"
            lines += [
                f"### {tst_id} — {sc['description']}{e2e_badge}{entry_badge}",
                "",
                "**测试步骤：**",
            ]
            for i, step in enumerate(sc.get("steps", []), 1):
                lines.append(f"{i}. {step}")
            lines += [
                "",
                f"**期望结果：** {sc['expected']}",
                "",
                "**状态：** `active`",
                "",
            ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Public: trace_impact
# --------------------------------------------------------------------------

def trace_impact(
    changed_feature_ids: List[str],
    outline_path: str,
) -> List[str]:
    """
    Return list of TST-* IDs affected by changes to the given feature IDs.
    """
    if not Path(outline_path).exists():
        return []

    outline_text = Path(outline_path).read_text(encoding="utf-8", errors="replace")
    affected: List[str] = []

    for fid in changed_feature_ids:
        fid_upper = fid.upper()
        # Find all TST-{fid}-* in the outline
        matches = re.findall(rf"TST-{re.escape(fid_upper)}-\w+", outline_text)
        affected.extend(matches)

    return list(dict.fromkeys(affected))  # dedupe, preserve order


# --------------------------------------------------------------------------
# Public: generate_iteration_tests
# --------------------------------------------------------------------------

def generate_iteration_tests(
    iteration_plan: dict,
    outline: dict,
    iteration_number: int,
) -> List[dict]:
    """
    Generate E2E test cases for a specific iteration based on the master outline.

    Args:
        iteration_plan: Iteration dict with feature_ids.
        outline: MasterOutline dict.
        iteration_number: The iteration number.

    Returns:
        List of TestCase dicts.
    """
    feature_ids = iteration_plan.get("feature_ids", [])
    test_cases: List[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    entry_map = {e["feature_id"]: e for e in outline.get("entries", [])}

    for fid in feature_ids:
        entry = entry_map.get(fid)
        if not entry:
            continue
        for sc in entry.get("scenarios", []):
            tc_id = f"TST-{fid}-{sc['id']}"
            test_cases.append({
                "id": tc_id,
                "title": f"{entry['feature_name']}: {sc['description']}",
                "feature_id": fid,
                "scenario_id": sc["id"],
                "preconditions": ["系统已部署并可访问", "测试数据已准备就绪"],
                "steps": sc.get("steps", []),
                "expected": sc.get("expected", ""),
                "e2e": sc.get("e2e", False),
                "layer_entry": sc.get("layer_entry", "api"),
                "iteration_ref": iteration_number,
                "status": "active",
                "created_at": now,
            })

    return test_cases


def write_iteration_tests(
    test_cases: List[dict],
    output_path: str,
    iteration_number: int,
) -> None:
    """Write iteration test cases to markdown."""
    lines = [
        f"# 迭代 {iteration_number} — 测试用例",
        "",
        f"_共 {len(test_cases)} 个测试用例_",
        "",
        "---",
        "",
    ]
    for tc in test_cases:
        e2e_badge = " `[E2E]`" if tc.get("e2e") else ""
        entry_badge = f" `[{tc.get('layer_entry', '').upper()}]`"
        lines += [
            f"## {tc['id']} — {tc['title']}{e2e_badge}{entry_badge}",
            "",
        ]
        if tc.get("preconditions"):
            lines.append("**前置条件：**")
            for p in tc["preconditions"]:
                lines.append(f"- {p}")
            lines.append("")
        if tc.get("steps"):
            lines.append("**测试步骤：**")
            for i, step in enumerate(tc["steps"], 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        lines += [
            f"**期望结果：** {tc.get('expected', '')}",
            "",
            "**执行结果：** [ ] 未执行  [ ] 通过  [ ] 失败",
            "",
        ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test outline manager")
    sub = parser.add_subparsers(dest="cmd")

    gen_p = sub.add_parser("generate", help="Generate master test outline from PRD")
    gen_p.add_argument("--prd", required=True)
    gen_p.add_argument("--arch", default="")
    gen_p.add_argument("--output", default="Docs/tests/MASTER_OUTLINE.md")

    trace_p = sub.add_parser("trace", help="Trace impact of feature changes")
    trace_p.add_argument("--outline", required=True)
    trace_p.add_argument("--features", required=True, help="Comma-separated feature IDs, e.g. F01,F02")

    iter_p = sub.add_parser("iter-tests", help="Generate iteration test cases")
    iter_p.add_argument("--outline", required=True)
    iter_p.add_argument("--features", required=True, help="Comma-separated feature IDs for this iteration")
    iter_p.add_argument("--iteration", required=True, type=int)
    iter_p.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.cmd == "generate":
        outline = generate_outline(args.prd, args.arch or None)
        write_outline(outline, args.output)
        print(f"✓ 主测试大纲已生成: {args.output}")
        print(f"  功能点: {len(outline['entries'])}  测试场景: {outline['total_scenarios']}")

    elif args.cmd == "trace":
        feature_ids = [f.strip() for f in args.features.split(",")]
        affected = trace_impact(feature_ids, args.outline)
        if affected:
            print(f"受影响的测试用例 ({len(affected)}):")
            for t in affected:
                print(f"  - {t}")
        else:
            print("未找到受影响的测试用例（检查 feature ID 是否正确）")

    elif args.cmd == "iter-tests":
        # Load outline as dict
        outline_text = Path(args.outline).read_text(encoding="utf-8", errors="replace")
        # Parse outline from markdown (simplified)
        feature_ids = [f.strip() for f in args.features.split(",")]
        iter_plan = {"feature_ids": feature_ids}
        # Re-generate outline from scratch to get structured data
        outline_data = {"entries": [], "version": "1.0", "generated_at": "", "prd_version": "", "arch_version": "", "total_scenarios": 0}
        # Parse from markdown text
        current_entry = None
        for line in outline_text.split("\n"):
            m = re.match(r"## (F\d+) — (.+)", line)
            if m:
                if current_entry:
                    outline_data["entries"].append(current_entry)
                current_entry = {"feature_id": m.group(1), "feature_name": m.group(2), "prd_ref": "", "scenarios": []}
            sc_m = re.match(r"### (TST-\w+-\w+) — (.+?)(\s+`\[.*\]`)*$", line)
            if sc_m and current_entry:
                sc_id = sc_m.group(2)
                is_e2e = "[E2E]" in line
                entry_layer = "ui" if "[UI]" in line else "api"
                current_entry["scenarios"].append({
                    "id": sc_m.group(1).split("-")[-1],
                    "description": sc_id,
                    "steps": [],
                    "expected": "",
                    "e2e": is_e2e,
                    "layer_entry": entry_layer,
                })
        if current_entry:
            outline_data["entries"].append(current_entry)

        cases = generate_iteration_tests(iter_plan, outline_data, args.iteration)
        write_iteration_tests(cases, args.output, args.iteration)
        print(f"✓ 迭代 {args.iteration} 测试用例已生成: {args.output}  ({len(cases)} 个)")

    else:
        parser.print_help()
        sys.exit(1)
