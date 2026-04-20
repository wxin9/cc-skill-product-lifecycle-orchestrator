[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

> **脚本编排 + 交互暂停**的产品全生命周期管理 — orchestrator 自动执行 Phase 序列，在交互节点暂停，通知模型处理，然后恢复

## 🎯 核心价值

**解决的问题**：
- ❌ 模型驱动工作流：模型中途失忆，后续脚本不执行
- ❌ 手动步骤执行：用户必须知道下一步命令
- ❌ 无交互处理：模型无法暂停等待用户输入
- ❌ 无失败恢复：验证失败阻塞整个工作流

**解决方案**：
- ✅ **脚本编排引擎**：Orchestrator 自动执行 Phase 序列
- ✅ **交互暂停**：Orchestrator 在用户审核/访谈节点暂停，通知模型
- ✅ **失败恢复**：验证/DoD 失败暂停工作流，模型修复后恢复
- ✅ **状态持久化**：Checkpoint 记录 Phase 级别状态，支持从断点恢复

## ⭐ 新特性

### v2.0.1 — Checkpoint 跟踪改进

- **Intent 始终记录**：Intent 和 user_input 现在每次运行时都会更新（不再仅限初始化）
- **Resume 修复**：`get_phases_by_intent("resume")` 正确返回所有 Phase
- **自动 PRD 快照**：SnapshotManager 集成到 validate 命令 — 验证后自动创建快照
- **Phase 序列修复**：Phase 10 depends_on 已修正；prd-change 现在包含 Phase 7-8

### v2.0.0 — Orchestrator 架构

#### 1. Orchestrator 引擎
- **脚本编排工作流**：根据意图自动执行 Phase 序列
- **状态机**：Phase 级别状态转换，依赖检查
- **无需模型记忆**：Orchestrator 处理整个工作流，模型只需响应通知

#### 2. 交互暂停
- **自动暂停**：Orchestrator 在用户审核/访谈节点暂停
- **双重通知**：stdout + `.lifecycle/notification.json`
- **恢复支持**：模型修复问题后调用 `resume` 继续

#### 3. 失败恢复
- **验证失败**：Orchestrator 暂停，模型修复后重试
- **DoD 失败**：Orchestrator 暂停，模型解决后继续
- **重试策略**：每个 Phase 可配置重试次数

#### 4. Checkpoint 管理器
- **Phase 级别状态**：记录已完成 Phase、当前 Phase、Phase 数据
- **自动迁移**：迁移旧版 `steps/` 格式到 `checkpoint.json`
- **断点恢复**：加载 checkpoint 从暂停 Phase 继续
- **内存缓存**：带延迟写入的内存缓存 — 25 倍 I/O 减少
- **线程安全**：基于 RLock 的并发控制

#### 5. 意图解析器
- **正则匹配**：基于模式的意图识别
- **优先级排序**：Bug-fix (1) > PRD-change (3) > New-product (9)
- **复合意图**：按顺序处理多个意图

#### 6. 并行执行
- **ParallelExecutor**：使用 Kahn 算法进行拓扑排序的依赖图分析
- **并行分组**：独立的 Phase 并发执行（通过 `ORCHESTRATOR_PARALLEL=1` 启用）

#### 7. 条件分支
- **ConditionEvaluator**：安全地评估条件表达式，支持动态执行路径
- **支持的运算符**：比较（`==`、`!=`、`<`、`>`、`<=`、`>=`）、逻辑（`and`、`or`、`not`）、成员（`in`、`not in`）

#### 8. 回滚机制
- **文件快照**：每个 Phase 执行前自动创建 `Docs/` 和 `.lifecycle/` 的快照
- **回滚到任意节点**：恢复 checkpoint 状态和文件到任意历史回滚点
- **回滚 CLI**：`./orchestrator rollback --id <rollback-id>`

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git

# 安装为 Claude Code 技能
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### 使用（Orchestrator 命令）

安装后，使用 orchestrator 命令：

```bash
# 启动新产品工作流
./orchestrator run --intent new-product --user-input "我想做一个任务管理工具"

# Orchestrator 会：
# 1. 执行 Phase 1（自动）— 创建文档结构
# 2. 在 Phase 2 暂停 — 通知模型："等待 PRD 审核"
# 3. 模型生成 PRD 草案
# 4. 恢复：./orchestrator resume --from-phase phase-2-draft-prd
# 5. 继续 Phase 3-9...
```

**示例对话**：

```
你："我想做一个任务管理工具"
Claude: [调用 ./orchestrator run --intent new-product]
        [Orchestrator 在 Phase 2 暂停]
        [通知："等待 PRD 审核"]
        [Claude 生成 PRD 草案]
        [调用 ./orchestrator resume]

你："需求变了，要加支付功能"
Claude: [调用 ./orchestrator run --intent prd-change]
        [Orchestrator 执行 Phase 10 → Phase 2 → Phase 3...]

你："登录流程发现 bug"
Claude: [调用 ./orchestrator run --intent bug-fix]
        [Orchestrator 执行 Phase 10 故障处理 → 暂停等待修复]
```

## 💡 核心功能

| 功能 | 说明 |
|------|------|
| **AI 协作起草** | Claude 主动起草 PRD/架构，你做审稿人 |
| **脚本强制门控** | `sys.exit(1)` 物理阻断，无法跳步 |
| **复合意图识别** | "修了 bug 顺便调整需求" — 识别多个意图，排序执行 |
| **项目类型自动识别** | 5 种类型（Web/CLI/Mobile/Data/Microservices），测试维度自适应 |
| **自动快照 & Diff** | 验证通过自动快照，变更时自动对比 |
| **Velocity 追踪** | 估算 vs 实际工时 + ASCII 趋势图 |
| **DoD 门控扩展** | lint/覆盖率/代码审查，warn 或 fail |
| **ADR 管理** | 架构决策记录全生命周期管理 |
| **风险登记册** | 概率×影响矩阵自动评级 |
| **Sprint Review** | 门控通过自动生成评审材料 |
| **并行执行** | 独立 Phase 通过拓扑排序并发运行 |
| **条件分支** | 基于项目类型/条件的动态执行路径 |
| **回滚** | 恢复到任意历史 checkpoint，含文件快照还原 |

## 📖 工作流程

```
Phase 0: 意图识别
   ↓
Phase 1: 项目初始化 → DoD/Risk/ADR 初始化
   ↓
Phase 2: AI 起草 PRD → 你审核修改
   ↓
Phase 3: 验证 PRD → 自动快照
   ↓
Phase 4: 架构访谈
   ↓
Phase 5: AI 起草架构 → 包含 ADR 初稿
   ↓
Phase 6: 验证架构 → 自动快照
   ↓
Phase 7: 生成测试图谱 + 自适应大纲
   ↓
Phase 8: 规划迭代 → Velocity 估算
   ↓
Phase 9: 执行迭代 → 4 层门控验证
   ↓
Phase 10: 处理变更 → 图谱遍历级联更新
```

### 变更意图路径

| 意图 | Phase 序列 |
|------|-----------|
| `new-product` | Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 |
| `prd-change` | Phase 10 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 |
| `arch-change` | Phase 10 → 5 → 6 → 7 → 8 → 9 |
| `bug-fix` | Phase 10 → 暂停等待修复 |
| `new-iteration` | Phase 8 → 9 |
| `resume` | 从 checkpoint 继续 |

## 🛠️ 命令

### Orchestrator 命令

```bash
# 启动编排
./orchestrator run --intent new-product --user-input "我想做一个产品"

# 从暂停状态恢复
./orchestrator resume --from-phase phase-2-draft-prd

# 显示状态
./orchestrator status

# 取消工作流
./orchestrator cancel

# 并行执行（可选启用）
ORCHESTRATOR_PARALLEL=1 ./orchestrator run --intent new-product --user-input "..."
```

### 旧命令（v2.0 已移除）

- ~~`python -m scripts init`~~ → 使用 `./orchestrator run --intent new-product`
- ~~`python -m scripts validate`~~ → Orchestrator 自动验证
- ~~`python -m scripts draft`~~ → Orchestrator 自动起草
- ~~`python -m scripts plan`~~ → Orchestrator 自动规划
- ~~所有其他旧命令~~ → 使用 orchestrator 命令

## 📊 生成的项目结构

```
Docs/
├── product/PRD.md          # PRD 文档
├── tech/ARCH.md            # 架构文档
├── tests/MASTER_OUTLINE.md # 测试大纲
└── iterations/iter-N/      # 迭代计划 + 测试记录 + Sprint Review

.lifecycle/
├── checkpoint.json         # Phase 级别状态 (v2.0+)
├── notification.json       # 暂停/失败通知 (v2.0+)
├── test_graph.json         # 测试知识图谱
├── config.json             # 项目配置
├── dod.json                # DoD 规则
├── risk_register.json      # 风险登记册
├── velocity.json           # Velocity 追踪
└── snapshots/              # 文档快照 + 回滚点
```

## 🎓 模型兼容性

- **推荐**：Claude Sonnet 4+ — 最佳起草质量
- **可用**：Claude Haiku — 可完成完整工作流，起草质量稍低
- **核心机制**：Orchestrator 处理工作流，模型只需响应通知

## 📚 文档

- [CONTRIBUTING.md](docs/CONTRIBUTING.md) — 开发指南
- [CODE_OF_CONDUCT.md](docs/CODE_OF_CONDUCT.md) — 贡献者公约
- [SECURITY.md](docs/SECURITY.md) — 安全策略
- [CHANGELOG.md](CHANGELOG.md) — 版本历史

## 📄 许可证

Apache License 2.0 — 见 [LICENSE](LICENSE)

## 🏢 商业使用

商业使用请在产品文档中注明出处：

```
本产品使用 Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
Copyright 2026 Kaiser (wxin966@gmail.com)
Apache License 2.0
```

---

**完整变更日志**：[CHANGELOG.md](CHANGELOG.md) | **GitHub**：[wxin9/cc-skill-product-lifecycle](https://github.com/wxin9/cc-skill-product-lifecycle)
