"""
Machine-readable lifecycle specs.

This module turns approved human docs into JSON specs and builds a lifecycle
graph that can drive impact analysis, test generation, and gate checks.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scripts.core import paths


SPEC_DIR = Path(".lifecycle/specs")
SCHEMA_DIR = SPEC_DIR / "schemas"

PRODUCT_SPEC = SPEC_DIR / "product.spec.json"
UED_SPEC = SPEC_DIR / "ued.spec.json"
TECH_SPEC = SPEC_DIR / "tech.spec.json"
TEST_SPEC = SPEC_DIR / "test.spec.json"
LIFECYCLE_GRAPH = SPEC_DIR / "lifecycle_graph.json"
IMPACT_JSON = SPEC_DIR / "impact.json"

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "product.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Product Spec",
        "type": "object",
        "required": ["version", "product", "features"],
        "properties": {
            "version": {"type": "string"},
            "product": {"type": "object"},
            "features": {"type": "array"},
        },
    },
    "ued.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "UED Spec",
        "type": "object",
        "required": ["version", "implements_product_spec", "screens", "flows"],
        "properties": {
            "version": {"type": "string"},
            "implements_product_spec": {"type": "string"},
            "screens": {"type": "array"},
            "flows": {"type": "array"},
        },
    },
    "tech.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Tech Spec",
        "type": "object",
        "required": ["version", "implements_product_spec", "modules"],
        "properties": {
            "version": {"type": "string"},
            "implements_product_spec": {"type": "string"},
            "modules": {"type": "array"},
            "apis": {"type": "array"},
            "data_model": {"type": "array"},
        },
    },
    "test.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Test Spec",
        "type": "object",
        "required": ["version", "tests"],
        "properties": {
            "version": {"type": "string"},
            "tests": {"type": "array"},
        },
    },
    "lifecycle_graph.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Lifecycle Graph",
        "type": "object",
        "required": ["version", "nodes", "edges"],
        "properties": {
            "version": {"type": "string"},
            "nodes": {"type": "array"},
            "edges": {"type": "array"},
        },
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_path(root: str | Path, relative: str | Path) -> Path:
    return Path(root).resolve() / Path(relative)


def _write_json(path: Path, data: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_spec_dirs(root: str | Path) -> List[Path]:
    """Create spec directories and baseline schema files."""
    root = Path(root).resolve()
    written: List[Path] = []
    (root / SCHEMA_DIR).mkdir(parents=True, exist_ok=True)
    for filename, schema in SCHEMAS.items():
        schema_path = root / SCHEMA_DIR / filename
        if not schema_path.exists():
            _write_json(schema_path, schema)
            written.append(schema_path)
    return written


def generate_product_spec(root: str | Path, prd_path: str = paths.PRD_PATH) -> Dict[str, Any]:
    """Generate Product Spec from PRD.md."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    doc = _root_path(root, prd_path)
    content = doc.read_text(encoding="utf-8", errors="replace") if doc.exists() else ""

    features = _extract_product_features(content)
    if not features:
        features = [_fallback_feature(root.name, content)]

    product_name = _extract_title(content) or root.name
    spec = {
        "version": "1.0",
        "generated_at": now_iso(),
        "source_doc": prd_path,
        "product": {
            "name": product_name,
            "vision": _extract_section_summary(content, ["产品愿景", "Overview", "Vision"]) or product_name,
            "scope": {
                "in": _extract_scope(content, include=True),
                "out": _extract_scope(content, include=False),
            },
        },
        "features": features,
        "non_functional_requirements": _extract_nfr(content),
    }
    _write_json(root / PRODUCT_SPEC, spec)
    return spec


