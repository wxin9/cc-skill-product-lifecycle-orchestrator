"""
TypedDict schemas — shared vocabulary between all layers.
All data serialized to/from JSON uses these definitions.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationIssue(dict):
    """{'field': str, 'message': str, 'severity': 'error'|'warning'}"""

class ValidationResult(dict):
    """
    Result of validating a PRD or ARCH document.
    {
      'score': int,           # 0-100
      'passed': bool,         # score >= threshold (default 70)
      'issues': [...],        # List[ValidationIssue]
      'suggestions': [...],   # List[str]
      'doc_type': str,        # 'prd' | 'arch'
      'doc_path': str,
    }
    """


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

class FeatureChange(dict):
    """
    {
      'change_type': 'added'|'modified'|'deleted'|'adjusted',
      'feature_id': str,
      'feature_name': str,
      'old_description': Optional[str],
      'new_description': Optional[str],
      'affects_data_model': bool,
      'affects_api': bool,
    }
    """

class ChangeReport(dict):
    """
    Output of detect_prd_diff().
    {
      'timestamp': str,          # ISO 8601
      'old_version': str,
      'new_version': str,
      'changes': List[FeatureChange],
      'summary': str,
    }
    """

class ImpactItem(dict):
    """
    {
      'type': 'test'|'iteration'|'arch'|'task',
      'id': str,
      'description': str,
      'action_required': str,   # 'update'|'regenerate'|'deprecate'|'review'
    }
    """

class ImpactReport(dict):
    """
    Output of cascade_impact().
    {
      'change_report': ChangeReport,
      'affected_tests': List[str],       # TST-* IDs
      'affected_iterations': List[int],  # iteration numbers
      'needs_arch_update': bool,
      'impact_items': List[ImpactItem],
      'summary_md': str,                 # human-readable markdown
    }
    """


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class Task(dict):
    """
    {
      'id': str,              # PRD-001, ARCH-001, ITR-1.DEV-001, etc.
      'type': str,            # 'prd'|'arch'|'check'|'dev'|'test'
      'title': str,
      'description': str,
      'status': str,          # 'todo'|'in_progress'|'done'|'blocked'
      'iteration': Optional[int],
      'test_case_ref': Optional[str],  # TST-F01-S01
      'created_at': str,
      'updated_at': str,
      'blocked_by': List[str],  # task IDs
    }
    """

class GateResult(dict):
    """
    {
      'iteration': int,
      'passed': bool,
      'total_tasks': int,
      'done_tasks': int,
      'blocking_tasks': List[Task],  # not-done tasks
    }
    """


# ---------------------------------------------------------------------------
# Test outline
# ---------------------------------------------------------------------------

class TestScenario(dict):
    """
    {
      'id': str,              # S01, S02 …
      'description': str,
      'steps': List[str],
      'expected': str,
      'e2e': bool,            # True = full stack from UI/API to DB
      'layer_entry': str,     # 'ui'|'api'|'cli'  — where test starts
    }
    """

class OutlineEntry(dict):
    """
    One functional feature with its test scenarios.
    {
      'feature_id': str,      # F01, F02 …
      'feature_name': str,
      'prd_ref': str,         # REQ-001
      'scenarios': List[TestScenario],
    }
    """

class TestCase(dict):
    """
    A concrete, executable test case.
    {
      'id': str,              # TST-F01-S01
      'title': str,
      'feature_id': str,
      'scenario_id': str,
      'preconditions': List[str],
      'steps': List[str],
      'expected': str,
      'e2e': bool,
      'layer_entry': str,
      'iteration_ref': Optional[int],
      'status': str,          # 'active'|'deprecated'|'pending'
      'created_at': str,
    }
    """

class MasterOutline(dict):
    """
    {
      'version': str,
      'generated_at': str,
      'prd_version': str,
      'arch_version': str,
      'entries': List[OutlineEntry],
      'total_scenarios': int,
    }
    """


# ---------------------------------------------------------------------------
# Iterations
# ---------------------------------------------------------------------------

class E2ECriteria(dict):
    """
    {
      'description': str,       # "用户能够做什么" phrasing
      'entry_point': str,       # UI page / API endpoint / CLI command
      'data_flow': str,         # input → processing → storage → response
      'test_case_refs': List[str],
    }
    """

class Iteration(dict):
    """
    {
      'number': int,
      'name': str,
      'goal': str,              # "用户能够…" — user-centric description
      'feature_ids': List[str],
      'e2e_criteria': List[E2ECriteria],
      'task_ids': List[str],
      'dependencies': List[int],  # iteration numbers this depends on
      'status': str,              # 'planned'|'in_progress'|'done'
    }
    """


# ---------------------------------------------------------------------------
# Project scanner
# ---------------------------------------------------------------------------

class DetectedDoc(dict):
    """
    {
      'path': str,
      'doc_type': str,    # 'prd'|'arch'|'requirements'|'design'|'unknown'
      'confidence': float,
      'suggested_target': str,  # where it should live in Docs/
    }
    """

class ProjectScan(dict):
    """
    {
      'root_path': str,
      'scanned_at': str,
      'total_files': int,
      'detected_docs': List[DetectedDoc],
      'inferred_tech_stack': List[str],
      'has_docs_folder': bool,
      'has_lifecycle_folder': bool,
      'conflicts': List[str],
    }
    """

class MigrationPlan(dict):
    """
    {
      'moves': List[{'from': str, 'to': str}],
      'creates': List[str],    # directories to create
      'conflicts': List[str],  # files that need manual resolution
    }
    """


# ---------------------------------------------------------------------------
# Lifecycle state
# ---------------------------------------------------------------------------

class LifecycleConfig(dict):
    """
    Stored in .lifecycle/config.json
    {
      'project_name': str,
      'created_at': str,
      'current_iteration': int,
      'prd_version': str,
      'arch_version': str,
      'outline_version': str,
      'total_iterations': int,
    }
    """

class PauseState(dict):
    """
    Stored in .lifecycle/pause_state.json
    {
      'paused_at': str,
      'current_phase': str,
      'current_iteration': Optional[int],
      'reason': str,
      'pending_cascade_items': List[str],
      'incomplete_task_ids': List[str],
    }
    """
