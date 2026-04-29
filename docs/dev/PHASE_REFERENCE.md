# Phase Reference (v2.3)

v2.3 把 Human Docs 和 Machine Specs 显式拆成 0-12 阶段：PRD/UED/ARCH/Test 文档先给用户审阅，Product/UED/Tech/Test Specs 才是 AI 执行的 source of truth。

## Phase Registry

| Phase ID | Name | Order | Auto | Command | Mode | Depends On | Blocks | Intent Triggers |
|----------|------|-------|------|---------|------|------------|--------|-----------------|
| phase-0-intent | 意图识别 | 0 | Yes | - | - | - | phase-2-init, phase-1-impact-report | * |
| phase-1-analyze-solution | Solution Advisor | 1 | No | analyze_solution | - | phase-0-intent | phase-2-init | new-product, from-scratch |
| phase-1-impact-report | 影响分析报告 | 1 | Yes | change | - | phase-0-intent | - | new-feature, prd-change, arch-change, code-change, test-failure, bug-fix, gap |
| phase-2-init | 项目初始化 | 2 | Yes | init | - | phase-0-intent | phase-3-draft-prd | new-product, from-scratch |
| phase-3-draft-prd | AI 协作 PRD 起草 | 3 | No | draft | - | phase-2-init | phase-4-product-spec | new-product, new-feature, prd-change |
| phase-4-product-spec | Product Spec 生成与验证 | 4 | Yes | validate | - | phase-3-draft-prd | phase-5-draft-ued | new-product, new-feature, prd-change |
| phase-5-draft-ued | AI 协作 UED 设计 | 5 | No | draft | - | phase-4-product-spec | phase-6-ued-spec | new-product, new-feature, prd-change |
| phase-6-ued-spec | UED Spec 生成与验证 | 6 | Yes | specs | - | phase-5-draft-ued | phase-7-draft-arch | new-product, new-feature, prd-change |
| phase-7-draft-arch | AI 协作技术架构设计 | 7 | No | draft | - | phase-6-ued-spec | phase-8-tech-spec | new-product, new-feature, prd-change, arch-change |
| phase-8-tech-spec | Tech Spec 生成与验证 | 8 | Yes | validate | - | phase-7-draft-arch | phase-9-lifecycle-graph | new-product, new-feature, prd-change, arch-change |
| phase-9-lifecycle-graph | Lifecycle Graph / Skimmer | 9 | Yes | specs | - | phase-8-tech-spec | phase-10-test-spec | new-product, new-feature, prd-change, arch-change |
| phase-10-test-spec | Test Spec 与测试大纲生成 | 10 | Yes | outline | - | phase-9-lifecycle-graph | phase-11-iterations | new-product, new-feature, prd-change, arch-change, test-change |
| phase-11-iterations | Velocity 感知迭代规划 | 11 | Yes | plan | - | phase-10-test-spec | phase-12-iter-exec | new-product, new-feature, prd-change, arch-change, new-iteration |
| phase-12-iter-exec | 迭代执行循环 | 12 | No | gate | pause_then_command | phase-11-iterations | - | new-product, new-iteration, continue-iter |

## Intent → Phase Mapping

### new-product
1. phase-0-intent (auto) — 意图识别
2. phase-1-analyze-solution (pause) — Solution Advisor
3. phase-2-init (auto) — 项目初始化
4. phase-3-draft-prd (pause) — AI 协作 PRD 起草
5. phase-4-product-spec (auto) — Product Spec 生成与验证
6. phase-5-draft-ued (pause) — AI 协作 UED 设计
7. phase-6-ued-spec (auto) — UED Spec 生成与验证
8. phase-7-draft-arch (pause) — AI 协作技术架构设计
9. phase-8-tech-spec (auto) — Tech Spec 生成与验证
10. phase-9-lifecycle-graph (auto) — Lifecycle Graph / Skimmer
11. phase-10-test-spec (auto) — Test Spec 与测试大纲生成
12. phase-11-iterations (auto) — Velocity 感知迭代规划
13. phase-12-iter-exec (pause, gate on resume) — 迭代执行循环

### new-feature / prd-change
1. phase-0-intent (auto) — 意图识别
2. phase-1-impact-report (auto) — 影响分析报告
3. phase-3-draft-prd (pause) — AI 协作 PRD 起草
4. phase-4-product-spec (auto) — Product Spec 生成与验证
5. phase-5-draft-ued (pause) — AI 协作 UED 设计
6. phase-6-ued-spec (auto) — UED Spec 生成与验证
7. phase-7-draft-arch (pause) — AI 协作技术架构设计
8. phase-8-tech-spec (auto) — Tech Spec 生成与验证
9. phase-9-lifecycle-graph (auto) — Lifecycle Graph / Skimmer
10. phase-10-test-spec (auto) — Test Spec 与测试大纲生成
11. phase-11-iterations (auto) — Velocity 感知迭代规划
12. phase-12-iter-exec (pause, gate on resume) — 迭代执行循环

