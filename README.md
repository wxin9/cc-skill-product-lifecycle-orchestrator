[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

> **Script-Orchestrated + Interaction-Paused** product lifecycle management — orchestrator auto-executes phase sequences, pauses at interaction points, notifies model to handle, then resumes

## ⚠ BREAKING CHANGES (v2.0)

**All legacy commands have been removed**:
- ❌ `./lifecycle init` → **Removed**
- ❌ `./lifecycle validate` → **Removed**
- ❌ `./lifecycle draft` → **Removed**
- ❌ `./lifecycle plan` → **Removed**
- ❌ All other legacy commands → **Removed**

**New commands**:
- ✅ `./orchestrator run --intent <intent> --user-input "<input>"` — Start orchestration
- ✅ `./orchestrator resume --from-phase <phase-id>` — Resume from paused state
- ✅ `./orchestrator status` — Show status
- ✅ `./orchestrator cancel` — Cancel workflow

**Migration**: Orchestrator will auto-migrate legacy `steps/` format to `checkpoint.json`. See [Migration Guide](#migration-guide-from-v10) below.

## 🎯 Core Value

**Problems Solved**:
- ❌ Model-driven workflow: Model forgets midway, subsequent scripts never run
- ❌ Manual step execution: User must know next command
- ❌ No interaction handling: Model cannot pause for user input
- ❌ No failure recovery: Validation failure blocks entire workflow

**Solution**:
- ✅ **Script-orchestrated engine**: Orchestrator auto-executes phase sequences
- ✅ **Interaction pauses**: Orchestrator pauses at user review/interview nodes, notifies model
- ✅ **Failure recovery**: Validation/DoD failure pauses workflow, model fixes and resumes
- ✅ **State persistence**: Checkpoint records phase-level state, supports resume from breakpoint

## ⭐ v2.0.0 New Features

### 1. Orchestrator Engine
- **Script-orchestrated workflow**: Auto-executes phase sequences based on intent
- **State machine**: Phase-level state transitions with dependency checking
- **No model memory needed**: Orchestrator handles entire workflow, model just responds to notifications

### 2. Interaction Pauses
- **Automatic pause**: Orchestrator pauses at user review/interview nodes
- **Dual notification**: stdout + `.lifecycle/notification.json`
- **Resume support**: Model fixes issues and calls `resume` to continue

### 3. Failure Recovery
- **Validation failure**: Orchestrator pauses, model fixes and retries
- **DoD failure**: Orchestrator pauses, model resolves and continues
- **Retry strategy**: Configurable retry count per phase

### 4. Checkpoint Manager
- **Phase-level state**: Records completed phases, current phase, phase data
- **Auto-migration**: Migrates legacy `steps/` format to `checkpoint.json`
- **Resume from breakpoint**: Load checkpoint and continue from paused phase

### 5. Intent Resolver
- **Regex matching**: Pattern-based intent recognition
- **Priority ranking**: Bug-fix (1) > PRD-change (3) > New-product (9)
- **Compound intent**: Handles multiple intents in sequence

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git

# Install as Claude Code skill
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### Usage (Orchestrator Commands)

After installation, use orchestrator commands:

```bash
# Start new product workflow
./orchestrator run --intent new-product --user-input "我想做一个任务管理工具"

# Orchestrator will:
# 1. Execute Phase 1 (auto) — Create doc structure
# 2. Pause at Phase 2 — Notify model: "Waiting for PRD review"
# 3. Model generates PRD draft
# 4. Resume: ./orchestrator resume --from-phase phase-2-draft-prd
# 5. Continue Phase 3-9...
```

**Example Conversation**:

```
You: "我想做一个任务管理工具"
Claude: [Calls ./orchestrator run --intent new-product]
        [Orchestrator pauses at Phase 2]
        [Notification: "Waiting for PRD review"]
        [Claude generates PRD draft]
        [Calls ./orchestrator resume]

You: "需求变了，要加支付功能"
Claude: [Calls ./orchestrator run --intent prd-change]
        [Orchestrator executes Phase 10 → Phase 2 → Phase 3...]
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
# Start orchestration
./orchestrator run --intent new-product --user-input "我想做一个产品"

# Resume from paused state
./orchestrator resume --from-phase phase-2-draft-prd

# Show status
./orchestrator status

# Cancel workflow
./orchestrator cancel
```

**Legacy Commands (Removed in v2.0)**:
- ~~`python -m scripts init`~~ → Use `./orchestrator run --intent new-product`
- ~~`python -m scripts validate`~~ → Orchestrator auto-validates
- ~~`python -m scripts draft`~~ → Orchestrator auto-drafts
- ~~`python -m scripts plan`~~ → Orchestrator auto-plans
- ~~All other legacy commands~~ → Use orchestrator commands

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
- **Core Mechanism**: Orchestrator handles workflow, model just responds to notifications

## 🔄 Migration Guide (from v1.0)

### Step 1: Backup Existing Project

```bash
cp -r myproject myproject_backup
```

### Step 2: Update Skill

```bash
cd ~/.claude/skills/product-lifecycle
git pull origin main
# Or re-download from GitHub
```

### Step 3: Run Migration

Orchestrator will auto-migrate legacy `steps/` format to `checkpoint.json`:

```bash
./orchestrator status
# Output:
# ⚠ Migrating from legacy steps/ format...
# ✓ Migrated 5 phases from legacy format
```

### Step 4: Verify Migration

```bash
./orchestrator status
# Should show:
# Status: migrated
# Completed Phases: [phase-1-init, phase-3-validate-prd, ...]
```

### Step 5: Use New Commands

All legacy commands have been removed. Use orchestrator commands:

| Legacy Command | New Command |
|----------------|-------------|
| `./lifecycle init` | `./orchestrator run --intent new-product` |
| `./lifecycle validate` | Orchestrator auto-validates |
| `./lifecycle draft prd` | Orchestrator auto-drafts at Phase 2 |
| `./lifecycle plan` | Orchestrator auto-plans at Phase 8 |
| `./lifecycle gate --iteration 1` | Orchestrator auto-gates at Phase 9 |
| `./lifecycle change prd` | `./orchestrator run --intent prd-change` |

### Troubleshooting

**Problem**: Migration failed

**Solution**:
1. Check `.lifecycle/steps/` directory exists
2. Check step files are valid JSON
3. Manually delete `.lifecycle/checkpoint.json` and re-run `./orchestrator status`

**Problem**: Resume doesn't work

**Solution**:
1. Check `.lifecycle/checkpoint.json` exists
2. Check `current_phase` field is set
3. Check `.lifecycle/notification.json` exists

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
