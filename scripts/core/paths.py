"""
paths.py — 路径常量中心

所有跨模块共用的文件路径和文档类型字符串都在这里定义。
不允许在其他模块里硬编码这些路径，必须从这里 import。
"""

# ---------------------------------------------------------------------------
# 文档路径（相对于项目根目录）
# ---------------------------------------------------------------------------
PRD_PATH = "Docs/product/PRD.md"
UED_PATH = "Docs/product/UED.md"
ARCH_PATH = "Docs/tech/ARCH.md"
TEST_OUTLINE_PATH = "Docs/tests/MASTER_OUTLINE.md"
ITERATIONS_INDEX_PATH = "Docs/iterations/INDEX.md"
ADR_INDEX_PATH = "Docs/adr/INDEX.md"
DOCS_INDEX_PATH = "Docs/INDEX.md"

# ---------------------------------------------------------------------------
# lifecycle 状态文件（相对于项目根目录）
# ---------------------------------------------------------------------------
SOLUTION_JSON = ".lifecycle/solution.json"
CONFIG_JSON = ".lifecycle/config.json"
DOD_JSON = ".lifecycle/dod.json"
VELOCITY_JSON = ".lifecycle/velocity.json"
CHANGE_IMPACT_MD = ".lifecycle/CHANGE_IMPACT.md"
CHECKPOINT_JSON = ".lifecycle/checkpoint.json"

# ---------------------------------------------------------------------------
# snapshot 约定路径（phases.py artifact 的权威来源）
# ---------------------------------------------------------------------------
PRD_SNAPSHOT_LATEST = ".lifecycle/snapshots/prd_latest.md"
ARCH_SNAPSHOT_LATEST = ".lifecycle/snapshots/arch_latest.md"
PRD_SCORE_JSON = ".lifecycle/steps/prd-score.json"
ARCH_SCORE_JSON = ".lifecycle/steps/arch-score.json"

# ---------------------------------------------------------------------------
# 文档类型枚举字符串
# ---------------------------------------------------------------------------
DOC_TYPE_PRD = "prd"
DOC_TYPE_ARCH = "arch"
DOC_TYPE_OUTLINE = "test_outline"

# ---------------------------------------------------------------------------
# snapshot alias（传给 SnapshotManager.take 的 alias 参数）
# ---------------------------------------------------------------------------
SNAPSHOT_ALIAS_PRD = "prd"
SNAPSHOT_ALIAS_ARCH = "arch"

# ---------------------------------------------------------------------------
# 额外状态文件（phases.py artifact 声明）
# ---------------------------------------------------------------------------
ARCH_INTERVIEW_JSON = ".lifecycle/arch_interview.json"
PROJECT_TYPE_JSON = ".lifecycle/project_type.json"
TEST_GRAPH_JSON = ".lifecycle/test_graph.json"
SPECS_DIR = ".lifecycle/specs"
PRODUCT_SPEC_JSON = ".lifecycle/specs/product.spec.json"
UED_SPEC_JSON = ".lifecycle/specs/ued.spec.json"
TECH_SPEC_JSON = ".lifecycle/specs/tech.spec.json"
TEST_SPEC_JSON = ".lifecycle/specs/test.spec.json"
LIFECYCLE_GRAPH_JSON = ".lifecycle/specs/lifecycle_graph.json"
IMPACT_JSON = ".lifecycle/specs/impact.json"
