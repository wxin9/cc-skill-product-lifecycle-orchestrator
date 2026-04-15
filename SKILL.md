---
name: product-lifecycle
description: 产品全生命周期管理。当用户提到「产品设计」「PRD」「需求文档」「技术架构」「迭代规划」「TDD」「product-lifecycle」「产品管理」「从零开始做一个产品」「整理项目文档」「迭代门控」「ADR」「velocity追踪」「DoD」「Sprint Review」时立即触发。核心能力：AI 协作起草、复合意图识别、自适应测试维度、自动快照 diff、velocity 追踪、可配置 DoD、ADR 专项管理、Sprint Review 材料。
compatibility: Python 3.8+
---

# Product Lifecycle

**一句话**：AI 协作 + 强制门控的产品全生命周期管理——帮你起草 PRD、设计架构、追踪速度，全链路脚本强制执行，Haiku 也能跑完整个流程。

**核心能力**：

| 能力 | 说明 |
|------|------|
| AI 协作起草 | `draft prd` / `draft arch`：Claude 主动起草草案，用户做审稿人 |
| 复合意图识别 | 支持复合意图（"修了 bug 顺便调整了需求"）+ 对话式确认 |
| 自适应测试维度 | 自动识别项目类型（Web/CLI/Mobile/Data/Microservices），选对应维度集 |
| 智能变更处理 | `change prd` 无需 `--old`，自动读 validate 时建立的快照 diff |
| Velocity 追踪 | 每迭代记录估计/实际工时，ASCII 趋势图 |
| 可配置 DoD | 可配置 DoD：任务状态 + lint + coverage + 代码审查记录 |
| ADR 专项管理 | `Docs/adr/` 专目录，Proposed→Accepted→Deprecated 状态机 |
| Sprint Review | 门控通过自动生成 `sprint_review.md`，可直接发给 Stakeholder |

---

## 快速概览

```
Phase 0  — 意图识别（复合意图 + 对话式确认）
Phase 1  — 项目初始化（DoD + Risk Register + ADR 目录）
Phase 2  — AI 协作 PRD 起草（Draft Mode：用户做审稿人）
Phase 3  — PRD 验证 + 自动快照
Phase 4  — 架构访谈 + 项目类型识别
Phase 5  — AI 协作架构设计（含 ADR 初稿）
Phase 6  — 架构验证 + ADR 注册 + 快照
Phase 7  — 自适应测试大纲（按项目类型选维度）
Phase 8  — Velocity 感知迭代规划
Phase 9  — 迭代执行循环（DoD + Sprint Review + Velocity）
Phase 10 — 变更处理（PRD/Code/Test，自动快照 diff）
附录 A   — 命令速查
附录 B   — Velocity 追踪指南
附录 C   — ADR 管理指南
附录 D   — Risk Register 指南
```

---

## 前置：确定 `<SKILL_PATH>` 路径

```bash
# 初始化后，lifecycle 脚本会自动找到技能路径
# 所有命令均通过项目根目录下的 ./lifecycle 脚本执行
./lifecycle status  # 验证环境
```

---

## Phase 0 — 意图识别（必须，每次调用的第一步）

**特性**：支持复合意图（如"修了个 bug，顺便想调整下需求"），通过对话式确认分解为两个执行路径，而非强制匹配单一规则。

### 0a. 扫描项目状态

```bash
./lifecycle status
```

如果项目尚未初始化（无 `.lifecycle/` 目录），直接跳至 Phase 1。

已初始化则分析 Phase 进度：

```bash
python3 scripts/step_enforcer.py status
```

### 0b. 意图分类（复合意图处理）

根据用户输入，优先识别以下意图（可同时命中多个）：

