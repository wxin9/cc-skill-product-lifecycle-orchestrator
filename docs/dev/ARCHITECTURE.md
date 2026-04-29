# Architecture Overview

## Summary

Product Lifecycle Orchestrator is a Claude Code skill that orchestrates AI-collaborative product development through a phase-based workflow engine with checkpoint persistence, intent-driven execution paths, and adaptive test generation.

## Core Execution Model

```
Intent → Phase Selection → Execution Path → Checkpoint → Resume Cycle
```

1. **Intent Recognition**: User input mapped to intent (new-product, prd-change, etc.)
2. **Phase Selection**: Intent triggers subset of phases via `intent_triggers` field
3. **Execution Path**: DAG traversal respecting `depends_on` and `blocks` constraints
4. **Checkpoint Persistence**: State saved after each phase completion
5. **Resume Cycle**: Interrupted workflows resume from checkpoint

## Module Map

| File | Role |
|------|------|
| `scripts/core/phases.py` | Phase registry with 12 phases, dependency graph, validation |
| `scripts/core/orchestrator.py` | Main execution engine, state machine, notification system |
| `scripts/core/checkpoint_manager.py` | Checkpoint persistence with in-memory cache, migration |
| `scripts/core/command_executor.py` | Direct function calls (replaces subprocess-based v2.0) |
| `scripts/core/parallel_executor.py` | Experimental v2.2 parallel execution groups |
| `scripts/core/intent_resolver.py` | Auto-resolve intent from user input text |
| `scripts/core/solution_analyzer.py` | Phase 1: analyze requirements, generate solution options |
| `scripts/core/dod_checker.py` | Definition-of-Done validation rules |
| `scripts/core/condition_evaluator.py` | Conditional branching for v2.2 phase execution |
| `scripts/core/paths.py` | Centralized path constants, replaces hardcoded strings |

## Data Flow

```
User Input (CLI)
    │
    ▼
orchestrator.sh → __main__.py → Orchestrator.run(intent, user_input)
    │
    ▼
Intent Resolution (auto or explicit)
    │
    ▼
Phase Selection (get_phases_by_intent)
    │
    ▼
Execution Path Building (_build_execution_path)
    │   ├─ Filter by intent
    │   ├─ Sort by order
    │   ├─ Skip completed phases
    │   └─ Apply blocks enforcement
    │
    ▼
Phase Execution Loop
    │   ├─ Check dependencies
    │   ├─ Execute command (via CommandExecutor)
    │   ├─ Validate artifacts
    │   ├─ Record completion
    │   └─ Pause if needed (notification.json)
    │
    ▼
Checkpoint Update (CheckpointManager.save)
    │
    ▼
Next Phase or Exit
```

## Key Data Structures

### Checkpoint Format

```python
{
    "version": "2.0",
    "project_name": "xxx",
    "created_at": "2026-04-16T...",
    "updated_at": "2026-04-16T...",
    "current_phase": "phase-3-draft-prd",
    "status": "in_progress" | "paused" | "completed" | "failed",
    "completed_phases": ["phase-0-intent", "phase-2-init"],
    "phase_data": {
        "phase-3-draft-prd": {
            "started_at": "...",
            "completed_at": "...",
            "score": 85,
            "artifacts": ["Docs/product/PRD.md"]
        }
    },
    "intent": "new-product",
    "user_input": "我想做一个...",
    "metadata": {}
}
```

### Notification Format

```python
{
    "type": "pause_for_user" | "validation_failed" | "dod_failed" | "error",
    "phase_id": "phase-3-draft-prd",
    "phase_name": "AI 协作 PRD 起草",
    "message": "等待用户审核 PRD 草案",
    "detail": "补充 [❓待确认] 标注处",
    "timestamp": "2026-04-16T...",
    "actions": ["review PRD", "confirm sections"],
    # Optional enrichment for validation failures
    "score": 65,
    "threshold": 80,
    "issues": [...],
    "suggestions": [...]
}
```

### PhaseDefinition Fields

