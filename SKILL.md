---
name: product-lifecycle
description: 产品全环节管理技能，覆盖从产品设计到技术架构、迭代规划（TDD）、任务追踪和4层产物验证的完整研发生命周期。每个阶段通过脚本强校验，无法跳过，所有变更（PRD/代码/测试/迭代）都触发全链路级联更新。内置test-record命令强制记录测试执行结果，确保每个步骤到位。当用户提到「产品设计」「PRD」「需求文档」「技术架构」「迭代规划」「TDD」「product-lifecycle」「产品管理」「从零开始做一个产品」「整理项目文档」「迭代门控」「4层产物验证」「test-record」时立即触发。即使用户只说「帮我开始一个新产品」或「规划一下项目迭代」也应主动触发。
compatibility: Python 3.8+ stdlib only. No external packages required.
---

# Product Lifecycle

**快速摘要：**
- Phase 0：意图识别 → 自动判断用户需求类型
- Phase 1-6：从初始化 → PRD → 架构 → 测试大纲 → 迭代规划
- Phase 7：迭代执行 + 4层产物验证 + test-record + 自动生成操作手册
- Phase 8：变更处理（PRD/代码/测试失败级联更新）

**脚本强制的产品全环节管理工作流。** 每个阶段写入检查点文件，后续阶段的 gate 命令验证前置步骤，无法跳步。

所有脚本命令均在**用户项目目录**下运行（含 `.lifecycle/` 的目录）。

---

## Phase 0 — 意图识别（每次调用技能的第一步）

**目标：** 在执行任何操作之前，先自动判断用户的需求类型，决定从哪个 Phase 开始，无需用户手动声明。

### 0a. 快速探查项目状态

```bash
./lifecycle status
```

如果项目尚未初始化（无 `.lifecycle/` 目录），直接跳至 Phase 1，无需判断。

如果项目已初始化，也可以使用辅助脚本查看当前状态：

```bash
# 查看当前已完成的 Phase 和意图识别建议
python -c "
import sys; sys.path.insert(0, '$(cat .lifecycle/skill_path)')
from scripts.core.intent_classifier import check_project_state, suggest_entry_point
state = check_project_state('.')
print(state['phase_summary'])
# 可选：传入用户输入文本做意图分析
# result = suggest_entry_point('用户输入的内容', state)
# print(result)
"
```

### 0b. 意图分类规则

根据用户输入的内容，按以下优先级匹配（越具体的规则优先级越高）：

| 优先级 | 意图类型 | 典型输入示例 | 起始 Phase |
|---|---|---|---|
| 1（最高）| **Bug 修复 / Debug** | "报错了"、"测试失败"、"bug"、"修复XX" | Phase 8c（`change test --failure-type bug`） |
| 2 | **需求遗漏** | "测试发现了新场景"、"测试暴露了gap" | Phase 8c（`change test --failure-type gap`） |
| 3 | **PRD 变更** | "PRD 改了"、"需求变了"、"修改需求" | Phase 8a（`change prd`） |
| 4 | **代码变更** | "代码变更了"、"修改了XX模块" | Phase 8b（`change code`） |
| 5 | **补充测试** | "加测试用例"、"补充测试场景" | Phase 5（测试大纲更新） |
| 6 | **开始新迭代** | "新迭代"、"下一个迭代"、"迭代2" | Phase 7（迭代执行循环） |
| 7 | **技术架构调整** | "换数据库"、"调整架构"、"重构" | Phase 4（技术架构） |
| 8 | **新增功能需求** | "增加功能"、"新需求"、"PRD里加..." | Phase 2/3（PRD 更新 → 验证） |
| 9（最低）| **全新产品** | "新产品"、"从零开始"、"新项目" | Phase 1（初始化） |

**边界情况处理规则：**
- 如果意图不明确（输入模糊，如"帮我改个东西"），**不要猜测**，明确列出 2-3 个可能的意图选项请用户确认
- 如果前置步骤不满足（如说"开始新迭代"但迭代计划尚未生成），告知用户需要先完成前置步骤
- 如果多个规则同时命中，选择优先级最高的（数字最小的）

### 0c. 确认意图并制定执行计划

识别到意图后，**必须先通过 Plan 模式（或等效方式）列出执行计划，等用户确认后再执行**。

#### 在 Claude Code 环境中（有 `EnterPlanMode` / `ExitPlanMode` 工具）：

