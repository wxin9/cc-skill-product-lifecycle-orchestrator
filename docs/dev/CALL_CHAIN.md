# Product Lifecycle Orchestrator 完整调用链文档

本文档是 Product Lifecycle Orchestrator skill 的"source of truth"，覆盖从 shell 入口到每个命令最终输出的完整执行路径。

---

## 1. Shell 入口

```bash
# orchestrator shell script
if ! command -v python3 &> /dev/null; then echo "Error: python3 is required"; exit 1; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
exec python3 -m scripts orchestrator "$@"
```

**Exit codes:**
- `0` = success
- `1` = paused (等待用户输入)
- `2` = failed (需要人工干预)

---

## 2. CLI 入口 — `__main__.py`

### `main()` → argparse with subcommands

**Subcommands:** `run`, `resume`, `status`, `cancel`, `rollback`

**Dynamic `_VALID_INTENTS`** from `phases.py`:
```python
from scripts.core.phases import PHASES
_VALID_INTENTS = set()
for phase in PHASES:
    for intent in phase.get("intent_triggers", []):
        if intent != "*":
            _VALID_INTENTS.add(intent)
_VALID_INTENTS.update(["auto", "resume"])
```

---

### `cmd_orchestrator_run(args)` → int

**Execution path:**
1. `_find_project_root()` — 查找 `.lifecycle/` 目录
2. `Orchestrator(root)` — 初始化编排引擎
3. `orch.run(intent=args.intent, from_phase=args.from_phase, user_input=args.user_input)`
4. **Returns:** `0` / `1` / `2`

---

### `cmd_orchestrator_resume(args)` → int

**Execution path:**
1. `_find_project_root()`
2. `Orchestrator(root)`
3. `orch.run(intent="resume", from_phase=args.from_phase, user_input=args.user_input)`
4. **Returns:** `0` / `1` / `2`

---

### `cmd_orchestrator_cancel(args)` → int

**Execution path:**
1. `_find_project_root()`
2. `CheckpointManager(root)`
3. `checkpoint_mgr.load()`
4. **Updates checkpoint:**
   - `status = "cancelled"`
   - `current_phase = None`
   - `completed_phases = []`
   - `phase_data = {}`
5. `checkpoint_mgr.save(checkpoint, immediate=True)`
6. `checkpoint_mgr.clear_notification()`
7. **Returns:** `0`

---

### `cmd_orchestrator_status(args)` → int

**Execution path:**
1. `_find_project_root()`
2. Check if `.lifecycle/` exists → if not, return `1`
3. `CheckpointManager(root)`
4. `checkpoint_mgr.load()`
5. **Prints:**
   - Project name
   - Intent
   - Status
   - Current phase
   - Completed phases
   - Active notification (if exists)
6. **Returns:** `0`

---

### `cmd_orchestrator_rollback(args)` → int

**Execution path:**
1. `_find_project_root()`
2. `Orchestrator(root)`
3. **If `--list`:**
   - `orch.list_rollback_points()`
   - Print rollback points
   - Return `0`
4. **If `--rollback-point-id <id>`:**
   - `orch.rollback_to(rollback_id)`
   - Return `0` on success, `1` on failure

---

## 3. 编排引擎 — `orchestrator.py`

### `run(intent, from_phase=None, user_input="")` → int

**Execution path:**

1. **Auto-resolve intent** (if `intent == "auto"`):
   ```python
   from scripts.core.intent_resolver import IntentResolver
   resolved_intents, explanation = IntentResolver.resolve(user_input)
   intent = resolved_intents[0] if resolved_intents else "new-product"
   ```

2. **Load checkpoint:**
   ```python
   checkpoint = self.checkpoint_mgr.load()
   ```

3. **Update intent/user_input** (if not "resume"/"status"):
   ```python
   checkpoint["intent"] = intent
   checkpoint["user_input"] = user_input
   self.checkpoint_mgr.save(checkpoint)
   ```

4. **Initialize workflow** (if `status == "initialized"`):
   ```python
   self.checkpoint_mgr.init(project_name, intent, user_input)
   ```

5. **Mark phase-0-intent as completed** (auto-resolved from `--intent`):
   ```python
   self.checkpoint_mgr.record_phase_complete("phase-0-intent", {...})
   ```

6. **Determine starting phase:**
   - If `from_phase` provided → use it
   - Else if `checkpoint["current_phase"]` exists → use it
   - Else → `_resolve_entry_point(intent, user_input)`

7. **Build execution path:**
   - If `ORCHESTRATOR_PARALLEL=1` → `_build_parallel_execution_path()`
   - Else → `_build_execution_path()`

8. **Execute phases:**
   - If parallel → `_execute_parallel_groups()`
   - Else → `_execute_sequential()`

---

### `_build_execution_path(start_phase_id, intent)` → List[str]

**Execution path:**

1. **Get relevant phases:**
   ```python
   relevant_phases = get_phases_by_intent(intent)
   ```

2. **Sort by order:**
   ```python
   relevant_phases = sorted(relevant_phases, key=lambda p: p["order"])
   ```

3. **Filter completed phases:**
   - Change intents (`prd-change`, `code-change`, etc.) → include all phases
   - Normal intents → skip completed phases
   - Paused phase → always include

4. **Apply blocks enforcement:**
   - Build `blocks_map`: `{blocked_phase_id: [blocker_phase_ids]}`
   - Skip phases whose blockers are incomplete

5. **Returns:** `["phase-1-analyze-solution", "phase-2-init", ...]`

---

### `_execute_sequential(execution_path, checkpoint)` → int

