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


def _adjust_for_boundary(steps, feature_name):
    """Adjust steps for boundary testing."""
    result = steps[:]
    if len(result) > 1:
        result[0] = result[0].replace("有效", "边界值").replace("正常", "边界值")
    return result


def _adjust_for_error(steps, feature_name):
    """Adjust steps for error testing."""
    result = steps[:]
    if len(result) > 1:
        result[0] = result[0].replace("有效", "无效/异常").replace("正常", "异常")
    return result


def _adjust_for_data(steps, feature_name):
    """Adjust steps for data anomaly testing."""
    result = steps[:]
    if len(result) > 1:
        result[0] = result[0].replace("输入", "输入异常数据").replace("有效数据", "脏数据/空数据")
    return result


def _generate_scenarios_for_feature(feature, project_type="web", arch_context=None):
    """Generate test scenarios for a feature using dimension-driven approach."""
    from .project_type_detector import get_dimension_generators

    dimension_configs = get_dimension_generators(project_type)
    scenarios = []

    VARIANT_LABELS = {"happy": "正向", "boundary": "边界", "error": "异常", "data": "数据异常"}

    feature_name = feature.get("feature_name", feature.get("name", ""))
    feature_desc = feature.get("description", "")
    feature_text = f"{feature_name} {feature_desc}".lower()

    sid = 0

    for dim_config in dimension_configs:
        tag = dim_config["dimension_tag"]

        # Check conditional_keywords: if non-empty, feature must match at least one
        cond_kw = dim_config.get("conditional_keywords", [])
        if cond_kw and not any(kw.lower() in feature_text for kw in cond_kw):
            continue

        # Generate one scenario per defensive variant
        for variant in dim_config.get("defensive_variants", ["happy"]):
            sid += 1
            variant_label = VARIANT_LABELS.get(variant, variant)
            scenario = {
                "id": f"S{sid:02d}",
                "dimension": tag,
                "variant": variant,
                "description": dim_config["description_template"].format(
                    variant_label=variant_label, feature_name=feature_name
                ),
                "steps": [s.format(feature_name=feature_name) for s in dim_config["steps_template"]],
                "expected": dim_config["expected_template"].format(feature_name=feature_name),
                "e2e": dim_config.get("e2e", False) and variant == "happy",
                "layer_entry": dim_config.get("layer_entry", "api"),
                "preconditions": [],
                "feature_id": feature.get("feature_id", feature.get("id", "")),
            }

            # Adjust steps/expected based on variant type
            if variant == "boundary":
                scenario["steps"] = _adjust_for_boundary(scenario["steps"], feature_name)
                scenario["expected"] = f"系统正确处理边界情况，{feature_name}返回预期结果"
            elif variant == "error":
                scenario["steps"] = _adjust_for_error(scenario["steps"], feature_name)
                scenario["expected"] = f"系统正确处理异常输入，{feature_name}给出明确错误提示"
            elif variant == "data":
                scenario["steps"] = _adjust_for_data(scenario["steps"], feature_name)
                scenario["expected"] = f"系统正确处理异常数据，{feature_name}数据完整性得到保障"

            scenarios.append(scenario)

    return scenarios


# --------------------------------------------------------------------------
# Public: generate_outline
# --------------------------------------------------------------------------

def generate_outline(
    prd_path: str,
    arch_path: Optional[str] = None,
    prd_version: str = "1.0",
    arch_version: str = "1.0",
) -> tuple:
    """
    Generate a MasterOutline from PRD (and optionally ARCH).

    Uses dimension-driven scenario generation based on detected project type.
    Returns (legacy_dict, test_graph) tuple.
    """
    from .project_type_detector import detect_from_arch
    from .test_graph import TestGraph

    # Detect project type
    project_type = "web"  # default
    if arch_path and Path(arch_path).exists():
        try:
            project_type = detect_from_arch(arch_path)
        except Exception:
            pass

    # Extract features from PRD
    features = _extract_prd_features(prd_path)

    # Generate scenarios using dimension-driven approach
    all_scenarios = {}
    for feat in features:
        feat_id = feat.get("feature_id", "")
        feat_scenarios = _generate_scenarios_for_feature(feat, project_type=project_type)
        all_scenarios[feat_id] = feat_scenarios

    # Build TestGraph
    graph = _build_test_graph(features, all_scenarios, project_type, prd_version, arch_version, arch_path)

    # Build legacy MasterOutline dict (for backward compat output)
    legacy = _build_legacy_outline(features, all_scenarios, project_type, prd_version, arch_version)

    return legacy, graph


