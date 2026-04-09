[English](README.md) | [中文](README.zh-CN.md)

# Product Lifecycle

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

> 面向 Claude Code 的 AI 协作产品全生命周期管理技能 — 从 PRD 到交付，脚本强制门控 + 4 层产物验证。

## 为什么需要 Product Lifecycle？

手动管理产品生命周期时，你可能会遇到这些问题：

- **文档散落各处**：PRD 在 Wiki、架构在 Confluence、测试在 Excel，版本对不上
- **流程靠自律**：没有强制门控，跳过验证直接写代码，后期返工成本巨大
- **变更级联断裂**：改了 PRD 却忘了更新测试用例，测试失败才发现需求已经变了
- **估算全凭感觉**：每个迭代拍脑袋估工时，项目延期毫无预警
- **架构决策无记录**：三个月后没人记得当初为什么选了 MongoDB

Product Lifecycle 用**脚本强制门控**（`sys.exit(1)` 物理阻断）解决这些问题：每个阶段写入检查点文件，后续阶段验证前置条件，无法跳步。所有变更（PRD/代码/测试）触发全链路级联更新，确保产物始终一致。

## 核心特性

- **AI 协作起草**：Claude 主动起草 PRD 和架构文档，你做审稿人，告别面对空白模板
- **复合意图识别**："修了 bug 顺便调整需求" — 两个意图同时识别并排优先级，分步执行
- **脚本强制门控**：物理阻断（`sys.exit(1)`），无法跳步，双层 Gate（步骤检查 + 产物内容验证）
- **项目类型自动识别**：5 种类型（Web / CLI / 移动端 / 数据管道 / 微服务），测试维度自适应
- **自适应测试维度**：测试大纲根据项目类型自动选择对应维度集（如 Web 选 UI/API/DATA/AUTH/PERF/XSS）
- **自动快照 & Diff**：验证通过自动快照，`change prd` 无需手动 `--old`，自动读取快照做 diff
- **速度追踪**：估算 vs 实际工时 + ASCII 趋势图，历史数据自动推荐下一迭代估算值
- **可配置 DoD**：扩展门控检查（lint / 覆盖率 / 代码审查），`warn` 不阻断、`fail` 直接阻断
- **ADR 管理**：架构决策记录全生命周期（Proposed -> Accepted -> Deprecated -> Superseded）
- **风险登记册**：从项目初始化贯穿所有阶段，概率 x 影响矩阵自动评级
- **Sprint Review**：门控通过自动生成评审材料（目标/完成/验收/工时/ADR），可直接发给 Stakeholder
- **零外部依赖**：仅使用 Python 标准库，`pip install` 都不需要

## 架构流程

```mermaid
graph LR
    P0[阶段 0<br>意图识别] --> P1[阶段 1<br>项目初始化]
    P1 --> P2[阶段 2<br>起草 PRD]
    P2 --> P3[阶段 3<br>验证 PRD]
    P3 --> P4[阶段 4<br>架构访谈]
    P4 --> P5[阶段 5<br>起草架构]
    P5 --> P6[阶段 6<br>验证架构]
    P6 --> P7[阶段 7<br>测试大纲]
    P7 --> P8[阶段 8<br>迭代规划]
    P8 --> P9[阶段 9<br>迭代执行 & 门控]
    P9 -->|变更| P10[阶段 10<br>变更处理]
    P10 --> P3
```

## 快速开始

### 安装

**前置条件**：Python 3.8+

```bash
# 克隆仓库
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git

# 安装为 Claude Code 技能
mkdir -p ~/.claude/skills
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### 使用方式（推荐：自然语言对话）

安装完成后，无需记忆任何命令。用自然语言和 Claude Code 对话即可：

> "帮我启动一个叫 MyApp 的新产品"

> "帮我写一个任务管理工具的 PRD"

> "设计技术架构"

> "规划迭代并开始开发"

> "需求变了，更新一下 PRD"

> "修了个 bug，顺便想调整下需求"

Claude Code 会自动：识别意图（阶段 0） -> 执行对应工作流 -> 生成并验证所有产物 -> 管理迭代规划 -> 处理变更级联。

### 手动 CLI 使用

> 以下章节介绍如何手动使用脚本。对大多数用户来说，上述自然语言对话方式已经足够。

#### 1. 初始化新项目

```bash
mkdir my-product && cd my-product
python -m scripts init --name "我的产品"
```

#### 2. AI 协作起草 PRD

```bash
# Claude 根据产品描述生成 PRD 草案，你做审稿人
python -m scripts draft prd --description "一个帮助独立摄影师管理外拍档期的轻量 SaaS 平台"
```

#### 3. 验证 PRD（通过后自动快照）

```bash
python -m scripts validate --doc Docs/product/PRD.md --type prd
```

#### 4. AI 协作起草架构

```bash
python -m scripts draft arch
```

#### 5. 验证架构（通过后自动快照）

```bash
python -m scripts validate --doc Docs/tech/ARCH.md --type arch
```

#### 6. 生成自适应测试大纲

```bash
python -m scripts outline generate \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --output Docs/tests/MASTER_OUTLINE.md
```

#### 7. 规划迭代

```bash
python -m scripts plan \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md
```

#### 8. 执行迭代

```bash
# 创建任务
python -m scripts task create --category check --iteration 1 --title "搭建开发环境"
python -m scripts task create --category dev --iteration 1 --title "实现功能 F01"
python -m scripts task create --category test --iteration 1 --title "测试功能 F01" --test-case-ref TST-F01-S01