**Execution path:**

```python
for phase_id in execution_path:
    phase = get_phase_by_id(phase_id)
    
    # 1. Check dependencies
    if not self._check_dependencies(phase, relevant_phase_ids=set(execution_path)):
        return self._fail(...)
    
    # 2. Record phase start
    self.checkpoint_mgr.record_phase_start(phase_id)
    
    # 3. Create rollback point
    self.checkpoint_mgr.create_rollback_point(phase_id, f"Before {phase['name']}")
    
    # 4. Execute phase
    result = self._execute_phase(phase, checkpoint, skip_pause=is_resuming)
    
    # 5. Handle result
    if result["status"] == "paused":
        self.checkpoint_mgr.record_phase_paused(phase_id, result.get("reason"))
        self._notify_pause(phase, result.get("reason"))
        return 1
    
    elif result["status"] == "failed":
        self.checkpoint_mgr.record_phase_failed(phase_id, result.get("error"))
        self._notify_failure(phase, result.get("error"), result.get("data"))
        return 2
    
    # 6. Phase completed
    self.checkpoint_mgr.record_phase_complete(phase_id, result.get("data"))
    
    # 7. Increment iteration counter (if phase-12-iter-exec)
    if phase_id == "phase-12-iter-exec":
        meta["current_iteration"] = meta.get("current_iteration", 1) + 1
```

**Final:**
```python
checkpoint["status"] = "completed"
self.checkpoint_mgr.save(checkpoint, immediate=True)
self.checkpoint_mgr.clear_notification()
return 0
```

---

### `_execute_phase(phase, checkpoint, skip_pause=False)` → dict

**Execution order:**

1. **Evaluate condition** (if `phase["condition"]` exists):
   ```python
   from scripts.core.condition_evaluator import evaluate_condition
   if not evaluate_condition(phase["condition"], checkpoint):
       return {"status": "completed", "data": {"skipped": True}}
   ```

2. **Execute command** (if `phase["command"]` exists):
   - Prepare `cmd_args` from `phase["command_args"]`
   - Replace placeholders: `{project_name}`, `{user_description}`, `{intent}`, `{current_iteration}`, `{change_type}`
   - Call `self.command_executor.execute(phase["command"], cmd_args)`
   - If failed → return `{"status": "failed", "error": ...}`

3. **Check interaction pause** (if `not phase["auto"]` and `phase["pause_for"]` and `not skip_pause`):
   ```python
   return {"status": "paused", "reason": phase["pause_for"]}
   ```

4. **Artifact validation** (if `phase["artifacts"]` exists):
   - Check file existence
   - Check file size ≥ `min_bytes`
   - If failed → return `{"status": "failed", "error": ...}`

5. **Document validation** (if `phase["validation_type"]` exists):
   ```python
   from scripts.core.doc_validator import validate_document
   result = validate_document(str(doc_path), doc_type)
   ```

6. **Returns:** `{"status": "completed", "error": None, "data": None}`

---

### `_check_dependencies(phase, relevant_phase_ids=None)` → bool

**Execution path:**

```python
for dep_id in phase["depends_on"]:
    # Skip deps outside current execution path (change intent scenario)
    if relevant_phase_ids and dep_id not in relevant_phase_ids:
        continue
    if not self.checkpoint_mgr.is_phase_completed(dep_id):
        return False
return True
```

---

### `_resolve_command_args(phase, checkpoint)` → dict

**Placeholder replacement:**

| Placeholder | Replacement |
|------------|-------------|
| `{project_name}` | `checkpoint.get("project_name", self.root.name)` |
| `{user_description}` | `checkpoint.get("user_input", "")` |
| `{intent}` | `checkpoint.get("intent", "new-product")` |
| `{current_iteration}` | `str(checkpoint.get("metadata", {}).get("current_iteration", 1))` |
| `{change_type}` | `checkpoint.get("intent", "prd")` |

---

## 4. Phase 定义 — `phases.py`

### All 12 Phases

| ID | Name | Order | Auto | Command | Intent Triggers |
|----|------|-------|------|---------|-----------------|
| `phase-0-intent` | 意图识别 | 0 | ✓ | None | `*` |
| `phase-1-analyze-solution` | 实现方案分析 | 1 | ✗ | `analyze_solution` | `new-product`, `from-scratch`, `new-feature` |
| `phase-2-init` | 项目初始化 | 2 | ✓ | `init` | `new-product`, `from-scratch` |
| `phase-3-draft-prd` | AI 协作 PRD 起草 | 3 | ✗ | `draft` | `new-product`, `new-feature`, `prd-change` |
| `phase-4-product-spec` | PRD 验证 + 自动快照 | 4 | ✓ | `validate` | `new-product`, `new-feature`, `prd-change` |
| `phase-5-draft-ued` | 架构访谈 + 项目类型识别 | 5 | ✗ | None | `new-product`, `arch-change` |
| `phase-7-draft-arch` | AI 协作架构设计 | 6 | ✗ | `draft` | `new-product`, `arch-change` |
| `phase-8-tech-spec` | 架构验证 + ADR 注册 + 快照 | 7 | ✓ | `validate` | `new-product`, `arch-change` |
| `phase-10-test-spec` | 自适应测试大纲生成 | 8 | ✓ | `outline` | `new-product`, `test-change`, `prd-change` |
| `phase-11-iterations` | Velocity 感知迭代规划 | 9 | ✓ | `plan` | `new-product`, `new-iteration`, `prd-change` |
| `phase-12-iter-exec` | 迭代执行循环 | 10 | ✗ | `gate` | `new-product`, `new-iteration`, `continue-iter` |
| `phase-1-impact-report` | 变更处理 | 11 | ✓ | `change` | `prd-change`, `code-change`, `test-failure`, `bug-fix`, `gap` |