def generate_ued_spec(root: str | Path) -> Dict[str, Any]:
    """Generate UED/interaction spec from Product Spec."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    product = _load_or_generate_product(root)

    screens: List[Dict[str, Any]] = []
    flows: List[Dict[str, Any]] = []
    for feature in product.get("features", []):
        feature_id = feature.get("id", "F00")
        req_refs = _feature_requirement_ids(feature)
        screen_id = f"SCREEN-{feature_id}"
        flow_id = f"FLOW-{feature_id}"
        screens.append({
            "id": screen_id,
            "name": f"{feature.get('title', feature_id)} 交互界面",
            "feature_ref": feature_id,
            "requirement_refs": req_refs,
            "states": ["empty", "loading", "success", "error"],
            "actions": [
                {
                    "id": f"ACT-{feature_id}-PRIMARY",
                    "label": "执行主要操作",
                    "trigger": "user_action",
                    "requirement_refs": req_refs,
                }
            ],
        })
        flows.append({
            "id": flow_id,
            "name": f"{feature.get('title', feature_id)} 主流程",
            "feature_ref": feature_id,
            "requirement_refs": req_refs,
            "screen_refs": [screen_id],
        })

    spec = {
        "version": "1.0",
        "generated_at": now_iso(),
        "implements_product_spec": str(PRODUCT_SPEC),
        "source_doc": "Docs/product/UED.md",
        "screens": screens,
        "flows": flows,
    }
    _write_json(root / UED_SPEC, spec)
    return spec


def generate_tech_spec(root: str | Path, arch_path: str = paths.ARCH_PATH) -> Dict[str, Any]:
    """Generate Tech Spec from architecture doc and Product Spec."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    product = _load_or_generate_product(root)
    arch = _root_path(root, arch_path)
    arch_text = arch.read_text(encoding="utf-8", errors="replace") if arch.exists() else ""
    endpoints = _extract_api_endpoints(arch_text)
    entities = _extract_data_entities(arch_text)

    modules: List[Dict[str, Any]] = []
    apis: List[Dict[str, Any]] = []

    for feature in product.get("features", []):
        feature_id = feature.get("id", "F00")
        req_refs = _feature_requirement_ids(feature)
        module_id = f"MOD-{feature_id}"
        modules.append({
            "id": module_id,
            "name": f"{feature.get('title', feature_id)} 实现模块",
            "responsibility": f"实现 {feature.get('title', feature_id)} 相关需求",
            "feature_refs": [feature_id],
            "requirement_refs": req_refs,
            "paths": _infer_code_paths(feature),
            "apis": [],
            "data_entities": entities[:3],
            "risks": feature.get("risks", []),
        })

    all_req_refs = [req for f in product.get("features", []) for req in _feature_requirement_ids(f)]
    for idx, endpoint in enumerate(endpoints, 1):
        api_id = f"API-{idx:03d}"
        apis.append({
            "id": api_id,
            "method": endpoint[0],
            "path": endpoint[1],
            "requirement_refs": all_req_refs,
            "request_schema": {},
            "response_schema": {},
            "error_cases": ["400", "401", "403", "500"],
        })
    if apis and modules:
        for module in modules:
            module["apis"] = [api["id"] for api in apis]

    spec = {
        "version": "1.0",
        "generated_at": now_iso(),
        "implements_product_spec": str(PRODUCT_SPEC),
        "source_doc": arch_path,
        "modules": modules,
        "apis": apis,
        "data_model": [{"entity": e, "fields": []} for e in entities],
    }
    _write_json(root / TECH_SPEC, spec)
    return spec


