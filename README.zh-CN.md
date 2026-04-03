[English](README.md) | [中文](README.zh-CN.md)

# Product-Lifecycle Skill（产品全生命周期管理技能）

[![GitHub license](https://img.shields.io/github/license/wxin9/cc-skill-product-lifecycle)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/wxin9/cc-skill-product-lifecycle)](https://github.com/wxin9/cc-skill-product-lifecycle/releases)

为 Claude Code 打造的综合产品全生命周期管理技能，覆盖从产品设计到技术架构、迭代规划（TDD）、任务追踪和 4 层产物验证的完整研发生命周期。每个阶段通过脚本强制校验，无法跳过，所有变更（PRD/代码/测试/迭代）都触发全链路级联更新。

## 功能特性

- **Phase 0：意图识别** — 自动判断用户需求类型
- **Phase 1-6**：从初始化 → PRD → 架构 → 测试大纲 → 迭代规划
- **Phase 7**：迭代执行 + 4 层产物验证 + test-record + 自动生成操作手册
- **Phase 8**：变更处理（PRD/代码/测试失败级联更新）
- **脚本强制的工作流**：每个阶段写入检查点文件，后续阶段验证前置步骤，无法跳步
- **EARS 需求语法**：PRD 支持 EARS 模式编写，提高需求清晰度
- **IEEE 829 测试大纲**：测试大纲遵循 IEEE 829 精华 + BDD Given/When/Then
- **Arc42-Lite 架构**：架构文档采用 Arc42 Lite（适合中小型项目）
- **自动生成操作手册**：每次迭代门控通过后自动生成/更新用户操作手册

## 安装

### 前置条件

- Python 3.8 或更高版本
- Claude Code（可选，但推荐使用）

### 安装为 Claude Code 技能

1. 克隆此仓库：
```bash
git clone https://github.com/wxin9/cc-skill-product-lifecycle.git
```

2. 复制技能到 Claude Code 技能目录：
```bash
mkdir -p ~/.claude/skills
cp -r cc-skill-product-lifecycle ~/.claude/skills/product-lifecycle
```

### 或直接使用

你也可以在任何项目目录中直接使用脚本：

```bash
# 初始化新项目
python -m scripts init --name "My Project"
```

## 通过 Claude Code 使用（推荐）

使用本技能最简单的方式是通过与 Claude Code 的**自然语言对话**。安装完成后，你无需手动执行任何命令——只需描述你想做什么：

**示例：**

> "帮我启动一个叫 MyApp 的新产品"

> "帮我写一个任务管理工具的 PRD"

> "设计技术架构"

> "规划迭代并开始开发"

> "需求变了，更新一下 PRD"

Claude Code 会自动：
1. 识别你的意图（Phase 0）
2. 执行相应的阶段工作流
3. 生成并验证所有产物（PRD、架构文档、测试大纲等）
4. 管理迭代规划和执行
5. 在需求变化时处理级联更新

**无需记忆任何命令**——用自然语言和 Claude Code 对话即可，技能会自动处理其余工作。

## 手动使用（高级）

> 以下章节介绍如何手动使用脚本。对大多数用户来说，上述 Claude Code 对话方式已经足够。

## 快速开始

### 1. 初始化新项目

```bash
# 创建新项目
mkdir my-product && cd my-product

# 使用 product-lifecycle 初始化
python -m scripts init --name "我的产品"
```

### 2. 编写 PRD

```bash
# 复制 PRD 模板
cp ~/.claude/skills/product-lifecycle/references/doc_templates/prd_template.md Docs/product/PRD.md

# 编辑并填写 PRD
edit Docs/product/PRD.md

# 验证 PRD
python -m scripts validate --doc Docs/product/PRD.md --type prd
```

### 3. 创建技术架构

```bash
# 复制架构模板
cp ~/.claude/skills/product-lifecycle/references/doc_templates/arch_template.md Docs/tech/ARCH.md

# 编辑并填写架构
edit Docs/tech/ARCH.md

# 验证架构
python -m scripts validate --doc Docs/tech/ARCH.md --type arch
```

### 4. 生成测试大纲

```bash
# 从 PRD 和 ARCH 生成主测试大纲
python -m scripts outline generate \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md \
  --output Docs/tests/MASTER_OUTLINE.md
```

### 5. 规划迭代

```bash
# 生成迭代计划
python -m scripts plan \
  --prd Docs/product/PRD.md \
  --arch Docs/tech/ARCH.md
```

### 6. 执行迭代

```bash
# 为迭代 1 创建任务
python -m scripts task create --category check --iteration 1 --title "搭建开发环境"
python -m scripts task create --category dev --iteration 1 --title "实现功能 F01"
python -m scripts task create --category test --iteration 1 --title "测试功能 F01" --test-case-ref TST-F01-S01

# 记录测试结果
python -m scripts test-record --iteration 1 --test-id TST-F01-S01 --status pass

# 检查迭代门控
python -m scripts gate --iteration 1
```

## 文档

- [SKILL.md](SKILL.md) - 完整技能文档（中文）
- [PRD 模板](references/doc_templates/prd_template.md) - 产品需求文档模板
- [架构模板](references/doc_templates/arch_template.md) - 技术架构文档模板（Arc42-Lite）
- [测试大纲模板](references/doc_templates/test_outline_template.md) - 主测试大纲模板（IEEE 829）

## 命令参考

```bash
python -m scripts init              # 初始化项目结构
python -m scripts validate          # 验证 PRD 或 ARCH 文档清晰度
python -m scripts task              # 任务管理（create / update / list / stats / gate）
python -m scripts plan              # 从 PRD + ARCH 生成迭代计划
python -m scripts outline           # 测试大纲管理（generate / trace / iter-tests）
python -m scripts gate              # 检查迭代门控（所有任务完成？）
python -m scripts change            # 处理任意节点的变更（prd / code / test / iteration）
python -m scripts status            # 查看项目整体状态
python -m scripts pause             # 在当前点暂停工作
python -m scripts resume            # 从暂停状态恢复
python -m scripts cancel            # 取消当前工作流
python -m scripts test-record       # 记录测试用例执行结果
python -m scripts manual            # 生成/更新用户操作手册
python -m scripts step              # 步骤状态管理
```

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 许可证

本项目采用 Apache License 2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 灵感来自各种产品生命周期管理方法论
- 为 Claude Code 用户打造
- 感谢所有贡献者

## 商业使用

如果您将此技能用于商业目的，请在您的产品文档、网站或其他适当位置包含以下归属声明：

```
本产品使用 Product-Lifecycle Skill (https://github.com/wxin9/cc-skill-product-lifecycle)
版权所有 2026 Kaiser (wxin966@gmail.com)
采用 Apache License 2.0 许可证
```
