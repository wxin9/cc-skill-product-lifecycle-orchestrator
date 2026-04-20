"""
dependency_extractor.py — 依赖提取模块。

解析 ARCH.md（架构文档），自动提取 API 端点、数据实体和组件映射。
在 test_outline.py 的 _extract_arch_context() 基础上深入挖掘，
提供结构化的依赖声明，供迭代规划和测试大纲使用。

Usage:
  python scripts/core/dependency_extractor.py ARCH.md
"""
from __future__ import annotations

import re
import json
import sys
from pathlib import Path
from typing import Dict, List


# --------------------------------------------------------------------------
# 1. extract_apis
# --------------------------------------------------------------------------

def extract_apis(arch_text: str) -> List[str]:
    """
    从架构文档文本中提取 API 端点列表。

    支持格式：
    - 标准 REST 格式：GET /api/users
    - Markdown 表格单元格中的路径
    - 代码块内的路由定义
    - 中文上下文中提到的接口路径

    返回去重且按字母排序的列表。
    """
    if not arch_text:
        return []

    results: List[str] = []

    # 标准 REST METHOD /path 格式
    rest_pattern = re.compile(
        r"(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-{}\.:]+)",
        re.IGNORECASE,
    )
    for m in rest_pattern.finditer(arch_text):
        results.append(f"{m.group(1).upper()} {m.group(2)}")

    # 中文上下文：接口/端点/路由 + 路径
    chinese_pattern = re.compile(
        r"(?:接口|端点|路由|endpoint|route)[：:]\s*[`'\"]?(/[\w/\-{}\.:]+)",
        re.IGNORECASE,
    )
    for m in chinese_pattern.finditer(arch_text):
        # 中文上下文中无法确定 HTTP 方法，仅记录路径，避免重复
        path = m.group(1)
        if not any(path in entry for entry in results):
            results.append(path)

    # 去重并排序
    seen: Dict[str, bool] = {}
    deduped: List[str] = []
    for item in results:
        if item not in seen:
            seen[item] = True
            deduped.append(item)

    return sorted(deduped)


# --------------------------------------------------------------------------
# 2. extract_data_entities
# --------------------------------------------------------------------------

def extract_data_entities(arch_text: str) -> List[str]:
    """
    从架构文档文本中提取数据库表名、模型名和缓存键。

    支持格式：
    - SQL 风格：tb_orders、反引号包裹的表名
    - ORM 模型名：CamelCase（代码块中）
    - Redis/缓存键：user:*、session_cache
    - 中文上下文：数据表：orders

    返回去重且按字母排序的列表。
    """
    if not arch_text:
        return []

    results: List[str] = []

    # 中文表名引用：表/table/数据表 + 名称
    chinese_table = re.compile(
        r"(?:表|table|表名|数据表)[：:\s]+[`'\"]?([\w_]+)",
        re.IGNORECASE,
    )
    results.extend(m.group(1) for m in chinese_table.finditer(arch_text))

    # 反引号包裹的 tb_/tbl_ 前缀表名
    prefixed_table = re.compile(r"`((?:tb_|tbl_)[\w]+)`")
    results.extend(m.group(1) for m in prefixed_table.finditer(arch_text))

    # SQL DDL/DML 语句中的表名
    sql_pattern = re.compile(
        r"(?:CREATE\s+TABLE|ALTER\s+TABLE|FROM|JOIN|INTO)\s+[`'\"]?([\w_]+)",
        re.IGNORECASE,
    )
    results.extend(m.group(1) for m in sql_pattern.finditer(arch_text))

    # ORM 模型/Schema 名称（CamelCase）
    orm_pattern = re.compile(r"(?:model|Model|schema|Schema)\s+(\w+)")
    results.extend(m.group(1) for m in orm_pattern.finditer(arch_text))

    # 过滤掉 SQL 保留字和空字符串
    sql_reserved = {"SELECT", "WHERE", "SET", "VALUES", "TABLE", "INDEX", "DATABASE"}
    filtered = [r for r in results if r and r.upper() not in sql_reserved]

    # 去重并排序
    return sorted(dict.fromkeys(filtered))