1. 调用 `EnterPlanMode`
2. 在规划模式中：探查项目现状（读取相关文档和步骤文件）、列出将执行的阶段和具体命令
3. 调用 `ExitPlanMode` 呈现执行计划给用户
4. 等待用户确认后开始执行

**计划格式示例（Phase 0 识别结果）：**
```
意图识别：新增功能需求
将从 Phase 2 开始，执行以下步骤：
  □ 更新 Docs/product/PRD.md（新增功能 FXX）
  □ 运行 ./lifecycle validate --doc Docs/product/PRD.md
  □ 更新 Docs/tech/ARCH.md（架构影响评估）
  □ 重新生成测试大纲
跳过的阶段：Phase 1（已完成）
```

#### 在非 Claude Code 环境（如 claude.ai）：

1. 以对话形式列出执行计划（Markdown 清单）
2. 明确说："**以上是执行计划，请确认后我将开始执行。**"
3. 等待用户明确确认（"好的"/"开始"/"确认"等）后才执行

> **⚠ 重要**：Phase 0 不是可选步骤。每次调用技能时必须先完成意图识别，不允许静默直接执行。

---

## 取消/暂停协议

```bash
# 随时暂停（保存断点）
./lifecycle pause --reason "原因" --phase "当前阶段"

# 随时取消
./lifecycle cancel

# 恢复
./lifecycle resume
```

查看当前进度：
```bash
./lifecycle status
```

---

## Phase 1 — 项目初始化

**目标：** 建立规范的文档结构，或整合已有项目。

### 1a. 运行初始化

```bash
# 新项目（当前目录）
./lifecycle init --name "项目名称"

# 已有项目（扫描并整合）
./lifecycle init --path /path/to/project
```

初始化会自动：
- **新项目**：创建 `Docs/` 完整目录结构 + `.lifecycle/` 状态目录
- **已有项目**：扫描并识别现有文档，生成迁移方案，整合到 `Docs/` 规范结构

创建的文档结构：
```
Docs/
├── INDEX.md                 ← 总索引（分层）
├── product/                 ← PRD.md, requirements/, user_flows/
├── tech/                    ← ARCH.md, components/
├── iterations/              ← INDEX.md, iter-N/PLAN.md + test_cases.md
├── tests/                   ← MASTER_OUTLINE.md, cases/
└── manual/                  ← MANUAL.md（用户操作手册，每次迭代门控通过后自动更新）
.lifecycle/
├── config.json              ← 项目配置
├── tasks.json               ← 全局任务注册表
└── steps/                   ← 步骤检查点（*.json）
```

### 1b. 验证初始化完成

```bash
./lifecycle step status
# 应看到: project-initialized ✓
```

**步骤已由脚本自动记录：`project-initialized`**

---

## Phase 2 — PRD 编写（产品设计文档）

**Gate：**
```bash
./lifecycle step require project-initialized
```

### 2a. 复制模板并填写

```bash
cp <skill_path>/references/doc_templates/prd_template.md Docs/product/PRD.md
```

打开 `Docs/product/PRD.md`，按模板章节填写：

| 必填章节 | 说明 |
|---|---|
| 产品愿景 | ≥ 50 字，描述核心问题和目标用户价值 |
| 核心功能 | ≥ 3 个功能，格式 `### F01 — 功能名称`（**必须**，验证器和测试大纲依赖此格式） |
| 用户角色 | 明确定义目标用户（≥ 2 条 bullet） |
| 功能流程 | 每个流程 ≥ 3 步（按序号列出） |
| 非功能需求 | 含具体量化指标（如响应时间 < 2s） |
| 范围边界 | 明确 In Scope / Out of Scope（避免隐性期望） |
| 风险 | 主要风险 + 缓解方案（表格或列表） |

**EARS 需求语法（加分项）：** 功能描述中的需求语句建议使用 EARS 模式：
- 事件驱动：`当<事件>时，系统应<动作>`
- 条件/异常：`若<条件>，则系统应<动作>`
- 状态驱动：`在<状态>下，系统应<动作>`
- 通用：`系统应<动作>`

EARS 合规率 ≥ 50% 可获得额外加分（最多 +5 分）。

对于**已有项目**：将已有的需求文档内容整理到 PRD.md 中。

### 2b. 同步创建需求任务

```bash
./lifecycle task create --category prd --title "产品愿景定义"
./lifecycle task create --category prd --title "核心功能列表"
./lifecycle task create --category prd --title "用户角色定义"
./lifecycle task create --category prd --title "功能流程设计"
./lifecycle task create --category prd --title "非功能需求定义"
```

---

## Phase 3 — PRD 验证

