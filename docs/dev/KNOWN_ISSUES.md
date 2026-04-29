# Known Issues

This document lists known design limitations that are NOT bugs but deliberate constraints or placeholders for future work.

---

## 1. Web Search Stub

**Location**: `scripts/core/solution_analyzer.py` → `_web_search()`

**Behavior**: Always returns `[]`. Industry solutions are generic templates, not real web search results.

**Reason**: Web search would require API key injection at runtime (e.g., SerpAPI, Tavily). This is a local-first skill with no external API dependencies.

**Impact**: Phase 1 (solution analyzer) provides reasonable default solutions but cannot fetch real industry examples.

**Future**: Add optional web search integration with user-provided API keys.

---

## 2. eval() in ConditionEvaluator

**Location**: `scripts/core/condition_evaluator.py`

**Behavior**: Uses Python `eval()` with restricted namespace for condition evaluation.

**Security Boundary**: Regex-based sanitization, not AST-based.

**Risk Assessment**: Low. Skill runs locally with user's permissions. No remote execution or untrusted input.

**Acknowledged Constraint**: AST-based evaluation would be safer but more complex. Current implementation is acceptable for local execution. Re-confirmed acceptable in Round 9 audit — risk is unchanged and contained by local-only execution scope.

**Example**:
```python
# condition: "project_type == 'web'"
# Evaluated as: eval("project_type == 'web'", {"project_type": "web"})
```

---

## 3. Parallel Execution is Experimental

**Location**: `scripts/core/parallel_executor.py`, `orchestrator.py` → `_execute_parallel_groups()`

**Status**: Implemented for v2.2 but **all current phases execute sequentially**.

**Test Coverage**: Minimal. ParallelExecutor has basic unit tests but no integration tests.

**Enabling**: `ORCHESTRATOR_PARALLEL=1 ./orchestrator.sh`

**Warning**: Do not use in production. Phase dependencies may not be correctly resolved in parallel mode.

**Future**: Add comprehensive tests, verify dependency resolution, enable for specific phases.

---

## 4. Review Rule Always Warns

**Location**: `scripts/core/dod_checker.py` → review rule type

**Behavior**: Always returns `"warn"` status because there's no command to create `review_records.json`.

**Reason**: Placeholder for future Sprint Review functionality.

**Impact**: DoD checks with review rules will always show warnings, not failures.

**Example**:
```json
{
  "type": "review",
  "description": "Sprint Review completed",
  "status": "warn",  // Always warn, never pass/fail
  "message": "review_records.json not found"
}
```

**Future**: Implement Sprint Review material generation and validation.

---

## 5. Blocks Enforcement is Execution-Path-Only

**Location**: `orchestrator.py` → `_build_execution_path()` vs `_check_dependencies()`

**Behavior**:
- `blocks` field is checked in `_build_execution_path()` ✅
- `blocks` field is NOT checked in `_check_dependencies()` ❌

**Impact**: In parallel execution mode, a blocked phase could pass the dependency check even if its blocker hasn't completed.

**Example**:
```python
# phase-0-intent blocks: ["phase-2-init"]
# In parallel mode:
#   - phase-0-intent and phase-2-init could both pass _check_dependencies()
#   - phase-2-init might execute before phase-0-intent completes
```

**Acceptable Because**: Parallel mode is experimental and not used in production.

**Future**: Add blocks check to `_check_dependencies()` when enabling parallel execution.

---

## 6. Solution Analyzer Scans Full Project

**Location**: `scripts/core/solution_analyzer.py` → `_detect_language()`, `_detect_patterns()`

**Behavior**: Uses `rglob("*")` which includes `.git/`, `node_modules/`, `__pycache__/`, etc.

**Impact**: Can be slow on large projects (10k+ files).

**Reason**: Simplicity. Filtering specific directories would require configuration.

**Workaround**: Run on smaller projects or accept slower analysis.

**Future**: Add configurable exclude patterns (e.g., `.lifecycle/ignore_patterns.json`).

---

## 7. Rollback Only Snapshots Docs/ and .lifecycle/

**Location**: `scripts/core/checkpoint_manager.py` → rollback functionality

**Behavior**: Rollback snapshots include:
- `Docs/` directory
- `.lifecycle/` directory