---

### Helper Functions

#### `get_phase_by_id(phase_id)` → Optional[PhaseDefinition]

```python
for phase in PHASES:
    if phase["id"] == phase_id:
        return phase
return None
```

#### `get_phases_by_intent(intent)` → List[PhaseDefinition]

```python
if intent == "resume":
    return PHASES
return [p for p in PHASES if intent in p["intent_triggers"] or "*" in p["intent_triggers"]]
```

---

## 5. 命令实现 — `command_executor.py`

### `execute(command, args)` → Dict[str, Any]

**Returns:**
```python
{
    "success": bool,
    "message": str,
    "data": dict | None,
    "error": str | None
}
```

**Routing:**
```python
handler_name = f"_cmd_{command}"
handler = getattr(self, handler_name, None)
return handler(args)
```

---

### `_cmd_init(args)` → dict

**Execution path:**

1. **Create directories:**
   - `Docs/`
   - `.lifecycle/`
   - `Docs/adr/`

2. **Create `Docs/INDEX.md`:**
   ```markdown
   # {project_name} - Documentation Index
   
   ## Product Documents
   - **PRD**: [product/PRD.md](product/PRD.md)
   - **Architecture**: [tech/ARCH.md](tech/ARCH.md)
   ...
   ```

3. **Create `.lifecycle/config.json`:**
   ```json
   {
     "project_name": "...",
     "version": "2.3",
     "created_at": "...",
     "project_type": "unknown"
   }
   ```

4. **Create `.lifecycle/dod.json`:**
   ```json
   {
     "rules": [
       {"type": "command", "description": "All tests passing", "cmd": "python -m pytest tests/ -q", "required": true},
       {"type": "coverage", "description": "Code coverage >= 70%", "cmd": "...", "threshold": 70, "required": false},
       {"type": "review", "description": "Code review completed (manual)", "manual": true, "required": false}
     ]
   }
   ```

5. **Create `Docs/adr/INDEX.md`**

6. **Create `.lifecycle/project_type.json`**

7. **Create `.lifecycle/iter-1/task_status.json` and `test_results.json`**

8. **Returns:**
   ```python
   {
       "success": True,
       "message": f"Project '{project_name}' initialized successfully",
       "data": {"docs_dir": ..., "lifecycle_dir": ..., "adr_dir": ...}
   }
   ```

---

### `_cmd_validate(args)` → dict

**Execution path:**

1. **Resolve document path:**
   ```python
   doc_path = args.get("doc")
   doc_type = args.get("type", "auto")
   full_path = self.root / doc_path
   ```

2. **Validate document:**
   ```python
   from scripts.core.doc_validator import validate_document
   result = validate_document(str(full_path), doc_type)
   ```

3. **Create snapshot** (if validation passed):
   ```python
   from scripts.core.snapshot_manager import SnapshotManager
   snapshot_mgr = SnapshotManager(self.root)
   snapshot_path = snapshot_mgr.take(doc_path, alias=doc_type, label=f"validated_{doc_type}")
   ```

4. **Write score file:**
   ```python
   score_file = self.root / ".lifecycle" / "steps" / f"{doc_type}-score.json"
   score_data = {
       "score": result.get("score", 0),
       "threshold": 70,
       "passed": True,
       "doc_type": doc_type,
       "timestamp": ...
   }
   ```

5. **Returns:**
   ```python
   {
       "success": result.get("passed", False),
       "message": f"Document validation {'passed' if result.get('passed') else 'failed'}",
       "data": result
   }
   ```

---

### `_cmd_outline(args)` → dict

**Execution path:**

1. **Resolve paths:**
   ```python
   prd_path = args.get("prd", paths.PRD_PATH)
   arch_path = args.get("arch", paths.ARCH_PATH)
   output_path = args.get("output", paths.TEST_OUTLINE_PATH)
   ```

2. **Generate outline:**
   ```python
   from scripts.core.test_outline import generate_outline, write_outline
   legacy, graph = generate_outline(prd_path=str(full_prd), arch_path=str(full_arch) if full_arch.exists() else None)
   ```

3. **Write outline:**
   ```python
   write_outline(legacy, str(full_output), test_graph=graph)
   ```

4. **Returns:**
   ```python
   {
       "success": True,
       "message": f"Test outline generated: {output_path}",
       "data": {
           "output_path": str(full_output),
           "feature_count": len(legacy.get("entries", [])),
           "scenario_count": legacy.get("total_scenarios", 0)
       }
   }
   ```

---

### `_cmd_plan(args)` → dict

**Execution path:**

1. **Plan iterations:**
   ```python
   from scripts.core.iteration_planner import plan_iterations, write_iteration_plans
   iterations = plan_iterations(prd_path=str(full_prd), arch_path=str(full_arch) if full_arch.exists() else None)
   ```

2. **Write iteration plans:**
   ```python
   write_iteration_plans(iterations, str(full_output))
   ```

3. **Initialize velocity tracking:**
   ```python
   from scripts.core.velocity_tracker import VelocityTracker
   VelocityTracker(self.root).initialize(iterations)
   ```

4. **Returns:**
   ```python
   {
       "success": True,
       "message": f"Generated {len(iterations)} iteration plans",
       "data": {"iteration_count": len(iterations), "output_dir": str(full_output)}
   }
   ```

---

