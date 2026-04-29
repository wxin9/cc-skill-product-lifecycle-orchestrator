"""
test_graph.py — 测试知识图谱引擎

将 .lifecycle/test_graph.json 加载为内存中的有向图，支持：
  - O(1) 节点查找（flat index）
  - 按类型/标签过滤
  - API / 数据实体反查
  - BFS 影响范围遍历（上下游双向）
  - 向后兼容 MasterOutline 格式导出
  - Markdown 渲染

Usage:
  python scripts/core/test_graph.py stats .lifecycle/test_graph.json
  python scripts/core/test_graph.py load .lifecycle/test_graph.json
"""
from __future__ import annotations

import json
import sys
import argparse
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional



# ---------------------------------------------------------------------------
# 默认空依赖声明
# ---------------------------------------------------------------------------

def _empty_deps() -> dict:
    """返回结构完整的空 DependencyDecl。"""
    return {
        "upstream_nodes": [],
        "downstream_nodes": [],
        "apis": [],
        "data_entities": [],
        "state_pre": [],
        "state_post": [],
    }


# ---------------------------------------------------------------------------
# TestGraph
# ---------------------------------------------------------------------------

class TestGraph:
    """
    测试知识图谱引擎。
    内部维护两套视图：
      - self.nodes  : {node_id → TestNode dict}，O(1) 查询用的扁平索引
      - schema nodes: 顶层节点列表（含 children），序列化/渲染用的树结构
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, dict] = {}       # 扁平索引：node_id → TestNode dict
        self._roots: List[dict] = []           # 顶层节点（序列化时用）
        self.project_type: str = ""
        self.prd_version: str = ""
        self.arch_version: str = ""
        self.dimensions_used: List[str] = []
        self.global_apis: List[str] = []
        self.global_entities: List[str] = []
        self._generated_at: str = ""
        self._version: str = "1.1"

    # ------------------------------------------------------------------
    # 1. classmethod: load
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, json_path: str) -> "TestGraph":
        """
        从 .lifecycle/test_graph.json 加载图谱。
        重建扁平索引（self.nodes），保留原始树结构用于序列化。
        """
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        graph = cls()
        graph._version = data.get("version", "1.1")
        graph._generated_at = data.get("generated_at", "")
        graph.project_type = data.get("project_type", "")
        graph.prd_version = data.get("prd_version", "")
        graph.arch_version = data.get("arch_version", "")
        graph.dimensions_used = data.get("dimensions_used", [])
        graph.global_apis = data.get("global_apis", [])
        graph.global_entities = data.get("global_entities", [])
        # 恢复树结构并建立索引
        graph._roots = data.get("nodes", [])
        graph._index_tree(graph._roots)
        return graph

    # ------------------------------------------------------------------
    # 2. save
    # ------------------------------------------------------------------

    def save(self, json_path: str) -> None:
        """序列化为 JSON（树结构，保留中文，缩进 2）。"""
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(
            json.dumps(self.to_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 3. add_node
    # ------------------------------------------------------------------

    def add_node(self, node: dict, parent_id: Optional[str] = None) -> None:
        """
        添加节点到图谱。
        - 若 parent_id 为 None，加入顶层列表；否则追加到父节点的 children。
        - 同步更新扁平索引。
        """
        node.setdefault("children", [])
        node.setdefault("dependencies", _empty_deps())
        nid = node.get("node_id", "")
        if not nid:
            raise ValueError("node 必须包含 node_id 字段")
        self.nodes[nid] = node
        if parent_id is None:
            self._roots.append(node)
        else:
            parent = self.nodes.get(parent_id)
            if parent is None:
                raise KeyError(f"父节点 '{parent_id}' 不存在")
            parent.setdefault("children", []).append(node)

    # ------------------------------------------------------------------
    # 4. add_dependency
    # ------------------------------------------------------------------

    def add_dependency(self, from_id: str, to_id: str, dep_type: str = "upstream") -> None:
        """
        在两个节点之间建立依赖关系。

        dep_type="upstream":
          - to_id 加入 from_node 的 upstream_nodes
          - from_id 加入 to_node 的 downstream_nodes

        dep_type="downstream":
          - 反向：from_id 加入 to_node 的 upstream_nodes
          - to_id 加入 from_node 的 downstream_nodes

        幂等：重复调用不会产生重复条目。
        """
        if from_id not in self.nodes:
            raise KeyError(f"节点 '{from_id}' 不存在")
        if to_id not in self.nodes:
            raise KeyError(f"节点 '{to_id}' 不存在")

        from_node = self.nodes[from_id]
        to_node = self.nodes[to_id]

        # 确保 dependencies 及子键存在
        from_node.setdefault("dependencies", {})
        to_node.setdefault("dependencies", {})
        from_node["dependencies"].setdefault("upstream_nodes", [])
        from_node["dependencies"].setdefault("downstream_nodes", [])
        to_node["dependencies"].setdefault("upstream_nodes", [])
        to_node["dependencies"].setdefault("downstream_nodes", [])

        if dep_type == "upstream":
            # from_id 是 to_node 的上游
            if from_id not in to_node["dependencies"]["upstream_nodes"]:
                to_node["dependencies"]["upstream_nodes"].append(from_id)
            if to_id not in from_node["dependencies"]["downstream_nodes"]:
                from_node["dependencies"]["downstream_nodes"].append(to_id)
        elif dep_type == "downstream":
            # to_id 是 from_node 的上游
            if to_id not in from_node["dependencies"]["upstream_nodes"]:
                from_node["dependencies"]["upstream_nodes"].append(to_id)
            if from_id not in to_node["dependencies"]["downstream_nodes"]:
                to_node["dependencies"]["downstream_nodes"].append(from_id)
        else:
            raise ValueError(f"dep_type 必须为 'upstream' 或 'downstream'，收到: '{dep_type}'")

    # ------------------------------------------------------------------
    # 5. get_node
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[dict]:
        """按 node_id 精确查找，O(1)。"""
        return self.nodes.get(node_id)

    # ------------------------------------------------------------------
    # 6. find_nodes
    # ------------------------------------------------------------------

    def find_nodes(
        self,
        node_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        按节点类型和/或标签过滤（标签为交集匹配）。
        两者均为 None 时返回全部节点。
        """
        results = []
        for node in self.nodes.values():
            if node_type and node.get("node_type") != node_type:
                continue
            if tags:
                node_tags = set(node.get("tags") or [])
                if not all(t in node_tags for t in tags):
                    continue
            results.append(node)
        return results

    # ------------------------------------------------------------------
    # 7. find_by_api
    # ------------------------------------------------------------------

    def find_by_api(self, api: str) -> List[dict]:
        """找出 dependencies.apis 中包含指定 API 的所有节点。"""
        result = []
        for node in self.nodes.values():
            apis = (node.get("dependencies") or {}).get("apis", [])
            if api in apis:
                result.append(node)
        return result

    # ------------------------------------------------------------------
    # 8. find_by_entity
    # ------------------------------------------------------------------

    def find_by_entity(self, entity: str) -> List[dict]:
        """找出 dependencies.data_entities 中包含指定实体的所有节点。"""
        result = []
        for node in self.nodes.values():
            entities = (node.get("dependencies") or {}).get("data_entities", [])
            if entity in entities:
                result.append(node)
        return result

    # ------------------------------------------------------------------
    # 9. traverse_impact
    # ------------------------------------------------------------------

    def traverse_impact(
        self,
        changed_items: dict,
        direction: str = "both",
    ) -> List[dict]:
        """
        BFS 影响范围遍历。

        changed_items 可包含：
          - "apis"         : List[str]  — 变更的 API
          - "data_entities": List[str]  — 变更的数据实体
          - "node_ids"     : List[str]  — 直接变更的节点 ID

        direction: "forward"（仅下游）| "backward"（仅上游）| "both"

        返回 [{"node_id": str, "distance": int, "priority": str}]，
        按 distance 升序，同 node_id 保留最短距离。
        """
        # 收集距离 0 的种子节点
        seeds = self._collect_seeds(changed_items)
        if not seeds:
            return []
        visited: Dict[str, int] = {}   # node_id → shortest distance
        queue: deque = deque()
        for nid in seeds:
            if nid in self.nodes:
                visited[nid] = 0
                queue.append((nid, 0))
        self._bfs(queue, visited, direction)
        return self._format_impact(visited)

    def _collect_seeds(self, changed_items: dict) -> List[str]:
        """将 changed_items 转换为距离 0 的种子 node_id 列表。"""
        seeds: List[str] = list(changed_items.get("node_ids") or [])
        for api in changed_items.get("apis") or []:
            seeds.extend(n["node_id"] for n in self.find_by_api(api))
        for entity in changed_items.get("data_entities") or []:
            seeds.extend(n["node_id"] for n in self.find_by_entity(entity))
        # 去重保序
        seen = set()
        deduped = []
        for s in seeds:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        return deduped

    def _bfs(self, queue: deque, visited: Dict[str, int], direction: str) -> None:
        """BFS 遍历上游/下游节点，将最短距离写入 visited。"""
        while queue:
            nid, dist = queue.popleft()
            node = self.nodes.get(nid)
            if node is None:
                continue
            deps = node.get("dependencies") or {}
            neighbors: List[str] = []
            if direction in ("forward", "both"):
                neighbors.extend(deps.get("downstream_nodes") or [])
            if direction in ("backward", "both"):
                neighbors.extend(deps.get("upstream_nodes") or [])
            for neighbor in neighbors:
                new_dist = dist + 1
                if neighbor not in visited or visited[neighbor] > new_dist:
                    visited[neighbor] = new_dist
                    queue.append((neighbor, new_dist))

    @staticmethod
    def _format_impact(visited: Dict[str, int]) -> List[dict]:
        """将 {node_id: distance} 格式化为带 priority 的列表，按 distance 排序。"""
        def priority(d: int) -> str:
            if d == 0:
                return "P0"
            if d == 1:
                return "P1"
            return "P2"

        return sorted(
            [{"node_id": nid, "distance": d, "priority": priority(d)} for nid, d in visited.items()],
            key=lambda x: x["distance"],
        )

    # ------------------------------------------------------------------
    # 10. to_legacy_outline
    # ------------------------------------------------------------------

    def to_legacy_outline(self) -> dict:
        """
        转换为旧版 MasterOutline 格式（向后兼容）。
        只包含 feature 级和 scenario 级节点。
        """
        entries = []
        feature_nodes = self.find_nodes(node_type="feature")
        for feat in feature_nodes:
            scenarios = self._extract_scenario_children(feat)
            entries.append({
                "feature_id": feat.get("node_id", ""),
                "feature_name": feat.get("name", ""),
                "prd_ref": (feat.get("tags") or [""])[0] if feat.get("tags") else "",
                "scenarios": scenarios,
            })
        return {
            "version": self._version,
            "generated_at": self._generated_at or datetime.now(timezone.utc).isoformat(),
            "prd_version": self.prd_version,
            "arch_version": self.arch_version,
            "entries": entries,
            "total_scenarios": sum(len(e["scenarios"]) for e in entries),
        }

    def _extract_scenario_children(self, feature_node: dict) -> List[dict]:
        """从 feature 节点的直接子节点中提取 scenario 列表。"""
        scenarios = []
        for child in feature_node.get("children") or []:
            if child.get("node_type") != "scenario":
                continue
            scenarios.append({
                "id": child.get("node_id", ""),
                "description": child.get("name", ""),
                "steps": child.get("steps") or [],
                "expected": child.get("expected", ""),
                "e2e": child.get("e2e", False),
                "layer_entry": child.get("layer_entry", "api"),
            })
        return scenarios

    # ------------------------------------------------------------------
    # 11. to_markdown
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        """
        渲染为 MASTER_OUTLINE.md 格式的 Markdown 字符串。
        包含：版本信息、覆盖矩阵、各 feature 的场景详情。
        """
        lines = self._markdown_header()
        lines += self._markdown_matrix()
        lines += ["", "---", ""]
        for feat in self.find_nodes(node_type="feature"):
            lines += self._markdown_feature_section(feat)
        return "\n".join(lines)

    def _markdown_header(self) -> List[str]:
        """生成 Markdown 文件头部（版本、时间、维度）。"""
        ts = self._generated_at or datetime.now(timezone.utc).isoformat()
        dims = ", ".join(self.dimensions_used) if self.dimensions_used else "—"
        return [
            "# 主测试大纲 (Master Test Outline — Graph v1.1)",
            "",
            f"**版本：** {self._version}  |  **生成时间：** {ts}",
            f"**基于 PRD 版本：** {self.prd_version}  |  **架构版本：** {self.arch_version}",
            f"**项目类型：** {self.project_type}  |  **测试维度：** {dims}",
            f"**总场景数：** {self._collect_scenarios()}",
            "",
            "---",
            "",
        ]

    def _markdown_matrix(self) -> List[str]:
        """生成 feature × dimension 覆盖矩阵表格。"""
        dims = self.dimensions_used or ["UI", "API", "DATA"]
        header = "| 功能 ID | 功能名称 | 场景数 | " + " | ".join(dims) + " |"
        sep = "|---|---|---|" + "|".join(["---"] * len(dims)) + "|"
        lines = ["## 测试覆盖矩阵", "", header, sep]
        for feat in self.find_nodes(node_type="feature"):
            fid = feat.get("node_id", "")
            fname = feat.get("name", "")
            children = feat.get("children") or []
            sc_count = sum(1 for c in children if c.get("node_type") == "scenario")
            row = f"| {fid} | {fname} | {sc_count} |"
            for dim in dims:
                tag = f"[{dim}]"
                hit = any(tag in (c.get("dimension", "") or c.get("name", "")) for c in children)
                row += f" {'✓' if hit else '—'} |"
            lines.append(row)
        return lines

    def _markdown_feature_section(self, feat: dict) -> List[str]:
        """渲染单个 feature 节点（及其 scenario 子节点）的 Markdown 块。"""
        fid = feat.get("node_id", "")
        fname = feat.get("name", "")
        lines = [f"## {fid} — {fname}", ""]
        for child in feat.get("children") or []:
            if child.get("node_type") != "scenario":
                continue
            sc_id = child.get("node_id", "")
            sc_name = child.get("name", "")
            e2e_badge = " `[E2E]`" if child.get("e2e") else ""
            entry = (child.get("layer_entry") or "api").upper()
            lines += [
                f"### {sc_id} — {sc_name}{e2e_badge} `[{entry}]`",
                "",
                "**测试步骤：**",
            ]
            for i, step in enumerate(child.get("steps") or [], 1):
                lines.append(f"{i}. {step}")
            lines += [
                "",
                f"**期望结果：** {child.get('expected', '')}",
                "",
                "**状态：** `active`",
                "",
            ]
        return lines

    # ------------------------------------------------------------------
    # 12. to_schema
    # ------------------------------------------------------------------

    def to_schema(self) -> dict:
        """返回完整的 TestGraphSchema dict，用于 JSON 序列化（使用树结构）。"""
        return {
            "version": self._version,
            "generated_at": self._generated_at or datetime.now(timezone.utc).isoformat(),
            "project_type": self.project_type,
            "prd_version": self.prd_version,
            "arch_version": self.arch_version,
            "dimensions_used": self.dimensions_used,
            "nodes": self._roots,
            "global_apis": self.global_apis,
            "global_entities": self.global_entities,
            "total_nodes": len(self.nodes),
            "total_scenarios": self._collect_scenarios(),
        }

    # ------------------------------------------------------------------
    # 13. _index_tree (helper)
    # ------------------------------------------------------------------

    def _index_tree(self, nodes: list) -> None:
        """
        递归遍历节点树，将每个节点按 node_id 写入 self.nodes 扁平索引。
        每个节点保证有 children 和 dependencies 字段（补默认值）。
        """
        for node in nodes:
            node.setdefault("children", [])
            node.setdefault("dependencies", _empty_deps())
            nid = node.get("node_id")
            if nid:
                self.nodes[nid] = node
            if node.get("children"):
                self._index_tree(node["children"])

    # ------------------------------------------------------------------
    # 14. _collect_scenarios (helper)
    # ------------------------------------------------------------------

    def _collect_scenarios(self) -> int:
        """统计图谱中 scenario 类型节点的总数。"""
        return sum(1 for n in self.nodes.values() if n.get("node_type") == "scenario")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def _cmd_load(path: str) -> None:
    """加载并打印图谱摘要。"""
    graph = TestGraph.load(path)
    schema = graph.to_schema()
    print(f"[load] 已加载: {path}")
    print(f"  project_type : {graph.project_type}")
    print(f"  prd_version  : {graph.prd_version}")
    print(f"  arch_version : {graph.arch_version}")
    print(f"  total_nodes  : {schema['total_nodes']}")
    print(f"  total_scenarios: {schema['total_scenarios']}")
    print(f"  dimensions   : {', '.join(graph.dimensions_used) or '—'}")


def _cmd_stats(path: str) -> None:
    """打印图谱统计信息（各类型节点数量）。"""
    graph = TestGraph.load(path)
    type_counts: Dict[str, int] = {}
    for node in graph.nodes.values():
        t = node.get("node_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"[stats] {path}")
    print(f"  总节点数: {len(graph.nodes)}")
    for t, c in sorted(type_counts.items()):
        print(f"    {t:12s}: {c}")
    print(f"  总场景数: {graph._collect_scenarios()}")
    print(f"  global_apis    : {len(graph.global_apis)}")
    print(f"  global_entities: {len(graph.global_entities)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="测试知识图谱引擎 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/core/test_graph.py load .lifecycle/test_graph.json\n"
            "  python scripts/core/test_graph.py stats .lifecycle/test_graph.json\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("load", help="加载图谱并打印摘要").add_argument("path")
    sub.add_parser("stats", help="打印各类型节点统计").add_argument("path")

    args = parser.parse_args()

    if args.cmd == "load":
        _cmd_load(args.path)
    elif args.cmd == "stats":
        _cmd_stats(args.path)
    else:
        parser.print_help()
        sys.exit(1)
