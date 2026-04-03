"""
Document clarity validator — checks PRD, ARCH, and Test Outline documents.

Scoring (0-100):
  Base points for each section's existence (presence = passing gate).
  Depth bonus for content quality (depth = quality reward).
  Default passing threshold: 70.

  PRD:  base max 50, bonus max 47, total cap 100, threshold 70
  ARCH: base max 52, bonus max 43, total cap 100, threshold 70
  TEST: bonus only (0-100), threshold 70

Usage:
  python scripts/core/doc_validator.py --doc Docs/product/PRD.md [--type prd|arch|test_outline]
"""
from __future__ import annotations
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Tuple

THRESHOLD = 70

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _find_section(content: str, pattern: str) -> Tuple[bool, int]:
    """Return (found, start_char_index)."""
    m = re.search(pattern, content, re.IGNORECASE)
    return (bool(m), m.start() if m else -1)


def _section_body(content: str, start: int) -> str:
    """Extract body of a section from start_index to next ## heading."""
    if start < 0:
        return ""
    rest = content[start:]
    after_heading = rest.split("\n", 1)[1] if "\n" in rest else ""
    body = re.split(r"\n##?\s", after_heading)[0]
    return body.strip()


def _word_count(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_words = len(re.findall(r"[a-zA-Z0-9]+", text))
    return cjk + ascii_words


def _count_list_items(text: str) -> int:
    return len(re.findall(r"^\s*[-*•]\s+\S", text, re.MULTILINE))


def _count_ordered_steps(text: str) -> int:
    return len(re.findall(r"^\s*\d+[\.。\)]\s+\S", text, re.MULTILINE))


def _has_numbers(text: str) -> bool:
    """Check for concrete numbers like '< 200ms', '99.9%', '< 2秒'."""
    return bool(re.search(r"\d+\s*(ms|s|秒|%|分钟|个|条|MB|GB|并发|QPS)", text, re.IGNORECASE))


def _has_table(text: str, min_rows: int = 3) -> bool:
    """Check if text has a markdown table with at least min_rows pipe-separated rows."""
    rows = re.findall(r"^\s*\|.+\|", text, re.MULTILINE)
    return len(rows) >= min_rows


# --------------------------------------------------------------------------
# EARS (Easy Approach to Requirements Syntax) compliance checker
#
# EARS patterns:
#   Ubiquitous:   "The <system> shall <action>"
#   Event-driven: "When <event>, the <system> shall <action>"
#   State-driven: "While <state>, the <system> shall <action>"
#   Unwanted:     "If <condition>, then the <system> shall <action>"
#   Optional:     "Where <feature>, the <system> shall <action>"
#   Complex:      combinations of the above
#
# Chinese equivalents:
#   当...时，系统应...  /  若...则系统应...  /  在...状态下，系统应...
# --------------------------------------------------------------------------

# EARS pattern regexes (EN + CN)
EARS_PATTERNS = [
    # English patterns
    (r"(?:When|Whenever)\s+.+?,\s*(?:the\s+)?\w+\s+(?:shall|should|must|will)\s+", "Event-driven"),
    (r"(?:While|During)\s+.+?,\s*(?:the\s+)?\w+\s+(?:shall|should|must|will)\s+", "State-driven"),
    (r"If\s+.+?,\s*(?:then\s+)?(?:the\s+)?\w+\s+(?:shall|should|must|will)\s+", "Unwanted/Conditional"),
    (r"Where\s+.+?,\s*(?:the\s+)?\w+\s+(?:shall|should|must|will)\s+", "Optional"),
    (r"(?:The\s+)?\w+\s+(?:shall|should|must)\s+", "Ubiquitous"),
    # Chinese patterns
    (r"当.+?时[，,]\s*系统(?:应|应该|须|必须|会)", "Event-driven"),
    (r"(?:在|处于).+?(?:状态|期间|过程中)[，,]\s*系统(?:应|应该|须)", "State-driven"),
    (r"(?:若|如果).+?[，,]\s*(?:则)?系统(?:应|应该|须|必须)", "Unwanted/Conditional"),
    (r"系统(?:应|应该|须|必须|需要)", "Ubiquitous"),
]


def _check_ears_compliance(content: str) -> dict:
    """
    Check how well requirements in the PRD follow EARS patterns.

    Scans feature sections (### F01 — ...) for requirement-like statements
    and checks if they match any EARS pattern.

    Returns:
        {
            "total_requirements": int,
            "compliant_count": int,
            "non_compliant": [{"feature": str, "text": str}],
            "by_pattern": {"Event-driven": int, ...},
            "issues": [...],
            "suggestions": [...]
        }
    """
    # Extract feature sections
    feature_sections = re.findall(
        r"###\s+F\d+\s*[—\-–]\s*.+?\n(.*?)(?=\n###\s+|\n##\s+|\Z)",
        content, re.DOTALL
    )

    total_reqs = 0
    compliant = 0
    non_compliant = []
    by_pattern: dict = {}

    for section in feature_sections:
        # Find requirement-like statements: sentences containing shall/should/must/应/须
        req_sentences = re.findall(
            r"[^\n。.!！?？]*(?:shall|should|must|will|应该|应当|必须|须|需要)[^\n。.!！?？]*[。.!！?？\n]",
            section, re.IGNORECASE
        )
        # Also consider bullet items as potential requirements
        bullet_items = re.findall(r"^\s*[-*]\s+(.+)$", section, re.MULTILINE)

        candidates = req_sentences + bullet_items
        for text in candidates:
            text = text.strip()
            if len(text) < 10:  # skip trivially short
                continue
            total_reqs += 1
            matched = False
            for pattern, pname in EARS_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    compliant += 1
                    by_pattern[pname] = by_pattern.get(pname, 0) + 1
                    matched = True
                    break
            if not matched:
                non_compliant.append({"text": text[:80]})

    issues = []
    suggestions = []

    if total_reqs > 0 and compliant < total_reqs * 0.5:
        issues.append({
            "field": "EARS 规范",
            "message": f"需求语句 EARS 合规率偏低（{compliant}/{total_reqs}，建议 ≥ 50%）",
            "severity": "warning"
        })
        suggestions.append(
            "推荐使用 EARS 语法编写需求：\n"
            "  Event: 「当<事件>时，系统应<动作>」\n"
            "  State: 「在<状态>下，系统应<动作>」\n"
            "  Cond:  「若<条件>，则系统应<动作>」\n"
            "  Basic: 「系统应<动作>」"
        )

    return {
        "total_requirements": total_reqs,
        "compliant_count": compliant,
        "non_compliant": non_compliant[:5],  # limit to first 5
        "by_pattern": by_pattern,
        "issues": issues,
        "suggestions": suggestions,
    }


# --------------------------------------------------------------------------
# PRD validation
# Scoring design:
#   Base points: presence of section (gate check)
#   Bonus points: depth/content quality
#   THRESHOLD = 70 means: all sections present (50) + ~42% depth checks pass
# --------------------------------------------------------------------------

# (name, pattern, base_pts, bonus_pts)
PRD_SECTIONS = [
    ("产品愿景",   r"##?\s*(产品愿景|Product Vision|Vision)",                          10, 8),
    ("核心功能",   r"##?\s*(核心功能|Features?|功能列表|功能概述)",                    8,  7),
    ("用户角色",   r"##?\s*(用户角色|User Roles?|目标用户|Personas?)",                 7,  5),
    ("功能流程",   r"##?\s*(功能流程|User Flow|交互流程|业务流程)",                    8,  7),
    ("非功能需求", r"##?\s*(非功能需求|Non.functional|性能需求|安全需求)",             7,  5),
    ("范围边界",   r"##?\s*(范围边界|Scope|In Scope|Out of Scope|边界)",               5,  3),
    ("风险",       r"##?\s*(风险|Risks?|风险分析|风险评估)",                           5,  4),
]


def _validate_prd(content: str, path: str) -> dict:
    issues: List[dict] = []
    suggestions: List[str] = []
    score = 0

    for name, pattern, base_pts, bonus_pts in PRD_SECTIONS:
        found, idx = _find_section(content, pattern)
        if not found:
            issues.append({"field": name, "message": f"缺少「{name}」章节", "severity": "error"})
            continue

        score += base_pts
        body = _section_body(content, idx)

        # Depth bonus checks — order matters: 流程 before 功能 to avoid premature match
        if "愿景" in name or "Vision" in name:
            wc = _word_count(body)
            if wc >= 50:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": f"产品愿景描述过短（{wc} 字，建议 ≥ 50 字）", "severity": "warning"})
                suggestions.append("产品愿景应清晰描述核心问题和目标用户价值，建议 ≥ 50 字")

        elif "流程" in name or "Flow" in name:
            steps = _count_ordered_steps(body)
            if steps >= 3:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": f"功能流程步骤不足（{steps} 步，建议 ≥ 3 步）", "severity": "warning"})
                suggestions.append("功能流程应按序号列出完整用户操作步骤")

        elif "功能" in name and "非" not in name:
            # Count bullet items OR ### F\d+ entries
            bullet_items = _count_list_items(body)
            feature_headers = len(re.findall(r"^###\s+F\d+", body, re.MULTILINE))
            total_items = max(bullet_items, feature_headers)
            if total_items >= 3:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": f"核心功能条目不足（{total_items} 条，建议 ≥ 3 条）", "severity": "warning"})
                suggestions.append("核心功能应有 ≥ 3 个功能条目，推荐使用 `### F01 — 功能名称` 格式")

        elif "用户角色" in name or "Roles" in name or "Personas" in name:
            items = _count_list_items(body)
            if items >= 2:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": f"用户角色条目不足（{items} 条，建议 ≥ 2 条）", "severity": "warning"})
                suggestions.append("用户角色应列出 ≥ 2 类用户，每类一行 bullet")

        elif "非功能" in name or "Non" in name:
            if _has_numbers(body):
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "非功能需求缺少具体量化指标", "severity": "warning"})
                suggestions.append("非功能需求应包含可量化指标，如「API 响应时间 < 200ms」")

        elif "范围" in name or "Scope" in name:
            has_scope = bool(re.search(r"(In Scope|Out of Scope|包含|不包含|范围内|范围外)", body, re.IGNORECASE))
            if has_scope:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "范围边界章节缺少明确的 In/Out Scope 说明", "severity": "warning"})
                suggestions.append("范围边界应明确列出「本阶段包含」和「本阶段不包含」的内容")

        elif "风险" in name or "Risk" in name:
            has_risk_keyword = bool(re.search(r"(风险|risk)", body, re.IGNORECASE))
            items = max(_count_list_items(body), _has_table(body, 2))
            if has_risk_keyword and items:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "风险章节缺少风险列表（建议含风险描述 + 缓解方案）", "severity": "warning"})
                suggestions.append("风险章节应列出主要风险及缓解方案，可用表格或列表形式")

    # Overall content bonus
    total_words = _word_count(content)
    if total_words >= 200:
        score += 8
    else:
        issues.append({"field": "整体", "message": f"文档内容过少（{total_words} 字，建议 ≥ 200 字）", "severity": "warning"})

    # EARS compliance check (bonus, not blocking)
    ears_result = _check_ears_compliance(content)
    if ears_result["compliant_count"] > 0:
        # Up to 5 bonus points based on EARS adoption ratio
        ratio = ears_result["compliant_count"] / max(ears_result["total_requirements"], 1)
        ears_bonus = min(5, int(ratio * 5))
        score += ears_bonus
    if ears_result["issues"]:
        for iss in ears_result["issues"]:
            issues.append(iss)
    if ears_result["suggestions"]:
        suggestions.extend(ears_result["suggestions"])

    score = max(0, min(100, score))
    passed = score >= THRESHOLD

    return {
        "score": score,
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "doc_type": "prd",
        "doc_path": path,
        "ears_compliance": ears_result,
    }


