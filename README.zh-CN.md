[English](README.md)

# Product Lifecycle Orchestrator for Claude Code

Product Lifecycle Orchestrator 是一个 Claude Code skill，用来把产品从想法推进到 PRD、UED、技术架构、测试大纲和迭代执行，并通过 machine specs 和 Lifecycle Graph 保证 AI 执行过程可检查、可追踪。

它主要面向从零开始的新项目；已有项目也建议先从文档和 specs 重新梳理，而不是直接从代码开始。

这个仓库是公开的 Claude Code 分发仓库。真实开发维护在私有 source 仓库中完成，然后从 source 生成并发布到这里。

## 它能做什么

- 从用户想法生成 PRD、UED、技术架构、测试大纲和迭代计划。
- 把确认后的 Human Docs 转成 Product/UED/Tech/Test Specs。
- 生成 Lifecycle Graph，把需求、交互、模块、API、测试连接到一起。
- 在需求、架构、代码、测试变更前先做影响分析。
- 在需要用户确认的节点暂停，并支持从 checkpoint 恢复。
- 用 DoD gate 检查每轮迭代是否可以继续。

## 快速开始

把这个仓库安装或引用为 Claude Code skill，然后直接描述需求。

```text
使用 product-lifecycle-orchestrator。我想做一个给小团队用的任务管理工具。
```

AI 会先做意图识别，选择生命周期入口，启动或恢复流程，并在需要审核时暂停。

也可以手动运行 CLI：

```bash
./orchestrator run --user-input "我想做一个任务管理工具"
./orchestrator resume --from-phase phase-3-draft-prd
./orchestrator status
```

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

## 仓库结构

```text
SKILL.md                 Claude Code skill 指令
orchestrator             CLI wrapper
scripts/                 生命周期编排 runtime
docs/dev/                公开实现参考
manifest.json            Phase 与包元数据
skill_definition.json    Claude Code 分发元数据
```

## 生成的项目文件

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

这个 public 仓库由私有 source 仓库生成。不要直接修改这里的 generated files；修复应先进入 source，再重新发布。

## License

Apache License 2.0. See [LICENSE](LICENSE).
