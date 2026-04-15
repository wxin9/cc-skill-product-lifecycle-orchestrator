"""Data layer — TypedDict schemas and serialization."""
from .schemas import (
    ValidationResult,
    ChangeReport,
    ImpactReport,
    Task,
    GateResult,
    OutlineEntry,
    TestCase,
    MasterOutline,
    Iteration,
    ProjectScan,
    PauseState,
    LifecycleConfig,
    DependencyDecl,
    TestNode,
    DimensionConfig,
    TestGraphSchema,
)

__all__ = [
    "ValidationResult", "ChangeReport", "ImpactReport",
    "Task", "GateResult",
    "OutlineEntry", "TestCase", "MasterOutline",
    "Iteration", "ProjectScan", "PauseState", "LifecycleConfig",
    "DependencyDecl", "TestNode", "DimensionConfig", "TestGraphSchema",
]