# --------------------------------------------------------------------------
# ARCH validation (Arc42-Lite)
# Scoring design:
#   Base points: presence of Arc42-Lite section (gate check)
#   Bonus points: depth/content quality
#   THRESHOLD = 70 means: all 8 sections present (52) + ~40% depth checks pass
# --------------------------------------------------------------------------

# (name, pattern, base_pts, bonus_pts)
ARCH_SECTIONS = [
    ("系统边界与上下文", r"##?\s*(系统边界|上下文|System Context|Context|外部依赖)",                     6, 4),
    ("技术选型",         r"##?\s*(技术选型|Tech Stack|技术栈|选型)",                                     8, 5),
    ("系统架构",         r"##?\s*(系统架构|Architecture|架构概述|整体架构)",                             8, 5),
    ("模块分解",         r"##?\s*(模块分解|组件设计|Component|模块设计|Building Block)",                 6, 4),
    ("数据模型",         r"##?\s*(数据模型|Data Model|数据库设计|Schema)",                               8, 5),
    ("API设计",          r"##?\s*(API|接口设计|Endpoints?|API 设计)",                                    6, 4),
    ("部署方案",         r"##?\s*(部署|Deployment|运维|Infrastructure|部署方案)",                       6, 4),
    ("架构决策记录",     r"##?\s*(架构决策|ADR|Architecture Decision|决策记录)",                        4, 4),
]


