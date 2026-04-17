"""
PHASES Definition Table for Product-Lifecycle Orchestrator.

This module defines all phases in the product lifecycle workflow,
including their dependencies, artifacts, validation rules, and failure strategies.
"""
from __future__ import annotations
from typing import TypedDict, List, Optional, Literal


# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------

class PhaseArtifact(TypedDict):
    """Phase artifact validation rule."""
    path: str
    min_bytes: int
    required_headings: Optional[List[str]]
    required_substrings: Optional[List[str]]


class PhaseDefinition(TypedDict):
    """Complete phase definition with 15+ fields."""
    id: str
    name: str
    description: str
    order: int

    # Execution control
    auto: bool
    command: Optional[str]
    command_args: Optional[dict]

    # Dependencies
    depends_on: List[str]
    blocks: List[str]

    # Validation
    artifacts: List[PhaseArtifact]
    validation_type: Optional[str]

    # Failure handling
    on_failure: Literal["pause", "retry", "skip"]
    max_retries: int

    # Interaction
    pause_for: Optional[str]
    timeout_hint: Optional[str]

    # Intent mapping
    intent_triggers: List[str]

    # v2.2: Conditional branching
    condition: Optional[str]  # Condition expression (e.g., "project_type == 'web'")
    branches: Optional[dict]  # Branch mapping (e.g., {"web": "phase-7a", "cli": "phase-7b"})


# ---------------------------------------------------------------------------
# PHASES Registry
# ---------------------------------------------------------------------------

