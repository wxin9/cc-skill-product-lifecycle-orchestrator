[English](README.md) | [中文](README.zh-CN.md)

# Product-Lifecycle Skill

[![GitHub license](https://img.shields.io/github/license/wxin9/cc-skill-product-lifecycle)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

A comprehensive product lifecycle management skill for Claude Code, covering everything from product design to technical architecture, iteration planning (TDD), task tracking, and 4-layer artifact validation. Each phase is enforced by scripts and cannot be skipped. All changes (PRD/code/test/iteration) trigger full-link cascade updates.

## Features

- **Phase 0: Intent Recognition** - Automatically determine user requirement type
- **Phase 1-6**: From initialization → PRD → Architecture → Test Outline → Iteration Planning
- **Phase 7**: Iteration execution + 4-layer artifact validation + test-record + auto-generated user manual
- **Phase 8**: Change handling (PRD/code/test failure cascade updates)
- **Script-Enforced Workflow**: Each phase writes checkpoint files, subsequent phases verify prerequisites, cannot skip steps
- **EARS Requirement Syntax**: PRD supports EARS pattern writing for better requirement clarity
- **IEEE 829 Test Outline**: Test outline follows IEEE 829 essentials + BDD Given/When/Then
- **Arc42-Lite Architecture**: Architecture documentation uses Arc42 Lite (suitable for small to medium projects)
- **Auto-Generated User Manual**: User manual automatically generated/updated after each iteration gate passes

## Installation

### Prerequisites

- Python 3.8 or higher
- Claude Code (optional, but recommended)

### Install as a Claude Code Skill

1. Clone this repository:
```bash
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git
```

2. Copy the skill to your Claude Code skills directory:
```bash
mkdir -p ~/.claude/skills
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### Or Use Directly

You can also use the scripts directly in any project directory:

```bash
# Initialize a new project
python -m scripts init --name "My Project"
```

## Usage with Claude Code (Recommended)

The easiest way to use this skill is through **natural language conversation** with Claude Code. After installation, you don't need to run any commands manually — just describe what you want to do:

**Examples:**

> "Help me start a new product called MyApp"

> "Write the PRD for a task management tool"

> "Design the technical architecture"

> "Plan the iteration and start development"

> "The requirement has changed, update the PRD"

Claude Code will automatically:
1. Recognize your intent (Phase 0)
2. Execute the appropriate phase workflow
3. Generate and validate all artifacts (PRD, Architecture, Test Outline, etc.)
4. Manage iteration planning and execution
5. Handle change cascading when requirements evolve

**No need to memorize commands** — just talk to Claude Code naturally, and the skill takes care of the rest.

## Manual Usage (Advanced)

> The following sections describe how to use the scripts manually. For most users, the Claude Code conversation approach above is sufficient.

## Quick Start

### 1. Initialize a New Project

```bash
# Create a new project
mkdir my-product && cd my-product

# Initialize with product-lifecycle
python -m scripts init --name "My Product"
```

### 2. Write Your PRD

```bash
# Copy the PRD template
cp ~/.claude/skills/product-lifecycle/references/doc_templates/prd_template.md Docs/product/PRD.md

# Edit and fill in your PRD
edit Docs/product/PRD.md

# Validate your PRD
python -m scripts validate --doc Docs/product/PRD.md --type prd
```

### 3. Create Technical Architecture

```bash
# Copy the architecture template
cp ~/.claude/skills/product-lifecycle/references/doc_templates/arch_template.md Docs/tech/ARCH.md

# Edit and fill in your architecture
edit Docs/tech/ARCH.md

# Validate your architecture
python -m scripts validate --doc Docs/tech/ARCH.md --type arch
```

### 4. Generate Test Outline

```bash
# Generate master test outline from PRD and ARCH
python -m scripts outline generate \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --output Docs/tests/MASTER_OUTLINE.md
```

### 5. Plan Iterations

```bash
# Generate iteration plans
python -m scripts plan \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md
```

### 6. Execute an Iteration

```bash
# Create tasks for iteration 1
python -m scripts task create --category check --iteration 1 --title "Set up development environment"
python -m scripts task create --category dev --iteration 1 --title "Implement feature F01"
python -m scripts task create --category test --iteration 1 --title "Test feature F01" --test-case-ref TST-F01-S01

# Record test results
python -m scripts test-record --iteration 1 --test-id TST-F01-S01 --status pass

# Check iteration gate
python -m scripts gate --iteration 1
```

## Documentation

- [SKILL.md](SKILL.md) - Complete skill documentation (Chinese)
- [PRD Template](references/doc_templates/prd_template.md) - Product Requirements Document template
- [Architecture Template](references/doc_templates/arch_template.md) - Technical Architecture document template (Arc42-Lite)
- [Test Outline Template](references/doc_templates/test_outline_template.md) - Master Test Outline template (IEEE 829)

## Command Reference

```bash
python -m scripts init              # Initialize project structure
python -m scripts validate          # Validate PRD or ARCH document clarity
python -m scripts task              # Task management (create / update / list / stats / gate)
python -m scripts plan              # Generate iteration plan from PRD + ARCH
python -m scripts outline           # Test outline management (generate / trace / iter-tests)
python -m scripts gate              # Check iteration gate (all tasks done?)
python -m scripts change            # Handle a change from any node (prd / code / test / iteration)
python -m scripts status            # Show overall project status
python -m scripts pause             # Pause work at current point
python -m scripts resume            # Resume from pause state
python -m scripts cancel            # Cancel the current workflow
python -m scripts test-record       # Record test case execution results
python -m scripts manual            # Generate/update user operations manual
python -m scripts step              # Step status management
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by various product lifecycle management methodologies
- Built for Claude Code users
- Thanks to all contributors

## Commercial Use

If you use this skill for commercial purposes, please include the following attribution in your product documentation, website, or other appropriate places:

```
This product uses Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
Copyright 2026 Kaiser (wxin966@gmail.com)
Licensed under Apache License 2.0
```
