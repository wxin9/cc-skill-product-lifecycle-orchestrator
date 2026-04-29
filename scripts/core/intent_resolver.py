"""
Intent Resolver for Product Lifecycle Orchestrator.

Maps user input to execution intents using regex patterns and priority ranking.
"""
from __future__ import annotations
import re
from typing import List, Tuple, Literal, Optional
from dataclasses import dataclass


IntentType = Literal[
    "bug-fix",
    "gap",
    "prd-change",
    "code-change",
    "test-failure",
    "new-feature",
    "arch-change",
    "new-iteration",
    "continue-iter",
    "new-product",
    "from-scratch",
    "test-change"
]


@dataclass
class IntentMatch:
    """Represents a matched intent."""
    intent: IntentType
    pattern: str
    priority: int
    explanation: str


class IntentResolver:
    """
    Resolves user input to execution intents.

    Uses regex pattern matching and priority ranking to determine
    the most likely intent(s) from user input.
    """

    # Intent keyword patterns
    INTENT_PATTERNS = {
        "bug-fix": [
            r"报错", r"测试失败", r"bug", r"修复", r"fix",
            r"错误", r"异常", r"崩溃", r"报错了"
        ],
        "gap": [
            r"测试发现新场景", r"gap", r"遗漏", r"缺失",
            r"未覆盖", r"缺少", r"需求遗漏"
        ],
        "prd-change": [
            r"需求变", r"PRD 改", r"需求改", r"调整需求",
            r"修改需求", r"变更需求", r"prd change", r"改需求"
        ],
        "code-change": [
            r"修改了.*模块", r"重构", r"代码变更",
            r"换.*实现", r"code change", r"改代码"
        ],
        "test-failure": [
            r"测试失败", r"test fail", r"用例失败",
            r"测试挂了", r"测试不过"
        ],
        "new-feature": [
            r"增加功能", r"新需求", r"新增功能",
            r"加功能", r"new feature", r"新功能"
        ],
        "arch-change": [
            r"换数据库", r"换架构", r"重构架构",
            r"架构调整", r"技术栈变", r"arch change",
            r"改架构"
        ],
        "new-iteration": [
            r"下一个迭代", r"迭代 \d+", r"新迭代",
            r"开始迭代", r"new iteration", r"下个迭代"
        ],
        "continue-iter": [
            r"继续迭代", r"继续开发", r"continue",
            r"接着做", r"继续"
        ],
        "new-product": [
            r"新产品", r"从零开始", r"新项目",
            r"从零做", r"new product", r"做一个产品",
            r"开发一个"
        ],
        "from-scratch": [
            r"从零", r"from scratch", r"全新项目", r"空白项目",
            r"重头开始", r"重新开始"
        ],
        "test-change": [
            r"测试改", r"修改测试", r"test change", r"测试用例变",
            r"更新测试", r"调整测试"
        ],
    }

    # Intent priority (lower number = higher priority)
    INTENT_PRIORITY = {
        "bug-fix": 1,
        "test-failure": 1,
        "gap": 2,
        "prd-change": 3,
        "code-change": 4,
        "new-feature": 5,
        "arch-change": 6,
        "new-iteration": 7,
        "continue-iter": 8,
        "new-product": 9,
        "from-scratch": 9,   # Same priority as new-product
        "test-change": 5,    # Same priority as new-feature
    }

    @classmethod
    def resolve(cls, user_input: str) -> Tuple[List[IntentType], str]:
        """
        Resolve user input to intent(s).

        Args:
            user_input: Raw user input string

        Returns:
            (intents, explanation)
            intents — List of matched intents sorted by priority
            explanation — Human-readable explanation of matching
        """
        matches: List[IntentMatch] = []

        for intent, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    matches.append(IntentMatch(
                        intent=intent,
                        pattern=pattern,
                        priority=cls.INTENT_PRIORITY.get(intent, 99),
                        explanation=f"'{user_input}' 匹配意图 '{intent}' (关键词: {pattern})"
                    ))

        if not matches:
            return (["new-product"], "未识别到明确意图，默认为新项目")

        # Sort by priority
        matches.sort(key=lambda m: m.priority)

        intents = [m.intent for m in matches]
        explanation = "\n".join(m.explanation for m in matches)

        return (intents, explanation)

    @classmethod
    def get_execution_paths(cls, intents: List[IntentType]) -> List[List[str]]:
        """
        Get execution paths for each intent.

        Args:
            intents: List of intents

        Returns:
            List of phase sequences, one per intent
        """
        from .phases import get_phases_by_intent, get_ordered_phases

        paths = []
        for intent in intents:
            # Get phases triggered by this intent
            phases = get_phases_by_intent(intent)
            # Sort by order
            phases = sorted(phases, key=lambda p: p["order"])
            # Extract phase IDs
            path = [p["id"] for p in phases]
            if path:
                paths.append(path)

        return paths

    @classmethod
    def get_primary_intent(cls, intents: List[IntentType]) -> IntentType:
        """Get the highest priority intent from a list."""
        if not intents:
            return "new-product"
        return min(intents, key=lambda i: cls.INTENT_PRIORITY.get(i, 99))

    @classmethod
    def format_intents_report(cls, intents: List[IntentType], explanation: str) -> str:
        """Format a human-readable report of resolved intents."""
        lines = ["检测到以下意图（按优先级排序）："]
        for i, intent in enumerate(intents, 1):
            priority = cls.INTENT_PRIORITY.get(intent, 99)
            lines.append(f"  {i}. {intent} (优先级: {priority})")

        lines.append(f"\n匹配详情：\n{explanation}")

        if len(intents) > 1:
            lines.append("\n检测到复合意图，建议分步执行：")
            for i, intent in enumerate(intents, 1):
                lines.append(f"  步骤 {i}: 执行 {intent} 相关流程")

        return "\n".join(lines)


# Convenience functions
def resolve_intent(user_input: str) -> Tuple[List[IntentType], str]:
    """Convenience function to resolve intent."""
    return IntentResolver.resolve(user_input)


def get_primary_intent(user_input: str) -> IntentType:
    """Convenience function to get primary intent."""
    intents, _ = IntentResolver.resolve(user_input)
    return IntentResolver.get_primary_intent(intents)
