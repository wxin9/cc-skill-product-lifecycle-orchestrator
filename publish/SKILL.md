---
name: product-lifecycle
description: 产品全生命周期管理。当用户提到「产品设计」「PRD」「需求文档」「技术架构」「迭代规划」「TDD」「product-lifecycle」「产品管理」「从零开始做一个产品」「整理项目文档」「迭代门控」「ADR」「velocity追踪」「DoD」「Sprint Review」时立即触发。核心能力：脚本编排引擎、意图识别、自动执行 Phase 序列、交互暂停、失败恢复。
compatibility: Python 3.8+
---

# Product Lifecycle v2.0

**一句话**：脚本编排 + 交互暂停的产品全生命周期管理——orchestrator 自动执行 Phase 序列，遇到交互节点暂停通知模型，模型处理后 resume 继续。

**核心能力**：

| 能力 | 说明 |
|------|------|
| 脚本编排引擎 | Orchestrator 自动执行 Phase 序列，无需模型记忆下一步 |
| 意图识别 | 正则匹配 + 优先级排序，支持复合意图 |
| 交互暂停 | 遇到用户审核、访谈等节点自动暂停，通知模型 |
| 失败恢复 | 验证失败、DoD 失败时暂停，修复后 resume 继续 |
| 状态持久化 | Checkpoint 记录 Phase 级别状态，支持断点续做 |

---

## ⚠ 破坏性变更（v2.0）

**所有旧命令已废弃**：
- ❌ `./lifecycle init` → 废弃
- ❌ `./lifecycle validate` → 废弃
- ❌ `./lifecycle draft` → 废弃
- ❌ `./lifecycle plan` → 废弃
- ❌ 其他所有旧命令

**新命令**：
- ✅ `./orchestrator run --intent <intent> --user-input "<输入>"` — 启动编排
- ✅ `./orchestrator resume --from-phase <phase-id>` — 恢复执行
- ✅ `./orchestrator status` — 查看状态
- ✅ `./orchestrator cancel` — 取消流程

---

## 快速开始

### Phase 0 — 意图识别（必须，每次调用的第一步）

**模型行为**：
1. 读取用户输入
2. 调用 `./orchestrator run --intent <intent> --user-input "<用户输入>"`
3. Orchestrator 自动执行 Phase 序列
4. 遇到暂停节点时，orchestrator 会通知模型

**意图类型**：

| 意图 | 说明 | 触发关键词 |
|------|------|-----------|
| `new-product` | 新产品（从零开始） | "新产品"、"从零开始"、"做一个产品" |
| `new-feature` | 新增功能 | "增加功能"、"新需求"、"新功能" |
| `prd-change` | 需求变更 | "需求变了"、"PRD 改了"、"调整需求" |
| `code-change` | 代码变更 | "修改了模块"、"重构"、"代码变更" |
| `bug-fix` | Bug 修复 | "报错"、"测试失败"、"bug"、"修复" |
| `arch-change` | 架构调整 | "换数据库"、"换架构"、"重构架构" |
| `new-iteration` | 新迭代 | "下一个迭代"、"迭代 N"、"新迭代" |

**示例**：
```bash
# 用户: "我想做一个产品"
./orchestrator run --intent new-product --user-input "我想做一个产品"

# 用户: "需求变了，要加支付功能"
./orchestrator run --intent prd-change --user-input "需求变了，要加支付功能"

# 用户: "修了个 bug"
./orchestrator run --intent bug-fix --user-input "修了个 bug"
```

---

## Phase 1-10 — 自动执行

Orchestrator 会自动执行以下 Phase 序列，**模型不需要手动调用每个命令**：

| Phase | 名称 | 自动/交互 | 说明 |
|-------|------|----------|------|
| Phase 1 | 项目初始化 | 自动 | 创建文档结构、DoD 配置、Risk Register、ADR 目录 |
| Phase 2 | AI 协作 PRD 起草 | **交互** | Claude 生成 PRD 草案，用户审核 |
| Phase 3 | PRD 验证 + 自动快照 | 自动 | 验证 PRD 质量，通过后建快照 |
| Phase 4 | 架构访谈 + 项目类型识别 | **交互** | 用户回答 6 个访谈问题 |
| Phase 5 | AI 协作架构设计 | **交互** | Claude 生成架构草案，用户审核 + ADR 决策 |
| Phase 6 | 架构验证 + ADR 注册 + 快照 | 自动 | 验证架构文档，检查至少 1 条 ADR accepted |
| Phase 7 | 自适应测试大纲生成 | 自动 | 根据项目类型选择维度集，生成测试大纲 |
| Phase 8 | Velocity 感知迭代规划 | 自动 | 生成迭代计划，设定工时估算 |
| Phase 9 | 迭代执行循环 | **交互** | 用户开发、测试、通过 DoD 检查 |
| Phase 10 | 变更处理 | 自动 | 处理 PRD/Code/Test 变更，级联影响分析 |

---

## 交互节点处理

当 orchestrator 遇到交互节点时，会暂停并写入 `.lifecycle/notification.json`：