def _build_test_graph(features, all_scenarios, project_type, prd_version, arch_version, arch_path=None):
    """Build a TestGraph from features and scenarios."""
    from .test_graph import TestGraph
    from .dependency_extractor import extract_apis, extract_data_entities, infer_feature_dependencies

    graph = TestGraph()
    graph.project_type = project_type
    graph.prd_version = prd_version
    graph.arch_version = arch_version
    graph._generated_at = datetime.now(timezone.utc).isoformat()

    # Collect dimensions used
    dims_used = set()

    # Extract dependencies from ARCH.md if available
    arch_apis = []
    arch_entities = []
    if arch_path and Path(arch_path).exists():
        with open(arch_path, 'r', encoding='utf-8') as f:
            arch_text = f.read()
        arch_apis = extract_apis(arch_text)
        arch_entities = extract_data_entities(arch_text)
        graph.global_apis = arch_apis
        graph.global_entities = arch_entities

    # Add feature nodes
    for feat in features:
        feat_id = feat.get("feature_id", "")
        feat_node = {
            "node_id": feat_id,
            "node_type": "feature",
            "name": feat.get("feature_name", ""),
            "description": feat.get("description", ""),
            "priority": "P1",
            "tags": [],
            "children": [],
            "dependencies": {
                "upstream_nodes": [],
                "downstream_nodes": [],
                "apis": [],
                "data_entities": [],
                "state_pre": [],
                "state_post": [],
            },
            "business_rules": [],
        }
        graph.add_node(feat_node)

        # Add scenario children
        for i, sc in enumerate(all_scenarios.get(feat_id, []), 1):
            sc_id = f"{feat_id}-S{i:02d}"
            dim = sc.get("dimension", "")
            dims_used.add(dim)
            sc_node = {
                "node_id": sc_id,
                "node_type": "scenario",
                "name": sc.get("description", ""),
                "description": sc.get("description", ""),
                "priority": "P1",
                "tags": [dim],
                "children": [],
                "dependencies": {
                    "upstream_nodes": [],
                    "downstream_nodes": [],
                    "apis": [],
                    "data_entities": [],
                    "state_pre": [],
                    "state_post": [],
                },
                "business_rules": [],
                "steps": sc.get("steps", []),
                "expected": sc.get("expected", ""),
                "e2e": sc.get("e2e", False),
                "layer_entry": sc.get("layer_entry", "api"),
                "dimension": dim,
            }
            graph.add_node(sc_node, parent_id=feat_id)

    graph.dimensions_used = sorted(dims_used)

    # Infer dependencies
    if arch_apis or arch_entities:
        dep_map = infer_feature_dependencies(features, arch_text if arch_path and Path(arch_path).exists() else "")
        for feat_id, deps in dep_map.items():
            node = graph.get_node(feat_id)
            if node:
                node["dependencies"].update(deps)
                # Add graph edges for upstream/downstream
                for up_id in deps.get("upstream_nodes", []):
                    try:
                        graph.add_dependency(up_id, feat_id, "upstream")
                    except KeyError:
                        pass

    return graph


def _build_legacy_outline(features, all_scenarios, project_type, prd_version, arch_version):
    """Build the legacy MasterOutline dict from features and scenarios."""
    entries = []
    total_scenarios = 0

    for feat in features:
        feat_id = feat.get("feature_id", "")
        scenarios = all_scenarios.get(feat_id, [])
        total_scenarios += len(scenarios)
        entries.append({
            "feature_id": feat_id,
            "feature_name": feat.get("feature_name", ""),
            "prd_ref": feat.get("prd_ref", ""),
            "scenarios": scenarios,
        })

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prd_version": prd_version,
        "arch_version": arch_version,
        "project_type": project_type,
        "entries": entries,
        "total_scenarios": total_scenarios,
    }


# --------------------------------------------------------------------------
# Public: write_outline (to markdown)
# --------------------------------------------------------------------------

def write_outline(outline: dict, output_path: str, test_graph=None) -> None:
    """Write MasterOutline to MASTER_OUTLINE.md with coverage matrix.

    If test_graph is provided, also saves test_graph.json to .lifecycle/.
    """
    lines = [
        "# 主测试大纲 (Master Test Outline)",
        "",
        f"**版本：** {outline['version']}  |  **生成时间：** {outline['generated_at']}",
        f"**基于 PRD 版本：** {outline['prd_version']}  |  **架构版本：** {outline['arch_version']}",
        f"**项目类型：** {outline.get('project_type', 'web')}  |  **总测试场景数：** {outline['total_scenarios']}",
        "",
        "> 此文件是测试追溯的权威来源。任何需求或代码变更后，",
        "> 请通过 `python scripts/__main__.py outline trace` 找出受影响的测试用例。",
        "",
        "---",
        "",
        "## 测试覆盖矩阵",
        "",
    ]

    # Collect all dimensions dynamically from scenarios
    all_dims = set()
    for entry in outline["entries"]:
        for sc in entry["scenarios"]:
            dim = sc.get("dimension", "")
            if dim:
                all_dims.add(dim)
            # Fallback: parse from description for legacy scenarios
            elif sc.get("description", ""):
                m = re.match(r"\[(\w+)\]", sc["description"])
                if m:
                    all_dims.add(f"[{m.group(1)}]")

    dim_list = sorted(all_dims) if all_dims else ["UI", "API", "DATA"]

    # Build matrix header
    header = "| 功能 ID | 功能名称 | 场景数 | " + " | ".join(d.strip("[]") for d in dim_list) + " |"
    sep = "|---|---|---|" + "|".join(["---"] * len(dim_list)) + "|"
    lines.append(header)
    lines.append(sep)

    # Build coverage matrix rows
    for entry in outline["entries"]:
        fid = entry["feature_id"]
        fname = entry["feature_name"]
        sc_count = len(entry["scenarios"])
        dim_hits = {d: 0 for d in dim_list}
        for sc in entry["scenarios"]:
            sc_dim = sc.get("dimension", "")
            if sc_dim and sc_dim in dim_hits:
                dim_hits[sc_dim] += 1
            elif not sc_dim:
                # Fallback: parse from description
                m = re.match(r"\[(\w+)\]", sc.get("description", ""))
                if m:
                    tag = f"[{m.group(1)}]"
                    if tag in dim_hits:
                        dim_hits[tag] += 1
        row = f"| {fid} | {fname} | {sc_count} |"
        for d in dim_list:
            row += f" {'✓' if dim_hits[d] else '—'} |"
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

    # Save test_graph.json
    if test_graph is not None:
        graph_path = os.path.join(os.path.dirname(output_path), "..", "..", ".lifecycle", "test_graph.json")
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        test_graph.save(graph_path)


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
