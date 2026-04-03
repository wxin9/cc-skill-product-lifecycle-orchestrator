"""Core logic layer — no external dependencies."""
from .doc_validator import validate_document
from .change_detector import detect_prd_diff, cascade_impact
from .task_registry import TaskRegistry
from .test_outline import generate_outline, trace_impact, generate_iteration_tests
from .iteration_planner import plan_iterations, validate_e2e_testable

__all__ = [
    "validate_document",
    "detect_prd_diff",
    "cascade_impact",
    "TaskRegistry",
    "generate_outline",
    "trace_impact",
    "generate_iteration_tests",
    "plan_iterations",
    "validate_e2e_testable",
]
