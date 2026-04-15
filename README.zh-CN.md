[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

> **AI 协作 + 脚本强制门控** 的产品全生命周期管理技能 — 从 PRD 到交付，确保每一步都正确完成

## 🎯 核心价值

**解决问题**：
- ❌ 文档散落、版本混乱
- ❌ 流程靠自律、容易跳步
- ❌ 变更级联断裂
- ❌ 测试覆盖盲目

**解决方案**：
- ✅ 脚本强制门控（`sys.exit(1)` 物理阻断）
- ✅ 测试知识图谱驱动
- ✅ 维度自适应场景生成
- ✅ 自动变更影响分析

## ⭐ v1.1.0 新特性

### 1. 测试知识图谱 (Test Knowledge Graph)
- **结构化测试模型**：Feature → Scenario → Rule 层级结构
- **依赖关系图谱**：自动追踪上下游、API、数据实体依赖
- **存储格式**：`.lifecycle/test_graph.json`

### 2. 维度驱动场景生成
- **4 类防御场景**：每个维度自动生成 happy/boundary/error/data
- **项目类型自适应**：
  - Web → `[UI][API][AUTH][DATA][PERF][XSS]`
  - CLI → `[CLI][ARGS][IO][ERROR]`
  - Data-Pipeline → `[DATA][ASYNC][IDEMPOTENCY][VOLUME][SCHEMA][BACKFILL]`
  - Mobile → `[UI][OFFLINE][SYNC][PERF][BATTERY][PERMISSION]`
  - Microservices → `[API][RPC][CIRCUIT][CACHE][AUTH][TRACE]`

### 3. 图谱式影响分析
- **BFS 遍历**：精准计算变更影响范围
- **自动级联**：修改 PRD → 自动识别受影响的测试和迭代
- **距离和优先级**：输出影响距离，按优先级排序

### 4. 新增命令
- `outline dependency-review` — 审核功能依赖声明
- `outline migrate` — 旧版测试大纲迁移到图谱格式

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git

# 安装为 Claude Code 技能
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### 使用（自然语言对话）

安装后直接和 Claude Code 对话即可：

```
你: "帮我做一个任务管理工具的 PRD"
Claude: [自动起草 PRD 草案] → [你审核修改] → [验证通过自动快照]

你: "设计技术架构"
Claude: [自动起草架构文档] → [生成测试图谱] → [规划迭代]

你: "需求变了，用户登录要加二次认证"
Claude: [识别变更] → [图谱遍历影响分析] → [列出受影响的测试和迭代] → [级联更新]
```

## 💡 核心功能

| 功能 | 说明 |
|------|------|
| **AI 协作起草** | Claude 主动起草 PRD/架构文档，你做审稿人 |
| **脚本强制门控** | `sys.exit(1)` 物理阻断，无法跳步 |
| **复合意图识别** | "修了 bug 顺便调整需求" — 同时识别多个意图并排序执行 |
| **项目类型自动识别** | 5 种类型，测试维度自适应 |
| **自动快照 & Diff** | 验证通过自动快照，变更时自动对比 |
| **Velocity 追踪** | 估算 vs 实际工时 + ASCII 趋势图 |
| **DoD 门控扩展** | lint/覆盖率/代码审查，warn 或 fail |
| **ADR 管理** | 架构决策记录全生命周期管理 |
| **风险登记册** | 概率×影响矩阵自动评级 |
| **Sprint Review** | 门控通过自动生成评审材料 |

## 📖 工作流程

```
阶段 0: 意图识别
   ↓
阶段 1: 项目初始化 → DoD/Risk/ADR 初始化
   ↓
阶段 2: AI 起草 PRD → 你审核修改
   ↓
阶段 3: 验证 PRD → 自动快照
   ↓
阶段 4: 架构访谈
   ↓
阶段 5: AI 起草架构 → 包含 ADR 初稿
   ↓
阶段 6: 验证架构 → 自动快照
   ↓
阶段 7: 生成测试图谱 + 自适应大纲
   ↓
阶段 8: 规划迭代 → Velocity 估算
   ↓
阶段 9: 执行迭代 → 4 层门控验证
   ↓
阶段 10: 变更处理 → 图谱遍历级联更新
```

## 🛠️ 常用命令

```bash
# 初始化项目
python -m scripts init --name "项目名"

# AI 协作起草 PRD
python -m scripts draft prd --description "产品描述"

# 验证文档
python -m scripts validate --doc Docs/product/PRD.md --type prd

# 生成测试图谱和大纲
python -m scripts outline generate --prd PRD.md --arch ARCH.md

# 规划迭代
python -m scripts plan

# 迭代门控（4 层验证）
python -m scripts gate --iteration 1

# 变更处理（自动图谱遍历）
python -m scripts change prd

# 依赖审核
python -m scripts outline dependency-review
```

## 📊 生成的项目结构

```
Docs/
├── product/PRD.md          # PRD 文档
├── tech/ARCH.md            # 架构文档
├── tests/MASTER_OUTLINE.md # 测试大纲
└── iterations/iter-N/      # 迭代计划 + 测试记录 + Sprint Review

.lifecycle/
├── test_graph.json         # 测试知识图谱 ⭐ v1.1.0
├── config.json             # 项目配置
├── dod.json                # DoD 规则
├── risk_register.json      # 风险登记册
├── velocity.json           # 速度追踪
└── snapshots/              # 文档快照
```

## 🎓 模型兼容性

- **推荐**：Claude Sonnet 4+ — 最佳起草质量
- **可用**：Claude Haiku — 可完成全流程，起草质量略低
- **核心机制**：脚本强制门控不依赖模型能力

## 📄 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)

## 🏢 商业使用

商业使用请在产品文档中包含归属声明：

```
本产品使用 Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
版权所有 2026 Kaiser (wxin966@gmail.com)
Apache License 2.0
```

---

**完整更新日志**: [CHANGELOG.md](CHANGELOG.md) | **GitHub**: [wxin9/cc-skill-product-lifecycle](https://github.com/wxin9/cc-skill-product-lifecycle)
