"""
intent_classifier.py — 意图识别辅助模块

辅助 AI agent 在 Phase 0 快速判断用户输入属于哪种类型，
以及建议从哪个 Phase 开始执行 product-lifecycle-orchestrator 工作流。

核心函数：
  check_project_state(root)             → 返回项目当前已完成状态摘要
  suggest_entry_point(text, state)      → 返回建议起始 Phase 及原因

设计原则：
  - 这个模块只做辅助判断，最终决策仍由 AI agent（SKILL.md 规则）做出
  - check_project_state 读取物理检查点文件，结果完全可信
  - suggest_entry_point 做关键词匹配，置信度低时返回 needs_clarification=True
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 1. check_project_state
# ---------------------------------------------------------------------------

def check_project_state(root: str | Path) -> dict:
    """
    读取 .lifecycle/ 目录，返回项目当前已完成状态的摘要。

    返回结构：
    {
        "has_lifecycle": bool,           # .lifecycle/ 是否存在
        "project_name": str,             # 项目名称（来自 config.json）
        "current_iteration": int,        # 当前迭代号
        "completed_steps": List[str],    # 所有已完成的步骤 ID
        "completed_phases": List[str],   # 高层阶段描述（人类可读）
        "last_gate_passed": int | None,  # 最近通过的迭代门控号
        "phase_summary": str,            # 一句话项目状态描述
    }
    """
    root = Path(root).resolve()
    lifecycle = root / ".lifecycle"

    if not lifecycle.exists():
        return {
            "has_lifecycle": False,
            "project_name": "",
            "current_iteration": 0,
            "completed_steps": [],
            "completed_phases": [],
            "last_gate_passed": None,
            "phase_summary": "项目尚未初始化（无 .lifecycle/ 目录）",
        }

    # 读取 config.json
    config: dict = {}
    config_path = lifecycle / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 读取已完成阶段（优先从 checkpoint.json）
    completed_phases: list[str] = []
    checkpoint_file = lifecycle / "checkpoint.json"
    if checkpoint_file.exists():
        try:
            cp = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            completed_phases = cp.get("completed_phases", [])
        except Exception:
            pass

    # 最近通过的迭代门控（从 checkpoint metadata 读取）
    last_gate: Optional[int] = None
    if checkpoint_file.exists():
        try:
            cp = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            last_gate = cp.get("metadata", {}).get("current_iteration", None)
            if last_gate and last_gate > 1:
                last_gate = last_gate - 1
            elif last_gate == 1:
                last_gate = None
        except Exception:
            pass

    # 生成一句话状态描述
    if not completed_phases:
        summary = "项目已初始化但尚未开始任何 Phase"
    elif "phase-12-iter-exec" in completed_phases:
        summary = "迭代执行中，可继续迭代或接受变更"
    elif "phase-11-iterations" in completed_phases:
        summary = "迭代规划已完成，可开始执行迭代"
    elif "phase-10-test-spec" in completed_phases:
        summary = "测试大纲与 Test Spec 已生成，可规划迭代"
    elif "phase-8-tech-spec" in completed_phases:
        summary = "架构已验证并生成 Tech Spec，可生成 Lifecycle Graph 与测试规格"
    elif "phase-4-product-spec" in completed_phases:
        summary = "PRD 已验证并生成 Product Spec，可进行 UED 与技术架构设计"
    elif "phase-3-draft-prd" in completed_phases:
        summary = "PRD 已编写，等待验证"
    elif "phase-2-init" in completed_phases:
        summary = "项目已初始化，等待 PRD 编写"
    else:
        summary = "项目刚创建，等待意图识别"

    return {
        "has_lifecycle": True,
        "project_name": config.get("project_name", root.name),
        "current_iteration": config.get("current_iteration", 0),
        "completed_steps": completed_phases,
        "completed_phases": completed_phases,
        "last_gate_passed": last_gate,
        "phase_summary": summary,
    }


# ---------------------------------------------------------------------------
# 2. suggest_entry_point
# ---------------------------------------------------------------------------

# 意图关键词配置：每个意图有「触发词」列表 + 「建议 Phase」+ 「说明」
# 顺序很重要：越具体的规则越靠前（bug > 修改 > 新功能）
_INTENT_RULES = [
    {
        "intent": "debug_or_bug",
        "label": "Bug 修复 / Debug",
        "keywords": ["bug", "报错", "错误", "修复", "崩溃", "测试失败", "fail", "error",
                     "exception", "异常", "不能用", "不生效", "无法", "挂了"],
        "required_phases": [],
        "phase": "1",
        "phase_description": "Phase 1（影响分析报告：bug 修复）",
        "entry_command": "./orchestrator run --intent bug-fix",
    },
    {
        "intent": "test_gap",
        "label": "需求遗漏（测试暴露）",
        "keywords": ["需求遗漏", "gap", "测试发现新问题", "测试暴露了"],
        "required_phases": ["phase-10-test-spec"],
        "phase": "1",
        "phase_description": "Phase 1（影响分析报告：需求遗漏 → PRD 变更任务）",
        "entry_command": "./orchestrator run --intent gap",
    },
    {
        "intent": "prd_change",
        "label": "PRD 变更",
        "keywords": ["prd改了", "需求变了", "需求变更", "需求改了", "产品需求更新",
                     "变更需求", "修改需求", "修改prd", "prd 改", "prd改", "需求变",
                     "需求修改", "修改了prd", "更新prd", "prd更新"],
        "required_phases": ["phase-4-product-spec"],
        "phase": "1",
        "phase_description": "Phase 1（影响分析报告：PRD 变更 → 全链路级联）",
        "entry_command": "./orchestrator run --intent prd-change",
    },
    {
        "intent": "code_change",
        "label": "代码变更",
        "keywords": ["代码变更", "修改了模块", "重写了", "改了代码", "代码改动", "重构了代码"],
        "required_phases": ["phase-11-iterations"],
        "phase": "1",
        "phase_description": "Phase 1（影响分析报告：代码变更 → 测试影响追溯）",
        "entry_command": "./orchestrator run --intent code-change",
    },
    {
        "intent": "add_test",
        "label": "补充测试用例",
        "keywords": ["补充测试", "新增测试", "加测试用例", "测试场景", "测试覆盖", "增加测试"],
        "required_phases": ["phase-8-tech-spec"],
        "phase": "10",
        "phase_description": "Phase 10（Test Spec 与测试大纲更新）",
        "entry_command": "./orchestrator run --intent test-change",
    },
    {
        "intent": "new_iteration",
        "label": "开始新迭代",
        "keywords": ["新迭代", "下一个迭代", "开始迭代", "进入迭代", "迭代2", "第二迭代",
                     "迭代3", "第三迭代", "继续迭代", "下一迭代"],
        "required_phases": ["phase-11-iterations"],
        "phase": "12",
        "phase_description": "Phase 12（迭代执行循环）",
        "entry_command": "./orchestrator run --intent new-iteration",
    },
    {
        "intent": "arch_change",
        "label": "技术架构调整",
        "keywords": ["换数据库", "调整架构", "重构架构", "技术栈", "换技术", "架构变更",
                     "服务边界", "微服务", "架构升级", "技术调整", "换一下数据库",
                     "数据库换", "改数据库", "换框架", "改框架", "技术选型"],
        "required_phases": ["phase-4-product-spec"],
        "phase": "1",
        "phase_description": "Phase 1 + Phase 7/8（影响分析 → 架构设计 → Tech Spec）",
        "entry_command": "./orchestrator run --intent arch-change",
    },
    {
        "intent": "new_feature",
        "label": "新增功能需求",
        "keywords": ["新功能", "增加功能", "添加功能", "prd里加", "新需求", "功能扩展",
                     "增加一个", "添加一个", "需要支持", "需要增加"],
        "required_phases": ["phase-2-init"],
        "phase": "1",
        "phase_description": "Phase 1 + Phase 3-12（影响分析 → PRD/UED/Tech/Test Specs → 迭代）",
        "entry_command": "./orchestrator run --intent new-feature",
    },
    {
        "intent": "new_project",
        "label": "全新产品",
        "keywords": ["新产品", "从零", "全新", "全新项目", "开始一个", "创建项目",
                     "新项目", "搭建项目", "帮我做"],
        "required_phases": [],
        "phase": "1",
        "phase_description": "Phase 1（Solution Advisor）",
        "entry_command": "./orchestrator run --intent new-product",
    },
]


def suggest_entry_point(text: str, project_state: dict) -> dict:
    """
    根据用户输入文本和当前项目状态，建议从哪个 Phase 开始执行。

    返回结构：
    {
        "intent": str,                    # 识别到的意图 ID
        "intent_label": str,              # 意图的人类可读描述
        "phase": str,                     # 建议起始 Phase（如 "1", "7", "8c"）
        "phase_description": str,         # Phase 的人类可读描述
        "entry_command": str,             # 建议的首个执行命令
        "confidence": str,                # "high" | "medium" | "low"
        "needs_clarification": bool,      # 是否需要向用户确认
        "clarification_options": list,    # 如需确认时的选项列表
        "skip_summary": list,             # 将跳过的 phases（仅供展示）
        "reason": str,                    # 识别原因说明
    }
    """
    text_lower = text.lower()
    has_lifecycle = project_state.get("has_lifecycle", False)
    completed_phases_set = set(project_state.get("completed_steps", []))

    # 如果没有 .lifecycle 目录，无论说什么，都从 Phase 1 开始
    if not has_lifecycle:
        return {
            "intent": "new_project",
            "intent_label": "全新产品",
            "phase": "1",
            "phase_description": "Phase 1（项目初始化）",
            "entry_command": "./orchestrator run --intent new-product",
            "confidence": "high",
            "needs_clarification": False,
            "clarification_options": [],
            "skip_summary": [],
            "reason": "未检测到 .lifecycle/ 目录，必须从 Phase 1 初始化开始",
        }

    # 关键词匹配：按规则顺序（最具体优先）遍历
    matched_rules = []
    for rule in _INTENT_RULES:
        hit_keywords = [kw for kw in rule["keywords"] if kw in text_lower]
        if not hit_keywords:
            continue

        # 检查前置阶段是否满足
        required = rule.get("required_phases", [])
        missing_prereqs = [s for s in required if s not in completed_phases_set]

        matched_rules.append({
            "rule": rule,
            "hit_keywords": hit_keywords,
            "missing_prereqs": missing_prereqs,
            "keyword_score": len(hit_keywords),
        })

    # 没有匹配到任何意图
    if not matched_rules:
        return _needs_clarification_response(
            project_state,
            reason="未能从输入中识别出明确的意图，请选择或描述您希望进行的操作"
        )

    # 选出得分最高的匹配
    best = max(matched_rules, key=lambda x: x["keyword_score"])
    rule = best["rule"]
    missing = best["missing_prereqs"]

    # 如果有多个同分匹配，可能模糊 → 降为 medium confidence
    top_score = best["keyword_score"]
    ties = [m for m in matched_rules if m["keyword_score"] == top_score]
    confidence = "high" if len(ties) == 1 else "medium"

    # 如果前置步骤不满足，说明意图合理但流程顺序有问题
    if missing:
        return {
            "intent": rule["intent"],
            "intent_label": rule["label"],
            "phase": rule["phase"],
            "phase_description": rule["phase_description"],
            "entry_command": rule["entry_command"],
            "confidence": "medium",
            "needs_clarification": True,
            "clarification_options": [],
            "skip_summary": [],
            "reason": (
                f"识别为「{rule['label']}」，但前置步骤未完成：{missing}。"
                f"建议先完成 {missing[0]} 后再进行此操作。"
            ),
        }

    # 计算 skip_summary（将跳过哪些 phases）
    all_phases = ["Phase 0 意图识别", "Phase 1 Solution Advisor / Impact Report", "Phase 2 初始化",
                  "Phase 3 PRD 起草", "Phase 4 Product Spec", "Phase 5 UED 起草",
                  "Phase 6 UED Spec", "Phase 7 架构设计", "Phase 8 Tech Spec",
                  "Phase 9 Lifecycle Graph", "Phase 10 Test Spec", "Phase 11 迭代规划",
                  "Phase 12 迭代执行"]
    try:
        phase_num = int(rule["phase"])
        skip = all_phases[:max(0, phase_num)]
    except (ValueError, IndexError):
        skip = []

    # 如果置信度 medium 且有多个 tie，需要确认
    if confidence == "medium":
        options = [
            f"{m['rule']['label']} → {m['rule']['phase_description']}"
            for m in ties
        ]
        return {
            "intent": rule["intent"],
            "intent_label": rule["label"],
            "phase": rule["phase"],
            "phase_description": rule["phase_description"],
            "entry_command": rule["entry_command"],
            "confidence": "medium",
            "needs_clarification": True,
            "clarification_options": options,
            "skip_summary": skip,
            "reason": (
                f"检测到多个可能意图（{len(ties)} 个）。"
                f"最佳匹配：「{rule['label']}」（命中关键词：{best['hit_keywords']}）"
            ),
        }

    return {
        "intent": rule["intent"],
        "intent_label": rule["label"],
        "phase": rule["phase"],
        "phase_description": rule["phase_description"],
        "entry_command": rule["entry_command"],
        "confidence": confidence,
        "needs_clarification": False,
        "clarification_options": [],
        "skip_summary": skip,
        "reason": f"识别为「{rule['label']}」，命中关键词：{best['hit_keywords']}",
    }


def _needs_clarification_response(project_state: dict, reason: str) -> dict:
    """当无法识别意图时，返回需要确认的响应，附上基于项目状态的建议选项。"""
    completed = set(project_state.get("completed_steps", []))
    last_gate = project_state.get("last_gate_passed")

    options = []
    if "phase-11-iterations" in completed:
        n = (last_gate or 0) + 1
        options.append(f"开始迭代 {n} → Phase 12 迭代执行")
    if "phase-4-product-spec" in completed:
        options.append("新增/修改功能需求 → Phase 1 影响分析后刷新 PRD/Product Spec")
        options.append("代码或架构有变更 → Phase 1 影响分析后刷新相关 Specs")
    if not completed:
        options.append("全新产品 → Phase 1 初始化")

    options.append("其他（请描述您想做什么）")

    return {
        "intent": "unknown",
        "intent_label": "未能识别",
        "phase": "?",
        "phase_description": "需要用户确认",
        "entry_command": "",
        "confidence": "low",
        "needs_clarification": True,
        "clarification_options": options,
        "skip_summary": [],
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# CLI 入口（便于独立调试）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    state = check_project_state(root)
    print("=== 项目状态 ===")
    print(f"  has_lifecycle  : {state['has_lifecycle']}")
    print(f"  project_name   : {state['project_name']}")
    print(f"  phase_summary  : {state['phase_summary']}")
    print(f"  completed_steps: {state['completed_steps']}")

    if text:
        print("\n=== 意图识别 ===")
        result = suggest_entry_point(text, state)
        print(f"  intent        : {result['intent_label']}")
        print(f"  phase         : {result['phase_description']}")
        print(f"  confidence    : {result['confidence']}")
        print(f"  clarification : {result['needs_clarification']}")
        if result["needs_clarification"]:
            print("  options:")
            for opt in result["clarification_options"]:
                print(f"    - {opt}")
        print(f"  reason        : {result['reason']}")
        if result["entry_command"]:
            print(f"  entry_command : {result['entry_command']}")