### `_cmd_change(args)` → dict

**Execution path (prd-change):**

1. **Detect PRD diff:**
   ```python
   from scripts.core.change_detector import detect_prd_diff
   result = detect_prd_diff(old_prd_path=str(latest_snapshot), new_prd_path=str(full_new))
   ```

2. **Cascade impact:**
   ```python
   from scripts.core.change_detector import cascade_impact
   impact = cascade_impact(result, test_graph_path)
   ```

3. **Write CHANGE_IMPACT.md:**
   ```python
   impact_file = self.lifecycle_dir / "CHANGE_IMPACT.md"
   impact_file.write_text(impact.get("summary_md", ""), encoding="utf-8")
   ```

4. **Returns:**
   ```python
   {
       "success": True,
       "message": f"Detected {len(result.get('changes', []))} changes",
       "data": result
   }
   ```

---

### `_cmd_draft(args)` → dict

**Execution path (prd):**

1. **Generate draft prompt:**
   ```python
   from scripts.core.prd_drafter import generate_draft_prompt
   draft_prompt = generate_draft_prompt(user_desc)
   ```

2. **Returns:**
   ```python
   {
       "success": True,
       "message": "PRD draft mode activated",
       "data": {
           "instructions": "Model should generate PRD draft interactively",
           "output_path": paths.PRD_PATH,
           "draft_prompt": draft_prompt
       }
   }
   ```

---

### `_cmd_gate(args)` → dict

**Execution path:**

1. **Artifact validation:**
   ```python
   from scripts.core.artifact_validator import validate_iteration
   artifact_result = validate_iteration(self.root, iteration_n)
   ```

2. **DoD rule checks:**
   ```python
   from scripts.core.dod_checker import DoDChecker
   checker = DoDChecker(self.root)
   results = checker.run_all(iteration=iteration_n)
   ```

3. **Returns:**
   ```python
   {
       "success": gate_passed,
       "message": f"Gate check {'passed' if gate_passed else 'failed'} for iteration {iteration_n}",
       "data": {
           "dod_results": results,
           "artifact_validation": artifact_result
       }
   }
   ```

---

### `_cmd_analyze_solution(args)` → dict

**Execution path:**

1. **Analyze solution:**
   ```python
   from scripts.core.solution_analyzer import SolutionAnalyzer
   analyzer = SolutionAnalyzer(self.root)
   result = analyzer.analyze(intent, user_input)
   ```

2. **Save solution.json:**
   ```python
   solution_file = self.lifecycle_dir / "solution.json"
   solution_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
   ```

3. **Returns:**
   ```python
   {
       "success": True,
       "message": "方案分析完成",
       "data": result
   }
   ```

---

## 6. 领域模块调用链

### 6.1 `intent_resolver.py`

#### `IntentResolver.resolve(user_input)` → Tuple[List[IntentType], str]

**Execution path:**

```python
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
            break

matches.sort(key=lambda m: m.priority)
intents = [m.intent for m in matches]
explanation = "\n".join(m.explanation for m in matches)

return (intents, explanation)
```

**Intent patterns:**
- `bug-fix`: `报错`, `测试失败`, `bug`, `修复`, `fix`, ...
- `prd-change`: `需求变`, `PRD 改`, `调整需求`, ...
- `new-feature`: `增加功能`, `新需求`, `新增功能`, ...
- `new-product`: `新产品`, `从零开始`, `新项目`, ...

**Returns:**
```python
(["new-product"], "未识别到明确意图，默认为新项目")
```

---

### 6.2 `checkpoint_manager.py`

#### `CheckpointManager.load()` → dict

**Execution path:**

1. **Return from cache** (if available):
   ```python
   if self._cache is not None:
       return copy.deepcopy(self._cache)
   ```

2. **Load from disk:**
   ```python
   self._cache = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
   ```

3. **Migrate checkpoint version** (if needed):
   ```python
   self._cache = self._migrate_checkpoint_version(self._cache)
   ```

4. **Returns:** checkpoint dict

---

#### `CheckpointManager.save(checkpoint, immediate=False)`

**Execution path:**

```python
self._cache = checkpoint
self._cache["updated_at"] = datetime.now(timezone.utc).isoformat()
self._dirty = True

if immediate:
    self.flush()
```

---

#### `CheckpointManager.create_rollback_point(phase_id, description)` → dict

**Execution path:**

1. **Create rollback ID:**
   ```python
   rollback_id = f"rp-{uuid.uuid4().hex[:8]}"
   ```

2. **Create file snapshot:**
   ```python
   snapshot_dir = self._create_file_snapshot(phase_id)
   ```

3. **Build rollback point:**
   ```python
   rollback_point = {
       "id": rollback_id,
       "phase_id": phase_id,
       "timestamp": ...,
       "description": description,
       "checkpoint_snapshot": {
           "current_phase": checkpoint.get("current_phase"),
           "completed_phases": copy.deepcopy(checkpoint.get("completed_phases", [])),
           "status": checkpoint.get("status"),
           "phase_data": copy.deepcopy(checkpoint.get("phase_data", {}))
       },
       "snapshot_dir": str(snapshot_dir)
   }
   ```

4. **Save to checkpoint:**
   ```python
   checkpoint["metadata"]["rollback_points"].append(rollback_point)
   self.save(checkpoint, immediate=True)
   ```

5. **Returns:** rollback_point dict

---

### 6.3 `doc_validator.py`

#### `validate_document(doc_path, doc_type="auto")` → dict

**Execution path:**

