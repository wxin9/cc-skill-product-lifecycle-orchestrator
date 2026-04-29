---
name: product-lifecycle-orchestrator
description: 产品生命周期编排。当用户提到「Product Lifecycle Orchestrator」「product-lifecycle-orchestrator」「产品设计」「PRD」「需求文档」「技术架构」「迭代规划」「从零开始做一个产品」「整理项目文档」「迭代门控」「DoD」「machine spec」「Lifecycle Graph」时立即触发。核心能力：先做意图识别，再自动选择生命周期入口，执行 PRD/UED/Tech/Test Specs、Lifecycle Graph、影响分析和迭代 gate。
compatibility: Python 3.8+ (with `from __future__ import annotations`)
---

# Product Lifecycle Orchestrator v2.3

**一句话**：Product Lifecycle Orchestrator 是一个产品开发生命周期编排 skill。用户直接说需求，AI 先做意图识别，再由 `./orchestrator` 手动 CLI 或内置流程推进后续 Phase。

**v2.3 新增**：PRD/UED/ARCH/Test human docs 之后生成 `.lifecycle/specs/` 下的 Product/UED/Tech/Test Specs，并生成 `lifecycle_graph.json` 支撑影响分析和测试覆盖。`resume` 现在继承 checkpoint 原始 intent；Phase 12 先暂停等待开发，再在 resume 时执行 gate。

**核心能力**：

| 能力 | 说明 |
|------|------|
| 脚本编排引擎 | Orchestrator 自动执行 Phase 序列，无需模型记忆下一步 |
| 意图识别 | 正则匹配 + 优先级排序，支持复合意图 |
| 交互暂停 | 遇到用户审核、访谈等节点自动暂停，通知模型 |
| 失败恢复 | 验证失败、DoD 失败时暂停，修复后 resume 继续 |
| 状态持久化 | Checkpoint 记录 Phase 级别状态，支持断点续做 |
| Machine Specs | 生成 Product/UED/Tech/Test Specs，作为 AI 执行 source of truth |
| Lifecycle Graph | 连接需求、交互、技术、测试和影响分析 |

---

## 当前入口

Product Lifecycle Orchestrator 的 skill 名称是 `product-lifecycle-orchestrator`，手动 CLI 入口是 `./orchestrator`。

- `./orchestrator run --user-input "<输入>"` — 启动编排，默认自动识别 intent
- `./orchestrator run --intent <intent> --user-input "<输入>"` — 强制指定 intent
- `./orchestrator run --from-phase <phase-id>` — 从指定阶段开始
- `./orchestrator resume --from-phase <phase-id> [--user-input "<输入>"]` — 恢复执行（可选更新用户输入上下文）
- `./orchestrator status` — 查看状态
- `./orchestrator cancel` — 取消流程
- `./orchestrator rollback --list` — 列出所有回滚点
- `./orchestrator rollback --rollback-point-id <id>` — 回滚到指定点

---

## 快速开始

### Phase 0 — 意图识别（必须，每次调用的第一步）

**模型行为**：
1. 读取用户输入
2. 默认调用 `./orchestrator run --user-input "<用户输入>"`，由 orchestrator 自动识别 intent
3. Orchestrator 自动执行 Phase 序列
4. 遇到暂停节点时，orchestrator 会通知模型

**意图类型**：

| 意图 | 说明 | 触发关键词 |
|------|------|-----------|
| `new-product` | 新产品（从零开始） | "新产品"、"从零开始"、"做一个产品" |
| `from-scratch` | 从头搭建（仅 Phase 0→1→2，不含 PRD/ARCH） | "从零开始做"、"全新项目" |
| `new-feature` | 新增功能 | "增加功能"、"新需求"、"新功能" |
| `prd-change` | 需求变更 | "需求变了"、"PRD 改了"、"调整需求" |
| `code-change` | 代码变更 | "修改了模块"、"重构"、"代码变更" |
| `arch-change` | 架构调整 | "换数据库"、"换架构"、"重构架构" |
| `bug-fix` | Bug 修复 | "报错"、"测试失败"、"bug"、"修复" |
| `test-failure` | 测试失败修复 | "测试挂了"、"CI 失败" |
| `gap` | 缺口分析 | "差距分析"、"gap 分析" |
| `test-change` | 测试变更 | "改测试用例"、"更新测试" |
| `new-iteration` | 新迭代 | "下一个迭代"、"迭代 N"、"新迭代" |
| `continue-iter` | 继续当前迭代 | "继续迭代"、"接着开发" |

