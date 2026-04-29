# Fix Rounds History

This document tracks all fix rounds applied after the critical project audit.

---

## Round 1 (d938250): Resolve all 12 issues found in critical project audit

**Tests**: Unknown → Unknown (audit-driven fixes)

**Problems Fixed**:
- Fixed 12 critical/high issues identified in project audit
- Resolved phase ID inconsistencies (v2.0 → v2.2 numbering)
- Fixed dependency graph errors
- Corrected artifact path references
- Fixed validation type mismatches

**Root Cause Pattern**: Version migration issues — v2.0 to v2.2 phase renumbering left stale references in docs, tests, and examples.

---

## Round 2+3 (1ad07b7): Fix engine deadlocks, artifact contracts, and add anti-regression tests

**Tests**: Unknown → Passing (anti-regression tests added)

**Problems Fixed**:
- **Engine deadlocks**: Fixed circular dependency in phase execution
- **Artifact contracts**: Corrected `min_bytes` values for artifact validation
- **Anti-regression tests**: Added test suite to prevent regressions on:
  - Phase ID consistency
  - Dependency graph validity
  - Artifact path existence
  - Intent trigger coverage

**Root Cause Pattern**: Missing validation — artifact size thresholds were guessed, not measured; dependency cycles not detected at runtime.

---

## Round 4 (b80a0b2): Fix intent routing, dead code, iteration counter, paths.py adoption

**Tests**: Passing → Passing

**Problems Fixed**:
- **Intent routing**: Fixed `get_phases_by_intent()` to correctly filter phases
- **Dead code removal**: Deleted unused functions that looked functional but weren't wired up
- **Iteration counter**: Fixed iteration numbering in phase-10-iter-exec
- **paths.py adoption**: Replaced hardcoded path strings with centralized constants

**Root Cause Pattern**: Dead code accumulation — functions written but never integrated; hardcoded strings scattered across modules.

---

## Round 5 (487f414): Fix 22 audit issues (Critical/High/Medium/Low)

**Tests**: Passing → Passing

**Problems Fixed**:
- **Intent auto-resolution**: Added `intent_resolver.py` for automatic intent inference
- **Phase-11-change dependency**: Fixed empty `depends_on` → `["phase-0-intent"]`
- **Error message references**: Fixed messages pointing to deleted commands
- **Missing imports**: Added `import json` in modules using TypedDict
- **TypedDict fields**: Added missing optional fields to type definitions
- **Stale phase IDs in docs**: Updated all documentation to v2.2 IDs
- **Version number consistency**: Aligned version across all files

**Root Cause Pattern**: Incomplete type definitions and stale documentation — TypedDict fields added but not populated; docs not updated during v2.0→v2.2 migration.

---

## Round 6 (0fe6b0c): Fix 32 audit issues (Critical/High/Medium/Low)

**Tests**: Passing → Passing

**Problems Fixed**:
- **Blocks enforcement**: Implemented mechanism to prevent phases from running before blockers complete
- **Execution path filtering**: Fixed `_build_execution_path()` to respect `blocks` field
- **Stale phase IDs in tests**: Updated test fixtures to v2.2 IDs
- **Error messages**: Fixed references to non-existent phases
- **Missing validation**: Added checks for `blocks` field in phase definitions
- **Documentation sync**: Updated all examples to use correct phase IDs

**Root Cause Pattern**: Feature incomplete — `blocks` field existed in PhaseDefinition but was never enforced at runtime.

---

## Recurring Problem Patterns

Across all 6 rounds, these patterns appeared repeatedly:

### 1. Stale Phase IDs in Docs/Tests/Examples

**Symptom**: Documentation and tests referenced v2.0 phase IDs (phase-1-init, phase-2-draft-prd) instead of v2.2 IDs (phase-2-init, phase-3-draft-prd).

**Root Cause**: v2.0→v2.2 renumbering (Phase 1 solution analyzer added) but docs/tests not updated.

**Fix Pattern**: Global search for old IDs, replace with new IDs, verify with tests.

### 2. Version Number Inconsistencies

**Symptom**: Different files had different version numbers (2.0, 2.1, 2.2).