def generate_test_spec(root: str | Path) -> Dict[str, Any]:
    """Generate Test Spec from Product/UED/Tech Specs."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    product = _load_or_generate_product(root)
    ued = _read_json(root / UED_SPEC) or generate_ued_spec(root)
    tech = _read_json(root / TECH_SPEC) or generate_tech_spec(root)

    tech_refs_by_req = _index_refs_by_requirement(
        tech.get("modules", []) + tech.get("apis", []),
        id_key="id",
    )
    ued_refs_by_req = _index_refs_by_requirement(
        ued.get("screens", []) + ued.get("flows", []),
        id_key="id",
    )

    tests: List[Dict[str, Any]] = []
    for feature in product.get("features", []):
        feature_id = feature.get("id", "F00")
        for req_idx, req in enumerate(feature.get("requirements", []), 1):
            req_id = req.get("id", f"REQ-{feature_id}-{req_idx:03d}")
            tech_refs = tech_refs_by_req.get(req_id, [])
            ued_refs = ued_refs_by_req.get(req_id, [])
            layer = "api" if any(ref.startswith("API-") for ref in tech_refs) else "unit"
            tests.append({
                "id": f"TST-{feature_id}-{req_idx:03d}-HAPPY",
                "requirement_refs": [req_id],
                "tech_refs": tech_refs,
                "ued_refs": ued_refs,
                "feature_ref": feature_id,
                "layer": layer,
                "variant": "happy",
                "preconditions": [],
                "steps": [
                    f"Prepare valid input for {req_id}",
                    "Execute the mapped implementation path",
                    "Inspect returned state, output, or artifact",
                ],
                "expected": req.get("acceptance", []) or [req.get("statement", "Requirement is satisfied")],
                "automation_target": f"tests/generated/test_{feature_id.lower()}_{req_idx:03d}.py",
            })

    spec = {
        "version": "1.0",
        "generated_at": now_iso(),
        "tests": tests,
    }
    _write_json(root / TEST_SPEC, spec)
    return spec


def generate_lifecycle_graph(root: str | Path) -> Dict[str, Any]:
    """Generate Lifecycle Graph from all available specs."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    product = _load_or_generate_product(root)
    ued = _read_json(root / UED_SPEC) or generate_ued_spec(root)
    tech = _read_json(root / TECH_SPEC) or generate_tech_spec(root)
    test = _read_json(root / TEST_SPEC) or generate_test_spec(root)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, label: str, source: str, refs: Optional[List[str]] = None):
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "source": source,
            "refs": refs or [],
        }

    def add_edge(from_id: str, to_id: str, edge_type: str, confidence: str = "confirmed"):
        if from_id in nodes and to_id in nodes:
            edges.append({
                "from": from_id,
                "to": to_id,
                "type": edge_type,
                "confidence": confidence,
            })

    for feature in product.get("features", []):
        fid = feature.get("id")
        if not fid:
            continue
        add_node(fid, "Feature", feature.get("title", fid), str(PRODUCT_SPEC))
        for req in feature.get("requirements", []):
            rid = req.get("id")
            if not rid:
                continue
            add_node(rid, "Requirement", req.get("statement", rid), str(PRODUCT_SPEC), [fid])
            add_edge(fid, rid, "contains")

    for screen in ued.get("screens", []):
        sid = screen.get("id")
        if sid:
            add_node(sid, "UED Screen", screen.get("name", sid), str(UED_SPEC), screen.get("requirement_refs", []))
            for rid in screen.get("requirement_refs", []):
                add_edge(sid, rid, "expresses")
    for flow in ued.get("flows", []):
        flow_id = flow.get("id")
        if flow_id:
            add_node(flow_id, "UED Flow", flow.get("name", flow_id), str(UED_SPEC), flow.get("requirement_refs", []))
            for sid in flow.get("screen_refs", []):
                add_edge(flow_id, sid, "contains")
            for rid in flow.get("requirement_refs", []):
                add_edge(flow_id, rid, "expresses")

    for module in tech.get("modules", []):
        mid = module.get("id")
        if mid:
            add_node(mid, "Module", module.get("name", mid), str(TECH_SPEC), module.get("requirement_refs", []))
            for rid in module.get("requirement_refs", []):
                add_edge(mid, rid, "implements")
    for api in tech.get("apis", []):
        aid = api.get("id")
        if aid:
            label = f"{api.get('method', '')} {api.get('path', '')}".strip() or aid
            add_node(aid, "API", label, str(TECH_SPEC), api.get("requirement_refs", []))
            for rid in api.get("requirement_refs", []):
                add_edge(aid, rid, "implements")

    for test_case in test.get("tests", []):
        tid = test_case.get("id")
        if tid:
            add_node(tid, "Test", tid, str(TEST_SPEC), test_case.get("requirement_refs", []))
            for rid in test_case.get("requirement_refs", []):
                add_edge(tid, rid, "verifies")
            for ref in test_case.get("tech_refs", []):
                add_edge(tid, ref, "verifies")
            for ref in test_case.get("ued_refs", []):
                add_edge(tid, ref, "verifies")

    graph = {
        "version": "1.0",
        "generated_at": now_iso(),
        "nodes": list(nodes.values()),
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "source_specs": [
                str(PRODUCT_SPEC),
                str(UED_SPEC),
                str(TECH_SPEC),
                str(TEST_SPEC),
            ],
        },
    }
    _write_json(root / LIFECYCLE_GRAPH, graph)
    return graph


