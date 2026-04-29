[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle Orchestrator

Product Lifecycle Orchestrator 是一个 Claude Code skill，用来把产品从想法推进到需求、UED、技术架构、测试大纲和迭代执行，并通过 machine specs 和 Lifecycle Graph 保证 AI 执行过程可检查、可追踪。

它主要面向从零开始的新项目；已有项目也建议先从文档和 specs 重新梳理，而不是直接从代码开始。

## 它能做什么

- 从用户想法生成 PRD、UED、技术架构、测试大纲和迭代计划。
- 把确认后的 Human Docs 转成 Product/UED/Tech/Test Specs。
- 生成 Lifecycle Graph，把需求、交互、模块、API、测试连接到一起。
- 在需求、架构、代码、测试变更前先做影响分析。
- 在需要用户确认的节点暂停，并支持从 checkpoint 恢复。
- 用 DoD gate 检查每轮迭代是否可以继续。
- 同步维护 source 与 `publish/` 分发文件。

## 核心流程

```text
产品想法
  -> Solution Advisor
  -> PRD
  -> Product Spec
  -> UED
  -> UED Spec
  -> 技术架构
  -> Tech Spec
  -> Lifecycle Graph
  -> Test Spec + 测试大纲
  -> 迭代计划
  -> 迭代执行 gate
```

Specs 是最终 source of truth。Human Docs 是给用户确认和审阅的界面。

## 快速开始

最简单的使用方式：调用这个 skill，然后直接说需求。

```text
使用 product-lifecycle-orchestrator。我想做一个给小团队用的任务管理工具。
```

AI 接下来会：

1. 先做意图识别。
2. 根据你的需求和当前项目状态，判断应该从哪一步开始。
3. 启动或恢复对应的生命周期流程。
4. 在需要你确认或审核的时候暂停。

正常使用时，用户不需要自己选择 intent。

如果你手动运行 orchestrator，只需要传入 `--user-input`；`--intent` 默认就是 `auto`。

```bash
./orchestrator run --user-input "我想做一个任务管理工具"
```

流程暂停后，按通知生成或审核对应文件，然后恢复：

```bash
./orchestrator resume --from-phase phase-3-draft-prd
```

查看当前状态：

```bash
./orchestrator status
```

取消当前流程：

```bash
./orchestrator cancel
```

## AI 会判断什么

第一步永远是意图识别。AI 会根据你的描述和当前项目状态，选择合适的路径：

| Intent | 什么时候会被选择 |
|---|---|
| `new-product` | 从零开始一个新产品 |
| `new-feature` | 给已有 lifecycle 项目新增功能 |
| `prd-change` | 产品需求发生变化 |
| `arch-change` | 技术架构或技术选型变化 |
| `bug-fix` | 修复 bug，并记录影响范围 |
| `code-change` | 记录并分析代码层面的变更 |
| `test-change` | 更新测试范围或测试覆盖 |
| `new-iteration` | 开始下一轮迭代 |
| `continue-iter` | 继续当前迭代 |

如果你明确想强制走某条路径，也可以手动指定 intent：

```bash
./orchestrator run --intent prd-change --user-input "增加付费订阅能力"
```

## 生成的文件

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

## 变更流程

需求、架构、代码或测试发生变化时，直接告诉 AI 发生了什么。AI 会先识别变更类型，生成影响分析，再继续后续文档和 specs 刷新。

```text
使用 product-lifecycle-orchestrator。需求变了：增加付费订阅能力。
```

重点查看：

- `.lifecycle/CHANGE_IMPACT.md`
- `.lifecycle/specs/impact.json`

然后按工作流提示更新受影响的文档、specs 和测试。

## 开发文档

更详细的实现说明放在 `docs/dev/`：

- `docs/dev/PHASE_REFERENCE.md`
- `docs/dev/EXECUTION_PATHS.md`
- `docs/dev/LIFECYCLE_IMPLEMENTATION_PLAN.md`
- `docs/dev/OPTIMIZATION_DRAFT.md`

## 验证

```bash
python3 -m pytest -q
python3 - <<'PY'
from scripts.core.lifecycle_specs import validate_specs
print(validate_specs('.'))
PY
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