PHASES: List[PhaseDefinition] = [
    {
        "id": "phase-0-intent",
        "name": "意图识别",
        "description": "识别用户意图，确定执行路径",
        "order": 0,
        "auto": False,
        "command": None,
        "command_args": None,
        "depends_on": [],
        "blocks": ["phase-1-init", "phase-10-change"],
        "artifacts": [],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 0,
        "pause_for": "等待用户确认执行计划",
        "timeout_hint": None,
        "intent_triggers": ["*"]
    },
    {
        "id": "phase-1-init",
        "name": "项目初始化",
        "description": "创建文档结构、DoD 配置、Risk Register、ADR 目录",
        "order": 1,
        "auto": True,
        "command": "init",
        "command_args": {"name": "{project_name}"},
        "depends_on": [],
        "blocks": ["phase-2-draft-prd"],
        "artifacts": [
            {"path": "Docs/INDEX.md", "min_bytes": 200, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/config.json", "min_bytes": 100, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/dod.json", "min_bytes": 50, "required_headings": None, "required_substrings": None},
            {"path": "Docs/adr/INDEX.md", "min_bytes": 80, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 1,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["new-product", "from-scratch"]
    },
    {
        "id": "phase-2-draft-prd",
        "name": "AI 协作 PRD 起草",
        "description": "Claude 生成 PRD 草案，用户做审稿人",
        "order": 2,
        "auto": False,
        "command": "draft",
        "command_args": {"doc_type": "prd", "description": "{user_description}"},
        "depends_on": ["phase-1-init"],
        "blocks": ["phase-3-validate-prd"],
        "artifacts": [
            {"path": "Docs/product/PRD.md", "min_bytes": 800, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 0,
        "pause_for": "等待用户审核 PRD 草案，补充 [❓待确认] 标注处",
        "timeout_hint": "建议在 24h 内完成审核",
        "intent_triggers": ["new-product", "new-feature", "prd-change"]
    },
    {
        "id": "phase-3-validate-prd",
        "name": "PRD 验证 + 自动快照",
        "description": "验证 PRD 质量，通过后自动建快照",
        "order": 3,
        "auto": True,
        "command": "validate",
        "command_args": {"doc": "Docs/product/PRD.md", "type": "prd"},
        "depends_on": ["phase-2-draft-prd"],
        "blocks": ["phase-4-arch-interview"],
        "artifacts": [
            {"path": ".lifecycle/snapshots/prd_latest.md", "min_bytes": 800, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/steps/prd-score.json", "min_bytes": 30, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": "prd",
        "on_failure": "pause",
        "max_retries": 3,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["new-product", "new-feature", "prd-change"]
    },
    {
        "id": "phase-4-arch-interview",
        "name": "架构访谈 + 项目类型识别",
        "description": "与用户确认技术选型，自动识别项目类型",
        "order": 4,
        "auto": False,
        "command": None,
        "command_args": None,
        "depends_on": ["phase-3-validate-prd"],
        "blocks": ["phase-5-draft-arch"],
        "artifacts": [
            {"path": ".lifecycle/arch_interview.json", "min_bytes": 100, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/project_type.json", "min_bytes": 50, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 0,
        "pause_for": "等待用户回答架构访谈问题（6 个问题）",
        "timeout_hint": None,
        "intent_triggers": ["new-product", "arch-change"]
    },
    {
        "id": "phase-5-draft-arch",
        "name": "AI 协作架构设计",
        "description": "Claude 生成架构草案（含 ADR 初稿）",
        "order": 5,
        "auto": False,
        "command": "draft",
        "command_args": {"doc_type": "arch"},
        "depends_on": ["phase-4-arch-interview"],
        "blocks": ["phase-6-validate-arch"],
        "artifacts": [
            {"path": "Docs/tech/ARCH.md", "min_bytes": 800, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 0,
        "pause_for": "等待用户审核架构草案，对 ADR 做决策",
        "timeout_hint": None,
        "intent_triggers": ["new-product", "arch-change"]
    },
    {
        "id": "phase-6-validate-arch",
        "name": "架构验证 + ADR 注册 + 快照",
        "description": "验证架构文档，检查至少 1 条 ADR accepted",
        "order": 6,
        "auto": True,
        "command": "validate",
        "command_args": {"doc": "Docs/tech/ARCH.md", "type": "arch"},
        "depends_on": ["phase-5-draft-arch"],
        "blocks": ["phase-7-test-outline"],
        "artifacts": [
            {"path": ".lifecycle/snapshots/arch_latest.md", "min_bytes": 800, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/steps/arch-score.json", "min_bytes": 30, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": "arch",
        "on_failure": "pause",
        "max_retries": 3,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["new-product", "arch-change"]
    },
    {
        "id": "phase-7-test-outline",
        "name": "自适应测试大纲生成",
        "description": "根据项目类型选择维度集，生成测试大纲 + test_graph.json",
        "order": 7,
        "auto": True,
        "command": "outline",
        "command_args": {
            "action": "generate",
            "prd": "Docs/product/PRD.md",
            "arch": "Docs/tech/ARCH.md",
            "output": "Docs/tests/MASTER_OUTLINE.md"
        },
        "depends_on": ["phase-6-validate-arch"],
        "blocks": ["phase-8-iterations"],
        "artifacts": [
            {"path": "Docs/tests/MASTER_OUTLINE.md", "min_bytes": 600, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/test_graph.json", "min_bytes": 200, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": "test_outline",
        "on_failure": "pause",
        "max_retries": 2,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["new-product", "test-change", "prd-change"]
    },
    {
        "id": "phase-8-iterations",
        "name": "Velocity 感知迭代规划",
        "description": "生成迭代计划，设定工时估算",
        "order": 8,
        "auto": True,
        "command": "plan",
        "command_args": {
            "prd": "Docs/product/PRD.md",
            "arch": "Docs/tech/ARCH.md"
        },
        "depends_on": ["phase-7-test-outline"],
        "blocks": ["phase-9-iter-exec"],
        "artifacts": [
            {"path": "Docs/iterations/INDEX.md", "min_bytes": 200, "required_headings": None, "required_substrings": None},
            {"path": ".lifecycle/velocity.json", "min_bytes": 50, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 1,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["new-product", "new-iteration", "prd-change"]
    },
    {
        "id": "phase-9-iter-exec",
        "name": "迭代执行循环",
        "description": "开发、测试、DoD 检查、门控验证",
        "order": 9,
        "auto": False,
        "command": "gate",
        "command_args": {"iteration": "{current_iteration}"},
        "depends_on": ["phase-8-iterations"],
        "blocks": [],
        "artifacts": [],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 0,
        "pause_for": "等待用户完成开发任务，运行测试，通过 DoD 检查",
        "timeout_hint": None,
        "intent_triggers": ["new-iteration", "continue-iter"]
    },
    {
        "id": "phase-10-change",
        "name": "变更处理",
        "description": "处理 PRD/Code/Test 变更，级联影响分析",
        "order": 10,
        "auto": True,
        "command": "change",
        "command_args": {"change_type": "{change_type}"},
        "depends_on": ["phase-6-validate-arch"],
        "blocks": [],
        "artifacts": [
            {"path": ".lifecycle/CHANGE_IMPACT.md", "min_bytes": 100, "required_headings": None, "required_substrings": None}
        ],
        "validation_type": None,
        "on_failure": "pause",
        "max_retries": 1,
        "pause_for": None,
        "timeout_hint": None,
        "intent_triggers": ["prd-change", "code-change", "test-failure", "bug-fix", "gap"]
    }
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_phase_by_id(phase_id: str) -> Optional[PhaseDefinition]:
    """Get phase definition by ID."""
    for phase in PHASES:
        if phase["id"] == phase_id:
            return phase
    return None


def get_phases_by_intent(intent: str) -> List[PhaseDefinition]:
    """Get all phases triggered by a specific intent."""
    if intent == "*":
        return PHASES

    # Special handling for "resume" - return all phases
    # Orchestrator will filter based on checkpoint
    if intent == "resume":
        return PHASES

    return [p for p in PHASES if intent in p["intent_triggers"]]


def get_ordered_phases() -> List[PhaseDefinition]:
    """Get all phases ordered by execution order."""
    return sorted(PHASES, key=lambda p: p["order"])


def validate_phases() -> List[str]:
    """
    Validate phase definitions for consistency.
    Returns list of error messages (empty if valid).
    """
    errors = []
    phase_ids = {p["id"] for p in PHASES}

    for phase in PHASES:
        # Check dependencies exist
        for dep in phase["depends_on"]:
            if dep not in phase_ids:
                errors.append(f"Phase {phase['id']} depends on non-existent phase: {dep}")

        # Check blocks exist
        for block in phase["blocks"]:
            if block not in phase_ids:
                errors.append(f"Phase {phase['id']} blocks non-existent phase: {block}")

        # Check command exists (if specified)
        if phase["command"]:
            # Commands will be validated by orchestrator
            pass

        # Check artifacts paths are relative
        for artifact in phase["artifacts"]:
            if artifact["path"].startswith("/"):
                errors.append(f"Phase {phase['id']} artifact path should be relative: {artifact['path']}")

    return errors


# Run validation on import
_validation_errors = validate_phases()
if _validation_errors:
    import warnings
    warnings.warn("PHASES validation errors:\n" + "\n".join(f"  - {e}" for e in _validation_errors))