def _validate_arch(content: str, path: str) -> dict:
    issues: List[dict] = []
    suggestions: List[str] = []
    score = 0

    for name, pattern, base_pts, bonus_pts in ARCH_SECTIONS:
        found, idx = _find_section(content, pattern)
        if not found:
            issues.append({"field": name, "message": f"缺少「{name}」章节", "severity": "error"})
            continue

        score += base_pts
        body = _section_body(content, idx)

        if "边界" in name or "上下文" in name or "Context" in name:
            has_deps = bool(re.search(r"\|.+\|", body)) or _count_list_items(body) >= 2
            if has_deps:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "系统边界章节缺少外部依赖说明（表格或列表）", "severity": "warning"})
                suggestions.append("系统边界应列出外部系统依赖，如平台 API、第三方服务等")

        elif "选型" in name or "Stack" in name:
            has_reason = bool(re.search(r"(因为|选择|理由|原因|适合|because|reason|chose|优势)", body, re.IGNORECASE))
            if has_reason:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "技术选型缺少理由说明", "severity": "warning"})
                suggestions.append("技术选型应注明选择原因，如「选用 PostgreSQL 因为需要复杂查询」")

        elif "系统架构" in name or ("Architecture" in name and "Decision" not in name):
            has_diagram = bool(re.search(r"```|┌|┐|└|┘|─|│|【|】", body))
            if has_diagram:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "系统架构缺少架构图（代码块或 ASCII 图）", "severity": "warning"})
                suggestions.append("系统架构应包含架构示意图，可用 ASCII 图或代码块表示")

        elif "模块" in name or "Component" in name or "Building" in name:
            if _has_table(body, 3):
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "模块分解缺少结构化表格（建议 ≥ 3 行）", "severity": "warning"})
                suggestions.append("模块分解应用表格列出各模块名称、职责和技术实现")

        elif "数据" in name or "Model" in name or "Schema" in name:
            has_fields = _has_table(body, 3) or _count_list_items(body) >= 3
            if has_fields:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "数据模型缺少字段定义（表格或列表 ≥ 3 条）", "severity": "warning"})
                suggestions.append("数据模型应列出主要实体的字段名、类型和说明")

        elif "API" in name or "接口" in name or "Endpoints" in name:
            has_endpoints = bool(re.search(r"(GET|POST|PUT|DELETE|PATCH)\s+/\S+", body, re.IGNORECASE))
            if has_endpoints:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "API 设计缺少端点路径定义", "severity": "warning"})
                suggestions.append("API 设计应列出主要端点，如 `POST /api/v1/users`")

        elif "部署" in name or "Deployment" in name or "Infrastructure" in name:
            has_deploy = bool(re.search(r"(docker|kubernetes|k8s|nginx|步骤|部署|deploy)", body, re.IGNORECASE))
            if has_deploy:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "部署方案缺少部署步骤或技术说明", "severity": "warning"})
                suggestions.append("部署方案应说明容器化配置、环境变量或部署步骤")

        elif "决策" in name or "ADR" in name or "Decision" in name:
            has_adr = bool(re.search(r"(ADR|决策|背景|原因|影响|状态)", body, re.IGNORECASE))
            if has_adr:
                score += bonus_pts
            else:
                issues.append({"field": name, "message": "架构决策记录缺少决策内容和原因说明", "severity": "warning"})
                suggestions.append("ADR 应记录背景、决策选项、选择原因和影响")

    # Overall content bonus
    total_words = _word_count(content)
    if total_words >= 300:
        score += 8
    else:
        issues.append({"field": "整体", "message": f"文档内容过少（{total_words} 字，建议 ≥ 300 字）", "severity": "warning"})

    score = max(0, min(100, score))
    passed = score >= THRESHOLD

    return {
        "score": score,
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "doc_type": "arch",
        "doc_path": path,
    }