**Gate：**
```bash
./lifecycle step require project-initialized
```

### 3a. 自动验证文档清晰度

```bash
./lifecycle validate --doc Docs/product/PRD.md --type prd
```

- score ≥ 70：通过，步骤自动记录（`prd-written` + `prd-validated`）
- score < 70：显示具体问题，修改后重跑

**如果验证通过，步骤已记录：`prd-written`, `prd-validated`**

---

## Phase 4 — 技术架构

**Gate：**
```bash
./lifecycle step require prd-validated
```

### 4a. 架构访谈（与用户确认预期）

在进行架构设计之前，需要明确以下问题：

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

记录步骤：
```bash
./lifecycle step record arch-interview-done
```

### 4b. 编写技术架构文档

```bash
cp <skill_path>/references/doc_templates/arch_template.md Docs/tech/ARCH.md
```

基于 PRD 功能点和访谈结果填写 ARCH.md，遵循 **Arc42-Lite** 规范（Arc42 精华版），包含：
- 系统边界与上下文（外部依赖表）
- 技术选型（含选择原因）
- 系统架构图（ASCII 图或代码块）
- 模块分解（职责表格）
- 数据模型字段定义
- API 端点列表
- 部署方案
- 架构决策记录（ADR 格式）

### 4c. 验证架构文档

```bash
./lifecycle validate --doc Docs/tech/ARCH.md --type arch
```

验证通过后记录步骤：
```bash
./lifecycle step record arch-doc-written
```

---

## Phase 5 — 主测试大纲

**Gate：**
```bash
./lifecycle step require arch-doc-written
```

### 5a. 生成主测试大纲

```bash
./lifecycle outline generate \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --output Docs/tests/MASTER_OUTLINE.md
```

生成 `MASTER_OUTLINE.md`：
- 每个 PRD 功能点 → 多维度测试场景（根据架构上下文自动识别）
- 覆盖维度：`[UI]` 前端交互、`[API]` 后端接口、`[DATA]` 数据完整性、`[ASYNC]` 异步任务、`[EXT]` 外部依赖降级、`[FILE]` 文件操作边界、`[AUTH]` 权限控制
- 自动生成覆盖矩阵表格，一目了然各功能的测试维度覆盖
- 测试 ID 格式：`TST-{功能ID}-{场景ID}`，如 `TST-F01-S01`

**步骤自动记录：`test-outline-written`**

---

## Phase 6 — 迭代规划

**Gate：**
```bash
./lifecycle step require test-outline-written
```

### 6a. 生成迭代计划

```bash
./lifecycle plan \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --constraints '{"max_features_per_iter": 3}'
```

生成原则：
- 每个迭代用「**用户能够...**」描述目标（不是「实现XX模块」）
- 每个迭代必须 E2E 可测（有明确的界面入口或 API 端点 + 完整数据流）
- 自动验证：输出每个迭代的 E2E 验证状态（✓ / ⚠）

生成文件：
- `Docs/iterations/INDEX.md` — 迭代总览
- `Docs/iterations/iter-N/PLAN.md` — 各迭代计划（含 E2E 验收标准）

**步骤自动记录：`iterations-planned`**

---

## Phase 7 — 迭代执行循环

对每个迭代（N = 1, 2, 3 ...）重复以下步骤。

**进入迭代 N 的 Gate：**
```bash
# 首次迭代：检查 iterations-planned
./lifecycle step require iterations-planned

# 后续迭代：检查上一迭代门控
./lifecycle step require iter-{N-1}-gate-passed
```

### 7a. 创建迭代任务

```bash
# 检查任务（CHK）：环境/依赖
./lifecycle task create --category check --iteration N --title "搭建开发环境"

# 开发任务（DEV）：每个功能点创建对应任务
./lifecycle task create --category dev --iteration N --title "实现用户登录功能"
./lifecycle task create --category dev --iteration N --title "实现数据持久化"

# 测试任务（TST）：从测试大纲中取对应用例
./lifecycle task create --category test --iteration N \
  --title "验证用户登录 E2E" --test-case-ref TST-F01-S01
```

记录步骤：
```bash
./lifecycle step record iter-{N}-tasks-created
```

### 7b. 生成迭代测试用例

```bash
./lifecycle outline iter-tests \
  --features F01,F02 \
  --iteration N \
  --output Docs/iterations/iter-N/test_cases.md
```

记录步骤：
```bash
./lifecycle step record iter-{N}-tests-written
```

### 7c. 开发实现