| 优先级 | 意图类型 | 典型输入示例 | 起始 Phase |
|--------|---------|------------|-----------|
| 1（最高）| Bug 修复 | "报错了"、"测试失败"、"bug" | Phase 10（change test --failure-type bug）|
| 2 | 需求遗漏 | "测试发现新场景"、"gap" | Phase 10（change test --failure-type gap）|
| 3 | PRD 变更 | "需求变了"、"PRD 改了" | Phase 10（change prd，**无需 --old**）|
| 4 | 代码变更 | "修改了 XX 模块" | Phase 10（change code）|
| 5 | 补充测试 | "加测试用例" | Phase 7（测试大纲更新）|
| 6 | 新迭代 | "下一个迭代"、"迭代 2" | Phase 9（迭代执行）|
| 7 | 架构调整 | "换数据库"、"重构" | Phase 5（架构设计）|
| 8 | 新增功能 | "增加功能"、"新需求" | Phase 2/3（PRD 更新）|
| 9（最低）| 全新产品 | "新产品"、"从零开始" | Phase 1（初始化）|

**复合意图处理规则**：

若输入同时命中多个意图（如"修了个 bug，顺便想调整下需求"命中优先级 1 和 3），**不要强制选一个**，而是：

1. 列出识别到的所有意图，并标注优先顺序
2. 明确说明："检测到复合意图，建议分两步执行，是否按此顺序进行？"
3. 等待用户确认后，**先执行高优先级意图，再执行低优先级意图**
4. 两步之间自动评估影响（如 bug fix 是否会引发 PRD 变更）

**不明确时**：不猜测，列出 2-3 个候选，请用户确认。

### 0c. 进入规划模式，展示执行计划

识别到意图后，**必须**通过 EnterPlanMode 制定并展示执行计划：

```
意图识别：PRD 变更（新增支付功能）
将从 Phase 10a 开始，执行以下步骤：
  □ 运行 ./lifecycle change prd（自动读取最新快照做 diff）
  □ 查看 .lifecycle/CHANGE_IMPACT.md 影响范围
  □ 重新运行 Phase 3 PRD 验证
  □ 更新受影响的测试用例
跳过的阶段：Phase 1-9（已完成）
```

ExitPlanMode 后等待用户确认再执行。

> **⚠ 每次调用技能必须先完成 Phase 0，不允许静默直接执行。**

---

## Phase 1 — 项目初始化

> **Gate（前置验证）**：无（Phase 1 是起点）

**目标**：建立规范文档结构，同时初始化 DoD / Risk Register / ADR 目录等组件。

### 1a. 运行初始化

```bash
# 新项目（当前目录）
./lifecycle init --name "项目名称"

# 已有项目（自动扫描整合）
./lifecycle init --path /path/to/project
```

初始化自动完成：
- 创建 `Docs/` 完整目录结构（含 `Docs/adr/` ADR 专目录）
- 初始化 `.lifecycle/dod.json`（默认 DoD 规则）
- 初始化 `.lifecycle/risk_register.json`（空 Risk Register）
- 初始化 `.lifecycle/velocity.json`（空 Velocity 记录）
- 生成 `./lifecycle` 可执行包装脚本

创建的文档结构：
```
Docs/
├── INDEX.md                       ← 总索引
├── product/                       ← PRD.md, requirements/
├── tech/                          ← ARCH.md, components/
├── adr/                           ← ADR-001-xxx.md + INDEX.md
├── iterations/                    ← iter-N/PLAN.md + test_cases.md + sprint_review.md
├── tests/                         ← MASTER_OUTLINE.md
└── manual/                        ← MANUAL.md
.lifecycle/
├── config.json                    ← 项目配置
├── dod.json                       ← DoD 规则（可自定义）
├── risk_register.json             ← 风险登记册
├── velocity.json                  ← 速度追踪数据
├── snapshots/                     ← 文档快照（validate 自动建）
├── tasks.json                     ← 全局任务注册表
└── steps/                         ← 步骤检查点
```

### 1b. 配置 DoD（可选，推荐）

默认 DoD 只检查任务状态 + 测试记录。如需扩展（lint / coverage / review）：

```bash
# 查看当前 DoD 规则
./lifecycle dod show

# 手动编辑扩展
nano .lifecycle/dod.json
```