def generate_all_specs(root: str | Path) -> Dict[str, Any]:
    """Generate all lifecycle specs in dependency order."""
    product = generate_product_spec(root)
    ued = generate_ued_spec(root)
    tech = generate_tech_spec(root)
    test = generate_test_spec(root)
    graph = generate_lifecycle_graph(root)
    validation = validate_specs(root)
    return {
        "product": product,
        "ued": ued,
        "tech": tech,
        "test": test,
        "graph": graph,
        "validation": validation,
    }


def validate_specs(root: str | Path) -> Dict[str, Any]:
    """Validate required spec files and cross-references."""
    root = Path(root).resolve()
    ensure_spec_dirs(root)
    issues: List[Dict[str, Any]] = []
    required = [PRODUCT_SPEC, UED_SPEC, TECH_SPEC, TEST_SPEC, LIFECYCLE_GRAPH]

    loaded: Dict[str, Dict[str, Any]] = {}
    for rel in required:
        path = root / rel
        if not path.exists():
            issues.append({"severity": "error", "file": str(rel), "message": "missing spec file"})
            continue
        try:
            loaded[str(rel)] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append({"severity": "error", "file": str(rel), "message": f"invalid json: {exc}"})

    product = loaded.get(str(PRODUCT_SPEC), {})
    req_ids = {
        req.get("id")
        for feature in product.get("features", [])
        for req in feature.get("requirements", [])
        if req.get("id")
    }
    if product and not req_ids:
        issues.append({"severity": "error", "file": str(PRODUCT_SPEC), "message": "no requirements found"})

    def check_refs(file_key: str, items_key: str, refs_key: str = "requirement_refs"):
        spec = loaded.get(file_key, {})
        for item in spec.get(items_key, []):
            for ref in item.get(refs_key, []):
                if ref not in req_ids:
                    issues.append({
                        "severity": "error",
                        "file": file_key,
                        "message": f"{item.get('id', '?')} references unknown requirement {ref}",
                    })

    check_refs(str(UED_SPEC), "screens")
    check_refs(str(UED_SPEC), "flows")
    check_refs(str(TECH_SPEC), "modules")
    check_refs(str(TECH_SPEC), "apis")
    check_refs(str(TEST_SPEC), "tests")

    covered_by_tech = {
        ref
        for item in loaded.get(str(TECH_SPEC), {}).get("modules", []) + loaded.get(str(TECH_SPEC), {}).get("apis", [])
        for ref in item.get("requirement_refs", [])
    }
    covered_by_tests = {
        ref
        for item in loaded.get(str(TEST_SPEC), {}).get("tests", [])
        for ref in item.get("requirement_refs", [])
    }
    for req_id in sorted(req_ids):
        if req_id not in covered_by_tech:
            issues.append({"severity": "error", "file": str(TECH_SPEC), "message": f"{req_id} has no tech mapping"})
        if req_id not in covered_by_tests:
            issues.append({"severity": "error", "file": str(TEST_SPEC), "message": f"{req_id} has no test mapping"})

    return {
        "passed": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
        "counts": {
            "requirements": len(req_ids),
            "issues": len(issues),
        },
    }


def generate_change_impact(
    root: str | Path,
    change_type: str,
    user_input: str = "",
) -> Dict[str, Any]:
    """Generate impact.json and full-highlight CHANGE_IMPACT.md from lifecycle graph."""
    root = Path(root).resolve()
    graph = _read_json(root / LIFECYCLE_GRAPH)
    if not graph:
        graph = generate_lifecycle_graph(root)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    changed_nodes = _match_changed_nodes(nodes, user_input)
    if not changed_nodes:
        changed_nodes = [n["id"] for n in nodes if n.get("type") in ("Requirement", "Feature")][:3]

    impacted = _walk_impacted_nodes(changed_nodes, edges)
    affected_nodes = [n for n in nodes if n.get("id") in impacted]

    impact = {
        "change_id": f"CHG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "change_type": change_type,
        "generated_at": now_iso(),
        "changed_nodes": changed_nodes,
        "affected_features": _filter_node_ids(affected_nodes, "Feature"),
        "affected_ued": _filter_node_ids(affected_nodes, "UED"),
        "affected_modules": _filter_node_ids(affected_nodes, "Module"),
        "affected_apis": _filter_node_ids(affected_nodes, "API"),
        "affected_tests": _filter_node_ids(affected_nodes, "Test"),
        "docs_to_update": ["PRD.md", "UED.md", "ARCH.md", "MASTER_OUTLINE.md"],
        "specs_to_update": [
            "product.spec.json",
            "ued.spec.json",
            "tech.spec.json",
            "test.spec.json",
            "lifecycle_graph.json",
        ],
        "highlighted_impact": changed_nodes + [n["id"] for n in affected_nodes[:8] if n["id"] not in changed_nodes],
        "requires_user_confirmation": True,
        "confidence": "confirmed" if changed_nodes else "needs_review",
    }
    _write_json(root / IMPACT_JSON, impact)
    _write_change_impact_md(root, impact, affected_nodes)
    return impact


