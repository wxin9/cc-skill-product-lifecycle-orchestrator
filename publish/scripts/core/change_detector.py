"""
Change detector — detects PRD diffs and cascades impact across all downstream artifacts.

Four cascade paths:
  A. PRD change → arch / test outline / iteration plans / test cases
  B. Code change → test outline trace → test cases / iteration tasks / arch consistency
  C. Test failure → route to: bug fix (dev) | PRD gap (prd) | test fix (test)
  D. Iteration change → task redistribution / test case alignment / gate reset

Usage:
  python scripts/core/change_detector.py detect --old OLD_PRD --new NEW_PRD
  python scripts/core/change_detector.py impact --change CHANGE.json --graph test_graph.json
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
# Feature extraction from PRD
# --------------------------------------------------------------------------

_FEATURE_HEADING = re.compile(
    r"^\s*#{1,4}\s+(?:F\d+[\.:\s]|功能\d+[\.:\s]|feature\s*\d+[\.:\s])?([^\n]+)",
    re.IGNORECASE | re.MULTILINE,
)
_REQ_ID = re.compile(r"\bREQ-(\d+)\b", re.IGNORECASE)
_FEATURE_ID = re.compile(r"\bF(\d+)\b", re.IGNORECASE)


def _extract_features(content: str) -> dict[str, str]:
    """
    Extract a {feature_id: description} mapping from PRD content.
    Falls back to heading-based extraction when explicit IDs are absent.
    """
    features: dict[str, str] = {}

    # Try explicit REQ-NNN blocks first
    req_blocks = re.finditer(
        r"(REQ-\d+)[^\n]*\n((?:.+\n)*)",
        content,
        re.IGNORECASE,
    )
    for m in req_blocks:
        fid = m.group(1).upper()
        desc = m.group(2).strip()
        features[fid] = desc

    if features:
        return features

    # Fallback: use ## headings as feature IDs
    in_features_section = False
    for m in _FEATURE_HEADING.finditer(content):
        heading = m.group(1).strip()
        if re.search(r"(核心功能|Features?|功能列表)", heading, re.IGNORECASE):
            in_features_section = True
            continue
        if in_features_section:
            if re.match(r"^(用户角色|非功能|数据|架构|API|部署)", heading, re.IGNORECASE):
                break  # left features section
            fid = "F" + str(len(features) + 1).zfill(2)
            features[fid] = heading

    return features


def _infer_affects_data_model(old_desc: str, new_desc: str) -> bool:
    keywords = r"(字段|属性|表|实体|数据库|schema|model|field|column|属性)"
    return bool(re.search(keywords, new_desc or "", re.IGNORECASE)) or bool(
        re.search(keywords, old_desc or "", re.IGNORECASE)
    )


def _infer_affects_api(old_desc: str, new_desc: str) -> bool:
    keywords = r"(接口|API|endpoint|路由|请求|响应|参数)"
    return bool(re.search(keywords, new_desc or "", re.IGNORECASE))


# --------------------------------------------------------------------------
# Public: detect_prd_diff
# --------------------------------------------------------------------------

def detect_prd_diff(
    old_prd_path: str,
    new_prd_path: str,
    old_version: str = "previous",
    new_version: str = "current",
) -> dict:
    """
    Compare two PRD files and return a ChangeReport.

    Args:
        old_prd_path: Path to old PRD (or empty string for new-project baseline).
        new_prd_path: Path to new/updated PRD.

    Returns:
        ChangeReport dict.
    """
    if old_prd_path and Path(old_prd_path).exists():
        old_content = Path(old_prd_path).read_text(encoding="utf-8", errors="replace")
        old_features = _extract_features(old_content)
    else:
        old_features = {}

    new_content = Path(new_prd_path).read_text(encoding="utf-8", errors="replace")
    new_features = _extract_features(new_content)

    changes: List[dict] = []

    # Added
    for fid in new_features:
        if fid not in old_features:
            changes.append({
                "change_type": "added",
                "feature_id": fid,
                "feature_name": new_features[fid][:80],
                "old_description": None,
                "new_description": new_features[fid],
                "affects_data_model": _infer_affects_data_model("", new_features[fid]),
                "affects_api": _infer_affects_api("", new_features[fid]),
            })

    # Deleted
    for fid in old_features:
        if fid not in new_features:
            changes.append({
                "change_type": "deleted",
                "feature_id": fid,
                "feature_name": old_features[fid][:80],
                "old_description": old_features[fid],
                "new_description": None,
                "affects_data_model": _infer_affects_data_model(old_features[fid], ""),
                "affects_api": _infer_affects_api(old_features[fid], ""),
            })

    # Modified / adjusted
    for fid in old_features:
        if fid in new_features and old_features[fid] != new_features[fid]:
            # Heuristic: adjusted = minor wording, modified = structural change
            old_words = set(re.findall(r"\w+", old_features[fid].lower()))
            new_words = set(re.findall(r"\w+", new_features[fid].lower()))
            overlap = len(old_words & new_words) / max(len(old_words | new_words), 1)
            ctype = "adjusted" if overlap > 0.7 else "modified"
            changes.append({
                "change_type": ctype,
                "feature_id": fid,
                "feature_name": new_features[fid][:80],
                "old_description": old_features[fid],
                "new_description": new_features[fid],
                "affects_data_model": _infer_affects_data_model(old_features[fid], new_features[fid]),
                "affects_api": _infer_affects_api(old_features[fid], new_features[fid]),
            })

    added = sum(1 for c in changes if c["change_type"] == "added")
    modified = sum(1 for c in changes if c["change_type"] in ("modified", "adjusted"))
    deleted = sum(1 for c in changes if c["change_type"] == "deleted")

    summary = f"{added} 个功能新增, {modified} 个修改, {deleted} 个删除"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "old_version": old_version,
        "new_version": new_version,
        "changes": changes,
        "summary": summary,
    }


# --------------------------------------------------------------------------
# Internal: graph-based impact analysis
# --------------------------------------------------------------------------

def _cascade_impact_graph(change_report: dict, test_graph_path: str) -> dict:
    """
    Graph-based impact analysis using TestGraph.

    For each changed feature in change_report, uses traverse_impact() to find
    affected nodes. For API changes, uses find_by_api() to locate affected
    nodes first, then traverse_impact() for cascading.

    Returns an ImpactReport dict (same structure as the public functions).
    """
    from .test_graph import TestGraph

    graph = TestGraph.load(test_graph_path)
    changes = change_report.get("changes", [])

    affected_tests: List[str] = []
    affected_iterations: List[int] = []
    impact_items: List[dict] = []
    needs_arch_update = any(
        c.get("affects_data_model") or c.get("affects_api") for c in changes
    )

    # Collect all impacted nodes via graph traversal per change
    impacted_node_ids: set[str] = set()

    for change in changes:
        ctype = change["change_type"]
        fid = change["feature_id"]
        fname = change["feature_name"]

        # Build changed_items for traverse_impact
        changed_items: dict = {"node_ids": [], "apis": [], "data_entities": []}

        # Find graph nodes that belong to this feature (node_id contains fid)
        feature_node_ids = [
            nid for nid in graph.nodes
            if fid.upper() in nid.upper()
        ]
        changed_items["node_ids"] = feature_node_ids

        # If the change affects APIs, locate nodes via find_by_api
        if change.get("affects_api"):
            # Extract API-like patterns from the description
            desc = change.get("new_description") or change.get("old_description") or ""
            api_patterns = re.findall(r"(?:API|api|接口)[\-:/]?\s*([A-Za-z][\w/\-]*)", desc)
            for api_pat in api_patterns:
                matching = graph.find_by_api(api_pat)
                changed_items["apis"].extend(n["node_id"] for n in matching)
            # Also try the feature name itself as an API lookup
            matching = graph.find_by_api(fname)
            changed_items["apis"].extend(n["node_id"] for n in matching)

        # If the change affects data model, locate nodes via find_by_entity
        if change.get("affects_data_model"):
            desc = change.get("new_description") or change.get("old_description") or ""
            entity_patterns = re.findall(
                r"(?:实体|表|model|entity)[\-:/]?\s*([A-Za-z][\w]*)", desc, re.IGNORECASE,
            )
            for entity_pat in entity_patterns:
                matching = graph.find_by_entity(entity_pat)
                changed_items["data_entities"].extend(n["node_id"] for n in matching)

        # Run BFS traversal to find all impacted nodes
        impact_results = graph.traverse_impact(changed_items, direction="both")
        for item in impact_results:
            impacted_node_ids.add(item["node_id"])

        # Build impact items per change type
        if ctype == "added":
            impact_items.append({
                "type": "test",
                "id": f"TST-{fid}-*",
                "description": f"新增功能「{fname}」需要生成测试场景",
                "action_required": "regenerate",
            })
            impact_items.append({
                "type": "iteration",
                "id": "TBD",
                "description": f"新功能「{fname}」需要加入迭代计划",
                "action_required": "update",
            })

        elif ctype in ("modified", "adjusted"):
            verb = "重新生成" if ctype == "modified" else "检查并更新"
            # Find TST-* nodes impacted by this feature change
            for nid in impacted_node_ids:
                node = graph.get_node(nid)
                if node and nid.upper().startswith("TST-") and fid.upper() in nid.upper():
                    impact_items.append({
                        "type": "test",
                        "id": nid,
                        "description": f"功能「{fname}」变更，{verb}对应测试用例",
                        "action_required": "regenerate" if ctype == "modified" else "review",
                    })

        elif ctype == "deleted":
            for nid in impacted_node_ids:
                node = graph.get_node(nid)
                if node and nid.upper().startswith("TST-") and fid.upper() in nid.upper():
                    impact_items.append({
                        "type": "test",
                        "id": nid,
                        "description": f"功能「{fname}」已删除，废弃对应测试用例",
                        "action_required": "deprecate",
                    })

    # Map impacted nodes back to TST-* IDs and iteration numbers
    for nid in impacted_node_ids:
        node = graph.get_node(nid)
        if node is None:
            continue
        # Collect TST-* IDs
        if nid.upper().startswith("TST-"):
            affected_tests.append(nid)
        # Extract iteration references from node tags or node_id
        tags = node.get("tags") or []
        for tag in tags:
            iter_match = re.match(r"iter[- ]?(\d+)", tag, re.IGNORECASE)
            if iter_match:
                n_int = int(iter_match.group(1))
                if n_int not in affected_iterations:
                    affected_iterations.append(n_int)
        # Also check node_id for iteration patterns like TST-F01-ITER3-*
        iter_match = re.search(r"ITER(\d+)", nid, re.IGNORECASE)
        if iter_match:
            n_int = int(iter_match.group(1))
            if n_int not in affected_iterations:
                affected_iterations.append(n_int)

    if needs_arch_update:
        impact_items.append({
            "type": "arch",
            "id": "ARCH.md",
            "description": "变更影响数据模型或 API 设计，需要同步更新架构文档",
            "action_required": "update",
        })

    # Generate summary markdown
    lines = [
        "# 变更影响报告",
        "",
        f"**变更摘要：** {change_report.get('summary', '')}",
        f"**时间：** {change_report.get('timestamp', '')}",
        f"**分析方式：** 图谱遍历（Graph-based）",
        "",
        "## 受影响的测试用例",
    ]
    if affected_tests:
        for t in affected_tests:
            lines.append(f"- [ ] `{t}` — 需要重新验证")
    else:
        lines.append("- 无（无已有测试用例受影响）")

    lines += ["", "## 受影响的迭代"]
    if affected_iterations:
        for n in sorted(affected_iterations):
            lines.append(f"- [ ] 迭代 {n} — 需要重新核对范围和测试覆盖")
    else:
        lines.append("- 无")

    if needs_arch_update:
        lines += ["", "## 架构文档更新", "- [ ] ARCH.md 需要同步更新（数据模型/API 变更）"]

    lines += ["", "## 所有影响项"]
    for item in impact_items:
        action = item["action_required"]
        lines.append(f"- [{item['type'].upper()}] `{item['id']}` — {item['description']} (`{action}`)")

    summary_md = "\n".join(lines)

    return {
        "change_report": change_report,
        "affected_tests": list(dict.fromkeys(affected_tests)),  # dedupe, preserve order
        "affected_iterations": sorted(affected_iterations),
        "needs_arch_update": needs_arch_update,
        "impact_items": impact_items,
        "summary_md": summary_md,
    }


# --------------------------------------------------------------------------
# Public: cascade_impact (from PRD change)
# --------------------------------------------------------------------------

def cascade_impact(change_report: dict, test_graph_path: str) -> dict:
    """
    Given a ChangeReport, find all downstream artifacts that need updating
    using graph-based impact analysis.

    Args:
        change_report: Output of detect_prd_diff().
        test_graph_path: Path to test_graph.json (TestGraph JSON file).

    Returns:
        ImpactReport dict.
    """
    return _cascade_impact_graph(change_report, test_graph_path)


# --------------------------------------------------------------------------
# Public: cascade_from_code_change
# --------------------------------------------------------------------------

def cascade_from_code_change(
    changed_components: List[str],
    test_graph_path: str,
) -> dict:
    """
    Cascade a code/development change through the test graph.

    Uses TestGraph.find_by_api() and TestGraph.find_by_entity() to find
    affected nodes, then traverse_impact() for cascading.

    Args:
        changed_components: List of component names / module descriptions changed.
        test_graph_path: Path to test_graph.json (TestGraph JSON file).

    Returns:
        ImpactReport-like dict focused on test impact.
    """
    from .test_graph import TestGraph

    graph = TestGraph.load(test_graph_path)

    affected_tests: List[str] = []
    impact_items: List[dict] = []
    impacted_node_ids: set[str] = set()

    for comp in changed_components:
        # Try to find nodes via API lookup
        api_nodes = graph.find_by_api(comp)
        # Try to find nodes via entity lookup
        entity_nodes = graph.find_by_entity(comp)
        # Also find nodes whose node_id or name contains the component
        name_match_ids = [
            nid for nid, node in graph.nodes.items()
            if comp.lower() in (node.get("name") or "").lower()
            or comp.lower() in nid.lower()
        ]

        # Collect seed node IDs from all lookup strategies
        seed_node_ids = list(name_match_ids)
        seed_node_ids.extend(n["node_id"] for n in api_nodes)
        seed_node_ids.extend(n["node_id"] for n in entity_nodes)
        # Deduplicate while preserving order
        seen_seeds: set[str] = set()
        unique_seeds: List[str] = []
        for sid in seed_node_ids:
            if sid not in seen_seeds:
                seen_seeds.add(sid)
                unique_seeds.append(sid)

        # Run BFS traversal from these seeds
        changed_items = {"node_ids": unique_seeds}
        impact_results = graph.traverse_impact(changed_items, direction="both")
        for item in impact_results:
            impacted_node_ids.add(item["node_id"])

    # Map impacted nodes to TST-* IDs
    for nid in impacted_node_ids:
        node = graph.get_node(nid)
        if node is None:
            continue
        if nid.upper().startswith("TST-"):
            affected_tests.append(nid)

    affected_tests = list(dict.fromkeys(affected_tests))

    for tst in affected_tests:
        impact_items.append({
            "type": "test",
            "id": tst,
            "description": f"代码变更影响此测试用例，需要重跑/重写",
            "action_required": "review",
        })

    lines = [
        "# 代码变更影响报告",
        "",
        f"**变更组件：** {', '.join(changed_components)}",
        f"**分析方式：** 图谱遍历（Graph-based）",
        "",
        "## 受影响的测试用例",
    ]
    for t in affected_tests:
        lines.append(f"- [ ] `{t}` — 需要重新验证")
    if not affected_tests:
        lines.append("- 未在测试图谱中找到直接关联的测试用例")

    return {
        "change_report": {"changes": [], "summary": f"代码变更：{changed_components}"},
        "affected_tests": affected_tests,
        "affected_iterations": [],
        "needs_arch_update": False,
        "impact_items": impact_items,
        "summary_md": "\n".join(lines),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect PRD changes and cascade impact")
    sub = parser.add_subparsers(dest="cmd")

    detect_p = sub.add_parser("detect", help="Compare two PRD versions")
    detect_p.add_argument("--old", default="", help="Old PRD path (empty for new project)")
    detect_p.add_argument("--new", required=True, help="New/updated PRD path")
    detect_p.add_argument("--output", help="Write ChangeReport JSON to file")

    impact_p = sub.add_parser("impact", help="Cascade change to downstream artifacts")
    impact_p.add_argument("--change", required=True, help="ChangeReport JSON file")
    impact_p.add_argument("--graph", required=True, help="test_graph.json path")
    impact_p.add_argument("--output", help="Write ImpactReport to file")
    impact_p.add_argument("--md", help="Write impact summary markdown to file")

    args = parser.parse_args()

    if args.cmd == "detect":
        report = detect_prd_diff(args.old, args.new)
        out = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"ChangeReport written to {args.output}")
        else:
            print(out)

    elif args.cmd == "impact":
        change_data = json.loads(Path(args.change).read_text(encoding="utf-8"))
        impact = cascade_impact(change_data, args.graph)
        if args.md:
            Path(args.md).write_text(impact["summary_md"], encoding="utf-8")
            print(f"Impact summary written to {args.md}")
        if args.output:
            impact_copy = dict(impact)
            impact_copy["summary_md"] = "[see --md output]"
            Path(args.output).write_text(
                json.dumps(impact_copy, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"ImpactReport written to {args.output}")
        else:
            print(impact["summary_md"])

    else:
        parser.print_help()
        sys.exit(1)
