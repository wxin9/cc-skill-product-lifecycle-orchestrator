"""
adr_manager.py — Architecture Decision Record 生命周期管理。

状态机：Proposed → Accepted → Deprecated / Superseded
目录：Docs/adr/ADR-NNN-<slug>.md
索引：Docs/adr/INDEX.md（自动维护）
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path


VALID_STATUSES = {"proposed", "accepted", "deprecated", "superseded"}

ADR_TEMPLATE = """# ADR-{num:03d} — {title}

**状态**: {status}
**日期**: {date}
**决策者**: {deciders}

## 背景

{context}

## 决策

{decision}

## 后果

### 优点
- （待填写）

### 缺点 / 风险
- （待填写）

## 备注

{notes}
"""


class ADRManager:
    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.adr_dir = self.root / "Docs" / "adr"
        self.adr_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.root / ".lifecycle" / "adr_registry.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> list:
        if self.registry_file.exists():
            return json.loads(self.registry_file.read_text(encoding="utf-8"))
        return []

    def _save_registry(self, records: list):
        self.registry_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_num(self, records: list) -> int:
        if not records:
            return 1
        return max(r["num"] for r in records) + 1

    def _slug(self, title: str) -> str:
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug.strip())
        return slug[:40]

    def create(self, title: str, status: str = "proposed",
               context: str = "（待填写）", decision: str = "（待填写）",
               deciders: str = "团队", notes: str = "") -> Path:
        """创建新 ADR 文件，返回文件路径。"""
        if status not in VALID_STATUSES:
            raise ValueError(f"无效状态: {status}，合法值: {VALID_STATUSES}")

        records = self._load_registry()
        num = self._next_num(records)
        slug = self._slug(title)
        filename = f"ADR-{num:03d}-{slug}.md"
        path = self.adr_dir / filename

        content = ADR_TEMPLATE.format(
            num=num, title=title, status=status.capitalize(),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            deciders=deciders, context=context,
            decision=decision, notes=notes,
        )
        path.write_text(content, encoding="utf-8")

        records.append({
            "num": num, "title": title, "status": status,
            "file": filename, "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_registry(records)
        self._rebuild_index(records)

        print(f"[adr] 已创建: {filename} [{status}]")
        return path

    def update_status(self, num: int, new_status: str, superseded_by: int = None):
        """更新 ADR 状态（如 proposed → accepted）。"""
        if new_status not in VALID_STATUSES:
            raise ValueError(f"无效状态: {new_status}")

        records = self._load_registry()
        entry = next((r for r in records if r["num"] == num), None)
        if not entry:
            raise ValueError(f"ADR-{num:03d} 不存在")

        old_status = entry["status"]
        entry["status"] = new_status
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        if superseded_by:
            entry["superseded_by"] = superseded_by

        # 同步更新文件中的状态行
        path = self.adr_dir / entry["file"]
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = re.sub(r'\*\*状态\*\*:.*', f'**状态**: {new_status.lower()}', text)
            path.write_text(text, encoding="utf-8")

        self._save_registry(records)
        self._rebuild_index(records)
        print(f"[adr] ADR-{num:03d} 状态: {old_status} → {new_status}")

    def list_all(self) -> list:
        """返回所有 ADR 记录（按编号升序）。"""
        records = self._load_registry()
        return sorted(records, key=lambda r: r["num"])

    def print_table(self):
        """打印 ADR 列表表格。"""
        records = self.list_all()
        if not records:
            print("[adr] 暂无 ADR 记录")
            return

        STATUS_ICON = {
            "proposed": "🔵", "accepted": "✅",
            "deprecated": "❌", "superseded": "🔄",
        }
        print(f"\n{'编号':>8}  {'状态':>12}  {'标题'}")
        print("-" * 60)
        for r in records:
            icon = STATUS_ICON.get(r["status"], "?")
            print(f"ADR-{r['num']:03d}  {icon} {r['status']:>10}  {r['title']}")
        print()

    def _rebuild_index(self, records: list):
        """重建 Docs/adr/INDEX.md。"""
        STATUS_ICON = {
            "proposed": "🔵 Proposed", "accepted": "✅ Accepted",
            "deprecated": "❌ Deprecated", "superseded": "🔄 Superseded",
        }
        lines = ["# Architecture Decision Records\n",
                 f"> 最后更新: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n",
                 "| 编号 | 状态 | 标题 | 日期 |",
                 "|------|------|------|------|"]
        for r in sorted(records, key=lambda x: x["num"]):
            status_label = STATUS_ICON.get(r["status"], r["status"])
            created = r.get("created_at", "")[:10]
            lines.append(f"| [ADR-{r['num']:03d}]({r['file']}) | {status_label} | {r['title']} | {created} |")

        # 统计
        accepted_count = sum(1 for r in records if r["status"] == "accepted")
        lines.append(f"\n**合计**: {len(records)} 条 ADR，{accepted_count} 条已接受")

        (self.adr_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
