"""
risk_register.py — 产品风险登记册（Risk Register）。
贯穿全生命周期，从 PRD 风险章节初始化，每迭代可更新状态。

risk_register.json 格式：
{
  "risks": [
    {
      "id": "RISK-001",
      "title": "第三方 API 不稳定",
      "probability": "high",    // high / medium / low
      "impact": "high",         // high / medium / low
      "status": "open",         // open / mitigated / closed / accepted
      "mitigation": "增加重试机制和降级方案",
      "owner": "",
      "source": "PRD",          // 来源：PRD / iter-1 / etc.
      "updated_at": "...",
      "created_at": "..."
    }
  ]
}
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path


PROB_SCORE = {"high": 3, "medium": 2, "low": 1}
RISK_LEVEL = {
    (3, 3): "🔴 极高", (3, 2): "🔴 高", (2, 3): "🔴 高",
    (3, 1): "🟡 中", (2, 2): "🟡 中", (1, 3): "🟡 中",
    (2, 1): "🟢 低", (1, 2): "🟢 低", (1, 1): "🟢 极低",
}


class RiskRegister:
    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.register_file = self.root / ".lifecycle" / "risk_register.json"
        self.register_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if self.register_file.exists():
            return json.loads(self.register_file.read_text(encoding="utf-8"))
        return {"risks": []}

    def _save(self, data: dict):
        self.register_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_id(self, risks: list) -> str:
        nums = [int(r["id"].split("-")[1]) for r in risks if re.match(r'RISK-\d+', r["id"])]
        n = max(nums) + 1 if nums else 1
        return f"RISK-{n:03d}"

    def init_from_prd(self, prd_path: str):
        """从 PRD.md 风险章节提取风险，初始化 risk_register.json。"""
        prd = Path(self.root / prd_path)
        risks_text = ""
        if prd.exists():
            text = prd.read_text(encoding="utf-8", errors="ignore")
            # 提取风险章节（支持中英文）
            m = re.search(r'##\s*风险.*?\n(.*?)(?:\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
            if m:
                risks_text = m.group(1)

        data = self._load()
        existing_titles = {r["title"] for r in data["risks"]}

        # 从风险章节提取每行作为风险条目
        added = 0
        for line in risks_text.splitlines():
            # Skip Markdown table rows
            if line.startswith("|"):
                continue
            line = line.strip().lstrip("-*•").strip()
            if len(line) < 5 or line in existing_titles:
                continue
            risk_id = self._next_id(data["risks"])
            data["risks"].append({
                "id": risk_id,
                "title": line[:80],
                "probability": "medium",
                "impact": "medium",
                "status": "open",
                "mitigation": "（待填写）",
                "owner": "",
                "source": "PRD",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            added += 1

        if not data["risks"]:
            print(f"[risk] PRD 中未发现风险条目，风险列表为空")

        self._save(data)
        print(f"[risk] 初始化完成，共 {len(data['risks'])} 条风险（来自 PRD: {added} 条）")

    def add(self, title: str, probability: str = "medium", impact: str = "medium",
            mitigation: str = "", source: str = "manual") -> str:
        """手动添加风险，返回 RISK-ID。"""
        data = self._load()
        risk_id = self._next_id(data["risks"])
        data["risks"].append({
            "id": risk_id, "title": title,
            "probability": probability, "impact": impact,
            "status": "open", "mitigation": mitigation,
            "owner": "", "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save(data)
        print(f"[risk] 新增: {risk_id} — {title}")
        return risk_id

    def update(self, risk_id: str, **kwargs):
        """更新风险字段（status / mitigation / probability / impact）。"""
        data = self._load()
        entry = next((r for r in data["risks"] if r["id"] == risk_id), None)
        if not entry:
            raise ValueError(f"风险不存在: {risk_id}")
        for k, v in kwargs.items():
            entry[k] = v
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        print(f"[risk] 已更新 {risk_id}")

    def print_matrix(self):
        """打印风险矩阵（按风险等级排序）。"""
        data = self._load()
        risks = [r for r in data["risks"] if r["status"] == "open"]
        if not risks:
            print("[risk] 无开放风险")
            return

        def risk_score(r):
            p = PROB_SCORE.get(r["probability"], 2)
            i = PROB_SCORE.get(r["impact"], 2)
            return p * i

        risks_sorted = sorted(risks, key=risk_score, reverse=True)

        print(f"\n{'编号':>9}  {'风险等级':>8}  {'概率':>6}  {'影响':>6}  {'标题'}")
        print("-" * 70)
        for r in risks_sorted:
            p = PROB_SCORE.get(r["probability"], 2)
            i = PROB_SCORE.get(r["impact"], 2)
            level = RISK_LEVEL.get((p, i), "🟡 中")
            print(f"{r['id']:>9}  {level:>10}  {r['probability']:>6}  {r['impact']:>6}  {r['title'][:40]}")
        print()

        closed = len([r for r in data["risks"] if r["status"] in ("mitigated", "closed")])
        print(f"共 {len(data['risks'])} 条风险，{len(risks)} 条开放，{closed} 条已处理\n")
