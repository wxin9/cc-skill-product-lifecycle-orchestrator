"""
PHASES Definition Table for Product Lifecycle Orchestrator.

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
    execution_mode: Optional[str]

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


def _artifact(path: str, min_bytes: int) -> PhaseArtifact:
    return {
        "path": path,
        "min_bytes": min_bytes,
        "required_headings": None,
        "required_substrings": None,
    }


def _phase(
    *,
    id: str,
    name: str,
    description: str,
    order: int,
    auto: bool,
    command: Optional[str],
    command_args: Optional[dict],
    depends_on: List[str],
    artifacts: List[PhaseArtifact],
    intent_triggers: List[str],
    blocks: Optional[List[str]] = None,
    validation_type: Optional[str] = None,
    pause_for: Optional[str] = None,
    execution_mode: Optional[str] = None,
    on_failure: Literal["pause", "retry", "skip"] = "pause",
    max_retries: int = 0,
    timeout_hint: Optional[str] = None,
) -> PhaseDefinition:
    return {
        "id": id,
        "name": name,
        "description": description,
        "order": order,
        "auto": auto,
        "command": command,
        "command_args": command_args,
        "execution_mode": execution_mode,
        "depends_on": depends_on,
        "blocks": blocks or [],
        "artifacts": artifacts,
        "validation_type": validation_type,
        "on_failure": on_failure,
        "max_retries": max_retries,
        "pause_for": pause_for,
        "timeout_hint": timeout_hint,
        "intent_triggers": intent_triggers,
        "condition": None,
        "branches": None,
    }


# ---------------------------------------------------------------------------
# PHASES Registry
# ---------------------------------------------------------------------------

PHASES: List[PhaseDefinition] = [
    _phase(
        id="phase-0-intent",
        name="意图识别",
        description="识别用户意图，确定执行路径",
        order=0,
        auto=True,
        command=None,
        command_args=None,
        depends_on=[],
        blocks=["phase-2-init", "phase-1-impact-report"],
        artifacts=[],
        intent_triggers=["*"],
    ),
    _phase(
        id="phase-1-analyze-solution",
        name="Solution Advisor",
        description="分析需求、项目代码、业界方案，生成方案建议和轻量模式建议",
        order=1,
        auto=False,
        command="analyze_solution",
        command_args={"intent": "{intent}", "user_input": "{user_description}"},
        depends_on=["phase-0-intent"],
        blocks=["phase-2-init"],
        artifacts=[_artifact(".lifecycle/solution.json", 100)],
        intent_triggers=["new-product", "from-scratch"],
        pause_for="等待用户选择实现方案",
        timeout_hint="建议在 1h 内完成方案选择",
    ),
    _phase(
        id="phase-1-impact-report",
        name="影响分析报告",
        description="在需求或代码变更前生成全量高亮 Impact Report",
        order=1,
        auto=True,
        command="change",
        command_args={"change_type": "{change_type}", "user_input": "{user_description}"},
        depends_on=["phase-0-intent"],
        artifacts=[
            _artifact(".lifecycle/CHANGE_IMPACT.md", 100),
            _artifact(".lifecycle/specs/impact.json", 100),
        ],
        intent_triggers=["new-feature", "prd-change", "arch-change", "code-change", "test-failure", "bug-fix", "gap"],
    ),
    _phase(
        id="phase-2-init",
        name="项目初始化",
        description="创建 Human Docs、runtime state、spec schema 和基础目录",
        order=2,
        auto=True,
        command="init",
        command_args={"name": "{project_name}"},
        depends_on=["phase-0-intent"],
        blocks=["phase-3-draft-prd"],
        artifacts=[
            _artifact("Docs/INDEX.md", 200),
            _artifact(".lifecycle/config.json", 100),
            _artifact(".lifecycle/dod.json", 50),
            _artifact("Docs/adr/INDEX.md", 80),
            _artifact(".lifecycle/specs/schemas/product.schema.json", 100),
        ],
        intent_triggers=["new-product", "from-scratch"],
        max_retries=1,
    ),
    _phase(
        id="phase-3-draft-prd",
        name="AI 协作 PRD 起草",
        description="生成 Human PRD，用户审核需求语义和范围边界",
        order=3,
        auto=False,
        command="draft",
        command_args={"doc_type": "prd", "description": "{user_description}"},
        depends_on=["phase-2-init"],
        blocks=["phase-4-product-spec"],
        artifacts=[_artifact("Docs/product/PRD.md", 800)],
        intent_triggers=["new-product", "new-feature", "prd-change"],
        pause_for="等待用户审核 PRD 草案，补充 [❓待确认] 标注处",
        timeout_hint="建议在 24h 内完成审核",
    ),
    _phase(
        id="phase-4-product-spec",
        name="Product Spec 生成与验证",
        description="验证 PRD，通过后生成 Product Spec 和 PRD 快照",
        order=4,
        auto=True,
        command="validate",
        command_args={"doc": "Docs/product/PRD.md", "type": "prd"},
        depends_on=["phase-3-draft-prd"],
        blocks=["phase-5-draft-ued"],
        artifacts=[
            _artifact(".lifecycle/snapshots/prd_latest.md", 800),
            _artifact(".lifecycle/steps/prd-score.json", 30),
            _artifact(".lifecycle/specs/product.spec.json", 200),
        ],
        validation_type="prd",
        intent_triggers=["new-product", "new-feature", "prd-change"],
        max_retries=3,
    ),
    _phase(
        id="phase-5-draft-ued",
        name="AI 协作 UED 设计",
        description="从 Product Spec 推导 Human UED，用户审核页面、流程、状态和反馈",
        order=5,
        auto=False,
        command="draft",
        command_args={"doc_type": "ued", "doc": "Docs/product/UED.md"},
        depends_on=["phase-4-product-spec"],
        blocks=["phase-6-ued-spec"],
        artifacts=[_artifact("Docs/product/UED.md", 400)],
        intent_triggers=["new-product", "new-feature", "prd-change"],
        pause_for="等待用户审核 UED 草案，确认核心界面、流程、状态和错误反馈",
    ),
    _phase(
        id="phase-6-ued-spec",
        name="UED Spec 生成与验证",
        description="从 Product Spec 和 Human UED 生成 UED Spec",
        order=6,
        auto=True,
        command="specs",
        command_args={"action": "generate", "target": "ued"},
        depends_on=["phase-5-draft-ued"],
        blocks=["phase-7-draft-arch"],
        artifacts=[_artifact(".lifecycle/specs/ued.spec.json", 200)],
        intent_triggers=["new-product", "new-feature", "prd-change"],
        max_retries=1,
    ),
    _phase(
        id="phase-7-draft-arch",
        name="AI 协作技术架构设计",
        description="从 Product/UED Specs 推导 Human Architecture Doc 和关键 ADR",
        order=7,
        auto=False,
        command="draft",
        command_args={"doc_type": "arch", "doc": "Docs/tech/ARCH.md"},
        depends_on=["phase-6-ued-spec"],
        blocks=["phase-8-tech-spec"],
        artifacts=[_artifact("Docs/tech/ARCH.md", 800)],
        intent_triggers=["new-product", "new-feature", "prd-change", "arch-change"],
        pause_for="等待用户审核技术架构草案，对 ADR 做决策",
    ),
    _phase(
        id="phase-8-tech-spec",
        name="Tech Spec 生成与验证",
        description="验证架构文档，通过后生成 Tech Spec 和架构快照",
        order=8,
        auto=True,
        command="validate",
        command_args={"doc": "Docs/tech/ARCH.md", "type": "arch"},
        depends_on=["phase-7-draft-arch"],
        blocks=["phase-9-lifecycle-graph"],
        artifacts=[
            _artifact(".lifecycle/snapshots/arch_latest.md", 800),
            _artifact(".lifecycle/steps/arch-score.json", 30),
            _artifact(".lifecycle/specs/tech.spec.json", 200),
        ],
        validation_type="arch",
        intent_triggers=["new-product", "new-feature", "prd-change", "arch-change"],
        max_retries=3,
    ),
    _phase(
        id="phase-9-lifecycle-graph",
        name="Lifecycle Graph / Skimmer",
        description="全量索引 Product、UED、Tech、Test、ADR、Risk 和迭代依赖",
        order=9,
        auto=True,
        command="specs",
        command_args={"action": "generate", "target": "graph"},
        depends_on=["phase-8-tech-spec"],
        blocks=["phase-10-test-spec"],
        artifacts=[_artifact(".lifecycle/specs/lifecycle_graph.json", 200)],
        intent_triggers=["new-product", "new-feature", "prd-change", "arch-change"],
        max_retries=1,
    ),
    _phase(
        id="phase-10-test-spec",
        name="Test Spec 与测试大纲生成",
        description="从 Lifecycle Graph 生成 Test Spec、测试大纲和回归选择依据",
        order=10,
        auto=True,
        command="outline",
        command_args={
            "action": "generate",
            "prd": "Docs/product/PRD.md",
            "arch": "Docs/tech/ARCH.md",
            "output": "Docs/tests/MASTER_OUTLINE.md",
        },
        depends_on=["phase-9-lifecycle-graph"],
        blocks=["phase-11-iterations"],
        artifacts=[
            _artifact("Docs/tests/MASTER_OUTLINE.md", 600),
            _artifact(".lifecycle/test_graph.json", 200),
            _artifact(".lifecycle/specs/test.spec.json", 200),
            _artifact(".lifecycle/specs/lifecycle_graph.json", 200),
        ],
        validation_type="test_outline",
        intent_triggers=["new-product", "new-feature", "prd-change", "arch-change", "test-change"],
        max_retries=2,
    ),
    _phase(
        id="phase-11-iterations",
        name="Velocity 感知迭代规划",
        description="生成迭代计划，设定工时估算和验收边界",
        order=11,
        auto=True,
        command="plan",
        command_args={"prd": "Docs/product/PRD.md", "arch": "Docs/tech/ARCH.md"},
        depends_on=["phase-10-test-spec"],
        blocks=["phase-12-iter-exec"],
        artifacts=[
            _artifact("Docs/iterations/INDEX.md", 200),
            _artifact(".lifecycle/velocity.json", 50),
        ],
        intent_triggers=["new-product", "new-feature", "prd-change", "arch-change", "new-iteration"],
        max_retries=1,
    ),
    _phase(
        id="phase-12-iter-exec",
        name="迭代执行循环",
        description="开发、测试、DoD 检查、门控验证",
        order=12,
        auto=False,
        command="gate",
        command_args={"iteration": "{current_iteration}"},
        execution_mode="pause_then_command",
        depends_on=["phase-11-iterations"],
        artifacts=[],
        intent_triggers=["new-product", "new-iteration", "continue-iter"],
        pause_for="等待用户完成开发任务，运行测试，通过 DoD 检查",
    ),
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

    # Include phases that match the intent OR have wildcard '*' in intent_triggers
    return [p for p in PHASES if intent in p["intent_triggers"] or "*" in p["intent_triggers"]]


def get_ordered_phases() -> List[PhaseDefinition]:
    """Get all phases ordered by execution order."""
    return sorted(PHASES, key=lambda p: p["order"])


def validate_phases() -> List[str]:
    """
    Validate phase definitions for consistency.

    Checks:
    - depends_on references existing phase IDs
    - blocks references existing phase IDs
    - artifact paths are relative
    - No circular dependencies (DFS)
    - depends_on phases have lower order values than current phase

    Returns list of error messages (empty if valid).
    """
    errors = []
    phase_ids = {p["id"] for p in PHASES}
    phase_by_id = {p["id"]: p for p in PHASES}

    for phase in PHASES:
        # Check dependencies exist
        for dep in phase["depends_on"]:
            if dep not in phase_ids:
                errors.append(f"Phase {phase['id']} depends on non-existent phase: {dep}")

        # Check blocks exist
        for block in phase.get("blocks", []):
            if block not in phase_ids:
                errors.append(f"Phase {phase['id']} blocks non-existent phase: {block}")

        # Check artifact paths are relative
        for artifact in phase.get("artifacts", []):
            if artifact.get("path", "").startswith("/"):
                errors.append(
                    f"Phase {phase['id']} artifact path should be relative: {artifact['path']}"
                )

    # Check for circular dependencies using DFS
    def has_cycle(phase_id: str, visited: set, rec_stack: set) -> bool:
        visited.add(phase_id)
        rec_stack.add(phase_id)
        phase = phase_by_id.get(phase_id)
        if phase:
            for dep in phase.get("depends_on", []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True
        rec_stack.discard(phase_id)
        return False

    visited: set = set()
    for phase in PHASES:
        if phase["id"] not in visited:
            if has_cycle(phase["id"], visited, set()):
                errors.append(f"Circular dependency detected involving phase: {phase['id']}")

    # Check that depends_on phases have lower order values
    for phase in PHASES:
        phase_order = phase.get("order", 0)
        for dep_id in phase.get("depends_on", []):
            dep_phase = phase_by_id.get(dep_id)
            if dep_phase and dep_phase.get("order", 0) >= phase_order:
                errors.append(
                    f"Phase {phase['id']} (order={phase_order}) depends on "
                    f"{dep_id} (order={dep_phase['order']}), dependency should have lower order"
                )

    return errors


# Run validation on import
_validation_errors = validate_phases()
if _validation_errors:
    import warnings
    warnings.warn("PHASES validation errors:\n" + "\n".join(f"  - {e}" for e in _validation_errors))