# --------------------------------------------------------------------------
# 3. extract_component_map
# --------------------------------------------------------------------------

def extract_component_map(arch_text: str) -> Dict[str, List[str]]:
    """
    将组件/服务名称映射到其对应的 API 端点。

    策略：
    - 检测 ## / ### 章节标题（描述组件或服务）
    - 在每个章节内用 extract_apis() 提取 API
    - 返回：章节标题 → API 列表

    示例：{"用户服务": ["GET /api/users", "POST /api/users"]}
    """
    if not arch_text:
        return {}

    component_map: Dict[str, List[str]] = {}

    # 找出所有二级/三级标题的位置
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)", re.MULTILINE)
    headings = list(heading_pattern.finditer(arch_text))

    for i, heading in enumerate(headings):
        title = heading.group(2).strip()
        # 截取本节文本（到下一个同级或更高级标题为止）
        section_start = heading.end()
        section_end = headings[i + 1].start() if i + 1 < len(headings) else len(arch_text)
        section_text = arch_text[section_start:section_end]

        apis = extract_apis(section_text)
        if apis:
            component_map[title] = apis

    return component_map


# --------------------------------------------------------------------------
# 4. infer_feature_dependencies
# --------------------------------------------------------------------------

def infer_feature_dependencies(
    features: List[dict],
    arch_text: str,
) -> Dict[str, dict]:
    """
    推断每个功能点对应的 API 和数据实体依赖。

    策略：
    - 从 arch_text 提取全量 API 和实体
    - 对每个功能，检查功能名/描述的关键词是否出现在 API 路径段或实体名中
    - 结合 component_map 进行间接关联

    返回：feature_id → {apis, data_entities, upstream_nodes, downstream_nodes}
    """
    all_apis = extract_apis(arch_text)
    all_entities = extract_data_entities(arch_text)
    comp_map = extract_component_map(arch_text)
    upstream_downstream = infer_upstream_downstream(features)

    result: Dict[str, dict] = {}

    for feat in features:
        fid = feat.get("feature_id", "")
        fname = feat.get("feature_name", "")
        desc = feat.get("description", "")
        combined = (fname + " " + desc).lower()

        # 匹配 API 路径段关键词
        matched_apis: List[str] = []
        for api in all_apis:
            # 取路径部分，拆分为段
            path = api.split(" ")[-1]
            segments = [s for s in re.split(r"[/\-_{}]", path) if s]
            for seg in segments:
                if seg.lower() in combined or seg.lower() in fname.lower():
                    matched_apis.append(api)
                    break

        # 通过 component_map 进行间接匹配
        for comp_name, comp_apis in comp_map.items():
            if any(kw in combined for kw in comp_name.lower().split()):
                for api in comp_apis:
                    if api not in matched_apis:
                        matched_apis.append(api)

        # 匹配数据实体名称关键词
        matched_entities: List[str] = []
        for entity in all_entities:
            entity_clean = re.sub(r"^(tb_|tbl_)", "", entity).lower()
            if entity_clean in combined or entity_clean in fname.lower():
                matched_entities.append(entity)

        ud = upstream_downstream.get(fid, {})
        result[fid] = {
            "apis": sorted(set(matched_apis)),
            "data_entities": sorted(set(matched_entities)),
            "upstream_nodes": ud.get("upstream_nodes", []),
            "downstream_nodes": ud.get("downstream_nodes", []),
        }

    return result


# --------------------------------------------------------------------------
# 5. infer_upstream_downstream
# --------------------------------------------------------------------------

# 通常处于上游的功能关键词（基础能力）
_UPSTREAM_KEYWORDS = re.compile(
    r"(登录|注册|认证|鉴权|auth|login|register|初始化|配置|setup|基础|用户管理)",
    re.IGNORECASE,
)