1. **Auto-detect doc_type** (if "auto"):
   ```python
   if "arch" in name_lower:
       doc_type = "arch"
   elif "outline" in name_lower or "test" in name_lower:
       doc_type = "test_outline"
   else:
       doc_type = "prd"
   ```

2. **Route to validator:**
   ```python
   if doc_type == "arch":
       return _validate_arch(content, doc_path)
   elif doc_type == "test_outline":
       return _validate_test_outline(content, doc_path)
   else:
       return _validate_prd(content, doc_path)
   ```

---

#### `_validate_prd(content, path)` → dict

**Scoring design:**
- Base points: section presence (max 50)
- Bonus points: content depth (max 47)
- Total cap: 100
- Threshold: 70

**Sections checked:**
1. 产品愿景 (10 base + 8 bonus)
2. 核心功能 (8 base + 7 bonus)
3. 用户角色 (7 base + 5 bonus)
4. 功能流程 (8 base + 7 bonus)
5. 非功能需求 (7 base + 5 bonus)
6. 范围边界 (5 base + 3 bonus)
7. 风险 (5 base + 4 bonus)

**Returns:**
```python
{
    "score": 85,
    "passed": True,
    "issues": [...],
    "suggestions": [...],
    "doc_type": "prd",
    "doc_path": "...",
    "ears_compliance": {...}
}
```

---

### 6.4 `dod_checker.py`

#### `DoDChecker.run_all(iteration=None, task_data=None, test_results=None)` → List[dict]

**Execution path:**

```python
rules = self.load_rules()["rules"]
results = []

for rule in rules:
    rule_type = rule["type"]
    
    if rule_type == "tasks":
        # Check task_status.json
        tasks_data = json.loads(task_file.read_text())
        incomplete = [t for t in tasks_list if t.get("status") not in ("done", "completed")]
        results.append({"rule": desc, "status": "fail" if incomplete else "pass", ...})
    
    elif rule_type == "test_records":
        # Check test_results.json
        unresolved = [r for r in records if r.get("status") == "fail" and not r.get("resolution")]
        results.append({"rule": desc, "status": "fail" if unresolved else "pass", ...})
    
    elif rule_type == "command":
        passed, output = self.check_command(cmd)
        results.append({"rule": desc, "status": "pass" if passed else "fail", ...})
    
    elif rule_type == "coverage":
        passed, detail = self.check_coverage(cmd, threshold)
        results.append({"rule": desc, "status": "pass" if passed else "fail", ...})

return results
```

---

### 6.5 `artifact_validator.py`

#### `validate_iteration(root, iteration_n)` → dict

**4-layer validation:**

1. **Layer 1: 基础文档存在性**
   - `Docs/product/PRD.md` exists and ≥ 500 bytes
   - `Docs/tech/ARCH.md` exists and ≥ 300 bytes
   - `Docs/tests/MASTER_OUTLINE.md` exists and contains TST-IDs

2. **Layer 2: 迭代专属产物**
   - `Docs/iterations/iter-N/PLAN.md` exists and has goal + E2E criteria
   - `Docs/iterations/iter-N/test_cases.md` exists and has TST-IDs
   - TST task `test_case_ref` cross-validation

3. **Layer 3: 测试执行记录**
   - `.lifecycle/iter-N/test_results.json` exists
   - All done TST tasks have execution records
   - All fail tests have resolution

4. **Layer 4: 架构覆盖检查 (警告)**
   - Feature IDs referenced in PLAN.md exist in ARCH.md

**Returns:**
```python
{
    "passed": bool,
    "iteration": int,
    "layers": {
        "layer1": {"passed": bool, "checks": [...]},
        "layer2": {"passed": bool, "checks": [...]},
        "layer3": {"passed": bool, "checks": [...]},
        "layer4": {"passed": True, "warnings": [...]}
    },
    "blocking_failures": [...],
    "warnings": [...]
}
```

---

### 6.6 `change_detector.py`

#### `detect_prd_diff(old_prd_path, new_prd_path)` → dict

**Execution path:**

1. **Extract features from PRDs:**
   ```python
   old_features = _extract_features(old_content)
   new_features = _extract_features(new_content)
   ```

2. **Detect changes:**
   - Added: features in `new_features` but not in `old_features`
   - Deleted: features in `old_features` but not in `new_features`
   - Modified: features with different descriptions

3. **Infer impacts:**
   - `affects_data_model`: if keywords like `字段`, `属性`, `表` in description
   - `affects_api`: if keywords like `接口`, `API`, `endpoint` in description

4. **Returns:**
   ```python
   {
       "timestamp": "...",
       "changes": [
           {"change_type": "added", "feature_id": "F03", "feature_name": "...", ...},
           {"change_type": "modified", "feature_id": "F01", ...}
       ],
       "summary": "1 个功能新增, 1 个修改, 0 个删除"
   }
   ```

---

#### `cascade_impact(change_report, test_graph_path)` → dict

**Execution path:**

1. **Load test graph:**
   ```python
   from .test_graph import TestGraph
   graph = TestGraph.load(test_graph_path)
   ```

2. **Traverse impact for each change:**
   ```python
   for change in changes:
       changed_items = {"node_ids": [feature_node_ids], "apis": [...], "data_entities": [...]}
       impact_results = graph.traverse_impact(changed_items, direction="both")
   ```

3. **Build impact report:**
   - Affected tests: all TST-* nodes in impact_results
   - Affected iterations: extract from node tags
   - Needs arch update: if any change affects data model or API