def _write_change_impact_md(root: Path, impact: Dict[str, Any], affected_nodes: List[Dict[str, Any]]) -> None:
    lines = [
        "# Change Impact Report",
        "",
        f"- Change ID: `{impact['change_id']}`",
        f"- Change Type: `{impact['change_type']}`",
        f"- Generated At: `{impact['generated_at']}`",
        f"- Requires User Confirmation: `{impact['requires_user_confirmation']}`",
        "",
        "## Highlighted Impact",
        "",
    ]
    for node_id in impact.get("highlighted_impact", []):
        lines.append(f"- `{node_id}`")
    lines.extend(["", "## Full Affected Nodes", ""])
    for node in affected_nodes:
        lines.append(f"- `{node.get('id')}` [{node.get('type')}] {node.get('label')}")
    lines.extend(["", "## Specs To Update", ""])
    for spec in impact.get("specs_to_update", []):
        lines.append(f"- `{spec}`")
    lines.extend(["", "## Docs To Update", ""])
    for doc in impact.get("docs_to_update", []):
        lines.append(f"- `{doc}`")
    lines.append("")
    path = root / paths.CHANGE_IMPACT_MD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _load_or_generate_product(root: Path) -> Dict[str, Any]:
    product = _read_json(root / PRODUCT_SPEC)
    if product:
        return product
    return generate_product_spec(root)


