"""
manual_generator.py — 用户操作手册生成模块

基于已完成的所有迭代内容，生成/更新唯一一份操作手册：
  Docs/manual/MANUAL.md

设计原则：
  - 全项目只有一份操作手册，每次迭代完成后覆盖更新
  - 无版本号，只标注基于第几个迭代生成 + 日期
  - 生成前必须先通过 plan_format_normalizer 规范化所有 PLAN.md
  - 从 ARCH.md 提取安装/卸载相关信息，从 PLAN.md 提取功能使用说明

手册结构：
  > 本手册基于已完成的 N 个迭代生成，最后更新：YYYY-MM-DD

  # [项目名] 用户操作手册

  ## 安装
  ## 功能使用指南
  ## 卸载
  ## 更新记录
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .plan_format_normalizer import normalize_all_plans


# ---------------------------------------------------------------------------
# 主函数：generate_manual
# ---------------------------------------------------------------------------

def generate_manual(root: str | Path, iteration_n: int) -> dict:
    """
    生成/更新唯一操作手册 Docs/manual/MANUAL.md。

    参数：
      root        — 项目根目录（含 .lifecycle/ 和 Docs/）
      iteration_n — 已完成的最高迭代编号

    返回：
    {
        "ok": bool,
        "path": str,           # 生成的手册路径
        "error": str,          # 错误信息（ok=False 时）
        "warnings": List[str], # 非致命警告
    }
    """
    root = Path(root).resolve()
    warnings: list[str] = []

    # ── 0. 创建 Docs/manual/ 目录 ───────────────────────────────────────────
    manual_dir = root / "Docs" / "manual"
    manual_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. 规范化所有 PLAN.md ────────────────────────────────────────────────
    if iteration_n > 0:
        norm_result = normalize_all_plans(root, iteration_n)
        if not norm_result["all_ok"]:
            # 收集所有不合格的迭代
            failed = {
                k: v for k, v in norm_result["results"].items()
                if not v["ok"]
            }
            error_lines = [f"以下迭代的 PLAN.md 格式不符合标准，无法生成操作手册："]
            for iter_key, res in failed.items():
                error_lines.append(f"\n  [{iter_key}]")
                for field in res.get("manual_required", []):
                    error_lines.append(f"    ✗ 需要填写：{field}")
                if res.get("error"):
                    error_lines.append(f"    ✗ 错误：{res['error']}")
            error_lines.append(
                "\n请先手动补全上述字段，然后重新运行手册生成命令。"
            )
            return {
                "ok": False,
                "path": "",
                "error": "\n".join(error_lines),
                "warnings": warnings,
            }

    # ── 2. 读取项目配置 ──────────────────────────────────────────────────────
    config = _load_config(root)
    project_name = config.get("project_name", root.name)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── 3. 提取 ARCH.md 信息 ────────────────────────────────────────────────
    arch_info = _extract_arch_info(root)

    # ── 4. 提取各迭代功能信息 ────────────────────────────────────────────────
    iterations_info = _extract_iterations_info(root, iteration_n)

    # ── 5. 生成手册内容 ──────────────────────────────────────────────────────
    content = _render_manual(
        project_name=project_name,
        iteration_n=iteration_n,
        today=today,
        arch_info=arch_info,
        iterations_info=iterations_info,
    )

    # ── 6. 写入文件（覆盖）──────────────────────────────────────────────────
    manual_path = manual_dir / "MANUAL.md"
    manual_path.write_text(content, encoding="utf-8")

    # ── 7. 更新 Docs/INDEX.md ────────────────────────────────────────────────
    index_warnings = update_manual_index(root)
    warnings.extend(index_warnings)

    return {
        "ok": True,
        "path": str(manual_path.relative_to(root)),
        "error": "",
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 更新 Docs/INDEX.md
# ---------------------------------------------------------------------------

def update_manual_index(root: str | Path) -> list[str]:
    """
    在 Docs/INDEX.md 的文档目录表格中确保存在操作手册条目。

    返回：warnings 列表（非致命问题）
    """
    root = Path(root).resolve()
    index_path = root / "Docs" / "INDEX.md"
    warnings: list[str] = []

    if not index_path.exists():
        warnings.append("Docs/INDEX.md 不存在，跳过更新")
        return warnings

    content = index_path.read_text(encoding="utf-8")

    # 检查是否已有操作手册条目
    if "manual/" in content or "MANUAL.md" in content or "操作手册" in content:
        return warnings  # 已存在，不重复插入

    # 在表格末尾插入操作手册行（在最后一个 | 行之后）
    manual_row = "| 操作手册 | [manual/](manual/MANUAL.md) | 产品操作手册（安装、使用、卸载） |\n"

    # 找到表格区域，在最后一个表格行后插入
    lines = content.splitlines(keepends=True)
    last_table_line = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "|" in line:
            last_table_line = i

    if last_table_line >= 0:
        lines.insert(last_table_line + 1, manual_row)
        index_path.write_text("".join(lines), encoding="utf-8")
    else:
        # 在文件末尾追加
        content += f"\n## 操作手册\n\n- [MANUAL.md](manual/MANUAL.md) — 产品操作手册\n"
        index_path.write_text(content, encoding="utf-8")

    return warnings


# ---------------------------------------------------------------------------
# 内部：提取 ARCH.md 安装/卸载信息
# ---------------------------------------------------------------------------

def _extract_arch_info(root: Path) -> dict:
    """从 ARCH.md 提取安装相关信息（技术选型、运行环境）。"""
    arch_path = root / "Docs" / "tech" / "ARCH.md"
    result = {
        "tech_stack": [],
        "install_steps": [],
        "uninstall_notes": "",
        "raw_tech_section": "",
    }

    if not arch_path.exists():
        return result

    content = arch_path.read_text(encoding="utf-8", errors="replace")

    # 提取技术选型章节
    tech_match = re.search(
        r"##\s*(?:技术选型|技术栈|Technology Stack)[^\n]*\n(.*?)(?=\n##|\Z)",
        content, re.DOTALL | re.IGNORECASE
    )
    if tech_match:
        result["raw_tech_section"] = tech_match.group(1).strip()

    # 提取技术栈列表（bullet points 或 表格中的技术名称）
    tech_items = re.findall(
        r"[-*|]\s*([A-Za-z][A-Za-z0-9\s.#+\-]{2,30})(?:\s*[：:|-]|\s*\|)",
        result["raw_tech_section"]
    )
    result["tech_stack"] = [t.strip() for t in tech_items if len(t.strip()) > 2][:10]

    # 提取部署/运行环境章节作为安装参考
    deploy_match = re.search(
        r"##\s*(?:部署|Deployment|运行环境)[^\n]*\n(.*?)(?=\n##|\Z)",
        content, re.DOTALL | re.IGNORECASE
    )
    if deploy_match:
        # 从中提取命令（代码块里的内容）
        cmds = re.findall(r"```[^\n]*\n(.*?)```", deploy_match.group(1), re.DOTALL)
        if cmds:
            result["install_steps"] = cmds[0].strip().splitlines()[:10]

    return result


# ---------------------------------------------------------------------------
# 内部：提取各迭代功能信息
# ---------------------------------------------------------------------------

def _extract_iterations_info(root: Path, max_iter: int) -> list[dict]:
    """
    读取各迭代 PLAN.md，提取功能使用说明。
    此函数调用时 PLAN.md 已通过 normalize_all_plans，格式可信。
    """
    results = []

    for n in range(1, max_iter + 1):
        plan_path = root / "Docs" / "iterations" / f"iter-{n}" / "PLAN.md"
        if not plan_path.exists():
            continue

        content = plan_path.read_text(encoding="utf-8", errors="replace")

        # 提取标题
        title_m = re.search(r"^#\s+迭代\s+\d+[：:]\s*(.+)$", content, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else f"迭代 {n}"

        # 提取目标
        goal_m = re.search(r"\*\*目标[：:]\*\*\s*(.+)", content)
        goal = goal_m.group(1).strip() if goal_m else ""

        # 提取关联功能
        feat_m = re.search(r"\*\*关联功能[：:]\*\*\s*(.+)", content)
        features = [f.strip() for f in feat_m.group(1).split(",")] if feat_m else []

        # 提取 E2E 验收标准（用于生成操作步骤）
        e2e_entries = []
        e2e_blocks = re.findall(
            r"###\s+E2E-\d+[：:]\s*(.+?)\n(.*?)(?=###\s+E2E|\n##|\Z)",
            content, re.DOTALL
        )
        for e2e_desc, e2e_body in e2e_blocks:
            entry_m = re.search(r"\*\*入口点[：:]\*\*\s*(.+)", e2e_body)
            flow_m = re.search(r"\*\*数据流[：:]\*\*\s*(.+)", e2e_body)
            e2e_entries.append({
                "description": e2e_desc.strip(),
                "entry_point": entry_m.group(1).strip() if entry_m else "",
                "data_flow": flow_m.group(1).strip() if flow_m else "",
            })

        # 提取完成时间（从步骤文件推断）
        gate_step = root / ".lifecycle" / "steps" / f"iter-{n}-gate-passed.json"
        completed_at = ""
        if gate_step.exists():
            try:
                gate_data = json.loads(gate_step.read_text(encoding="utf-8"))
                completed_at = gate_data.get("recorded_at", "")[:10]  # YYYY-MM-DD
            except Exception:
                pass

        results.append({
            "number": n,
            "title": title,
            "goal": goal,
            "features": features,
            "e2e_entries": e2e_entries,
            "completed_at": completed_at,
        })

    return results


# ---------------------------------------------------------------------------
# 内部：渲染手册 Markdown
# ---------------------------------------------------------------------------

def _render_manual(
    project_name: str,
    iteration_n: int,
    today: str,
    arch_info: dict,
    iterations_info: list[dict],
) -> str:
    lines: list[str] = []

    # ── 头部说明（无版本号） ─────────────────────────────────────────────────
    if iteration_n == 0:
        lines.append(f"> 本手册尚未完成迭代，内容为初始占位。最后更新：{today}")
    else:
        lines.append(
            f"> 本手册基于已完成的 **{iteration_n}** 个迭代生成，最后更新：{today}"
        )
    lines.append("")

    # ── 标题 ────────────────────────────────────────────────────────────────
    lines.append(f"# {project_name} 用户操作手册")
    lines.append("")

    # ── 目录 ────────────────────────────────────────────────────────────────
    lines += [
        "## 目录",
        "",
        "1. [安装](#安装)",
        "2. [功能使用指南](#功能使用指南)",
        "3. [卸载](#卸载)",
        "4. [更新记录](#更新记录)",
        "",
        "---",
        "",
    ]

    # ── 安装 ────────────────────────────────────────────────────────────────
    lines += ["## 安装", ""]

    if arch_info["tech_stack"]:
        lines.append("### 环境依赖")
        lines.append("")
        for tech in arch_info["tech_stack"]:
            lines.append(f"- {tech}")
        lines.append("")

    if arch_info["install_steps"]:
        lines.append("### 安装步骤")
        lines.append("")
        lines.append("```bash")
        for cmd in arch_info["install_steps"]:
            if cmd.strip():
                lines.append(cmd)
        lines.append("```")
        lines.append("")
    else:
        lines += [
            "### 安装步骤",
            "",
            "> 请参考 [技术架构文档](../tech/ARCH.md) 中的「部署」章节获取详细安装指南。",
            "",
        ]

    lines += ["---", ""]

    # ── 功能使用指南 ─────────────────────────────────────────────────────────
    lines += ["## 功能使用指南", ""]

    if not iterations_info:
        lines += [
            "> 尚无已完成的迭代，功能使用指南将在第一个迭代完成后自动生成。",
            "",
        ]
    else:
        for iter_info in iterations_info:
            n = iter_info["number"]
            title = iter_info["title"]
            goal = iter_info["goal"]
            e2e_entries = iter_info["e2e_entries"]

            lines += [f"### 迭代 {n}：{title}", ""]
            if goal:
                lines += [f"> {goal}", ""]

            if e2e_entries:
                for e2e in e2e_entries:
                    desc = e2e["description"]
                    entry = e2e["entry_point"]
                    flow = e2e["data_flow"]

                    lines += [f"#### {desc}", ""]
                    if entry:
                        lines.append(f"**操作入口：** {entry}")
                        lines.append("")
                    if flow:
                        # 把数据流的箭头展开为步骤列表
                        steps = _expand_data_flow(flow)
                        lines.append("**操作步骤：**")
                        lines.append("")
                        for i, step in enumerate(steps, 1):
                            lines.append(f"{i}. {step}")
                        lines.append("")
            else:
                lines += [
                    "> 本迭代暂无 E2E 验收标准描述，请参考对应迭代计划。",
                    "",
                ]

    lines += ["---", ""]

    # ── 卸载 ────────────────────────────────────────────────────────────────
    lines += ["## 卸载", ""]

    if arch_info["raw_tech_section"] and any(
        kw in arch_info["raw_tech_section"].lower()
        for kw in ["docker", "容器", "pip", "npm", "brew"]
    ):
        # 尝试给出通用卸载指引
        if "docker" in arch_info["raw_tech_section"].lower():
            lines += [
                "```bash",
                "# 停止并删除容器",
                "docker-compose down",
                "",
                "# 如需清理数据卷",
                "docker-compose down -v",
                "```",
                "",
            ]
        elif "pip" in arch_info["raw_tech_section"].lower():
            lines += [
                "```bash",
                "# 卸载 Python 包",
                f"pip uninstall {project_name.lower().replace(' ', '-')}",
                "```",
                "",
            ]
        elif "npm" in arch_info["raw_tech_section"].lower():
            lines += [
                "```bash",
                "# 卸载 npm 包",
                f"npm uninstall {project_name.lower().replace(' ', '-')}",
                "```",
                "",
            ]
    else:
        lines += [
            "请按以下步骤卸载本产品：",
            "",
            "1. 停止运行中的服务或进程",
            "2. 删除项目目录及相关配置文件",
            "3. 如有数据库，请备份后删除相关数据库及用户",
            "",
            "> 详细卸载步骤请参考 [技术架构文档](../tech/ARCH.md)。",
            "",
        ]

    lines += ["---", ""]

    # ── 更新记录 ────────────────────────────────────────────────────────────
    lines += ["## 更新记录", ""]

    if iterations_info:
        lines += [
            "| 迭代 | 完成日期 | 新增功能 |",
            "|---|---|---|",
        ]
        for iter_info in iterations_info:
            n = iter_info["number"]
            completed = iter_info["completed_at"] or "—"
            goal_short = iter_info["goal"][:50] + "..." if len(iter_info["goal"]) > 50 else iter_info["goal"]
            lines.append(f"| 迭代 {n} | {completed} | {goal_short} |")
        lines.append("")
    else:
        lines += ["> 尚无已完成迭代的记录。", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 内部：将数据流字符串展开为操作步骤
# ---------------------------------------------------------------------------

def _expand_data_flow(flow: str) -> list[str]:
    """
    将「用户输入 → 处理 → 存储 → 响应」式的数据流字符串
    拆分为操作步骤列表。
    """
    # 按箭头（→ 或 ->）分割
    steps = re.split(r"\s*[→>]\s*", flow)
    steps = [s.strip() for s in steps if s.strip()]

    # 如果没有箭头，直接返回完整字符串
    if len(steps) <= 1:
        return [flow] if flow.strip() else []

    return steps


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _load_config(root: Path) -> dict:
    config_path = root / ".lifecycle" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# CLI 入口（便于独立调试）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    result = generate_manual(root, n)
    if result["ok"]:
        print(f"✓ 操作手册已生成: {result['path']}")
        if result["warnings"]:
            for w in result["warnings"]:
                print(f"  ⚠ {w}")
    else:
        print(f"✗ 生成失败:\n{result['error']}")
        sys.exit(1)
