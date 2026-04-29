[中文](README.zh-CN.md)

# Product Lifecycle Orchestrator for Claude Code

Product Lifecycle Orchestrator is a Claude Code skill for building products through a controlled lifecycle: clarify requirements, generate human-readable docs, convert them into machine specs, build the lifecycle graph, plan tests, and execute iterations with gates.

It is designed for greenfield product development, and can also be used to restart an existing project from documentation first.

This repository is the public Claude Code distribution. Runtime development happens in a private source repository, then this package is generated and published from that source.

## What It Does

- Guides a new product from idea to PRD, UED, architecture, test plan, and iteration plan.
- Converts approved human docs into machine-readable Product/UED/Tech/Test Specs.
- Builds a Lifecycle Graph that connects requirements, UX, technical modules, APIs, and tests.
- Runs impact analysis before requirement, architecture, code, or test changes.
- Pauses at human review points and resumes from the saved checkpoint.
- Uses DoD gates to check whether an iteration is ready to continue.

## Quick Start

Install or reference this repository as a Claude Code skill, then describe what you need in natural language.

```text
Use product-lifecycle-orchestrator. I want to build a task manager for a small team.
```

The AI should identify your intent, choose the lifecycle entry point, start or resume the workflow, and pause when review is needed.

Manual CLI usage is also supported:

```bash
./orchestrator run --user-input "I want to build a task manager"
./orchestrator resume --from-phase phase-3-draft-prd
./orchestrator status
```

## Core Flow

```text
Idea
  -> Solution Advisor
  -> PRD
  -> Product Spec
  -> UED
  -> UED Spec
  -> Architecture
  -> Tech Spec
  -> Lifecycle Graph
  -> Test Spec + Test Outline
  -> Iteration Plan
  -> Iteration Execution Gate
```

Specs are the source of truth. Human docs are the review surface.

## Repository Layout

```text
SKILL.md                 Claude Code skill instructions
orchestrator             CLI wrapper
scripts/                 Runtime orchestration engine
docs/dev/                Public implementation references
manifest.json            Phase and package metadata
skill_definition.json    Claude Code distribution metadata
```

## Generated Project Files

```text
Docs/
  product/PRD.md
  product/UED.md
  tech/ARCH.md
  tests/MASTER_OUTLINE.md
  iterations/

.lifecycle/
  checkpoint.json
  notification.json
  CHANGE_IMPACT.md
  specs/
    product.spec.json
    ued.spec.json
    tech.spec.json
    test.spec.json
    lifecycle_graph.json
```

## Source And Releases

This public repository is generated from the private source repository. Do not patch generated files directly here; fixes should be made in source and republished.

## License

Apache License 2.0. See [LICENSE](LICENSE).