### arch-change
1. phase-0-intent (auto) — 意图识别
2. phase-1-impact-report (auto) — 影响分析报告
3. phase-7-draft-arch (pause) — AI 协作技术架构设计
4. phase-8-tech-spec (auto) — Tech Spec 生成与验证
5. phase-9-lifecycle-graph (auto) — Lifecycle Graph / Skimmer
6. phase-10-test-spec (auto) — Test Spec 与测试大纲生成
7. phase-11-iterations (auto) — Velocity 感知迭代规划

### bug-fix / code-change / test-failure / gap
1. phase-0-intent (auto) — 意图识别
2. phase-1-impact-report (auto) — 影响分析报告

### new-iteration / continue-iter
1. phase-0-intent (auto) — 意图识别
2. phase-11-iterations (auto) — Velocity 感知迭代规划
3. phase-12-iter-exec (pause, gate on resume) — 迭代执行循环

## Source Of Truth Chain

1. Human PRD -> Product Spec (`.lifecycle/specs/product.spec.json`)
2. Product Spec -> Human UED -> UED Spec (`.lifecycle/specs/ued.spec.json`)
3. Product/UED Specs -> Human ARCH -> Tech Spec (`.lifecycle/specs/tech.spec.json`)
4. Product/UED/Tech Specs -> Lifecycle Graph (`.lifecycle/specs/lifecycle_graph.json`)
5. Lifecycle Graph -> Test Spec + MASTER_OUTLINE + TestGraph (`.lifecycle/specs/test.spec.json`, `Docs/tests/MASTER_OUTLINE.md`, `.lifecycle/test_graph.json`)

Specs 是最终 source of truth；Human Docs 是用户审阅界面。若二者冲突，先更新 Specs 并重新生成 Graph，再继续实现。

## Pause Points

| Phase | Pause Reason | User/Model Action |
|-------|--------------|-------------------|
| phase-1-analyze-solution | 等待用户选择实现方案 | 生成或审阅对应 artifact 后 resume |
| phase-3-draft-prd | 等待用户审核 PRD 草案，补充 [❓待确认] 标注处 | 生成或审阅对应 artifact 后 resume |
| phase-5-draft-ued | 等待用户审核 UED 草案，确认核心界面、流程、状态和错误反馈 | 生成或审阅对应 artifact 后 resume |
| phase-7-draft-arch | 等待用户审核技术架构草案，对 ADR 做决策 | 生成或审阅对应 artifact 后 resume |
| phase-12-iter-exec | 等待用户完成开发任务，运行测试，通过 DoD 检查 | 生成或审阅对应 artifact 后 resume |

## Artifact Requirements

### phase-1-analyze-solution
- `.lifecycle/solution.json` (min 100 bytes)

### phase-1-impact-report
- `.lifecycle/CHANGE_IMPACT.md` (min 100 bytes)
- `.lifecycle/specs/impact.json` (min 100 bytes)

### phase-2-init
- `Docs/INDEX.md` (min 200 bytes)
- `.lifecycle/config.json` (min 100 bytes)
- `.lifecycle/dod.json` (min 50 bytes)
- `Docs/adr/INDEX.md` (min 80 bytes)
- `.lifecycle/specs/schemas/product.schema.json` (min 100 bytes)

### phase-3-draft-prd
- `Docs/product/PRD.md` (min 800 bytes)

### phase-4-product-spec
- `.lifecycle/snapshots/prd_latest.md` (min 800 bytes)
- `.lifecycle/steps/prd-score.json` (min 30 bytes)
- `.lifecycle/specs/product.spec.json` (min 200 bytes)

### phase-5-draft-ued
- `Docs/product/UED.md` (min 400 bytes)

### phase-6-ued-spec
- `.lifecycle/specs/ued.spec.json` (min 200 bytes)

### phase-7-draft-arch
- `Docs/tech/ARCH.md` (min 800 bytes)

### phase-8-tech-spec
- `.lifecycle/snapshots/arch_latest.md` (min 800 bytes)
- `.lifecycle/steps/arch-score.json` (min 30 bytes)
- `.lifecycle/specs/tech.spec.json` (min 200 bytes)

### phase-9-lifecycle-graph
- `.lifecycle/specs/lifecycle_graph.json` (min 200 bytes)

### phase-10-test-spec
- `Docs/tests/MASTER_OUTLINE.md` (min 600 bytes)
- `.lifecycle/test_graph.json` (min 200 bytes)
- `.lifecycle/specs/test.spec.json` (min 200 bytes)
- `.lifecycle/specs/lifecycle_graph.json` (min 200 bytes)

### phase-11-iterations
- `Docs/iterations/INDEX.md` (min 200 bytes)
- `.lifecycle/velocity.json` (min 50 bytes)

## Compatibility Notes

旧 v2.2 Phase ID 会在 checkpoint 读取时迁移到 v2.3 ID。常见映射：

| v2.2 | v2.3 |
|------|------|
| phase-4-validate-prd | phase-4-product-spec |
| phase-6-draft-arch | phase-7-draft-arch |
| phase-7-validate-arch | phase-8-tech-spec |
| phase-8-test-outline | phase-10-test-spec |
| phase-9-iterations | phase-11-iterations |
| phase-10-iter-exec | phase-12-iter-exec |
| phase-11-change | phase-1-impact-report |