```json
{
  "type": "pause_for_user",
  "phase_id": "phase-2-draft-prd",
  "phase_name": "AI 协作 PRD 起草",
  "message": "Phase AI 协作 PRD 起草 paused",
  "detail": "等待用户审核 PRD 草案，补充 [❓待确认] 标注处",
  "timestamp": "2026-04-16T12:34:56Z",
  "actions": [
    "完成用户交互后，运行: python -m scripts orchestrator resume --from-phase phase-2-draft-prd",
    "取消流程: python -m scripts orchestrator cancel"
  ]
}
```

**模型行为**：
1. Orchestrator 打印通知到 stdout（模型直接可见）
2. 模型读取通知，执行交互任务（如生成 PRD 草案、回答访谈问题）
3. 模型调用 `./orchestrator resume --from-phase <phase-id>`
4. Orchestrator 继续执行后续 Phase

---

## 失败处理

当验证失败时，orchestrator 会暂停并通知模型：

```json
{
  "type": "validation_failed",
  "phase_id": "phase-3-validate-prd",
  "phase_name": "PRD 验证 + 自动快照",
  "message": "Phase PRD 验证 + 自动快照 failed",
  "detail": "PRD 验证分数 < 70: 缺少核心功能",
  "timestamp": "2026-04-16T12:45:00Z",
  "actions": [
    "修复问题后，运行: python -m scripts orchestrator resume --from-phase phase-3-validate-prd"
  ]
}
```

**模型行为**：
1. 读取失败原因
2. 修复问题（如补充 PRD 功能点）
3. 调用 `./orchestrator resume --from-phase <phase-id>`
4. Orchestrator 重试该 Phase

---

## 复合意图处理

如果用户输入同时命中多个意图（如"修了个 bug，顺便想调整下需求"），orchestrator 会：
1. 列出所有匹配的意图（按优先级排序）
2. 串行执行每个意图对应的 Phase 序列

**示例**：
```
用户输入: "修了个 bug，顺便想调整下需求"
匹配意图:
  1. bug-fix (优先级 1)
  2. prd-change (优先级 3)

执行路径:
  步骤 1: 执行 bug-fix 流程 (Phase 10 → Phase 3)
  步骤 2: 执行 prd-change 流程 (Phase 10 → Phase 2 → Phase 3)
```

---

## 命令速查

```bash
# 启动编排
./orchestrator run --intent <intent> --user-input "<输入>"

# 恢复执行
./orchestrator resume --from-phase <phase-id>

# 查看状态
./orchestrator status

# 取消流程
./orchestrator cancel
```

---

## 工作流示例

### 示例 1：新产品流程

```bash
# 1. 用户: "我想做一个产品"
./orchestrator run --intent new-product --user-input "我想做一个产品"

# 2. Orchestrator 执行 Phase 1 (自动)
#    创建文档结构...

# 3. Orchestrator 暂停在 Phase 2
#    通知: "等待用户审核 PRD 草案"

# 4. 模型生成 PRD 草案
#    写入 Docs/product/PRD.md

# 5. 模型调用 resume
./orchestrator resume --from-phase phase-2-draft-prd

# 6. Orchestrator 执行 Phase 3 (自动)
#    验证 PRD...

# 7. Orchestrator 暂停在 Phase 4
#    通知: "等待用户回答架构访谈问题"

# 8. 用户回答访谈问题
#    模型写入 .lifecycle/arch_interview.json

# 9. 模型调用 resume
./orchestrator resume --from-phase phase-4-arch-interview

# ... 继续执行 Phase 5-9
```

### 示例 2：PRD 变更流程

```bash
# 1. 用户: "需求变了，要加支付功能"
./orchestrator run --intent prd-change --user-input "需求变了，要加支付功能"

# 2. Orchestrator 执行 Phase 10 (自动)
#    读取 PRD 快照，diff 识别变更，生成影响报告

# 3. Orchestrator 暂停在 Phase 2
#    通知: "等待用户修改 PRD"

# 4. 用户修改 PRD
#    更新 Docs/product/PRD.md

# 5. 模型调用 resume
./orchestrator resume --from-phase phase-2-draft-prd

# 6. Orchestrator 执行 Phase 3 (自动)
#    重新验证 PRD...

# 7. Orchestrator 执行 Phase 7-8 (自动)
#    更新测试大纲、迭代计划...
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
  "version": "2.0",
  "project_name": "xxx",
  "current_phase": "phase-3-validate-prd",
  "status": "in_progress",
  "completed_phases": ["phase-0-intent", "phase-1-init"],
  "phase_data": {
    "phase-3-validate-prd": {
      "started_at": "...",
      "completed_at": "...",
      "score": 85
    }
  },
  "intent": "new-product",
  "user_input": "我想做一个..."
}
```

### 通知文件格式

`.lifecycle/notification.json`：
```json
{
  "type": "pause_for_user" | "validation_failed" | "dod_failed" | "error",
  "phase_id": "phase-2-draft-prd",
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

---

**详细计划**：`/Users/admin/.claude/plans/radiant-churning-sunbeam.md`