4. **Returns:**
   ```python
   {
       "change_report": {...},
       "affected_tests": ["TST-F01-S01", "TST-F01-S02", ...],
       "affected_iterations": [1, 2],
       "needs_arch_update": True,
       "impact_items": [...],
       "summary_md": "# 变更影响报告\n..."
   }
   ```

---

### 6.7 `test_outline.py`

#### `generate_outline(prd_path, arch_path=None)` → Tuple[dict, TestGraph]

**Execution path:**

1. **Detect project type:**
   ```python
   from .project_type_detector import detect_from_arch
   project_type = detect_from_arch(arch_path)
   ```

2. **Extract features from PRD:**
   ```python
   features = _extract_prd_features(prd_path)
   ```

3. **Generate scenarios for each feature:**
   ```python
   for feat in features:
       feat_scenarios = _generate_scenarios_for_feature(feat, project_type=project_type)
       all_scenarios[feat_id] = feat_scenarios
   ```

4. **Build TestGraph:**
   ```python
   graph = _build_test_graph(features, all_scenarios, project_type, ...)
   ```

5. **Build legacy outline:**
   ```python
   legacy = _build_legacy_outline(features, all_scenarios, project_type, ...)
   ```

6. **Returns:** `(legacy, graph)`

---

#### `_generate_scenarios_for_feature(feature, project_type="web")` → List[dict]

**Execution path:**

```python
from .project_type_detector import get_dimension_generators

dimension_configs = get_dimension_generators(project_type)
scenarios = []

for dim_config in dimension_configs:
    tag = dim_config["dimension_tag"]
    
    # Check conditional_keywords
    if cond_kw and not any(kw in feature_text for kw in cond_kw):
        continue
    
    # Generate one scenario per defensive variant
    for variant in dim_config.get("defensive_variants", ["happy"]):
        scenario = {
            "id": f"S{sid:02d}",
            "dimension": tag,
            "variant": variant,
            "description": dim_config["description_template"].format(...),
            "steps": [s.format(...) for s in dim_config["steps_template"]],
            "expected": dim_config["expected_template"].format(...),
            "e2e": dim_config.get("e2e", False) and variant == "happy",
            "layer_entry": dim_config.get("layer_entry", "api"),
            ...
        }
        scenarios.append(scenario)

return scenarios
```

---

### 6.8 `iteration_planner.py`

#### `plan_iterations(prd_path, arch_path=None, constraints=None)` → List[dict]

**Execution path:**

1. **Extract features from PRD:**
   ```python
   features = _extract_prd_features(prd_path)
   ```

2. **Group features into iterations:**
   ```python
   feature_groups = _group_features_into_iterations(features, constraints)
   ```

3. **Build iteration dicts:**
   ```python
   for i, group in enumerate(feature_groups, 1):
       iterations.append({
           "number": i,
           "name": f"迭代 {i}：{feature_names[0]}",
           "goal": "用户能够" + "、".join(feature_names[:2]),
           "feature_ids": feature_ids,
           "e2e_criteria": _build_e2e_criteria(group, project_type),
           "task_ids": [],
           "dependencies": list(range(1, i)),
           "status": "planned"
       })
   ```

4. **Returns:** iterations list

---

### 6.9 `solution_analyzer.py`

#### `SolutionAnalyzer.analyze(intent, user_input)` → Dict[str, Any]

**Execution path:**

1. **Analyze project code:**
   ```python
   project_context = self._analyze_project_code()
   ```
   - Detect project type
   - Detect language
   - Detect framework
   - Analyze dependencies
   - Scan code structure
   - Detect patterns
   - Estimate test coverage

2. **Search industry solutions:**
   ```python
   industry_solutions = self._search_industry_solutions()
   ```
   - WebSearch for best practices
   - WebSearch for open source implementations

3. **Generate solutions:**
   ```python
   proposed_solutions = self._generate_solutions(project_context, industry_solutions)
   ```
   - Conservative solution (low risk)
   - Recommended solution (balanced)
   - Innovative solution (high risk)
   - Adapt industry solutions

4. **Recommend best solution:**
   ```python
   recommendation, confidence = self._recommend(proposed_solutions)
   ```

5. **Returns:**
   ```python
   {
       "project_context": {...},
       "industry_solutions": [...],
       "proposed_solutions": [...],
       "recommendation": "solution-recommended",
       "confidence": 0.85
   }
   ```

---

### 6.10 `velocity_tracker.py`

#### `VelocityTracker.initialize(iterations)` → None

**Execution path:**

```python
data = self._load()
existing_nums = {i["iteration"] for i in data.get("iterations", [])}

for it in iterations:
    n = it.get("number", 1)
    if n not in existing_nums:
        data["iterations"].append({
            "iteration": n,
            "name": it.get("name", f"迭代 {n}"),
            "estimated_hours": None,
            "actual_hours": None,
            "started_at": None,
            "completed_at": None
        })

data["initialized_at"] = datetime.now(timezone.utc).isoformat()
self._save(data)
```

---

### 6.11 `snapshot_manager.py`

#### `SnapshotManager.take(doc_path, alias=None, label=None)` → Path

**Execution path:**

1. **Create snapshot filename:**
   ```python
   ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
   doc_key = doc_path.replace("/", "_").replace(".", "_")
   snapshot_name = f"{doc_key}_{ts}.md"
   ```

2. **Copy document:**
   ```python
   shutil.copy2(src, dst)
   shutil.copy2(src, latest)  # <doc_key>_latest.md
   ```

3. **Update index:**
   ```python
   index[doc_key].append({
       "timestamp": ts,
       "file": snapshot_name,
       "label": label,
       "source": doc_path,
       "size": dst.stat().st_size
   })
   ```