开发过程中，随时更新任务状态：
```bash
./lifecycle task update --id ITR-1.DEV-001 --status in_progress
./lifecycle task update --id ITR-1.DEV-001 --status done
```

查看当前迭代任务：
```bash
./lifecycle task list --iteration N
```

### 7c.5. 测试执行与结果记录（强制，门控前必须完成）

每执行完一个测试用例后，**必须立即记录执行结果**。这是 gate 的硬性前置条件——门控通过前，代码会验证每个 done 状态的 TST 任务都有对应的执行记录。

```bash
# 测试通过
./lifecycle test-record --iteration N --test-id TST-F01-S01 --status pass

# 测试失败（--resolution 必填，说明如何处理该失败）
./lifecycle test-record --iteration N --test-id TST-F01-S02 --status fail \
  --resolution "已创建 ITR-N.DEV-005 修复，预计下一迭代解决"

# 可附加关联任务 ID（可选）
./lifecycle test-record --iteration N --test-id TST-F01-S01 --status pass \
  --task-ref ITR-1.TST-001

# 查看当前迭代全部测试执行状态
./lifecycle test-record --iteration N --list
```

**规则：**
- 每个标记为 `done` 的 TST 任务，其 `test_case_ref` 指向的 TST-ID **必须** 在 `.lifecycle/iter-N/test_results.json` 中有执行记录
- `fail` 状态必须填写 `--resolution`（描述处理方式），否则 gate 不通过
- 一个 TST-ID 可以多次记录，最新的记录生效

> **⚠ gate 强制检查**：`./lifecycle gate --iteration N` 在检查任务状态之前，会先运行 **4 层产物验证**：
> - Layer 1：PRD.md / ARCH.md / MASTER_OUTLINE.md 存在且有实质内容
> - Layer 2：iter-N/PLAN.md 和 test_cases.md 存在、TST-ID 交叉引用有效
> - Layer 3：所有 done 的 TST 任务有测试执行记录，fail 有 resolution
> - Layer 4：架构覆盖检查（警告，不阻断）
>
> 任何 Layer 1-3 验证失败 → **exit 1 阻断**，打印具体原因，不进入任务状态检查。

### 7d. 迭代门控验证（强制）

```bash
./lifecycle gate --iteration N
```

- 所有 CHK/DEV/TST 任务均为 `done` → **通过**，自动记录 `iter-N-gate-passed`
- 有任何未完成任务 → **exit 1**，显示阻塞任务列表，**不可进入下一迭代**

### 7e. 操作手册自动更新（门控通过后自动触发）

迭代门控通过后，`./lifecycle gate` 会**自动**生成/更新操作手册。无需手动操作。

如需手动触发（例如修复手册内容后重新生成）：
```bash
./lifecycle manual
```

**重要原则：**
- 全项目**只有一份**操作手册：`Docs/manual/MANUAL.md`
- 每次迭代完成后**覆盖更新**同一份文件（不新建版本文件）
- 手册开头注明基于第几个迭代生成，**无版本号**
- 手册内容基于所有已完成迭代的 `PLAN.md`，从用户视角描述功能使用方法
- 如果 `PLAN.md` 格式不符合标准（缺少目标/E2E验收标准等），手册生成会**报错并提示需要补全的字段**，不静默跳过

手册包含以下章节（从用户使用视角）：
- **安装**：环境依赖 + 安装步骤（来自 ARCH.md 技术选型/部署章节）
- **功能使用指南**：按迭代顺序，每个迭代的每个功能一节，包含操作入口、步骤、预期结果
- **卸载**：通用卸载指引（结合技术栈自动适配）
- **更新记录**：各迭代完成日期和新增功能摘要

---

## Phase 8 — 变更处理（随时可触发）

任何节点的变更都通过此 phase 处理，**不允许单点修改**，必须全链路级联。

### 8a. PRD 变更（产品设计节点）

```bash
# 修改 PRD 后运行：
./lifecycle change prd \
  --old Docs/product/PRD.md.backup \
  --new Docs/product/PRD.md
```

自动执行：
1. 识别 diff（added / modified / deleted / adjusted）
2. 找出受影响的测试用例（`TST-*`）
3. 找出受影响的迭代
4. 生成 `.lifecycle/CHANGE_IMPACT.md`（全链路影响报告）
5. 自动创建下游任务（架构更新、测试重验等）
6. **重置** `prd-validated` 步骤（需重新验证新版 PRD）

> 规则：PRD 变更后必须重新运行 Phase 3 验证，才能继续后续步骤。