DoD 配置示例（添加 lint + coverage）：
```json
{
  "rules": [
    {"type": "tasks", "description": "所有 CHK/DEV/TST 任务状态为 done"},
    {"type": "test_records", "description": "所有 TST 任务有测试执行记录"},
    {"type": "command", "cmd": "npm run lint", "description": "ESLint 通过"},
    {"type": "coverage", "threshold": 80,
     "cmd": "pytest --cov=src --cov-report=term-missing -q",
     "description": "代码覆盖率 ≥ 80%"},
    {"type": "review", "manual": true, "description": "已完成代码审查"}
  ]
}
```

### 1c. 验证初始化

```bash
./lifecycle step status
# 应看到: project-initialized ✓
```

> **完成记录**
> ```bash
> python3 scripts/step_enforcer.py record project-bootstrapped
> ```

---

## Phase 2 — AI 协作 PRD 起草（Draft Mode）

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require project-bootstrapped
> ```

**特性**：不再让用户面对空白模板，而是用一句话描述产品，Claude 生成完整 PRD 草案，用户做"审稿人"。

### 2a. 启动 PRD Draft Mode

```bash
./lifecycle draft prd --description "用一句话描述你的产品"
```

**示例**：
```bash
./lifecycle draft prd --description "一个帮助独立摄影师管理外拍档期、客户沟通和收款的轻量 SaaS 平台"
```

这会：
1. 显示 Draft Mode 说明
2. 将起草提示词保存到 `.lifecycle/prd_draft_prompt.md`
3. Claude（当前会话）会自动读取提示词并生成 PRD 草案

### 2b. Claude 生成 PRD 草案（自动执行）

Claude 会根据以下系统角色生成草案：

> 你是资深产品经理，根据用户描述推断目标用户、核心痛点、商业目标，生成完整 PRD 草案。功能点使用 `### F01 — 功能名称` 格式（验证器依赖此格式），需求语句使用 EARS 语法，在模糊处用 `[❓待确认: 问题]` 标注，末尾附"审稿建议"。

草案生成后，Claude 会将内容写入 `Docs/product/PRD.md`。

### 2c. 用户审核草案

审核要点（Claude 会在草案末尾的"审稿建议"中列出）：

1. 检查 `[❓待确认]` 标注处，补充具体信息
2. 确认功能点是否完整（格式：`### F01 — 功能名称`）
3. 确认用户角色定义准确
4. 非功能需求是否有量化指标（如 `< 200ms`）
5. 范围边界（Out of Scope）是否明确

> **完成记录**
> ```bash
> python3 scripts/step_enforcer.py record prd-drafted
> ```

---

## Phase 3 — PRD 验证 + 自动快照

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require prd-drafted
> ```

**特性**：验证通过后自动建快照，`change prd` 命令直接读最新快照做 diff，无需手动备份。

### 3a. 验证 PRD

```bash
./lifecycle validate --doc Docs/product/PRD.md --type prd
```

评分维度：
- 产品愿景 ≥ 50 字
- 核心功能 ≥ 3 个（`### F01 — ` 格式）
- 非功能需求含量化指标
- EARS 合规率 ≥ 50%（加分项）

**分数 ≥ 70 时**：
- 自动记录步骤 `prd-validated`
- **自动建快照** `.lifecycle/snapshots/Docs_product_PRD_md_<timestamp>.md`
- 写入 `.lifecycle/steps/prd-score.json`（供 DSL gate 验证）

**分数 < 70 时**：显示具体问题，修改后重跑。

> **完成记录（验证通过后自动完成）**
> ```bash
> python3 scripts/step_enforcer.py record prd-validated
> ```

---

