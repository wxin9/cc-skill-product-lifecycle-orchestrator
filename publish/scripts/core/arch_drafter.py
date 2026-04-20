"""
arch_drafter.py — AI 协作架构设计起草器。

使用方式：
  ./lifecycle draft arch

读取 PRD.md 功能点 + 架构访谈结果，自动生成架构草案（含 ADR 初稿、API 端点草案、数据模型草案）。
用户在草案基础上审核修改，而非从空 ARCH 模板填写。
"""
import json
from pathlib import Path

from .project_type_detector import detect_from_description, describe_project_type


ARCH_DRAFT_SYSTEM_PROMPT = """你是一位资深软件架构师，正在根据 PRD 和访谈信息起草技术架构文档。

你的任务：
1. 分析 PRD 中的功能点，推断系统边界和核心模块
2. 根据访谈信息（技术栈偏好、规模、部署环境）做技术选型
3. 生成完整的 Arc42-Lite 架构草案（含 ASCII 架构图）
4. 提出至少 2 条架构决策（ADR 格式），每条附上理由和权衡
5. 草案 API 端点列表（REST 格式）
6. 草案数据模型（实体 + 主要字段）
7. 在每个不确定处用 [❓待确认: 问题] 标注

生成后附上：
## 架构审稿建议
（3-5 个需要用户确认的关键决策点）
"""

ARCH_DRAFT_USER_PROMPT_TEMPLATE = """请根据以下信息生成技术架构草案：

## PRD 功能点摘要
{prd_summary}

## 访谈信息
{interview_info}

## 项目类型识别
{project_type}

请按以下章节生成：
1. 系统边界与上下文（外部依赖表）
2. 技术选型（含选择理由）
3. 系统架构图（ASCII）
4. 模块分解（职责表格）
5. 数据模型（实体 + 字段）
6. API 设计（REST 端点列表）
7. 部署方案
8. 架构决策记录（ADR 格式，≥ 2 条）
9. 架构审稿建议
"""


def load_prd_summary(prd_path: str, root: str = ".") -> str:
    """从 PRD.md 提取功能点摘要。"""
    import re
    p = Path(root) / prd_path
    if not p.exists():
        return "（PRD 文件不存在，请先完成 Phase 2）"
    text = p.read_text(encoding="utf-8", errors="ignore")
    # 提取所有 ### F01 — 功能名 段落（前 200 字符）
    features = re.findall(r'(### F\d+\s*[—-][^\n]+\n(?:(?!###).*\n){0,5})', text)
    if not features:
        return text[:600]
    return "\n".join(features[:6])


def load_interview_info(root: str = ".") -> str:
    """读取架构访谈结果。"""
    interview_file = Path(root) / ".lifecycle" / "arch_interview.json"
    if not interview_file.exists():
        return "（访谈信息未记录，请在 Phase 4 完成架构访谈后再起草架构）"
    data = json.loads(interview_file.read_text())
    lines = []
    field_labels = {
        "scale": "项目规模",
        "tech_stack_preference": "技术栈偏好",
        "team_size": "团队规模",
        "timeline": "上线时间线",
        "performance": "性能要求",
        "deployment": "部署环境",
    }
    for k, label in field_labels.items():
        v = data.get(k, "未指定")
        if isinstance(v, list):
            v = "、".join(v)
        lines.append(f"- {label}: {v}")
    return "\n".join(lines)


def generate_draft_prompt(root: str = ".") -> str:
    """生成架构草案提示词。"""
    prd_summary = load_prd_summary("Docs/product/PRD.md", root)
    interview_info = load_interview_info(root)

    # 项目类型识别（基于访谈信息）
    project_type = "web"
    try:
        proj_desc = interview_info + " " + prd_summary
        project_type = detect_from_description(proj_desc)
    except Exception:
        pass

    type_desc = describe_project_type(project_type)

    return ARCH_DRAFT_USER_PROMPT_TEMPLATE.format(
        prd_summary=prd_summary,
        interview_info=interview_info,
        project_type=type_desc,
    )


def get_system_prompt() -> str:
    return ARCH_DRAFT_SYSTEM_PROMPT


def print_draft_instructions(root: str = "."):
    """打印 Draft Mode 说明。"""
    interview_file = Path(root) / ".lifecycle" / "arch_interview.json"
    has_interview = interview_file.exists()
    print("""
╔═══════════════════════════════════════════════════════╗
║         Architecture Draft Mode — AI 协作起草          ║
╚═══════════════════════════════════════════════════════╝

Claude 将根据 PRD 功能点和架构访谈信息生成架构草案。
""")
    if not has_interview:
        print("⚠️  未找到架构访谈记录，建议先完成 Phase 4 架构访谈再起草。")
        print("   可运行 ./lifecycle interview --arch 完成访谈。\n")
    print("""草案生成后，请：
  1. 审阅技术选型，确认是否符合实际约束
  2. 检查 ADR 中的架构决策，用 ./lifecycle adr accept <NUM> 接受合理决策
  3. 补充 [❓待确认] 处
  4. 确认后运行 ./lifecycle validate --doc Docs/tech/ARCH.md --type arch

正在生成架案...\n""")
