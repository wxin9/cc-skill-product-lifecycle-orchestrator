[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle Orchestrator

Product Lifecycle Orchestrator is a Claude Code skill for building products through a controlled lifecycle: clarify requirements, generate human-readable docs, convert them into machine specs, build the lifecycle graph, plan tests, and execute iterations with gates.

It is designed for greenfield product development, and can also be used to restart an existing project from documentation first.

## What It Does

- Guides a new product from idea to PRD, UED, architecture, test plan, and iteration plan.
- Converts approved human docs into machine-readable Product/UED/Tech/Test Specs.
- Builds a Lifecycle Graph that connects requirements, UX, technical modules, APIs, and tests.
- Runs impact analysis before requirement, architecture, code, or test changes.
- Pauses at human review points and resumes from the saved checkpoint.
- Uses DoD gates to check whether an iteration is ready to continue.
- Keeps source and `publish/` skill distribution files aligned.

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

## Quick Start

The simplest way to use this skill is to call the skill and describe what you need in natural language.

```text
Use product-lifecycle-orchestrator. I want to build a task manager for a small team.
```

The AI should then:

1. Identify your intent.
2. Decide the correct lifecycle entry point.
3. Start or resume the orchestrated workflow.
4. Pause when it needs your review or confirmation.

You do not need to choose an intent yourself in normal use.

If you are running the orchestrator manually, pass your request as `--user-input`; `--intent` defaults to `auto`.

```bash
./orchestrator run --user-input "I want to build a task manager"
```

When the workflow pauses, complete or review the requested artifact, then resume:

```bash
./orchestrator resume --from-phase phase-3-draft-prd
```

Check current state:

```bash
./orchestrator status
```

Cancel the current workflow:

```bash
./orchestrator cancel
```

## What The AI Decides

The first step is always intent recognition. Based on your request and the current project state, the AI chooses one of these paths:

| Intent | When It Is Chosen |
|---|---|
| `new-product` | You are starting a new product from scratch |
| `new-feature` | You want to add a feature to an existing lifecycle project |
| `prd-change` | Requirements changed |
| `arch-change` | Architecture or technology choices changed |
| `bug-fix` | You need to fix a bug with impact tracking |
| `code-change` | Code changed and the impact should be recorded |
| `test-change` | Test scope or coverage needs updating |
| `new-iteration` | A new implementation iteration should start |
| `continue-iter` | The current iteration should continue |

Manual intent selection is still available when you want to force a path:

```bash
./orchestrator run --intent prd-change --user-input "Add paid subscription support"
```

## Generated Files

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
  test_graph.json
  specs/
    product.spec.json
    ued.spec.json
    tech.spec.json
    test.spec.json
    lifecycle_graph.json
    impact.json
```

## Change Workflow

For changes, describe the change directly. The AI identifies the change type and generates an impact report before continuing.

```text
Use product-lifecycle-orchestrator. Requirements changed: add paid subscription support.
```

Review:

- `.lifecycle/CHANGE_IMPACT.md`
- `.lifecycle/specs/impact.json`

Then update the affected docs/specs/tests as directed by the workflow.

## Development References

Detailed implementation docs live under `docs/dev/`:

- `docs/dev/PHASE_REFERENCE.md`
- `docs/dev/EXECUTION_PATHS.md`
- `docs/dev/LIFECYCLE_IMPLEMENTATION_PLAN.md`
- `docs/dev/OPTIMIZATION_DRAFT.md`

## Verification

```bash
python3 -m pytest -q
python3 - <<'PY'
from scripts.core.lifecycle_specs import validate_specs
print(validate_specs('.'))
PY
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
