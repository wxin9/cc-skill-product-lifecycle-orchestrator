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
)

__all__ = [
    "ValidationResult", "ChangeReport", "ImpactReport",
    "Task", "GateResult",
    "OutlineEntry", "TestCase", "MasterOutline",
    "Iteration", "ProjectScan", "PauseState", "LifecycleConfig",
]
