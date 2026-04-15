[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

> **AI-Collaborative + Script-Enforced Gates** for product lifecycle management — from PRD to delivery, ensuring every step completes correctly

## 🎯 Core Value

**Problems Solved**:
- ❌ Scattered docs, version chaos
- ❌ Process relies on self-discipline, easy to skip steps
- ❌ Broken change cascade
- ❌ Blind test coverage

**Solution**:
- ✅ Script-enforced gates (`sys.exit(1)` physical blocking)
- ✅ Test Knowledge Graph-driven
- ✅ Dimension-adaptive scenario generation
- ✅ Automatic change impact analysis

## ⭐ v1.1.0 New Features

### 1. Test Knowledge Graph
- **Structured test model**: Feature → Scenario → Rule hierarchy
- **Dependency graph**: Auto-track upstream/downstream, API, data entity dependencies
- **Storage format**: `.lifecycle/test_graph.json`

### 2. Dimension-Driven Scenario Generation
- **4 defensive variants**: Each dimension auto-generates happy/boundary/error/data
- **Project type adaptive**:
  - Web → `[UI][API][AUTH][DATA][PERF][XSS]`
  - CLI → `[CLI][ARGS][IO][ERROR]`
  - Data-Pipeline → `[DATA][ASYNC][IDEMPOTENCY][VOLUME][SCHEMA][BACKFILL]`
  - Mobile → `[UI][OFFLINE][SYNC][PERF][BATTERY][PERMISSION]`
  - Microservices → `[API][RPC][CIRCUIT][CACHE][AUTH][TRACE]`

### 3. Graph-Based Impact Analysis
- **BFS traversal**: Precisely calculate change impact scope
- **Auto cascade**: Modify PRD → auto-identify affected tests and iterations
- **Distance & priority**: Output impact distance, sorted by priority

### 4. New Commands
- `outline dependency-review` — Audit feature dependency declarations
- `outline migrate` — Migrate old test outline to graph format

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git

# Install as Claude Code skill
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### Usage (Natural Language Conversation)

After installation, just talk to Claude Code:

```
You: "Help me write a PRD for a task management tool"
Claude: [Auto-drafts PRD] → [You review] → [Auto-snapshot on validation]

You: "Design the technical architecture"
Claude: [Auto-drafts architecture] → [Generates test graph] → [Plans iterations]

You: "Requirements changed, need to add 2FA to login"
Claude: [Identifies change] → [Graph traversal impact analysis] → [Lists affected tests & iterations] → [Cascades updates]
```

## 💡 Core Features

| Feature | Description |
|---------|-------------|
| **AI-Collaborative Drafting** | Claude actively drafts PRD/architecture, you review |
| **Script-Enforced Gates** | `sys.exit(1)` physical blocking, cannot skip steps |
| **Compound Intent Recognition** | "Fixed bug and want to adjust requirements" — recognizes multiple intents, prioritizes and executes |
| **Project Type Auto-Detection** | 5 types, test dimensions self-adapt |
| **Auto-Snapshot & Diff** | Auto-snapshot on validation, auto-diff on change |
| **Velocity Tracking** | Estimated vs actual hours + ASCII trend charts |
| **DoD Gate Extension** | lint/coverage/code review, warn or fail |
| **ADR Management** | Architecture Decision Record full lifecycle |
| **Risk Register** | Probability×impact matrix auto-rating |
| **Sprint Review** | Auto-generates review materials on gate pass |

## 📖 Workflow

```
Phase 0: Intent Recognition
   ↓
Phase 1: Project Init → DoD/Risk/ADR setup
   ↓
Phase 2: AI Draft PRD → You review
   ↓
Phase 3: Validate PRD → Auto-snapshot
   ↓
Phase 4: Architecture Interview
   ↓
Phase 5: AI Draft Architecture → Includes ADR draft
   ↓
Phase 6: Validate Architecture → Auto-snapshot
   ↓
Phase 7: Generate Test Graph + Adaptive Outline
   ↓
Phase 8: Plan Iterations → Velocity estimation
   ↓
Phase 9: Execute Iterations → 4-layer gate validation
   ↓
Phase 10: Handle Changes → Graph traversal cascade update
```

## 🛠️ Common Commands

```bash
# Initialize project
python -m scripts init --name "Project Name"

# AI-collaborative PRD drafting
python -m scripts draft prd --description "Product description"

# Validate document
python -m scripts validate --doc Docs/product/PRD.md --type prd

# Generate test graph and outline
python -m scripts outline generate --prd PRD.md --arch ARCH.md

# Plan iterations
python -m scripts plan

# Iteration gate (4-layer validation)
python -m scripts gate --iteration 1

# Handle changes (auto graph traversal)
python -m scripts change prd

# Dependency review
python -m scripts outline dependency-review
```

## 📊 Generated Project Structure

```
Docs/
├── product/PRD.md          # PRD document
├── tech/ARCH.md            # Architecture document
├── tests/MASTER_OUTLINE.md # Test outline
└── iterations/iter-N/      # Iteration plan + test records + Sprint Review

.lifecycle/
├── test_graph.json         # Test Knowledge Graph ⭐ v1.1.0
├── config.json             # Project configuration
├── dod.json                # DoD rules
├── risk_register.json      # Risk register
├── velocity.json           # Velocity tracking
└── snapshots/              # Document snapshots
```

## 🎓 Model Compatibility

- **Recommended**: Claude Sonnet 4+ — Best drafting quality
- **Usable**: Claude Haiku — Can complete full workflow, slightly lower drafting quality
- **Core Mechanism**: Script-enforced gates don't depend on model capability

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE)

## 🏢 Commercial Use

For commercial use, please include attribution in your product documentation:

```
This product uses Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
Copyright 2026 Kaiser (wxin966@gmail.com)
Apache License 2.0
```

---

**Full Changelog**: [CHANGELOG.md](CHANGELOG.md) | **GitHub**: [wxin9/cc-skill-product-lifecycle](https://github.com/wxin9/cc-skill-product-lifecycle)