**Root Cause**: Version bumps not propagated across all files.

**Fix Pattern**: Centralize version in one file, derive elsewhere; or use grep to verify consistency.

### 3. Dead Code That Looked Functional

**Symptom**: Functions existed but were never called; looked important but weren't wired up.

**Root Cause**: Refactoring left behind unused code; no dead code elimination.

**Fix Pattern**: Trace all function calls; remove if unused; add tests for coverage.

### 4. Error Messages Pointing to Deleted Commands

**Symptom**: Error messages said "Run xyz command" but command no longer existed.

**Root Cause**: Commands removed but error messages not updated.

**Fix Pattern**: Grep for command names in strings; verify existence.

### 5. Missing `import json` / Missing Fields in TypedDict

**Symptom**: Modules used `json.loads()` but didn't import json; TypedDict fields defined but not populated.

**Root Cause**: Incremental additions without full verification.

**Fix Pattern**: Static analysis (mypy, pyright); comprehensive tests.

---

## Lessons Learned

1. **Version migrations require global search-replace**: Phase ID changes must be propagated everywhere.
2. **Dead code is dangerous**: It looks functional but isn't — remove or wire up.
3. **Type definitions must match runtime**: TypedDict fields must be populated; missing imports break at runtime.
4. **Error messages are code**: They reference commands/IDs that must exist.
5. **Features must be enforced**: `blocks` field existed but wasn't checked — implement or remove.
6. **Tests prevent regressions**: Anti-regression tests caught issues that would have recurred.

---

## Round 7 (efc55c7): Fix 23 audit issues + create knowledge documentation

**Tests**: 239 passed, 0 failed (before and after)

**Problems Fixed**:
- **Critical**: `resume --user-input` silently ignored; `_trim_rollback_points` wrong directory; publish/SKILL.md stale v2.1
- **High**: config.json version; docstring phase IDs; phase-11 dependency contradiction; SKILL.md missing rollback docs
- **Medium**: DoD checker crash on non-dict data; hardcoded phase IDs in __main__.py; silent exception swallowing; solution_analyzer performance
- **Low**: stale phase ID comments; dead code annotation; test file phase IDs

**Key Change**: Created `docs/dev/` knowledge base with ARCHITECTURE.md, ROUNDS_HISTORY.md, KNOWN_ISSUES.md, PHASE_REFERENCE.md.

**Root Cause Pattern**: Lack of persistent code knowledge caused repeated discovery of same issues across rounds.

---

## Round 8 (pending): Architecture-level fixes — change intent usability + doc/code alignment

**Tests**: 239 passed → 239 passed

**Problems Fixed**:

### Critical
- **C1: Change intent dependency blocking** — `_check_dependencies` strictly checked all `depends_on`, even for phases not in the current execution path. prd-change on a fresh project would fail at Phase 3 because it depends on phase-2-init (not in prd-change's path). Fixed by adding `relevant_phase_ids` parameter: deps outside the execution path are treated as optional.
- **C2/C4: Composite intent was fake feature** — SKILL.md claimed serial execution of multiple intents, but code only used `resolved_intents[0]`. Removed false claim from SKILL.md, replaced with honest note.

### High
- **H1-H3: IntentType Literal incomplete** — Missing `from-scratch`, `test-change`, `continue-iter`. Added all 3.
- **H4/H7: SKILL.md PRD change example wrong order** — Example showed Phase 11 first, but code executes by order (Phase 3→4→8→9→11). Rewrote example with correct order and added prerequisite note.
- **H6/L2: SKILL.md intent table incomplete** — Only listed 7 intents, now lists all 12.

### Medium
- **M3/M9: Resume/completed-phase warning** — Now prints warning when user resumes from an already-completed phase.
- **M4/M10: Repeated run protection** — Prints warning when overwriting an in-progress workflow.
- **M5: Shell script set -e removed** — Conflicted with exit code 1 = paused semantics.
- **M6: Version number centralized** — `CURRENT_VERSION = "2.2"` constant in checkpoint_manager.py.
- **L1: Checkpoint format example** — Added missing created_at/updated_at/metadata fields.

**Root Cause Pattern**: Documentation drifted from implementation over time without validation. SKILL.md was written as a design spec but never reconciled against actual code behavior.

---

## Lessons Learned (updated after Round 8)

1. **Version migrations require global search-replace**: Phase ID changes must be propagated everywhere.
2. **Dead code is dangerous**: It looks functional but isn't — remove or wire up.
3. **Type definitions must match runtime**: TypedDict fields must be populated; missing imports break at runtime.
4. **Error messages are code**: They reference commands/IDs that must exist.
5. **Features must be enforced**: `blocks` field existed but wasn't checked — implement or remove.
6. **Tests prevent regressions**: Anti-regression tests caught issues that would have recurred.
7. **Documentation IS code**: SKILL.md claims must be verified against implementation. False claims are worse than missing docs.
8. **Change intent scenarios need special handling**: Dependency checking must account for execution path context — strict checks work for new-product but block change intents.
9. **Knowledge persistence prevents repeated discovery**: docs/dev/ knowledge base eliminates "re-finding" known issues each round.

---

## Round 9: Command implementation layer fixes + legacy code cleanup

**Tests**: 239 passed → 239 passed (3 tests updated for new artifact validation)

**Key Insight**: Previous 8 rounds audited orchestrator/phases/checkpoint (orchestration layer) but never traced actual command execution paths. Exhaustively tracing all 12 intent paths revealed bugs hidden in command implementations.

### Why These Issues Were Missed

| Blind Spot | Explanation | How Round 9 Avoided It |
|---|---|---|
| **Orchestration bias** | 90% of audit effort on orchestrator/phases/checkpoint; never read _cmd_gate etc. | Exhaustive execution path tracing forced reading every _cmd_* method |
| **Happy path testing** | 239 tests only covered success paths | Traced "what happens when user can't create files?" paths |
| **KNOWN_ISSUES comfort zone** | eval() marked "acceptable" → never re-examined | Reviewed but confirmed acceptable; focused on new discoveries |
| **Point fixes** | Fixed config.json version but missed template string | Global grep verification after each fix |

### Critical Fixes

- **T1.1: Gate validation incomplete** — `_cmd_gate` only ran DoD checks, skipped artifact validation entirely. Layer 1-4 artifacts (PRD, ARCH, MASTER_OUTLINE, PLAN, test_cases, test_results) were never verified at gate time. Fixed by adding `artifact_validator.validate_iteration()` call before DoD checks.
- **T1.2: Phase 5 dead loop** — When `command=None` + artifact validation fails → pause → resume → fail → infinite loop with no exit path. Fixed by adding exit guidance (cancel command + file format instructions) to failure notification.

### High Fixes

- **T2.1: arch_text NameError** — Variable only assigned inside if-block at line 277 but referenced at line 340. Fixed by initializing `arch_text = ""` at function start.
- **T2.2: Legacy files** — Deleted `scripts/step_enforcer.py` and `scripts/artifact_validator.py` (root-level) which used old step IDs and were never called by v2.2 orchestrator.
- **T2.3: PRD draft missing draft_prompt** — `_cmd_draft` ARCH branch called arch_drafter but PRD branch didn't call prd_drafter. Fixed by adding prd_drafter.generate_draft_prompt() call with graceful degradation.
- **T2.4: Non-prd-change intents empty** — code-change/bug-fix/test-failure/gap intents produced only template CHANGE_IMPACT.md with no project analysis. Fixed by calling project_scanner for code-change/bug-fix and scanning test failures for test-failure intent.

### Medium Fixes

- **T3.1+T3.7: snapshot_manager** — Added threading.Lock for thread safety; fixed `datetime.now()` → `datetime.now(timezone.utc)`.
- **T3.2: Phase 6 command_args** — Added missing `"doc": "Docs/tech/ARCH.md"` to Phase 6 command_args.
- **T3.3: velocity_tracker UTC** — All `datetime.now()` → `datetime.now(timezone.utc)` for timestamp consistency.
- **T3.4: sys.exit(1) in library** — `_extract_prd_features` called `sys.exit(1)` on bad PRD format, crashing the orchestrator process. Changed to `ValueError`.
- **T3.5: INDEX.md version string** — Template had `v2.1` instead of `v2.2`.
- **T3.6: __import__('re')** — sprint_review_generator used `__import__('re')` instead of proper `import re`.
- **T3.8: Missing default files** — `_cmd_init` created dod.json but not task_status.json/test_results.json in iter-1/, causing gate to crash on fresh projects. Added default template creation.

### Test Updates

3 gate tests needed updates because `_cmd_gate` now runs artifact validation in addition to DoD checks. Added `make_minimal_artifacts()` helper to create the required artifact files.

---

## Lessons Learned (updated after Round 9)

1. **Version migrations require global search-replace**: Phase ID changes must be propagated everywhere.
2. **Dead code is dangerous**: It looks functional but isn't — remove or wire up.
3. **Type definitions must match runtime**: TypedDict fields must be populated; missing imports break at runtime.
4. **Error messages are code**: They reference commands/IDs that must exist.
5. **Features must be enforced**: `blocks` field existed but wasn't checked — implement or remove.
6. **Tests prevent regressions**: Anti-regression tests caught issues that would have recurred.
7. **Documentation IS code**: SKILL.md claims must be verified against implementation. False claims are worse than missing docs.
8. **Change intent scenarios need special handling**: Dependency checking must account for execution path context.
9. **Knowledge persistence prevents repeated discovery**: docs/dev/ knowledge base eliminates "re-finding" known issues each round.
10. **Orchestration bias blinds**: Auditing only the orchestrator misses bugs in command implementations. Trace full execution paths, not just routing.
11. **Library code must never sys.exit()**: Functions called by orchestrator should raise exceptions, not terminate the process.
12. **Gate validation is two-layer**: Artifact validation + DoD rules are complementary; missing either gives false passes.

---

## Round 10: Ultimate audit fix — systematic layer-by-layer coverage

**Tests**: 239 passed → 272 passed (+33 new tests across 3 test files)

**Key Insight**: Previous 9 rounds had a systematic blind spot — only auditing orchestration (L3-4) and command (L4) layers. Round 10 mapped all 10 architectural layers and audited each systematically, finding 20+ issues in layers 5-9 that were never touched before.

### Layer Audit Coverage

| Layer | Name | Issues Found | Status |
|-------|------|-------------|--------|
| L1 | Shell Entry | 1 | Fixed (exit code forwarding) |
| L2 | CLI/__main__ | 5 | Fixed (cancel reset, dynamic intents, status exit code) |
| L3 | Orchestration | 2 | Known Issues (parallel mode, eval) |
| L4 | Command Dispatch | 4 | Fixed (gate safety, iter-N defaults) |
| L5 | Intent Recognition | 2 | Fixed (stale refs, test coverage) |
| L6 | State Persistence | 3 | Fixed (encoding, timestamps) |
| L7 | Validation | 6 | Fixed (shell injection, JSON safety, encoding) |
| L8 | Domain Logic | 2 | Fixed (dead code, unused imports) |
| L9 | Analysis/Generation | 11 | Fixed (encoding, timestamps, typos, None display) |
| L10 | Data Schemas | 0 | Clean |
| L11 | Adapters | 0 | Clean |

### Systematic Fixes (by category)

**Encoding consistency** (6 modules, 20 locations):
All `read_text()`/`write_text()` calls now include `encoding="utf-8"`. Previously, non-UTF-8 locale systems would crash.

**Timestamp consistency** (3 modules):
All `datetime.now()` → `datetime.now(timezone.utc)`. Plus removed redundant `from datetime import datetime` in velocity_tracker.py.

**Critical security + state machine**:
- Shell injection defense: dod_checker now uses `shlex.split()` + `shell=False` + dangerous char sanitization
- JSON parsing safety: dod_checker returns graceful defaults on malformed JSON
- Cancel resets state: `current_phase=None, completed_phases=[], phase_data={}`
- Gate creates iter-N defaults: prevents crash for iter-2+
- artifact_validator import failure → gate fails (not silently passes)
- change_detector checks PRD existence before reading

**High fixes**:
- intent_classifier: replaced 9 stale `./lifecycle` command references
- Shell script: `exec` for exit code forwarding
- Dynamic intent list from phases.py (no more hardcoded _VALID_INTENTS)
- artifact_validator falls back to task_status.json when tasks.json missing

**Medium fixes**:
- Deleted dead code (_insert_before_section, unused imports, rebalance doc)
- Fixed typos ("架案" → "架构草案", E2E regex `[^：：]` → `[^：:]`)
- Fixed velocity None display ("Noneh" → "（进行中）")
- Status returns exit code 1 for uninitialized projects
- manual_generator reads checkpoint.json instead of old steps/ path

**New test coverage** (+33 tests):
- test_intent_resolver.py: 14 tests (intent resolution + priority)
- test_dod_checker_extra.py: 14 tests (malformed JSON, shell injection)
- test_cli_basic.py: 5 tests (cancel reset, status exit codes)

### Not Fixed (by design)

| Issue | Reason |
|-------|--------|
| eval() in condition_evaluator | KNOWN_ISSUES #2, local-only risk, AST replacement is separate refactor |
| Parallel mode gaps | KNOWN_ISSUES #3, experimental feature, sequential only |
| _cmd_draft returns success without file | Design: draft phase activates AI mode, file created during pause |
| solution_analyzer web_search stub | KNOWN_ISSUES #1, requires external API key |
| intent_resolver/classifier overlap | Different responsibilities, merge would be refactor not bugfix |

---

## Lessons Learned (updated after Round 10)

1. **Version migrations require global search-replace**: Phase ID changes must be propagated everywhere.
2. **Dead code is dangerous**: It looks functional but isn't — remove or wire up.
3. **Type definitions must match runtime**: TypedDict fields must be populated; missing imports break at runtime.
4. **Error messages are code**: They reference commands/IDs that must exist.
5. **Features must be enforced**: `blocks` field existed but wasn't checked — implement or remove.
6. **Tests prevent regressions**: Anti-regression tests caught issues that would have recurred.
7. **Documentation IS code**: SKILL.md claims must be verified against implementation. False claims are worse than missing docs.
8. **Change intent scenarios need special handling**: Dependency checking must account for execution path context.
9. **Knowledge persistence prevents repeated discovery**: docs/dev/ knowledge base eliminates "re-finding" known issues each round.
10. **Orchestration bias blinds**: Auditing only the orchestrator misses bugs in command implementations. Trace full execution paths, not only routing.
11. **Library code must never sys.exit()**: Functions called by orchestrator should raise exceptions, not terminate the process.
12. **Gate validation is two-layer**: Artifact validation + DoD rules are complementary; missing either gives false passes.
13. **Layer-by-layer audit prevents round-after-round**: Systematic coverage of all 10 layers eliminates the "found another one" cycle.
14. **Encoding and timestamps are cross-cutting**: These affect every file and must be checked globally, not per-module.
15. **Shell=True is a security boundary**: User-editable config files (dod.json) feeding into subprocess.run(shell=True) is exploitable.
16. **Code is the source of truth, not documentation**: CALL_CHAIN.md is generated from code. All docs must follow code, never the reverse.
17. **continue/break in loops hide logic bugs**: Skipping iteration with `continue` in multi-strategy algorithms silently drops valid inference paths.
18. **In-memory state must sync with persisted state**: Incrementing a counter in JSON but not refreshing the Python variable is a classic cache staleness bug.
19. **User-perspective bugs differ from code-quality bugs**: Correct code can still produce wrong output — regex mismatches, format assumptions, key name mismatches. Audit from the user's view, not just the developer's.
20. **Output format contracts matter**: When Module A generates data and Module B consumes it, their format assumptions must be verified end-to-end. Both being "correct" in isolation isn't enough.
21. **Atomic file operations prevent data loss**: Never delete before copy — always copy to temp, then swap. Disk-full or permission errors mid-operation must not destroy data.

---

## Round 11: Call chain documentation + code logic fixes + doc alignment

**Tests**: 272 passed → 272 passed

**Key Insight**: Documented the complete call chain from shell entry to every command's final output in CALL_CHAIN.md — making code the source of truth. All documentation must be generated from code, not the other way around. Combined with systematic audit of all domain modules.

### Critical Fixes

- **C1: Iteration counter memory staleness** — `orchestrator.py` incremented `current_iteration` in checkpoint but didn't reload the in-memory variable, so subsequent phases used stale iteration number. Fixed by reloading checkpoint after save + only incrementing on `status == "completed"` (also fixes H1).
- **C2: Dependency chain broken for upstream/downstream features** — `dependency_extractor.py` used `continue` after setting upstream/downstream keywords, skipping the sequence inference loop entirely. F01(auth)→F02→F03 would miss F02→F03 dependency. Fixed by removing `continue` and changing second `if` to `elif`.

### High Fixes

- **H2: Shell injection defense incomplete** — `dod_checker.py` command sanitization didn't block `\n` or `<>` (newline injection and file redirection). Added to blocked character regex.
- **H3: risk_register PRD parsing includes table headers** — Markdown table rows (`| 风险 | 概率 |`) were treated as risk entries. Added `startswith("|")` filter.
- **H4: arch_drafter swallows all exceptions** — `except Exception: pass` gave no feedback when project type detection failed. Changed to print error message.

### Medium Fixes

- **M1: test_outline docstring mismatch** — Docstring said `raises SystemExit`, actual code `raise ValueError`.
- **M2: intent_resolver break skips patterns** — First matching pattern caused `break`, preventing other patterns for same intent from being checked. Removed `break`.
- **M3: dod.json parse failure silent** — Custom DoD rules silently ignored on JSON parse error. Added warning print.
- **M4: coverage extraction silent failure** — Regex mismatch on coverage output returned success status. Now returns `(False, error_message)`.
- **M5: arch_drafter hardcoded path** — Used `"Docs/product/PRD.md"` instead of `paths.PRD_PATH`. Replaced with constant.
- **M6: adr_manager status case inconsistency** — `.capitalize()` wrote "Accepted" to markdown but registry stored "accepted". Changed to `.lower()`.
- **M7: plan_format_normalizer "待补充" substring match** — Contained "待补充" in normal goal text was flagged as placeholder. Changed to exact match.

### Low Fixes

- **L1: condition_evaluator missing os/subprocess/sys patterns** — Forbidden patterns didn't include `os.`, `subprocess.`, `sys.`. Added all three.
- **L2: risk_register forced placeholder entries** — Empty PRD risk section created fake risk entries. Removed forced creation.
- **L3: _insert_after_goal position** — Used `m.start()` instead of `m.end()` (functionally identical for single-line regex, but `m.end()` is more robust).

### Documentation

- **T1.1: CALL_CHAIN.md created** — Complete call chain from shell entry to every command's final output, covering all 33 modules. This is the source of truth for all other documentation.

### Not Fixed (by design)

| Issue | Reason |
|-------|--------|
| artifact_validator only checks done tasks | Design: incomplete tests don't need execution records |
| velocity_tracker complete_iteration partial entry | command_executor always start→complete; defensive check value low |
| intent_classifier substring matching | Low-frequency module, refactor cost > benefit |
| parallel_executor error messages | Experimental feature |

---

## Round 12: User-perspective audit — output correctness + format mismatches

**Tests**: 272 passed → 272 passed

**Key Insight**: Previous 11 rounds audited code quality (encoding, timestamps, logic errors). Round 12 shifted to the user's perspective: does the Skill actually produce correct output? Found that several modules generate data in wrong formats, use stale regexes, or silently drop user input.

### Critical Fix

- **C1: Rollback data loss risk** — `checkpoint_manager._restore_file_snapshot` deleted Docs/ before copying from snapshot. If copytree failed, data was permanently lost. Fixed with atomic swap: copy to temp dir first, then rename.

### High Fixes

- **H1: PRD drafter never receives user input** — `phases.py` passes `description` key but `_cmd_draft` reads `user_description` key. User's description was always empty string. Fixed by checking both keys.
- **H2: Sprint review goal always shows fallback** — Regex `##\s*目标` matched heading format but iteration_planner generates `**目标：**` (bold text). Added primary match for bold format.
- **H3: Sprint review test_results always 0/0/0** — Code assumed dict format but `_cmd_init` creates list format. Fixed to handle both formats.
- **H4: Plan format normalizer placeholder not detected** — Inserted placeholder `（待补充：...）` but check used `== "待补充"` exact match. Changed to `in` operator.
- **H5: _insert_after_goal ValueError** — `content.index("\n")` fails on last line without newline. Added try/except with fallback.

### Medium Fixes

- **M1: intent_classifier uses stale Phase 1-7 numbering** — Read from deprecated `steps/` directory, used old step IDs. Rewrote to read from `checkpoint.json` with new phase IDs.
- **M2: doc_validator risk validation too lenient** — `_has_table()` returns bool used as int in `max()`, `max(3, True)` = 3 (not 2). Fixed with explicit check.
- **M3: velocity_tracker crashes on corrupted JSON** — No error handling on `json.loads`. Added `try/except json.JSONDecodeError`.
- **M4: task_registry move doesn't update ID** — Moved task keeps old `ITR-1.DEV-001` ID. Now regenerates ID prefix to match new iteration.
- **M5: test_outline step adjustments silent no-op** — Only modified `result[0]`; if first step lacked expected keywords, adjustment was silently skipped. Now iterates all steps.

### Low Fix

- **L1: intent_resolver absolute import** — `from scripts.core.phases import ...` fails depending on CWD. Changed to relative import.

### Not Fixed (by design)

(None — all Round 12 audit issues now resolved.)

---

## Round 13: Fix remaining "by design" issues from Round 12 audit

**Tests**: 272 passed → 272 passed

**Key Insight**: Round 12 marked 5 issues as "not fixing" but they all cause actual functional problems — unreliable Chinese PRD diff detection, silent cross-validation skipping, noisy dependency graphs, fragile table matching, and keyword duplication. All fixed without external dependencies.

### Fixes

- **M3: change_detector CJK word splitting** — `re.findall(r"\w+")` splits CJK characters individually, making Jaccard similarity unreliable for Chinese PRDs. Changed to `r"[a-zA-Z0-9_]+|[一-鿿]+"` which groups consecutive CJK characters as single tokens. No external dependencies needed.
- **M4: artifact_validator task_status format divergence** — When falling back to `task_status.json`, field names (`task_type`, `iter`) didn't match expected schema (`type`, `iteration`), causing cross-validation to silently skip. Added field normalization + warning when no task data file exists.
- **L3: dependency_extractor dense dependency graph** — Sequence inference created O(N^2) edges (F01 upstream of ALL others). Limited to adjacent features only (F01→F02, F02→F03), reducing noise while preserving real sequential dependencies.
- **L4: manual_generator table row matching** — `startswith("|") and "|" in line` matched separator lines and non-table content. Now requires ≥3 pipe characters and excludes pure separator lines as insertion anchor.
- **L2: project_type_detector keyword duplication** — `"terminal"` appeared twice in cli keyword list. Removed duplicate.

### Lessons Learned

22. **CJK text requires Unicode-aware tokenization**: `\w+` splits CJK characters individually, making similarity metrics (Jaccard, cosine) completely unreliable for Chinese text. Use `[a-zA-Z0-9_]+|[一-鿿]+` to group consecutive CJK characters as single tokens — no external libraries needed.
23. **Schema drift between data producers and consumers is silent**: When two files store the same data with different field names (`task_type` vs `type`), cross-validation silently skips those records. Always normalize at the consumption boundary.
24. **O(N^2) heuristics produce noisy output**: Sequence-based inference that marks all prior features as upstream creates dense, uninformative dependency graphs. Adjacent-only inference (prev→next) is sufficient and produces actionable output.
25. **Markdown table parsing needs structural guards**: `startswith("|")` matches separators and non-table lines. Requiring ≥3 pipes + excluding separator-only lines prevents misinsertion in generated documents.