4. **Create alias snapshot** (if provided):
   ```python
   alias_path = self.snapshot_dir / f"{alias}_latest.md"
   shutil.copy2(src, alias_path)
   ```

5. **Returns:** `dst` (snapshot path)

---

### 6.12 `adr_manager.py`

#### `ADRManager.create(title, status="proposed", ...)` → Path

**Execution path:**

1. **Generate ADR number:**
   ```python
   num = self._next_num(records)
   slug = self._slug(title)
   filename = f"ADR-{num:03d}-{slug}.md"
   ```

2. **Create ADR content:**
   ```python
   content = ADR_TEMPLATE.format(
       num=num, title=title, status=status.capitalize(),
       date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
       deciders=deciders, context=context,
       decision=decision, notes=notes
   )
   ```

3. **Write ADR file:**
   ```python
   path = self.adr_dir / filename
   path.write_text(content, encoding="utf-8")
   ```

4. **Update registry:**
   ```python
   records.append({
       "num": num, "title": title, "status": status,
       "file": filename, "created_at": ..., "updated_at": ...
   })
   self._save_registry(records)
   ```

5. **Rebuild INDEX.md:**
   ```python
   self._rebuild_index(records)
   ```

6. **Returns:** `path`

---

### 6.13 `risk_register.py`

#### `RiskRegister.init_from_prd(prd_path)` → None

**Execution path:**

1. **Extract risk section from PRD:**
   ```python
   m = re.search(r'##\s*风险.*?\n(.*?)(?:\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
   risks_text = m.group(1)
   ```

2. **Parse risk lines:**
   ```python
   for line in risks_text.splitlines():
       line = line.strip().lstrip("-*•").strip()
       if len(line) >= 5:
           data["risks"].append({
               "id": risk_id,
               "title": line[:80],
               "probability": "medium",
               "impact": "medium",
               "status": "open",
               "mitigation": "（待填写）",
               "source": "PRD",
               ...
           })
   ```

3. **Save risk register:**
   ```python
   self._save(data)
   ```

---

### 6.14 `sprint_review_generator.py`

#### `SprintReviewGenerator.generate(iteration)` → Path

**Execution path:**

1. **Load iteration data:**
   ```python
   plan = self._load_plan(iter_dir)
   test_results = self._load_test_results(iteration)
   velocity = self._load_velocity()
   adrs = self._load_recent_adrs(iteration)
   ```

2. **Render sprint review:**
   ```python
   content = self._render(iteration, plan, test_results, velocity, adrs)
   ```

3. **Write sprint review:**
   ```python
   output = iter_dir / "sprint_review.md"
   output.write_text(content, encoding="utf-8")
   ```

4. **Returns:** `output`

---

### 6.15 `condition_evaluator.py`

#### `evaluate_condition(expression, checkpoint, additional_context=None)` → bool

**Execution path:**

1. **Build context from checkpoint:**
   ```python
   context = {
       'project_type': checkpoint.get('metadata', {}).get('project_type', 'unknown'),
       'has_prd': checkpoint.get('metadata', {}).get('has_prd', False),
       'has_architecture': checkpoint.get('metadata', {}).get('has_architecture', False),
       'iteration_count': checkpoint.get('metadata', {}).get('current_iteration', 0),
       'status': checkpoint.get('status', 'unknown'),
       'intent': checkpoint.get('intent', 'unknown')
   }
   ```

2. **Create evaluator:**
   ```python
   evaluator = ConditionEvaluator(context)
   ```

3. **Evaluate expression:**
   ```python
   return evaluator.evaluate(expression, additional_context)
   ```

---

### 6.16 `parallel_executor.py`

#### `ParallelExecutor.topological_sort(start_phases=None)` → List[List[str]]

**Execution path:**

1. **Build in-degree map:**
   ```python
   in_degree = {}
   for phase_id in phases_to_process:
       deps = self.get_dependencies(phase_id) & phases_to_process
       in_degree[phase_id] = len(deps)
   ```

2. **Kahn's algorithm:**
   ```python
   groups = []
   remaining = set(phases_to_process)
   
   while remaining:
       current_group = [phase_id for phase_id in remaining if in_degree[phase_id] == 0]
       groups.append(sorted(current_group))
       
       for phase_id in current_group:
           remaining.remove(phase_id)
           for dependent in self.get_dependents(phase_id):
               if dependent in remaining:
                   in_degree[dependent] -= 1
   ```

3. **Returns:** `groups` (parallel execution groups)

---

### 6.17 `test_graph.py`

#### `TestGraph.load(json_path)` → TestGraph

**Execution path:**

```python
data = json.loads(Path(json_path).read_text())
graph = cls()
graph._version = data.get("version", "1.1")
graph.project_type = data.get("project_type", "")
graph.prd_version = data.get("prd_version", "")
graph.arch_version = data.get("arch_version", "")
graph.dimensions_used = data.get("dimensions_used", [])
graph._roots = data.get("nodes", [])
graph._index_tree(graph._roots)  # Build flat index
return graph
```

---

#### `TestGraph.traverse_impact(changed_items, direction="both")` → List[dict]

**Execution path:**

1. **Collect seed nodes:**
   ```python
   seeds = list(changed_items.get("node_ids") or [])
   for api in changed_items.get("apis") or []:
       seeds.extend(n["node_id"] for n in self.find_by_api(api))
   for entity in changed_items.get("data_entities") or []:
       seeds.extend(n["node_id"] for n in self.find_by_entity(entity))
   ```

