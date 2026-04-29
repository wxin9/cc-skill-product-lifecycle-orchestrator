# Execution Paths (v2.3)

本文件从 `scripts/core/phases.py` 的当前 Phase registry 同步生成，用于检查 intent 路径、暂停点和 artifact 门槛是否与实现一致。

## Registry Summary

| Phase | Auto | Command | Mode | Depends On | Artifacts |
|-------|------|---------|------|------------|-----------|
| phase-0-intent | Yes | - | - | - | - |
| phase-1-analyze-solution | No | analyze_solution | - | phase-0-intent | .lifecycle/solution.json |
| phase-1-impact-report | Yes | change | - | phase-0-intent | .lifecycle/CHANGE_IMPACT.md; .lifecycle/specs/impact.json |
| phase-2-init | Yes | init | - | phase-0-intent | Docs/INDEX.md; .lifecycle/config.json; .lifecycle/dod.json; Docs/adr/INDEX.md; .lifecycle/specs/schemas/product.schema.json |
| phase-3-draft-prd | No | draft | - | phase-2-init | Docs/product/PRD.md |
| phase-4-product-spec | Yes | validate | - | phase-3-draft-prd | .lifecycle/snapshots/prd_latest.md; .lifecycle/steps/prd-score.json; .lifecycle/specs/product.spec.json |
| phase-5-draft-ued | No | draft | - | phase-4-product-spec | Docs/product/UED.md |
| phase-6-ued-spec | Yes | specs | - | phase-5-draft-ued | .lifecycle/specs/ued.spec.json |
| phase-7-draft-arch | No | draft | - | phase-6-ued-spec | Docs/tech/ARCH.md |
| phase-8-tech-spec | Yes | validate | - | phase-7-draft-arch | .lifecycle/snapshots/arch_latest.md; .lifecycle/steps/arch-score.json; .lifecycle/specs/tech.spec.json |
| phase-9-lifecycle-graph | Yes | specs | - | phase-8-tech-spec | .lifecycle/specs/lifecycle_graph.json |
| phase-10-test-spec | Yes | outline | - | phase-9-lifecycle-graph | Docs/tests/MASTER_OUTLINE.md; .lifecycle/test_graph.json; .lifecycle/specs/test.spec.json; .lifecycle/specs/lifecycle_graph.json |
| phase-11-iterations | Yes | plan | - | phase-10-test-spec | Docs/iterations/INDEX.md; .lifecycle/velocity.json |
| phase-12-iter-exec | No | gate | pause_then_command | phase-11-iterations | - |

## Intent Paths

- `new-product`: phase-0-intent -> phase-1-analyze-solution -> phase-2-init -> phase-3-draft-prd -> phase-4-product-spec -> phase-5-draft-ued -> phase-6-ued-spec -> phase-7-draft-arch -> phase-8-tech-spec -> phase-9-lifecycle-graph -> phase-10-test-spec -> phase-11-iterations -> phase-12-iter-exec
- `new-feature / prd-change`: phase-0-intent -> phase-1-impact-report -> phase-3-draft-prd -> phase-4-product-spec -> phase-5-draft-ued -> phase-6-ued-spec -> phase-7-draft-arch -> phase-8-tech-spec -> phase-9-lifecycle-graph -> phase-10-test-spec -> phase-11-iterations -> phase-12-iter-exec
- `arch-change`: phase-0-intent -> phase-1-impact-report -> phase-7-draft-arch -> phase-8-tech-spec -> phase-9-lifecycle-graph -> phase-10-test-spec -> phase-11-iterations
- `bug-fix / code-change / test-failure / gap`: phase-0-intent -> phase-1-impact-report
- `new-iteration / continue-iter`: phase-0-intent -> phase-11-iterations -> phase-12-iter-exec

## Execution Rules

- `resume` 使用 checkpoint 中保存的原始 intent，避免把 unrelated phases 拉进当前路径。
- `phase-12-iter-exec` 使用 `pause_then_command`：首次进入只暂停，恢复时才执行 DoD gate。
- `phase-1-impact-report` 是所有变更类 intent 的入口，先写 `CHANGE_IMPACT.md` 和 `.lifecycle/specs/impact.json`。
- 中间 Spec 阶段允许局部生成；`target=all` 和测试大纲阶段负责完整交叉验证。
