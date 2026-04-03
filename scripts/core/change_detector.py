"""
Change detector — detects PRD diffs and cascades impact across all downstream artifacts.

Four cascade paths:
  A. PRD change → arch / test outline / iteration plans / test cases
  B. Code change → test outline trace → test cases / iteration tasks / arch consistency
  C. Test failure → route to: bug fix (dev) | PRD gap (prd) | test fix (test)
  D. Iteration change → task redistribution / test case alignment / gate reset

Usage:
  python scripts/core/change_detector.py detect --old OLD_PRD --new NEW_PRD
  python scripts/core/change_detector.py impact --change CHANGE.json --outline OUTLINE.md
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
# Public: cascade_impact (from PRD change)
# --------------------------------------------------------------------------

def cascade_impact(change_report: dict, master_outline_path: str) -> dict:
    """
    Given a ChangeReport, find all downstream artifacts that need updating.

    Args:
        change_report: Output of detect_prd_diff().
        master_outline_path: Path to MASTER_OUTLINE.md.

    Returns:
        ImpactReport dict.
    """
    changes = change_report.get("changes", [])
    changed_ids = {c["feature_id"] for c in changes}

    affected_tests: List[str] = []
    affected_iterations: List[int] = []
    impact_items: List[dict] = []
    needs_arch_update = any(
        c.get("affects_data_model") or c.get("affects_api") for c in changes
    )

    # Scan MASTER_OUTLINE.md for affected scenarios
    if Path(master_outline_path).exists():
        outline_text = Path(master_outline_path).read_text(encoding="utf-8", errors="replace")
        for fid in changed_ids:
            # Find TST-{fid}-* references
            tst_refs = re.findall(rf"TST-{re.escape(fid)}-\w+", outline_text, re.IGNORECASE)
            affected_tests.extend(tst_refs)
            # Find iteration references near this feature
            iter_refs = re.findall(rf"iter[- ]?(\d+)", outline_text[
                max(0, outline_text.lower().find(fid.lower()) - 200):
                outline_text.lower().find(fid.lower()) + 200
            ], re.IGNORECASE)
            for n in iter_refs:
                n_int = int(n)
                if n_int not in affected_iterations:
                    affected_iterations.append(n_int)

    # Build impact items
    for change in changes:
        ctype = change["change_type"]
        fid = change["feature_id"]
        fname = change["feature_name"]

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
            for tst in [t for t in affected_tests if fid in t]:
                impact_items.append({
                    "type": "test",
                    "id": tst,
                    "description": f"功能「{fname}」变更，{verb}对应测试用例",
                    "action_required": "regenerate" if ctype == "modified" else "review",
                })

        elif ctype == "deleted":
            for tst in [t for t in affected_tests if fid in t]:
                impact_items.append({
                    "type": "test",
                    "id": tst,
                    "description": f"功能「{fname}」已删除，废弃对应测试用例",
                    "action_required": "deprecate",
                })

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
# Public: cascade_from_code_change
# --------------------------------------------------------------------------

def cascade_from_code_change(
    changed_components: List[str],
    master_outline_path: str,
) -> dict:
    """
    Cascade a code/development change through the test outline.

    Args:
        changed_components: List of component names / module descriptions changed.
        master_outline_path: Path to MASTER_OUTLINE.md.

    Returns:
        ImpactReport-like dict focused on test impact.
    """
    affected_tests: List[str] = []
    impact_items: List[dict] = []

    if Path(master_outline_path).exists():
        outline_text = Path(master_outline_path).read_text(encoding="utf-8", errors="replace")
        for comp in changed_components:
            # Search for component name mentions in outline
            matches = re.finditer(re.escape(comp), outline_text, re.IGNORECASE)
            for m in matches:
                # Find nearby TST-* references (within ±500 chars)
                window = outline_text[max(0, m.start()-500):m.end()+500]
                tsts = re.findall(r"TST-[A-Z0-9]+-[A-Z0-9]+", window)
                affected_tests.extend(tsts)

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
        "",
        "## 受影响的测试用例",
    ]
    for t in affected_tests:
        lines.append(f"- [ ] `{t}` — 需要重新验证")
    if not affected_tests:
        lines.append("- 未在测试大纲中找到直接关联的测试用例")

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
    impact_p.add_argument("--outline", required=True, help="MASTER_OUTLINE.md path")
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
        impact = cascade_impact(change_data, args.outline)
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