### 8b. 代码变更（开发节点）

```bash
./lifecycle change code \
  --components "用户认证模块,密码加密逻辑"
```

自动执行：
1. 在测试大纲中追溯受影响的测试用例
2. 为下一迭代自动创建测试任务
3. 重置已通过的迭代门控（如有新增测试任务）
4. 生成 `.lifecycle/CODE_CHANGE_IMPACT.md`

### 8c. 测试失败（测试节点）

```bash
# 情况 A：代码 Bug
./lifecycle change test --test-id TST-F01-S01 --failure-type bug
# → 自动创建当前迭代的 DEV Bug 修复任务

# 情况 B：需求遗漏（测试暴露了 PRD 没有覆盖的场景）
./lifecycle change test --test-id TST-F02-S01 --failure-type gap
# → 自动创建 PRD 变更任务，必须从源头修改 PRD，走完整级联
# （不允许只在测试层打补丁）

# 情况 C：测试用例本身有误
./lifecycle change test --test-id TST-F01-S02 --failure-type wrong-test
# → 提示修改对应测试用例文件 + 同步更新 MASTER_OUTLINE.md
```

### 8d. 迭代计划变更（迭代节点）

```bash
./lifecycle change iteration --from-iter 2 --to-iter 3
```

手动编辑 `Docs/iterations/iter-N/PLAN.md` 后，重新验证门控：
```bash
./lifecycle gate --iteration N
```

---

## 文档分层索引

所有文档通过分层 INDEX.md 组织，主次分明：

```
Docs/INDEX.md              ← Level 1 总索引（入口）
  ├── product/INDEX.md     ← Level 2 产品文档（PRD + 需求 + 流程）
  ├── tech/INDEX.md        ← Level 2 技术文档（架构 + 组件）
  ├── iterations/INDEX.md  ← Level 2 迭代总览（所有迭代状态）
  └── tests/INDEX.md       ← Level 2 测试文档（大纲 + 用例）
```

每个 INDEX.md 自动维护，包含：文件列表、状态、最后更新时间。

---

## 任务编号规范

| 前缀 | 类型 | 示例 |
|---|---|---|
| `PRD-NNN` | 产品需求任务 | `PRD-001` |
| `ARCH-NNN` | 架构设计任务 | `ARCH-001` |
| `ITR-N.CHK-NNN` | 迭代检查任务 | `ITR-1.CHK-001` |
| `ITR-N.DEV-NNN` | 迭代开发任务 | `ITR-1.DEV-003` |
| `ITR-N.TST-NNN` | 迭代测试任务 | `ITR-1.TST-002` |
| `TST-{F}-{S}` | 测试用例 ID | `TST-F01-S01` |

查看所有任务：
```bash
./lifecycle task list
./lifecycle task stats
```

---

## 脚本命令速查

```bash
./lifecycle init              # 初始化项目（同时创建 lifecycle 包装脚本）
./lifecycle validate --doc Docs/product/PRD.md --type prd         # 验证 PRD（通过后自动保存快照）
./lifecycle validate --doc Docs/tech/ARCH.md --type arch          # 验证 ARCH（Arc42-Lite 规范）
./lifecycle validate --doc Docs/tests/MASTER_OUTLINE.md --type test_outline  # 验证测试大纲（IEEE 829）
./lifecycle plan              # 生成迭代计划
./lifecycle outline generate  # 生成测试大纲（需 PRD 功能点使用 ### F01 — 格式）
./lifecycle outline trace --features F01,F02  # 追溯影响
./lifecycle gate --iteration N  # 检查门控（先4层产物验证，再任务状态检查，通过后自动更新操作手册）
./lifecycle test-record --iteration N --test-id TST-F01-S01 --status pass  # 记录测试通过
./lifecycle test-record --iteration N --test-id TST-F01-S02 --status fail --resolution "..."  # 记录测试失败
./lifecycle test-record --iteration N --list  # 查看当前迭代测试执行状态
./lifecycle manual            # 手动生成/更新操作手册（自动检测已完成迭代数）
./lifecycle change prd        # 处理 PRD 变更（无需 --old，自动用快照）
./lifecycle change code       # 处理代码变更
./lifecycle change test       # 处理测试失败
./lifecycle status            # 查看仪表盘（工作流进度、文档评分、任务进度条）
./lifecycle task list         # 查看任务列表
./lifecycle step status       # 查看步骤完成情况
./lifecycle step record <id>  # 手动记录步骤
./lifecycle step require <id> # 检查步骤是否完成（门控）
```