**NOT Included**:
- Source code files (`.py`, `.js`, etc.)
- Configuration files (`package.json`, `requirements.txt`)
- Any files outside `Docs/` and `.lifecycle/`

**Impact**: Rolling back restores documentation state but not code changes.

**Reason**: Source code is version-controlled by git. Documentation is the skill's domain.

**Example**:
```bash
# Before rollback:
#   - Docs/product/PRD.md (modified)
#   - src/app.py (modified)
# After rollback:
#   - Docs/product/PRD.md (restored)
#   - src/app.py (still modified)
```

**Recommendation**: Use git for code rollback, skill rollback for documentation.

---

## 8. Intent Resolution is Keyword-Based

**Location**: `scripts/core/intent_resolver.py`

**Behavior**: Pattern matching on keywords, not semantic understanding.

**Limitations**:
- Ambiguous input may resolve incorrectly
- Non-Chinese input has lower accuracy
- Context not considered (e.g., "add feature" could be new-feature or prd-change)

**Example**:
```python
# "我想添加一个新功能" → new-feature (correct)
# "添加功能到现有系统" → new-feature (could be prd-change)
# "I want to add a feature" → new-product (fallback, non-Chinese)
```

**Future**: Integrate with Claude for semantic intent classification.

---

## 9. Phase Timeout Hints are Suggestions

**Location**: `phases.py` → `timeout_hint` field

**Behavior**: `timeout_hint` is a user-facing suggestion, not enforced.

**Impact**: Phases can take arbitrarily long; no automatic timeout.

**Reason**: Timeout enforcement would require async execution with timeout handling.

**Example**:
```python
{
    "pause_for": "等待用户审核 PRD 草案",
    "timeout_hint": "建议在 24h 内完成"  # Not enforced
}
```

**Future**: Add optional timeout enforcement with notification.

---

## 10. No Concurrent Execution Protection

**Location**: `orchestrator.py`

**Behavior**: Multiple orchestrator instances can run simultaneously on the same project.

**Risk**: Checkpoint corruption if two instances write simultaneously.

**Mitigation**: v2.2 added thread-safe checkpoint with RLock, but only within a single process.

**Recommendation**: Don't run multiple orchestrator instances on the same project.

**Future**: Add file-based lock (e.g., `.lifecycle/lock`) for cross-process protection.

---

## 11. _cmd_draft Returns Success Without Creating Files

**Location**: `scripts/core/command_executor.py` → `_cmd_draft()`

**Behavior**: The draft command returns `success: True` but doesn't actually create PRD.md or ARCH.md files. It returns a prompt template for the AI to use during the pause phase.

**Reason**: This is by design — draft phases activate AI collaboration mode. The actual document is created by the AI during the pause period, not by the command itself.

**Impact**: Users expecting `_cmd_draft` to produce a file will see `success: True` with no file. This can be confusing.

**Workaround**: After draft command returns, the orchestrator pauses for AI to create the document. The document is then validated in the next phase.

**Future**: Consider returning `success: True, paused: True` to clarify the document isn't created yet.

---

## 12. Cancel Does Not Delete Created Files

**Location**: `scripts/__main__.py` → `cmd_orchestrator_cancel()`

**Behavior**: Cancel resets checkpoint state (current_phase=None, completed_phases=[], phase_data={}) but does not delete any files that were created during the workflow (Docs/, .lifecycle/ artifacts).

**Reason**: File deletion is destructive and potentially irreversible. Users may want to keep partial work.

**Impact**: After cancel, running a new workflow will see existing files and may skip phases that created them (idempotent behavior).

**Workaround**: Manually delete Docs/ and .lifecycle/ if a clean start is needed.

**Future**: Add `--clean` flag to cancel that removes all created files.

---

## 13. artifact_validator and dod_checker Use Different Task Data Sources

**Location**: `scripts/core/artifact_validator.py`, `scripts/core/dod_checker.py`

**Behavior**:
- dod_checker reads `task_status.json` (created by gate defaults)
- artifact_validator reads `tasks.json` (created by task_registry)
- Round 10 added fallback: artifact_validator now tries `task_status.json` if `tasks.json` is missing

**Impact**: Cross-validation may use different data depending on which file exists. If both exist, they may be out of sync.

**Future**: Unify on a single task data source, or add sync mechanism between the two files.
