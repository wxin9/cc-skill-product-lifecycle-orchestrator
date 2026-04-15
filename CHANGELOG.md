# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-15

### Added
- **Test Knowledge Graph** — Structure-based test model with node tree, dependency edges, and dimension tags (`.lifecycle/test_graph.json`)
- **Graph-based Impact Analysis** — `change` and `outline trace` now use BFS traversal for accurate dependency tracking
- **Dimension-driven Scenario Generation** — 4 defensive variants per dimension (happy, boundary, error, data) using `DIMENSION_GENERATORS`
- **Adaptive E2E Templates** — Project-type-specific E2E acceptance criteria (web/cli/mobile/data-pipeline/microservices)
- **Dependency Review Command** — `outline dependency-review` audits feature dependencies
- **Migrate Command** — `outline migrate` converts old MASTER_OUTLINE.md to test_graph.json format
- **Coverage Metrics** — API coverage, dependency coverage, dimension coverage in gate reports
- **Graph Structure Validation** — Validates dependencies declared and defensive scenarios present
- New TypedDicts: `TestNode`, `DependencyDecl`, `DimensionConfig`, `TestGraphSchema`
- New functions: `add_dependency()`, `get_dimension_generators()`, `extract_apis()`, `extract_data_entities()`, `infer_feature_dependencies()`

### Changed
- `test_outline.py` refactored: 9 hardcoded dimensions → dimension-driven generation
- `change_detector.py` refactored: text scanning → graph traversal
- `iteration_planner.py` enhanced: hardcoded E2E → project-type-aware templates
- `__main__.py` enhanced: iter-tests bug fixed + graph integration
- `doc_validator.py` enhanced: graph structure validation
- `artifact_validator.py` enhanced: coverage metrics computation
- `project_type_detector.py` expanded: DIMENSION_GENERATORS dict (+150 lines)

### Fixed
- iter-tests always generated empty test cases (outline_data was never loaded)

### Removed
- Fallback logic for old MASTER_OUTLINE.md format (v1.1 uses graph directly)

## [1.0.0] - 2026-04-09

### Added
- AI-collaborative drafting (Draft Mode) for PRD and Architecture documents
- Compound intent recognition with conversational confirmation (Phase 0)
- Project type auto-detection (Web / CLI / Mobile / Data-Pipeline / Microservices)
- Adaptive test outline dimensions based on project type
- Auto-snapshot on document validation (`change prd` no longer requires `--old`)
- Iteration velocity tracking with ASCII trend charts
- Configurable Definition of Done (DoD) with task/lint/coverage/review rules
- Architecture Decision Record (ADR) management (Proposed → Accepted → Deprecated)
- Risk Register for full lifecycle risk tracking
- Sprint Review auto-generation on gate pass
- 8 new core modules: prd_drafter, arch_drafter, project_type_detector, dod_checker, adr_manager, snapshot_manager, velocity_tracker, risk_register, sprint_review_generator
- `manifest.json` with DSL-based phase artifact definitions
- `skill_definition.json` with version metadata and compatibility matrix
- `completion_rate.md` cross-model evaluation report
- 5 evaluation scenarios (up from 3)
- Top-level `artifact_validator.py` (auto-generated from manifest.json)

### Changed
- SKILL.md expanded from 603 to 870 lines with comprehensive Phase descriptions
- CLI expanded from 14 to 20 commands
- `step_enforcer.py` refactored from 12 KB to 4 KB (simplified checkpoint model)
- `intent_classifier.py` upgraded with compound intent and 9-level priority rules
- `doc_validator.py` enhanced with bilingual EARS compliance checking

### Removed
- `references/doc_templates/` directory (replaced by AI-collaborative Draft Mode)

## [0.1.0] - 2026-04-03

### Added
- Initial release of product-lifecycle skill
- Phase 0–8 workflow with script-enforced gates
- 14 CLI commands (init, validate, task, plan, outline, gate, change, test-record, manual, status, pause, resume, cancel, step)
- EARS requirement syntax validation for PRD documents
- IEEE 829 + BDD test outline generation with 9 dimensions
- Arc42-Lite architecture documentation template
- Auto-generated user manual (MANUAL.md)
- 4-layer artifact validation (documents, iteration deliverables, test records, architecture coverage)
- Full change cascade handling (PRD → Architecture → Tests → Iterations)
- Existing project scanner and migration support
- PRD / Architecture / Test Outline document templates