**示例**：
```bash
# 用户: "我想做一个产品"
./orchestrator run --user-input "我想做一个产品"

# 用户: "需求变了，要加支付功能"
./orchestrator run --user-input "需求变了，要加支付功能"

# 用户: "修了个 bug"
./orchestrator run --user-input "修了个 bug"
```

---

## Phase 1-12 — 自动执行

Orchestrator 会自动执行以下 Phase 序列，**模型不需要手动调用每个命令**：

| Phase | 名称 | 自动/交互 | 说明 |
|-------|------|----------|------|
| Phase 1 | 实现方案分析 | **交互** | 分析需求、项目代码、业界方案，生成多个方案供用户选择 |
| Phase 2 | 项目初始化 | 自动 | 创建文档结构、DoD 配置、Risk Register、ADR 目录 |
| Phase 3 | AI 协作 PRD 起草 | **交互** | Claude 生成 PRD 草案，用户审核 |
| Phase 4 | PRD 验证 + Product Spec | 自动 | 验证 PRD，通过后生成 `product.spec.json` 和快照 |
| Phase 5 | AI 协作 UED 设计 | **交互** | 从 Product Spec 推导 UED 文档，用户审核页面、流程、状态 |
| Phase 6 | UED Spec 生成与验证 | 自动 | 生成 `ued.spec.json`，映射 Product Spec |
| Phase 7 | AI 协作技术架构设计 | **交互** | 从 Product/UED Specs 推导架构草案，用户审核 + ADR 决策 |
| Phase 8 | Tech Spec 生成与验证 | 自动 | 验证架构文档，生成 `tech.spec.json` 和快照 |
| Phase 9 | Lifecycle Graph / Skimmer | 自动 | 生成 `lifecycle_graph.json`，索引需求、UED、技术、测试依赖 |
| Phase 10 | Test Spec 与测试大纲 | 自动 | 生成 `test.spec.json`、`MASTER_OUTLINE.md` 和 `.lifecycle/test_graph.json` |
| Phase 11 | Velocity 感知迭代规划 | 自动 | 生成迭代计划，设定工时估算 |
| Phase 12 | 迭代执行循环 | **交互** | 首次进入先暂停等待开发，resume 后执行 DoD gate |

---

## 交互节点处理

当 orchestrator 遇到交互节点时，会暂停并写入 `.lifecycle/notification.json`：

```json
{
  "type": "pause_for_user",
  "phase_id": "phase-3-draft-prd",
  "phase_name": "AI 协作 PRD 起草",
  "message": "Phase AI 协作 PRD 起草 paused",
  "detail": "等待用户审核 PRD 草案，补充 [❓待确认] 标注处",
  "timestamp": "2026-04-16T12:34:56Z",
  "actions": [
    "完成用户交互后，运行: ./orchestrator resume --from-phase phase-3-draft-prd",
    "取消流程: ./orchestrator cancel"
  ]
}
```

**模型行为**：
1. Orchestrator 打印通知到 stdout（模型直接可见）
2. 预期交互暂停返回 exit code `0`，模型通过 checkpoint `status: paused` 和 `.lifecycle/notification.json` 判断仍需继续处理
3. 模型读取通知，执行交互任务（如生成 PRD 草案、回答访谈问题）
4. 模型调用 `./orchestrator resume --from-phase <phase-id>`
5. Orchestrator 继续执行后续 Phase

---

## 失败处理

当验证失败时，orchestrator 会暂停并通知模型，通知文件包含 validator 的**完整诊断信息**：

```json
{
  "type": "validation_failed",
  "phase_id": "phase-4-product-spec",
  "phase_name": "Product Spec 生成与验证",
  "message": "Phase Product Spec 生成与验证 failed",
  "detail": "Document validation failed",
  "score": 42,
  "threshold": 70,
  "issues": [
    {"field": "产品愿景", "message": "缺少「产品愿景」章节", "severity": "error"},
    {"field": "非功能需求", "message": "非功能需求缺少具体量化指标", "severity": "warning"},
    {"field": "范围边界", "message": "范围边界章节缺少明确的 In/Out Scope 说明", "severity": "warning"}
  ],
  "suggestions": [
    "非功能需求应包含可量化指标，如「API 响应时间 < 200ms」",
    "范围边界应明确列出「本阶段包含」和「本阶段不包含」的内容"
  ],
  "timestamp": "2026-04-16T12:45:00Z",
  "actions": [
    "修复问题后，运行: ./orchestrator resume --from-phase phase-4-product-spec"
  ]
}
```