2. **BFS traversal:**
   ```python
   visited = {seed: 0 for seed in seeds}
   queue = deque([(seed, 0) for seed in seeds])
   
   while queue:
       nid, dist = queue.popleft()
       node = self.nodes.get(nid)
       neighbors = deps.get("downstream_nodes") + deps.get("upstream_nodes")
       for neighbor in neighbors:
           new_dist = dist + 1
           if neighbor not in visited or visited[neighbor] > new_dist:
               visited[neighbor] = new_dist
               queue.append((neighbor, new_dist))
   ```

3. **Format results:**
   ```python
   return sorted(
       [{"node_id": nid, "distance": d, "priority": priority(d)} for nid, d in visited.items()],
       key=lambda x: x["distance"]
   )
   ```

---

### 6.18 `project_type_detector.py`

#### `detect_from_arch(arch_path)` → str

**Execution path:**

```python
text = Path(arch_path).read_text()
scores = {t: 0 for t in KEYWORD_MAP}

for proj_type, keywords in KEYWORD_MAP.items():
    for kw in keywords:
        if re.search(re.escape(kw), text, re.IGNORECASE):
            scores[proj_type] += 1

best = max(scores, key=lambda t: scores[t])
return best if scores[best] > 0 else "web"
```

**Keyword map:**
- `web`: `React`, `Vue`, `Angular`, `Django`, `Flask`, `FastAPI`, ...
- `cli`: `CLI`, `命令行`, `argparse`, `click`, ...
- `mobile`: `iOS`, `Android`, `React Native`, `Flutter`, ...
- `data-pipeline`: `Kafka`, `Flink`, `Spark`, `ETL`, ...
- `microservices`: `微服务`, `gRPC`, `Kubernetes`, ...

---

### 6.19 `dependency_extractor.py`

#### `extract_apis(arch_text)` → List[str]

**Execution path:**

```python
results = []

# Standard REST METHOD /path format
rest_pattern = re.compile(r"(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-{}\.:]+)", re.IGNORECASE)
for m in rest_pattern.finditer(arch_text):
    results.append(f"{m.group(1).upper()} {m.group(2)}")

# Chinese context: 接口/端点/路由 + path
chinese_pattern = re.compile(r"(?:接口|端点|路由)[：:]\s*[`'\"]?(/[\w/\-{}\.:]+)", re.IGNORECASE)
for m in chinese_pattern.finditer(arch_text):
    results.append(m.group(1))

return sorted(set(results))
```

---

#### `infer_feature_dependencies(features, arch_text)` → Dict[str, dict]

**Execution path:**

1. **Extract all APIs and entities:**
   ```python
   all_apis = extract_apis(arch_text)
   all_entities = extract_data_entities(arch_text)
   ```

2. **Match features to APIs/entities:**
   ```python
   for feat in features:
       matched_apis = []
       for api in all_apis:
           path = api.split(" ")[-1]
           segments = [s for s in re.split(r"[/\-_{}]", path) if s]
           for seg in segments:
               if seg.lower() in fname.lower():
                   matched_apis.append(api)
       
       matched_entities = []
       for entity in all_entities:
           if entity.lower() in fname.lower():
               matched_entities.append(entity)
       
       result[fid] = {
           "apis": sorted(set(matched_apis)),
           "data_entities": sorted(set(matched_entities)),
           "upstream_nodes": [...],
           "downstream_nodes": [...]
       }
   ```

3. **Returns:** `result`

---

### 6.20 `paths.py`

**Constants:**

```python
PRD_PATH = "Docs/product/PRD.md"
ARCH_PATH = "Docs/tech/ARCH.md"
TEST_OUTLINE_PATH = "Docs/tests/MASTER_OUTLINE.md"
ITERATIONS_INDEX_PATH = "Docs/iterations/INDEX.md"
ADR_INDEX_PATH = "Docs/adr/INDEX.md"
DOCS_INDEX_PATH = "Docs/INDEX.md"

SOLUTION_JSON = ".lifecycle/solution.json"
CONFIG_JSON = ".lifecycle/config.json"
DOD_JSON = ".lifecycle/dod.json"
VELOCITY_JSON = ".lifecycle/velocity.json"
CHANGE_IMPACT_MD = ".lifecycle/CHANGE_IMPACT.md"
CHECKPOINT_JSON = ".lifecycle/checkpoint.json"

PRD_SNAPSHOT_LATEST = ".lifecycle/snapshots/prd_latest.md"
ARCH_SNAPSHOT_LATEST = ".lifecycle/snapshots/arch_latest.md"
PRD_SCORE_JSON = ".lifecycle/steps/prd-score.json"
ARCH_SCORE_JSON = ".lifecycle/steps/arch-score.json"

DOC_TYPE_PRD = "prd"
DOC_TYPE_ARCH = "arch"
DOC_TYPE_OUTLINE = "test_outline"

SNAPSHOT_ALIAS_PRD = "prd"
SNAPSHOT_ALIAS_ARCH = "arch"
```

---

## 总结

本文档覆盖了 Product Lifecycle Orchestrator skill 的完整调用链，包括：

1. **Shell 入口** → Python 模块调用
2. **CLI 入口** → 子命令路由
3. **编排引擎** → 状态机、依赖检查、Phase 执行
4. **Phase 定义** → 12 个 Phase 的完整定义
5. **命令实现** → 7 个核心命令的执行路径
6. **领域模块** → 20+ 个模块的函数签名、执行逻辑和返回值

所有内容均基于实际源码，保证 100% 准确。本文档将作为其他文档的"source of truth"。