## Phase 4 — 架构访谈 + 项目类型识别

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require prd-validated
> ```

**特性**：访谈时自动识别项目类型，后续测试大纲据此自适应选择维度集。

### 4a. 架构访谈

与用户确认以下问题：

```
1. 项目规模预期：（小型独立项目 / 中型团队协作 / 大型企业级）
2. 技术栈偏好：（如有限制请说明）
3. 团队规模：（独立开发者 / 2-5人 / 5人以上）
4. 上线时间线：（1个月内 / 3个月 / 6个月以上）
5. 性能要求：（用户规模、并发量、响应时间要求）
6. 部署环境：（本地 / 云端 / 容器化）
```

将访谈结果写入 `.lifecycle/arch_interview.json`：
```json
{
  "scale": "中型团队协作",
  "tech_stack_preference": ["Python", "React"],
  "team_size": "3人",
  "timeline": "3个月",
  "performance": "< 200ms 响应时间，100并发",
  "deployment": "Docker + 云端"
}
```

### 4b. 项目类型自动识别

访谈完成后，根据技术栈偏好自动识别项目类型：

| 类型 | 识别关键词 | 测试维度集 |
|------|-----------|-----------|
| **web** | React/Vue/Django/FastAPI/nginx | [UI][API][DATA][AUTH][PERF][XSS] |
| **cli** | CLI/命令行/argparse/click/cobra | [UNIT][INT][E2E][EDGE][INSTALL] |
| **mobile** | iOS/Android/Flutter/小程序 | [UI][OFFLINE][PUSH][PERF][DEVICE] |
| **data-pipeline** | Kafka/Flink/ETL/数据管道/Celery | [DATA][ASYNC][IDEMPOTENCY][VOLUME][SCHEMA] |
| **microservices** | 微服务/gRPC/Kubernetes/k8s | [API][CONTRACT][CHAOS][LATENCY][SCALE] |

识别结果写入 `.lifecycle/project_type.json`，供 Phase 7 测试大纲生成使用。

```bash
./lifecycle step record arch-interview-done
```

---

## Phase 5 — AI 协作架构设计

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require prd-validated
> ```

**特性**：Claude 根据 PRD 功能点 + 访谈结果自动生成架构草案（含 ADR 初稿）。

### 5a. 启动 Architecture Draft Mode

```bash
./lifecycle draft arch
```

这会：
1. 读取 `Docs/product/PRD.md` 功能点摘要
2. 读取 `.lifecycle/arch_interview.json` 访谈结果
3. 识别项目类型，附加在提示词中
4. 将架构起草提示词保存到 `.lifecycle/arch_draft_prompt.md`
5. Claude 自动生成架构草案

### 5b. Claude 生成架构草案（自动执行）

草案按 Arc42-Lite 结构生成，包含：
- 系统边界与外部依赖
- 技术选型（含理由）
- ASCII 系统架构图
- 模块分解职责表格
- 数据模型草案
- REST API 端点列表
- 部署方案
- **≥ 2 条 ADR 草案**（推荐接受的架构决策）
- 审稿建议

### 5c. 用户审核 + ADR 注册

草案生成后：

1. 检查 `[❓待确认]` 处，补充细节
2. 对 Claude 提出的 ADR 做决策：

```bash
# 接受架构决策（如 "选择 PostgreSQL 而非 MongoDB"）
./lifecycle adr create --title "选择 PostgreSQL 作为主数据库" --status accepted \
  --context "项目需要强事务和复杂查询" \
  --decision "使用 PostgreSQL 14，通过 SQLAlchemy 访问"

# 查看所有 ADR
./lifecycle adr list
```

> **完成记录**
> ```bash
> python3 scripts/step_enforcer.py record arch-designed
> ```

---

## Phase 6 — 架构验证 + ADR 注册 + 快照

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require arch-designed
> ```

### 6a. 验证架构文档

```bash
./lifecycle validate --doc Docs/tech/ARCH.md --type arch
```

验证通过后：
- 自动记录 `arch-doc-written` 步骤
- **自动建快照** `.lifecycle/snapshots/Docs_tech_ARCH_md_<timestamp>.md`
- 写入 `.lifecycle/steps/arch-score.json`

### 6b. ADR 门控检查

确认至少 1 条 ADR 状态为 `accepted`：

```bash
./lifecycle adr list
# 至少有一行显示 ✅ accepted
```

> **完成记录**
> ```bash
> python3 scripts/step_enforcer.py record arch-validated
> ```

---

## Phase 7 — 自适应测试大纲生成

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require arch-validated
> ```