**模型行为**：
1. 读取 `.lifecycle/notification.json`，获取 `score`、`issues`、`suggestions`
2. 针对每条 `severity: "error"` 的 issue 优先修复（缺失章节）
3. 针对 `severity: "warning"` 的 issue 补充内容深度（量化指标、步骤数量等）
4. 参考 `suggestions` 了解具体改进方向
5. 修复完成后调用 `./orchestrator resume --from-phase <phase-id>`
6. Orchestrator 重试该 Phase

---

## 意图解析

当用户输入匹配到多个意图时，orchestrator **仅使用优先级最高的单一意图**执行。例如 "修了个 bug，顺便想调整下需求" 会匹配 bug-fix 和 prd-change，但只执行优先级更高的 bug-fix 流程。

> **注意**：复合意图（同时处理多个 intent）暂未实现。如需处理多种变更，请分别执行。

---

## 命令速查

```bash
# 启动编排
./orchestrator run --intent <intent> --user-input "<输入>"

# 恢复执行
./orchestrator resume --from-phase <phase-id> [--user-input "<输入>"]

# 查看状态
./orchestrator status

# 取消流程
./orchestrator cancel

# 回滚管理
./orchestrator rollback --list
./orchestrator rollback --rollback-point-id <id>
```

---

## 工作流示例

### 示例 1：新产品流程

```bash
# 1. 用户: "我想做一个产品"
./orchestrator run --intent new-product --user-input "我想做一个产品"

# 2. Orchestrator 自动执行 Phase 1 的 analyze_solution 命令
#    扫描项目代码、生成方案、写入 .lifecycle/solution.json
#    然后暂停在 Phase 1（交互节点）

# 3. 用户选择方案

# 4. 用户选择方案
#    模型更新 .lifecycle/solution.json

# 5. 模型调用 resume
./orchestrator resume --from-phase phase-1-analyze-solution

# 6. Orchestrator 执行 Phase 2 (自动)
#    创建文档结构...

# 7. Orchestrator 暂停在 Phase 3
#    通知: "等待用户审核 PRD 草案"

# 8. 模型生成 PRD 草案
#    写入 Docs/product/PRD.md

# 9. 模型调用 resume
./orchestrator resume --from-phase phase-3-draft-prd

# 10. Orchestrator 执行 Phase 4 (自动)
#     验证 PRD...

# 11. Orchestrator 暂停在 Phase 5
#     通知: "等待用户审核 UED 草案"

# 12. 用户审核 UED，模型写入 Docs/product/UED.md

# 13. 模型调用 resume
./orchestrator resume --from-phase phase-5-draft-ued

# ... 继续执行 Phase 6-12
```

### 示例 2：PRD 变更流程

> **前提**：项目已完成初始化（至少跑过一次 new-product 流程，phase-2-init 已完成）。

```bash
# 1. 用户: "需求变了，要加支付功能"
./orchestrator run --intent prd-change --user-input "需求变了，要加支付功能"

# 2. Orchestrator 先执行 Phase 1 Impact Report，再暂停在 Phase 3（交互）
#    通知: "等待用户修改 PRD"

# 3. 用户修改 PRD
#    更新 Docs/product/PRD.md

# 4. 模型调用 resume
./orchestrator resume --from-phase phase-3-draft-prd

# 5. Orchestrator 自动执行 Phase 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12
#    Phase 4: 验证 PRD 并生成 Product Spec
#    Phase 5-8: 更新 UED/Tech 文档与 Specs
#    Phase 9-10: 更新 Lifecycle Graph、Test Spec 和测试大纲
#    Phase 11-12: 更新迭代计划并进入执行 gate
```

---

## 附录 — PHASES 定义

完整的 Phase 定义见 `scripts/core/phases.py`，包含：
- Phase ID、名称、描述
- 是否自动执行（auto=True/False）
- 前置步骤依赖
- 对应的命令
- 产物验证规则
- 失败处理策略
- 交互节点描述

---

## 技术细节

### Checkpoint 文件格式

`.lifecycle/checkpoint.json`：
```json
{
  "version": "2.3",
  "project_name": "xxx",
  "created_at": "2026-04-16T12:00:00Z",
  "updated_at": "2026-04-16T12:34:56Z",
  "current_phase": "phase-4-product-spec",
  "status": "in_progress",
  "completed_phases": ["phase-0-intent", "phase-1-analyze-solution", "phase-2-init"],
  "phase_data": {
    "phase-4-product-spec": {
      "started_at": "...",
      "completed_at": "...",
      "score": 85
    }
  },
  "intent": "new-product",
  "user_input": "我想做一个...",
  "metadata": {}
}
```