# 记录测试结果
python -m scripts test-record --iteration 1 --test-id TST-F01-S01 --status pass

# 迭代门控（4 层产物验证 + DoD 检查）
python -m scripts gate --iteration 1
```

#### 9. 变更处理

```bash
# PRD 变更（自动读取快照 diff，无需 --old）
python -m scripts change prd

# 代码变更
python -m scripts change code --components "用户认证模块"

# 测试失败
python -m scripts change test --test-id TST-F01-S01 --failure-type bug
```

## 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `init` | 初始化项目结构（含 DoD / Risk Register / ADR 目录） | `init --name "项目名"` |
| `draft prd` | AI 协作起草 PRD（Claude 生成草案，用户审核） | `draft prd --description "产品描述"` |
| `draft arch` | AI 协作起草架构文档（含 ADR 初稿） | `draft arch` |
| `validate` | 验证文档质量（PRD / ARCH / 测试大纲），通过后自动快照 | `validate --doc PRD.md --type prd` |
| `outline generate` | 根据项目类型自适应生成测试大纲 | `outline generate --prd PRD.md --arch ARCH.md` |
| `plan` | 从 PRD + ARCH 生成迭代计划 | `plan --prd PRD.md --arch ARCH.md` |
| `task create` | 创建迭代任务（check / dev / test） | `task create --category dev --iteration 1 --title "..."` |
| `task update` | 更新任务状态 | `task update --id ITR-1.DEV-001 --status done` |
| `task list` | 查看任务列表 | `task list --iteration 1` |
| `task stats` | 任务统计 | `task stats --iteration 1` |
| `test-record` | 记录测试用例执行结果（门控前强制） | `test-record --iteration 1 --test-id TST-F01-S01 --status pass` |
| `gate` | 迭代门控（4 层产物验证 + DoD + 自动生成 Sprint Review） | `gate --iteration 1` |
| `change prd` | PRD 变更处理（自动快照 diff，无需 --old） | `change prd` |
| `change code` | 代码变更处理 | `change code --components "模块名"` |
| `change test` | 测试失败处理（bug / gap / wrong-test） | `change test --test-id TST-F01-S01 --failure-type bug` |
| `adr create` | 创建架构决策记录 | `adr create --title "标题" --status proposed` |
| `adr list` | 查看所有 ADR | `adr list` |
| `adr accept` | 接受架构决策 | `adr accept --num 1` |
| `adr deprecate` | 废弃架构决策 | `adr deprecate --num 2` |
| `velocity start` | 设定迭代估算工时 | `velocity start --iteration 1 --hours 12` |
| `velocity record` | 记录迭代实际工时 | `velocity record --iteration 1 --hours 15` |
| `velocity report` | 查看 Velocity 趋势（ASCII 图） | `velocity report` |
| `risk init` | 从 PRD 风险章节初始化风险登记册 | `risk init` |
| `risk list` | 查看风险矩阵（按等级排序） | `risk list` |
| `risk add` | 新增风险条目 | `risk add --title "..." --probability high --impact medium` |
| `risk update` | 更新风险状态 | `risk update --risk-id RISK-001 --status mitigated` |
| `dod show` | 查看当前 DoD 规则 | `dod show` |
| `dod check` | DoD 预检查（warn 不阻断，fail 阻断） | `dod check --iteration 1` |
| `snapshot list` | 查看所有文档快照 | `snapshot list` |
| `snapshot diff` | 查看文档变更 diff | `snapshot diff --doc Docs/product/PRD.md` |
| `status` | 查看项目整体状态 | `status` |
| `step status` | 查看已完成的阶段进度 | `step status` |
| `pause` | 暂停工作（保存断点） | `pause --reason "等待设计稿"` |
| `resume` | 从暂停状态恢复 | `resume` |
| `cancel` | 取消当前工作流 | `cancel` |
| `manual` | 生成/更新用户操作手册 | `manual` |

## 生成的项目结构

```
Docs/
├── INDEX.md                       # 总索引
├─��� product/                       # PRD.md, requirements/
├── tech/                          # ARCH.md, components/
├── adr/                           # ADR-001-xxx.md + INDEX.md
├── iterations/                    # iter-N/PLAN.md + test_cases.md + sprint_review.md
├── tests/                         # MASTER_OUTLINE.md
└── manual/                        # MANUAL.md
.lifecycle/
├── config.json                    # 项目配置
├── dod.json                       # DoD 规则（可自定义）
├── risk_register.json             # 风险登记册
├── velocity.json                  # 速度追踪数据
├── snapshots/                     # 文档快照（validate 自动建立）
├── tasks.json                     # 全局任务注册表
└── steps/                         # 步骤检查点
```

## 模型兼容性

本技能仅依赖 Python 标准库，无外部依赖。对 Claude 模型的要求：

- **推荐**：Claude Sonnet 4+ — 最佳的起草质量和推理能力
- **可用**：Claude Haiku — 可完成全流程，起草质量略低但门控验证不受影响
- **核心机制**：脚本强制门控（`sys.exit(1)`）不依赖模型能力，任何能执行 Python 脚本的环境均可运行

## 贡献指南

欢迎贡献！请随时提交 Pull Request。

## 许可证

本项目采用 Apache License 2.0 许可证 — 详见 [LICENSE](LICENSE) 文件。

## 商业使用

如果您将此技能用于商业目的，请在您的产品文档、网站或其他适当位置包含以下归属声明：

```
本产品使用 Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
版权所有 2026 Kaiser (wxin966@gmail.com)
采用 Apache License 2.0 许可证
```