**特性**：根据 Phase 4 识别的项目类型，自动选择合适的测试维度集，而非固定 7 维度。

### 7a. 生成测试大纲

```bash
./lifecycle outline generate \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --output Docs/tests/MASTER_OUTLINE.md
```

生成器会：
1. 读取 `.lifecycle/project_type.json`（Phase 4 识别结果）
2. 选择对应维度集（见 Phase 4 表格）
3. 为每个 PRD 功能点（`### F01 — ` 格式）生成多维度测试场景
4. 分配 TST-ID（格式 `TST-{F}-{S}`，如 `TST-F01-S01`）
5. 生成覆盖矩阵表格
6. **生成测试依赖图** `.lifecycle/test_graph.json`（v1.1.0 新增）

**如未识别到项目类型，默认使用 web 维度集。**

#### v1.1.0 新特性

**1. 新增产物：test_graph.json**

`outline generate` 现在会在 `.lifecycle/` 目录下生成 `test_graph.json`，与 `MASTER_OUTLINE.md` 同步生成。该文件包含：
- 测试用例节点（TST-ID）
- 依赖关系边（功能依赖、数据依赖、时序依赖）
- 维度标签（用于快速查询）

**2. 维度驱动的场景生成**

测试场景基于项目类型使用 `DIMENSION_GENERATORS` 自动生成，每个维度生成 4 种防御性变体：
- **happy**：正常路径，符合预期的输入
- **boundary**：边界条件，极限值测试
- **error**：错误处理，异常路径
- **data**：数据完整性，脏数据、缺失字段

示例（Web 项目 [API] 维度）：
```
TST-F01-S01: API 正常调用（happy）
TST-F01-S02: API 边界参数（boundary）
TST-F01-S03: API 错误响应（error）
TST-F01-S04: API 数据校验（data）
```

**3. 自适应测试维度**

维度自动适配项目类型（Phase 4 识别）：

| 项目类型 | 维度集 | 说明 |
|---------|--------|------|
| web | [UI][API][DATA][AUTH][PERF][XSS] | Web 应用全栈测试 |
| cli | [UNIT][INT][E2E][EDGE][INSTALL] | 命令行工具测试 |
| mobile | [UI][OFFLINE][PUSH][PERF][DEVICE] | 移动端特性测试 |
| data-pipeline | [DATA][ASYNC][IDEMPOTENCY][VOLUME][SCHEMA] | 数据管道测试 |
| microservices | [API][CONTRACT][CHAOS][LATENCY][SCALE] | 微服务测试 |

**4. 基于图的变更影响分析**

`change` 命令和 `outline trace` 现在使用 `TestGraph.traverse_impact()` 进行更精确的依赖追踪：
- 从变更节点出发，沿依赖边遍历
- 识别直接依赖和传递依赖
- 生成影响范围报告（包含依赖路径）

### 7b. 验证测试大纲

```bash
./lifecycle validate --doc Docs/tests/MASTER_OUTLINE.md --type test_outline
```

### 7c. 依赖审查（v1.1.0 新增）

审查和审计测试用例的依赖声明：

```bash
./lifecycle outline dependency-review
```

检查项：
- 循环依赖检测
- 孤立节点（无依赖且未被依赖）
- 依赖合理性（如 E2E 不应依赖 UNIT）

### 7d. 格式迁移（v1.1.0 新增）

将旧版 `MASTER_OUTLINE.md` 迁移到新的 `test_graph.json` 格式：

```bash
./lifecycle outline migrate --from Docs/tests/MASTER_OUTLINE.md
```

迁移后：
- 保留原有测试用例和描述
- 自动推断依赖关系（基于命名约定）
- 生成 `test_graph.json` 并验证完整性