### 通知文件格式

`.lifecycle/notification.json`：
```json
{
  "type": "pause_for_user" | "validation_failed" | "dod_failed" | "error",
  "phase_id": "phase-3-draft-prd",
  "phase_name": "AI 协作 PRD 起草",
  "message": "...",
  "detail": "...",
  "timestamp": "...",
  "actions": ["..."]
}
```

---

## 迁移指南（从 v1.0 升级）

1. **备份现有项目**：`cp -r myproject myproject_backup`
2. **更新技能**：`git pull origin main`（或重新下载）
3. **运行迁移**：Orchestrator 会自动迁移旧版 `steps/` 格式到 `checkpoint.json`
4. **使用新命令**：所有旧命令已废弃，使用 `./orchestrator` 命令

**迁移后验证**：
```bash
./orchestrator status
# 应看到 "Status: migrated" 和已完成的 Phase 列表
```

---

## 故障排查

### 问题：Orchestrator 无法启动

**检查**：
- Python 版本 ≥ 3.8
- `PYTHONPATH` 是否设置正确
- `.lifecycle/` 目录是否存在

### 问题：Resume 不生效

**检查**：
- `.lifecycle/checkpoint.json` 是否存在
- `current_phase` 字段是否正确
- `.lifecycle/notification.json` 是否存在

### 问题：Phase 验证失败

**检查**：
- 产物文件是否存在（如 `Docs/product/PRD.md`）
- 文件大小是否满足 `min_bytes` 要求
- 验证分数是否达标（PRD ≥ 70，ARCH ≥ 70）
- 查看 `.lifecycle/notification.json` 中的 `issues` 字段，获取具体缺失项

---

## 附录 A：文档格式规范

> 本附录供 AI 模型生成文档时参考。所有格式规则与 `scripts/core/doc_validator.py` 的验证逻辑严格对应，确保生成的文档能通过 Phase 4（PRD验证）和 Phase 7（架构验证）。

---

### A.1 PRD 格式规范

**验证器**：`doc_validator.py` → `_validate_prd()`  
**评分**：满分 100，通过阈值 70（base 50 分 + bonus 最多 52 分：章节 39 + 整体字数 8 + EARS 5）

#### 必须包含的 7 个章节

章节名可加数字编号前缀（如 `## 1. Product Vision`），但关键词必须出现在标题中：

| 章节 | 可识别的标题关键词 | 内容深度要求 |
|------|-----------------|------------|
| 产品愿景 | `产品愿景` / `Product Vision` / `Vision` / `Introduction` / `Overview` / `Summary` | 正文 **≥ 50 词/字**，描述核心问题和目标用户价值 |
| 核心功能 | `核心功能` / `Features` / `功能列表` / `功能概述` / `Goals` / `Objectives` | **≥ 3 个功能条目**（bullet 列表或 `### F01 — 名称` 格式） |
| 用户角色 | `用户角色` / `User Roles` / `目标用户` / `Personas` | **≥ 2 类用户**，每类一行 bullet，说明角色和目标 |
| 功能流程 | `功能流程` / `User Flow` / `交互流程` / `业务流程` | 有序编号步骤，**≥ 3 步**，覆盖完整用户操作路径 |
| 非功能需求 | `非功能需求` / `Non-functional` / `性能需求` / `安全需求` | **必须含量化指标**：`< 200ms`、`99.9%`、`100 QPS`、`2秒`、`100 并发` 等 |
| 范围边界 | `范围边界` / `Scope` / `In Scope` / `Out of Scope` / `Constraints` | 必须同时出现 `In Scope`（范围内）和 `Out of Scope`（范围外）两种表述 |
| 风险 | `风险` / `Risks` / `风险分析` / `风险评估` | bullet 列表或表格，每条含**风险描述 + 缓解方案** |

**整体要求**：总字数 ≥ 200 词/字（获额外 8 分）

#### 功能章节格式（Feature Sections）

每个功能应使用如下格式，便于 EARS 需求检查器识别并给出加分：

```markdown
### F01 — 用户登录

**用户故事**：作为已注册用户，我希望通过邮箱和密码登录，以便访问我的个人数据。

**需求语句**（使用 EARS 语法）：
- 当用户提交登录表单时，系统应验证邮箱和密码组合。
- 若认证失败超过 5 次，系统应锁定账户 30 分钟。
- 系统应在 200ms 内完成认证响应。
```