# 通常处于下游的功能关键词（消费型能力）
_DOWNSTREAM_KEYWORDS = re.compile(
    r"(报表|导出|统计|分析|报告|dashboard|export|report|汇总|审计|日志)",
    re.IGNORECASE,
)


def infer_upstream_downstream(features: List[dict]) -> Dict[str, dict]:
    """
    基于编号顺序、关键词和显式引用推断功能间的上下游关系。

    策略：
    1. 序号推断：F01 在 F02 之前（默认上游）
    2. 关键词分析：登录/认证 → 基本上游；报表/导出 → 基本下游
    3. 显式引用：若 F02 描述中提到 F01 的名称，则 F01 是 F02 的上游

    返回：feature_id → {upstream_nodes: [...], downstream_nodes: [...]}
    """
    result: Dict[str, dict] = {
        f["feature_id"]: {"upstream_nodes": [], "downstream_nodes": []}
        for f in features
    }

    # 按 feature_id 排序，以便编号推断
    sorted_features = sorted(features, key=lambda f: f.get("feature_id", ""))

    for i, feat in enumerate(sorted_features):
        fid = feat.get("feature_id", "")
        fname = feat.get("feature_name", "")
        desc = feat.get("description", "")
        combined = fname + " " + desc

        # 关键词分析：登录/认证类功能是几乎所有功能的上游
        if _UPSTREAM_KEYWORDS.search(combined):
            for other in sorted_features:
                oid = other.get("feature_id", "")
                if oid != fid:
                    if fid not in result[oid]["upstream_nodes"]:
                        result[oid]["upstream_nodes"].append(fid)
                    if oid not in result[fid]["downstream_nodes"]:
                        result[fid]["downstream_nodes"].append(oid)
            continue  # 上游功能自身不再做序号推断

        # 关键词分析：报表/导出类功能是几乎所有功能的下游
        if _DOWNSTREAM_KEYWORDS.search(combined):
            for other in sorted_features:
                oid = other.get("feature_id", "")
                if oid != fid:
                    if oid not in result[fid]["upstream_nodes"]:
                        result[fid]["upstream_nodes"].append(oid)
                    if fid not in result[oid]["downstream_nodes"]:
                        result[oid]["downstream_nodes"].append(fid)
            continue

        # 序号推断：编号靠前的功能是靠后功能的默认上游
        for j, other in enumerate(sorted_features):
            oid = other.get("feature_id", "")
            if oid == fid:
                continue
            if j < i:
                # other 在 feat 之前 → other 是 feat 的上游
                if oid not in result[fid]["upstream_nodes"]:
                    result[fid]["upstream_nodes"].append(oid)
                if fid not in result[oid]["downstream_nodes"]:
                    result[oid]["downstream_nodes"].append(fid)

        # 显式引用：当前功能描述中提到其他功能名称
        for other in sorted_features:
            oid = other.get("feature_id", "")
            oname = other.get("feature_name", "")
            if oid != fid and oname and oname in desc:
                if oid not in result[fid]["upstream_nodes"]:
                    result[fid]["upstream_nodes"].append(oid)
                if fid not in result[oid]["downstream_nodes"]:
                    result[oid]["downstream_nodes"].append(fid)

    return result


# --------------------------------------------------------------------------
# CLI 入口
# --------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dependency_extractor.py <ARCH.md>")
        sys.exit(1)

    arch_path = Path(sys.argv[1])
    if not arch_path.exists():
        print(f"错误：文件不存在 — {arch_path}", file=sys.stderr)
        sys.exit(1)

    arch_text = arch_path.read_text(encoding="utf-8", errors="replace")

    output = {
        "source": str(arch_path),
        "apis": extract_apis(arch_text),
        "data_entities": extract_data_entities(arch_text),
        "component_map": extract_component_map(arch_text),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