> **完成记录（生成后自动记录）**
> ```bash
> python3 scripts/step_enforcer.py record test-outline-ready
> ```

---

## Phase 8 — Velocity 感知迭代规划

> **Gate（前置验证）**
> ```bash
> python3 scripts/step_enforcer.py require test-outline-ready
> ```

**特性**：每个迭代附带工时估算，历史数据自动推荐下一迭代估算值。

### 8a. 生成迭代计划

```bash
./lifecycle plan \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --constraints '{"max_features_per_iter": 3}'
```

生成原则（与原版相同）：
- 用「**用户能够...**」描述迭代目标
- 每个迭代 E2E 可测（有界面入口或 API 端点 + 完整数据流）

### 8b. 为每个迭代设定工时估算

```bash
# 为迭代 1 设定估算工时（首次推荐 8-16h）
./lifecycle velocity start --iteration 1 --hours 12

# 查看历史 velocity（如有）
./lifecycle velocity report
```

如果有历史数据，系统会自动建议估算值：
```
下一迭代建议工时: 14.5h（基于过去 3 个迭代加权平均）
```

> **完成记录**
> ```bash
> python3 scripts/step_enforcer.py record iterations-planned
> ```

---

## Phase 9 — 迭代执行循环

对每个迭代（N = 1, 2, 3 ...）重复以下步骤。

**进入迭代 N 的 Gate**：
```bash
# 首次迭代
python3 scripts/step_enforcer.py require iterations-planned

# 后续迭代：检查上一迭代门控
python3 scripts/step_enforcer.py require iter-{N-1}-gate-passed
```

### 9a. 创建迭代任务

```bash
./lifecycle task create --category check --iteration N --title "搭建开发环境"
./lifecycle task create --category dev --iteration N --title "实现用户登录功能"
./lifecycle task create --category test --iteration N \
  --title "验证用户登录 E2E" --test-case-ref TST-F01-S01
```

### 9b. 开发实现

```bash
./lifecycle task update --id ITR-1.DEV-001 --status in_progress
./lifecycle task update --id ITR-1.DEV-001 --status done
```

### 9c. 测试执行与结果记录（门控前强制）

```bash
# 测试通过
./lifecycle test-record --iteration N --test-id TST-F01-S01 --status pass

# 测试失败（--resolution 必填）
./lifecycle test-record --iteration N --test-id TST-F01-S02 --status fail \
  --resolution "已创建 ITR-N.DEV-005 修复，预计下一迭代解决"
```

### 9d. DoD 预检查（门控前建议运行）

```bash
./lifecycle dod check --iteration N
```

DoD 检查结果：
- `✓ pass` — 规则通过
- `⚠ warn` — 手动规则（如 code review），不阻断但会提示
- `✗ fail` — 命令类规则失败（如 lint 未通过），**门控阻断**

### 9e. 迭代门控验证（强制）

> **Gate（4 层产物验证 → DoD 检查 → 任务状态检查）**

```bash
./lifecycle gate --iteration N
```

门控通过后**自动触发**（三件事）：
1. **Sprint Review 生成**：`Docs/iterations/iter-N/sprint_review.md`（可发给 Stakeholder）
2. **Velocity 提示**：提示记录实际工时
3. **操作手册更新**：`Docs/manual/MANUAL.md` 覆盖更新

```bash
# 门控通过后，记录实际工时
./lifecycle velocity record --iteration N --hours <实际工时>

# 查看 velocity 趋势
./lifecycle velocity report
```

### 9f. Sprint Review 确认

门控通过后查看生成的 Sprint Review：

```bash
cat Docs/iterations/iter-N/sprint_review.md
```

Sprint Review 包含：
- 迭代目标 + 完成功能列表
- E2E 验收结果 + 测试通过率
- 工时估算 vs 实际对比
- 关键架构决策（最近 ADR）
- 下一迭代预告

可直接发给产品经理或老板。

---

## Phase 10 — 变更处理