#### EARS 需求语法（5 种模式）

| 模式 | 中文格式 | 英文格式 |
|------|---------|---------|
| Event-driven（事件驱动） | `当<触发事件>时，系统应<响应动作>` | `When <event>, the system shall <action>` |
| State-driven（状态驱动） | `在<系统状态>下，系统应<响应动作>` | `While <state>, the system shall <action>` |
| Unwanted/Conditional（条件/异常） | `若<条件/异常>，则系统应<处理动作>` | `If <condition>, the system shall <action>` |
| Optional（可选功能） | `当<特定功能启用>时，系统应<动作>` | `Where <feature>, the system shall <action>` |
| Ubiquitous（普适需求） | `系统应<持续保证的动作>` | `The system shall <action>` |

EARS 合规率 ≥ 50% 可获最多 5 分额外加分。

---

### A.2 架构文档格式规范（Arc42-Lite）

**验证器**：`doc_validator.py` → `_validate_arch()`  
**评分**：满分 100，通过阈值 70（base 52 分 + bonus 最多 43 分：章节 35 + 整体字数 8）  
**标准**：[Arc42](https://arc42.org) 精华 8 个视图

#### 必须包含的 8 个章节

| 章节 | 可识别的标题关键词 | 内容深度要求 |
|------|-----------------|------------|
| 系统边界与上下文 | `系统边界` / `System Overview` / `System Context` / `上下文` / `Context` / `外部依赖` | 外部依赖**表格**或 **≥ 2 条 bullet**，列出每个外部系统/API |
| 技术选型 | `技术选型` / `Tech Stack` / `技术栈` / `选型` | 每项技术**必须包含选择理由**（含：因为 / 理由 / 原因 / chose / because / 优势 等关键词） |
| 系统架构 | `系统架构` / `Architecture` / `架构概述` / `整体架构` / `High-Level Design` / `High Level` | **必须包含架构图**：ASCII 图（含 `┌┐└┘─│` 等字符）或代码块（` ``` `）内的图示 |
| 模块分解 | `模块分解` / `组件设计` / `Component` / `模块设计` / `Building Block` | Markdown **表格**，≥ 3 行（含表头 + 分隔符行 + ≥1 数据行），列出模块名、职责、技术 |
| 数据模型 | `数据模型` / `Data Model` / `数据库设计` / `Schema` | **表格（≥ 3 行）**或 **≥ 3 条列表**，列出字段名、类型、说明 |
| API 设计 | `API` / `接口设计` / `Endpoints` / `API 设计` | **至少一个端点路径**，格式：`GET /api/v1/users`、`POST /api/v1/items` 等 |
| 部署方案 | `部署` / `Deployment` / `运维` / `Infrastructure` / `部署方案` | 含 **docker / kubernetes / k8s / nginx / deploy / 部署** 等关键词，或列出部署步骤 |
| 架构决策记录 | `架构决策` / `ADR` / `Architecture Decision` / `决策记录` | 每条 ADR 含：**背景 + 决策 + 原因 + 状态**（至少 2 条 ADR） |

**整体要求**：总字数 ≥ 300 词/字（获额外 8 分）；Phase 7 还检查至少 1 条 `Status: Accepted` 的 ADR。

#### Arc42 各视图说明

| 章节 | Arc42 对应 | 核心内容 |
|------|-----------|---------|
| 系统边界与上下文 | §3 Context & Scope | 外部参与者及其与系统的交互边界 |
| 技术选型 | §4 Solution Strategy | 框架/数据库/基础设施的技术决策及依据 |
| 系统架构 | §5 Building Block View L1 | 顶层架构图，展示主要模块和数据流 |
| 模块分解 | §5 Building Block View L2 | 各子模块职责分工表 |
| 数据模型 | 数据视图 | 核心实体的字段定义 |
| API 设计 | §8 Cross-cutting Concepts | REST/RPC 端点列表 |
| 部署方案 | §7 Deployment View | 容器化配置、CI/CD 流程 |
| 架构决策记录 | §9 Architecture Decisions | ADR：每个关键技术决策的背景和依据 |

#### ADR 标准格式

```markdown
### ADR-001: 使用 PostgreSQL 替代 MongoDB

**背景**：项目需要复杂的关联查询，工作流状态有严格依赖关系。

**决策**：选用 PostgreSQL 15 作为主数据库。

**原因**：PostgreSQL 提供 ACID 合规性、复杂查询支持和强一致性，适合工作流状态管理。
NoSQL 的灵活 Schema 在此场景下反而增加一致性风险。

**影响**：需要定义严格 Schema，但获得了可靠的事务支持。

**状态**：Accepted
```

#### 架构图格式参考（ASCII Box-Drawing）

```
┌──────────────┐     REST API    ┌──────────────────┐
│   Frontend   │ ─────────────→  │   Backend Service │
│  (React/TS)  │                 └────────┬──────────┘
└──────────────┘                          │
                             ┌────────────┴────────────┐
                    ┌────────▼───────┐        ┌────────▼──────┐
                    │  PostgreSQL    │        │    Redis       │
                    │  (主数据库)    │        │  (缓存/会话)   │
                    └────────────────┘        └───────────────┘
```

---

### A.3 测试大纲格式规范（IEEE 829 精华）

**验证器**：`doc_validator.py` → `_validate_test_outline()`  
**评分**：bonus-only 评分，满分 100（基础 85 + 图验证 15）+ 可选 E2E bonus 最多 10 分，通过阈值 70  
**生成来源**：Phase 8 自动生成（`MASTER_OUTLINE.md`），PRD/架构变更后可能需要 AI 增补

#### 文档整体结构

```markdown
# Master Test Outline

| 功能 ID | 功能名称  | 场景数 | UI | API | DATA | AUTH |
|---------|---------|--------|----|----|------|------|
| F01     | 用户登录 |   4    | ✓  |  ✓ |  ✓   |  ✓   |
| F02     | 用户注册 |   3    | ✓  |  ✓ |  -   |  -   |

---

## F01 — 用户登录

**PRD 来源：** `PRD-F01`

### TST-F01-S01 — 正向｜正确凭证登录 [API]

**前置条件：**
- 用户账户已注册且处于活跃状态

**测试步骤：**
1. 向 POST /api/v1/auth/login 发送请求，包含有效 email 和 password
2. 接收响应并检查 HTTP 状态码
3. 验证响应体包含 access_token 字段

**期望结果：** HTTP 200，返回含 access_token 的 JSON

**状态：** `active`

---

### TST-F01-S02 — 异常｜密码错误 [API]

**前置条件：** 用户账户已注册

**测试步骤：**
1. 向 POST /api/v1/auth/login 发送请求，包含正确 email 但**错误密码**
2. 接收响应

**期望结果：** HTTP 401，返回错误信息，账户未锁定

**状态：** `active`
```

#### 评分规则

| 检查项 | 满足条件 | 分值 |
|--------|---------|------|
| 场景数量充足 | 每个功能模块 ≥ 2 个场景 | 20分 |
| 场景ID唯一无重复 | 格式 `TST-F01-S01`，全文无重复 ID | 15分 |
| 前置条件覆盖 | 含 `前置条件` 或 `Precondition` 关键词，覆盖 ≥ 50% 场景 | 10分 |
| 有序步骤充足 | `测试步骤` 或 `Steps` 后跟编号列表，≥ 3 步，覆盖 ≥ 50% 场景 | 15分 |
| 期望结果覆盖 | 含 `期望结果` 或 `Expected` 关键词，覆盖 ≥ 50% 场景 | 10分 |
| 异常路径覆盖 | 含 `异常/错误/失败/超时/无效/拒绝/Error/Fail/Invalid/Timeout`，每功能 ≥ 1 个 | 15分 |
| E2E 标签（可选） | 关键路径场景标注 `[E2E]`，有则加分 | bonus 最多 +10分 |

#### 必须出现的关键词

| 区域 | 关键词 |
|------|-------|
| 前置条件区 | `前置条件` 或 `Precondition` |
| 步骤区 | `测试步骤` 或 `Steps`（后跟 `1. ... 2. ... 3. ...` 格式） |
| 期望结果区 | `期望结果` 或 `Expected` |
| 异常标识（每功能至少1处） | `异常` / `错误` / `失败` / `超时` / `无效` / `拒绝` / `Error` / `Fail` / `Invalid` / `Timeout` |

#### 四种必须覆盖的场景变体（Defensive Testing）

| 变体 | 说明 | 示例 |
|------|------|------|
| `happy`（正向） | 正常输入，期望成功 | 正确凭证登录成功 |
| `boundary`（边界） | 临界值输入 | 密码恰好 8 位最小长度 |
| `error`（异常） | 无效输入或系统错误 | 密码错误、网络超时 |
| `data`（数据异常） | 数据格式/状态异常 | 账户已锁定、邮箱格式错误 |
