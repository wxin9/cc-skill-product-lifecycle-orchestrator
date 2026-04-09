"""
prd_drafter.py — AI 协作 PRD 起草器。

使用方式：
  ./lifecycle draft prd --description "用一段话描述你的产品"

Claude 根据描述自动生成 PRD 草案结构，用户在草案基础上审核修改，
而非从空白模板开始填写（"审稿人"模式代替"填空题"模式）。

本模块输出的是"起草提示词"（Draft Prompt）——Claude 在 SKILL.md 中读取
此提示词后，会主动生成 PRD 草案内容供用户审核。
"""
from pathlib import Path


PRD_DRAFT_SYSTEM_PROMPT = """你是一位资深产品经理，正在帮助用户起草产品需求文档（PRD）。

用户已提供了产品描述。你的任务是：
1. 根据描述推断用户角色、核心痛点、商业目标
2. 生成完整的 PRD 草案（markdown 格式）
3. 所有功能点必须使用 `### F01 — 功能名称` 格式（验证器依赖此格式）
4. 需求语句尽量使用 EARS 语法（当/若/在...下，系统应...）
5. 非功能需求必须包含量化指标（如响应时间 < 200ms）
6. 在每个模糊处用 [❓待确认: 你的问题] 标注，引导用户填充细节

生成后，在草案末尾附上：
## 审稿建议
（列出 3-5 个你认为用户需要重点确认的问题）
"""

PRD_DRAFT_USER_PROMPT_TEMPLATE = """请根据以下产品描述，生成完整的 PRD 草案：

---
{description}
---

请严格按照以下章节结构生成：
1. 产品愿景（≥ 50 字）
2. 目标用户（≥ 2 个角色）
3. 核心功能（≥ 3 个，格式：### F01 — 功能名称）
4. 功能流程（每个功能 ≥ 3 步）
5. 非功能需求（含量化指标）
6. 范围边界（In Scope / Out of Scope）
7. 风险（表格：风险 | 概率 | 缓解方案）
8. 审稿建议（3-5 个待确认问题）
"""


def generate_draft_prompt(description: str, output_path: str = None) -> str:
    """
    生成 PRD 起草提示词，供 Claude 在对话中执行。
    如果提供 output_path，同时将提示词保存到文件（供记录）。
    """
    prompt = PRD_DRAFT_USER_PROMPT_TEMPLATE.format(description=description.strip())

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# PRD Draft Prompt\n\n{prompt}", encoding="utf-8")

    return prompt


def get_system_prompt() -> str:
    return PRD_DRAFT_SYSTEM_PROMPT


def print_draft_instructions(description: str):
    """在终端打印 Draft Mode 说明，引导用户审核草案。"""
    print("""
╔═══════════════════════════════════════════════════════╗
║           PRD Draft Mode — AI 协作起草                ║
╚═══════════════════════════════════════════════════════╝

Claude 将根据你的描述生成 PRD 草案。

草案生成后，请：
  1. 阅读草案，关注 [❓待确认] 标注处
  2. 修改不准确的内容
  3. 补充空白的细节
  4. 确认后运行 ./lifecycle validate --doc Docs/product/PRD.md --type prd

你的产品描述：
""")
    print(f"  {description}\n")
    print("正在生成草案...\n")