任何节点的变更通过此 Phase 处理，**不允许单点修改**，必须全链路级联。

### 10a. PRD 变更（**无需 --old 参数**）

**特性**：`change prd` 命令自动读取 `validate` 时建立的最新快照做 diff，无需手动备份。

```bash
# 修改 PRD 后直接运行（无需 --old）：
./lifecycle change prd
```

自动执行：
1. 读取 `.lifecycle/snapshots/Docs_product_PRD_md_latest.md`（最新验证快照）
2. 与当前 `Docs/product/PRD.md` 做 diff，识别新增/修改/删除
3. 找出受影响的测试用例
4. 生成 `.lifecycle/CHANGE_IMPACT.md`（全链路影响报告）
5. 自动创建下游任务
6. **重置** `prd-validated` 步骤（需重新运行 Phase 3）

> **规则**：PRD 变更后必须重新验证（Phase 3），验证通过后自动建新快照。

### 10b. 代码变更

```bash
./lifecycle change code --components "用户认证模块,密码加密逻辑"
```

### 10c. 测试失败

```bash
# 情况 A：代码 Bug
./lifecycle change test --test-id TST-F01-S01 --failure-type bug
# → 创建 DEV Bug 修复任务

# 情况 B：需求遗漏（gap）
./lifecycle change test --test-id TST-F02-S01 --failure-type gap
# → 创建 PRD 变更任务，必须从源头修改 PRD

# 情况 C：测试用例本身有误
./lifecycle change test --test-id TST-F01-S02 --failure-type wrong-test
# → 提示修改测试用例 + 同步更新 MASTER_OUTLINE.md
```

---

## 附录 A — 命令速查

```bash
# 初始化
./lifecycle init --name "项目名"

# AI 协作起草
./lifecycle draft prd --description "产品描述"
./lifecycle draft arch

# 文档验证（通过后自动建快照）
./lifecycle validate --doc Docs/product/PRD.md --type prd
./lifecycle validate --doc Docs/tech/ARCH.md --type arch
./lifecycle validate --doc Docs/tests/MASTER_OUTLINE.md --type test_outline

# ADR 管理
./lifecycle adr create --title "标题" --status proposed
./lifecycle adr list
./lifecycle adr accept --num 1
./lifecycle adr deprecate --num 2

# Velocity 追踪
./lifecycle velocity start --iteration 1 --hours 12
./lifecycle velocity record --iteration 1 --hours 14
./lifecycle velocity report

# Risk Register
./lifecycle risk init
./lifecycle risk list
./lifecycle risk add --title "第三方 API 不稳定" --probability high --impact medium
./lifecycle risk update --risk-id RISK-001 --status mitigated --mitigation "已加重试"

# DoD 管理
./lifecycle dod show
./lifecycle dod init
./lifecycle dod check --iteration 1

# 快照管理
./lifecycle snapshot list
./lifecycle snapshot diff --doc Docs/product/PRD.md
./lifecycle snapshot take --doc Docs/product/PRD.md --label "before-change"

# 迭代相关
./lifecycle plan
./lifecycle outline generate --prd Docs/product/PRD.md --arch Docs/tech/ARCH.md --output Docs/tests/MASTER_OUTLINE.md
./lifecycle outline dependency-review  # v1.1.0 新增：审查依赖声明
./lifecycle outline migrate --from Docs/tests/MASTER_OUTLINE.md  # v1.1.0 新增：迁移到 test_graph.json
./lifecycle gate --iteration 1
./lifecycle test-record --iteration 1 --test-id TST-F01-S01 --status pass
./lifecycle test-record --iteration 1 --test-id TST-F01-S02 --status fail --resolution "..."

# 变更处理（PRD 无需 --old）
./lifecycle change prd
./lifecycle change code --components "模块名"
./lifecycle change test --test-id TST-F01-S01 --failure-type bug

# 状态与进度
./lifecycle status
./lifecycle task list
./lifecycle step status
```

---

## 附录 B — Velocity 追踪指南