# --------------------------------------------------------------------------
# Test Outline validation (IEEE 829 精华)
# Scoring: bonus-only system (0-100), threshold 70
# --------------------------------------------------------------------------

def _validate_test_outline(content: str, path: str) -> dict:
    issues: List[dict] = []
    suggestions: List[str] = []
    score = 0

    # Count feature sections (## F01 or ## F01 —)
    feature_matches = re.findall(r"^##\s+F\d+", content, re.MULTILINE)
    feature_count = len(feature_matches)

    # Count test scenario IDs (TST-F01-S01 format)
    scenario_ids = re.findall(r"TST-F\d+-S\d+", content)
    scenario_count = len(scenario_ids)
    unique_scenario_ids = len(set(scenario_ids))

    # Check: scenario count >= 2 per feature
    min_scenarios = feature_count * 2 if feature_count > 0 else 2
    if scenario_count >= min_scenarios:
        score += 20
    else:
        issues.append({
            "field": "场景数量",
            "message": f"测试场景数不足（{scenario_count} 个，建议每功能 ≥ 2 个，共需 {min_scenarios} 个）",
            "severity": "error"
        })
        suggestions.append("每个功能至少应有 1 个正常路径场景 + 1 个异常路径场景")

    # Check: unique scenario IDs (no duplicates)
    if unique_scenario_ids == scenario_count and scenario_count > 0:
        score += 15
    else:
        issues.append({
            "field": "场景ID",
            "message": f"场景 ID 有重复或缺失（唯一 {unique_scenario_ids} 个，总计 {scenario_count} 个）",
            "severity": "error"
        })

    # Check: preconditions exist
    precond_count = len(re.findall(r"(前置条件|前置|Given|Precondition)", content, re.IGNORECASE))
    if precond_count >= max(1, scenario_count // 2):
        score += 10
    else:
        issues.append({
            "field": "前置条件",
            "message": f"前置条件覆盖不足（{precond_count} 处，建议每场景都有前置条件说明）",
            "severity": "warning"
        })
        suggestions.append("每个测试场景应明确说明前置条件（如：用户已登录、已导入 API 等）")

    # Check: ordered steps >= 3 per scenario (check in whole doc)
    step_blocks = re.findall(r"(?:测试步骤|Steps?)[^\n]*\n((?:\s*\d+[\.。\)].+\n?)+)", content, re.IGNORECASE)
    scenarios_with_steps = sum(1 for block in step_blocks if _count_ordered_steps(block) >= 3)
    if scenario_count > 0 and scenarios_with_steps >= scenario_count * 0.5:
        score += 15
    else:
        issues.append({
            "field": "测试步骤",
            "message": f"有序步骤覆盖不足（{scenarios_with_steps}/{scenario_count} 个场景有 ≥ 3 步）",
            "severity": "warning"
        })
        suggestions.append("测试步骤应用序号列出，建议 ≥ 3 步，覆盖 Given/When/Then 三段逻辑")

    # Check: expected results exist
    expect_count = len(re.findall(r"(期望结果|预期结果|Expected|应该|应当)", content, re.IGNORECASE))
    if expect_count >= max(1, scenario_count // 2):
        score += 10
    else:
        issues.append({
            "field": "期望结果",
            "message": f"期望结果描述不足（{expect_count} 处，建议每场景都有明确的期望结果）",
            "severity": "warning"
        })
        suggestions.append("每个测试场景应明确描述期望结果，说明什么状态算「通过」")

    # Check: abnormal/error scenarios exist
    error_scenarios = len(re.findall(r"(异常|错误|失败|超时|拒绝|无效|Error|Fail|Invalid|Timeout)", content, re.IGNORECASE))
    if error_scenarios >= feature_count:
        score += 15
    else:
        issues.append({
            "field": "异常路径",
            "message": f"异常路径场景不足（{error_scenarios} 处，建议每功能至少 1 个异常场景）",
            "severity": "warning"
        })
        suggestions.append("测试大纲应覆盖异常路径：如认证失败、超时、无效输入等")

    # Check: E2E tagging coverage
    e2e_count = len(re.findall(r"\[E2E\]", content))
    if scenario_count > 0 and e2e_count >= scenario_count * 0.5:
        score += 15
    else:
        issues.append({
            "field": "E2E标记",
            "message": f"[E2E] 标记覆盖不足（{e2e_count}/{scenario_count} 个场景），建议 ≥ 50% 场景标记 [E2E]",
            "severity": "warning"
        })
        suggestions.append("端到端场景应标记 [E2E]，以便区分集成测试和单元测试")

    score = max(0, min(100, score))
    passed = score >= THRESHOLD

    return {
        "score": score,
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "doc_type": "test_outline",
        "doc_path": path,
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def validate_document(doc_path: str, doc_type: str = "auto") -> dict:
    """
    Validate a PRD, ARCH, or Test Outline document.

    Args:
        doc_path: Path to the document file.
        doc_type: 'prd', 'arch', 'test_outline', or 'auto' (inferred from filename).

    Returns:
        ValidationResult dict.
    """
    p = Path(doc_path)
    if not p.exists():
        return {
            "score": 0,
            "passed": False,
            "issues": [{"field": "file", "message": f"文件不存在: {doc_path}", "severity": "error"}],
            "suggestions": [],
            "doc_type": doc_type,
            "doc_path": doc_path,
        }

    content = p.read_text(encoding="utf-8", errors="replace")

    if doc_type == "auto":
        name_lower = p.name.lower()
        if "arch" in name_lower:
            doc_type = "arch"
        elif "outline" in name_lower or "test" in name_lower:
            doc_type = "test_outline"
        else:
            doc_type = "prd"

    if doc_type == "arch":
        return _validate_arch(content, doc_path)
    elif doc_type == "test_outline":
        return _validate_test_outline(content, doc_path)
    else:
        return _validate_prd(content, doc_path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_result(result: dict) -> None:
    score = result["score"]
    passed = result["passed"]
    status = "✓ PASSED" if passed else "✗ FAILED"
    print(f"\n文档验证结果: {status}  (score: {score}/100, threshold: {THRESHOLD})")
    print(f"文档类型: {result['doc_type'].upper()}  路径: {result['doc_path']}\n")

    if result["issues"]:
        print("Issues:")
        for iss in result["issues"]:
            icon = "✗" if iss["severity"] == "error" else "⚠"
            print(f"  {icon} [{iss['field']}] {iss['message']}")

    if result["suggestions"]:
        print("\nSuggestions:")
        for s in result["suggestions"]:
            print(f"  • {s}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate PRD, ARCH, or Test Outline document")
    parser.add_argument("--doc", required=True, help="Path to document file")
    parser.add_argument("--type", choices=["prd", "arch", "test_outline", "auto"], default="auto")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = validate_document(args.doc, args.type)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_result(result)

    sys.exit(0 if result["passed"] else 1)