def _extract_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_product_features(content: str) -> List[Dict[str, Any]]:
    pattern = re.compile(r"^###\s+(F(\d+))\s*[—\-–]\s*(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    features: List[Dict[str, Any]] = []
    for match in matches:
        raw_id = match.group(1)
        feature_id = f"F{int(match.group(2)):02d}"
        title = match.group(3).strip()
        start = match.end()
        next_match = re.search(r"^###\s+", content[start:], re.MULTILINE)
        body = content[start:start + next_match.start()].strip() if next_match else content[start:].strip()
        features.append(_build_feature(feature_id, raw_id, title, body))
    return features


def _build_feature(feature_id: str, raw_id: str, title: str, body: str) -> Dict[str, Any]:
    acceptance = _extract_acceptance_lines(body)
    if not acceptance:
        sentence = _first_sentence(body) or title
        acceptance = [sentence]
    requirements = []
    for idx, statement in enumerate(acceptance, 1):
        requirements.append({
            "id": f"REQ-{feature_id}-{idx:03d}",
            "type": "functional",
            "statement": statement,
            "acceptance": [statement],
            "non_functional_refs": [],
        })
    return {
        "id": feature_id,
        "source_ref": raw_id,
        "title": title,
        "status": "approved",
        "priority": "must",
        "user_roles": ["user"],
        "requirements": requirements,
        "dependencies": [],
        "risks": [],
    }


def _fallback_feature(project_name: str, content: str) -> Dict[str, Any]:
    return _build_feature(
        "F01",
        "F01",
        project_name,
        _first_sentence(content) or f"{project_name} core lifecycle requirement",
    )


def _extract_acceptance_lines(body: str) -> List[str]:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            stripped = stripped.lstrip("-* ").strip()
            if stripped:
                lines.append(stripped)
    return lines[:8]


def _first_sentence(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ""
    parts = re.split(r"[。.!?]", clean)
    return parts[0].strip()


def _extract_section_summary(content: str, headings: Iterable[str]) -> str:
    for heading in headings:
        pattern = re.compile(rf"^##+\s+.*{re.escape(heading)}.*$", re.MULTILINE | re.IGNORECASE)
        match = pattern.search(content)
        if not match:
            continue
        start = match.end()
        next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
        body = content[start:start + next_heading.start()].strip() if next_heading else content[start:].strip()
        return _first_sentence(body)
    return ""


def _extract_scope(content: str, include: bool) -> List[str]:
    keywords = ["包含", "In Scope"] if include else ["不包含", "Out of Scope"]
    result: List[str] = []
    for keyword in keywords:
        pattern = re.compile(rf"^###?\s+.*{re.escape(keyword)}.*$", re.MULTILINE | re.IGNORECASE)
        match = pattern.search(content)
        if not match:
            continue
        start = match.end()
        next_heading = re.search(r"^###+?\s+", content[start:], re.MULTILINE)
        body = content[start:start + next_heading.start()] if next_heading else content[start:]
        result.extend(_extract_acceptance_lines(body))
    return result[:8]


def _extract_nfr(content: str) -> List[Dict[str, Any]]:
    nfrs: List[Dict[str, Any]] = []
    if re.search(r"(性能|Performance|响应|response)", content, re.IGNORECASE):
        nfrs.append({"id": "NFR-001", "metric": "performance", "target": "defined in PRD"})
    if re.search(r"(安全|Security|认证|权限)", content, re.IGNORECASE):
        nfrs.append({"id": "NFR-002", "metric": "security", "target": "defined in PRD"})
    return nfrs


def _feature_requirement_ids(feature: Dict[str, Any]) -> List[str]:
    return [req.get("id") for req in feature.get("requirements", []) if req.get("id")]


def _extract_api_endpoints(text: str) -> List[Tuple[str, str]]:
    seen = set()
    endpoints: List[Tuple[str, str]] = []
    for match in re.finditer(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s`,)]+)", text, re.IGNORECASE):
        endpoint = (match.group(1).upper(), match.group(2).rstrip("."))
        if endpoint not in seen:
            endpoints.append(endpoint)
            seen.add(endpoint)
    return endpoints


def _extract_data_entities(text: str) -> List[str]:
    entities = []
    for match in re.finditer(r"(?:表|entity|model)\s*[:：]?\s*([A-Z][A-Za-z0-9_]+|[a-z][a-z0-9_]+)", text):
        value = match.group(1)
        if value not in entities:
            entities.append(value)
    return entities[:10]


def _infer_code_paths(feature: Dict[str, Any]) -> List[str]:
    title = feature.get("title", feature.get("id", "feature")).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", title).strip("_") or feature.get("id", "feature").lower()
    return [f"src/{slug}/*", f"tests/**/test_{slug}.py"]


def _index_refs_by_requirement(items: List[Dict[str, Any]], id_key: str) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for item in items:
        item_id = item.get(id_key)
        if not item_id:
            continue
        for req_id in item.get("requirement_refs", []):
            index.setdefault(req_id, []).append(item_id)
    return index


def _match_changed_nodes(nodes: List[Dict[str, Any]], user_input: str) -> List[str]:
    if not user_input:
        return []
    lowered = user_input.lower()
    matched = []
    for node in nodes:
        label = str(node.get("label", "")).lower()
        node_id = str(node.get("id", "")).lower()
        if node_id and node_id in lowered:
            matched.append(node["id"])
        elif label and len(label) >= 4 and label in lowered:
            matched.append(node["id"])
    return matched[:10]


def _walk_impacted_nodes(changed_nodes: List[str], edges: List[Dict[str, Any]]) -> set:
    adjacency: Dict[str, set] = {}
    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if not src or not dst:
            continue
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)

    impacted = set(changed_nodes)
    frontier = list(changed_nodes)
    while frontier:
        current = frontier.pop(0)
        for nxt in adjacency.get(current, set()):
            if nxt not in impacted:
                impacted.add(nxt)
                frontier.append(nxt)
    return impacted


def _filter_node_ids(nodes: List[Dict[str, Any]], node_type_prefix: str) -> List[str]:
    return [n["id"] for n in nodes if str(n.get("type", "")).startswith(node_type_prefix)]