Velocity 追踪帮助你了解实际开发速度，改善估算准确性。

### 使用流程

```bash
# 迭代开始时（Phase 8）
./lifecycle velocity start --iteration 1 --hours 12  # 估算 12 小时

# 迭代结束时（门控通过后）
./lifecycle velocity record --iteration 1 --hours 15  # 实际用了 15 小时

# 查看趋势（ASCII 图）
./lifecycle velocity report
```

### 示例输出

```
=== Velocity 趋势 ===

迭代  估算(h)  实际(h)  偏差%  图示
-----------------------------------------------
   1     12.0     15.0   +25%  ▲ ███████████████
   2     15.0     14.0    -7%  ● ██████████████
   3     14.0     13.5    -4%  ● █████████████
-----------------------------------------------
平均实际工时: 14.2h | 下一迭代建议估算: 13.8h
```

---

## 附录 C — ADR 管理指南

架构决策记录（ADR）让每个重要技术决策可追溯、可回溯。

### ADR 状态机

```
Proposed → Accepted → Deprecated
                    ↘ Superseded (by ADR-NNN)
```

### 常用操作

```bash
# 创建新 ADR
./lifecycle adr create \
  --title "使用 Redis 作为缓存层" \
  --status proposed \
  --context "API 响应时间超过 500ms，需要缓存" \
  --decision "使用 Redis 7.0，TTL 60s，key 格式 api:v1:{endpoint}:{hash}"

# 接受决策
./lifecycle adr accept --num 1

# 废弃决策
./lifecycle adr deprecate --num 2

# 被新 ADR 取代
./lifecycle adr supersede --num 2 --by 5

# 查看所有 ADR
./lifecycle adr list
```

ADR 文件保存在 `Docs/adr/ADR-NNN-<slug>.md`，`Docs/adr/INDEX.md` 自动维护。

---

## 附录 D — Risk Register 指南

Risk Register 贯穿整个产品生命周期，从 PRD 风险章节初始化，每迭代可更新状态。

### 风险矩阵

风险等级 = 概率 × 影响：

| 概率 ↓ \ 影响 → | 低 | 中 | 高 |
|----------------|----|----|-----|
| 高 | 🟡 中 | 🔴 高 | 🔴 极高 |
| 中 | 🟢 低 | 🟡 中 | 🔴 高 |
| 低 | 🟢 极低 | 🟢 低 | 🟡 中 |

### 常用操作

```bash
# 从 PRD 风险章节初始化（Phase 1 已自动运行）
./lifecycle risk init

# 查看风险矩阵（按风险等级排序）
./lifecycle risk list

# 新增风险
./lifecycle risk add \
  --title "第三方支付 API 不稳定" \
  --probability high \
  --impact high \
  --mitigation "增加重试机制 + 降级方案"

# 更新风险状态
./lifecycle risk update --risk-id RISK-001 \
  --status mitigated \
  --mitigation "已实现断路器模式，测试验证通过"
```

---

## 取消/暂停协议

```bash
# 暂停（保存断点）
./lifecycle pause --reason "等待设计稿" --phase "Phase 5"

# 取消
./lifecycle cancel

# 恢复
./lifecycle resume

# 查看进度
./lifecycle status
python3 scripts/step_enforcer.py status
```

---

## 断点续做

上下文被压缩后，从状态文件恢复：

```bash
# 查看当前已完成的 Phase
python3 scripts/step_enforcer.py status

# 查看整体项目状态
./lifecycle status
```

---

## 脚本强制说明

本 Skill 使用双层 Gate 强制：

**Soft Gate（SKILL.md 内）**：每个 Phase 开头的 `python3 scripts/step_enforcer.py require` 命令在步骤文件不存在时 exit(1)，中断执行。

**Artifact Gate（artifact_validator.py）**：检查每个 Phase 的产物文件是否存在且有实质内容（最小字节数），防止"记录步骤但未写内容"的作弊行为，包含时间戳验证（文件 mtime 必须 ≥ checkpoint 时间）。