```python
{
    "id": "phase-3-draft-prd",
    "name": "AI 协作 PRD 起草",
    "description": "...",
    "order": 3,
    "auto": False,                    # Auto-execute or pause for user
    "command": "draft",               # Command to execute
    "command_args": {...},            # Command arguments
    "depends_on": ["phase-2-init"],   # Must complete before this phase
    "blocks": ["phase-4-product-spec"], # Prevents these phases from running
    "artifacts": [...],               # Expected output files
    "validation_type": "prd",         # Validation type (prd, arch, test_outline)
    "on_failure": "pause",            # pause | retry | skip
    "max_retries": 0,
    "pause_for": "等待用户审核...",   # User interaction prompt
    "timeout_hint": "建议在 24h 内完成",
    "intent_triggers": ["new-product", "new-feature", "prd-change"],
    "condition": None,                # v2.2: Conditional branching
    "branches": None                  # v2.2: Branch mapping
}
```

## Entry Points

```
orchestrator.sh (shell wrapper)
    │
    ▼
scripts/core/__main__.py
    │
    ▼
Orchestrator(project_root).run(intent, from_phase, user_input)
```

**CLI Usage**:
```bash
./orchestrator.sh --intent new-product --user-input "我想做一个..."
./orchestrator.sh --intent resume
./orchestrator.sh --intent status
```

## Execution Modes

### Sequential (Default)

Phases execute one at a time in order, respecting `depends_on` constraints.

```
phase-0 → phase-1 → phase-2 → ... → phase-N
```

### Parallel (v2.2 Experimental)

Phases grouped by dependency level, executed in parallel within groups.

```
Group 0: [phase-0-intent]
Group 1: [phase-1-analyze-solution]  # Can run in parallel if no inter-dependencies
Group 2: [phase-2-init]
...
```

Enabled via: `ORCHESTRATOR_PARALLEL=1 ./orchestrator.sh`

**Warning**: Parallel execution has minimal test coverage. Use with caution.

## State Machine

```
         ┌─────────────┐
         │ initialized │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │ in_progress │◄────────┐
         └──────┬──────┘         │
                │                │
        ┌───────┴───────┐        │
        │               │        │
        ▼               ▼        │
  ┌──────────┐   ┌──────────┐    │
  │  paused  │   │ completed│    │
  └────┬─────┘   └──────────┘    │
       │                         │
       │ (resume)                 │
       └─────────────────────────┘
        │
        ▼
  ┌──────────┐
  │  failed  │
  └──────────┘
```

**Transitions**:
- `initialized → in_progress`: First phase starts
- `in_progress → paused`: Phase requires user interaction
- `paused → in_progress`: Resume from checkpoint
- `in_progress → completed`: All phases done
- `in_progress → failed`: Unrecoverable error

## Blocks Enforcement Mechanism (Round 6)

**Purpose**: Prevent phases from executing before their blocker completes.

**Implementation** (`_build_execution_path`):
1. Build `blocks_map`: `{blocked_phase_id: [blocker_phase_ids]}`
2. For each phase in execution path:
   - Check if any blocker is incomplete
   - If blocker incomplete → skip phase
   - If blocker complete → include phase

**Example**:
```python
# phase-0-intent blocks: ["phase-2-init", "phase-1-impact-report"]
# Until phase-0-intent completes, phase-2-init and phase-1-impact-report are excluded
```

**Edge Case**: Paused phases treated as complete (will complete during current run).

**Limitation**: Only enforced in execution path, NOT in `_check_dependencies()`. See KNOWN_ISSUES.md.

## Intent Auto-Resolution Mechanism (Round 5)

**Purpose**: Automatically infer intent from user input text.

**Implementation** (`intent_resolver.py`):
1. Pattern matching on keywords:
   - "从零开始", "新项目" → `new-product`
   - "新功能", "添加功能" → `new-feature`
   - "PRD 变更", "修改需求" → `prd-change`
   - "bug", "修复" → `bug-fix`
   - etc.
2. Fallback to `new-product` if no match

**Usage**:
```bash
./orchestrator.sh --intent auto --user-input "我想从零开始做一个博客系统"
# → Resolves to: new-product
```

**Trigger**: Intent `auto` + non-empty `user_input`.

## Performance Optimizations (v2.1)

1. **In-memory checkpoint cache**: Reduces disk I/O
2. **Delayed writing**: Batch updates, single disk write
3. **Direct function calls**: Replaces subprocess overhead
4. **Thread-safe checkpoint**: RLock for concurrent access
