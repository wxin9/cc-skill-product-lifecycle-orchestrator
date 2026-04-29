"""
sprint_review_generator.py — Sprint Review 材料生成器。
迭代门控通过后自动生成 Docs/iterations/iter-N/sprint_review.md。
面向 Stakeholder，简洁、可直接发送。
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path


class SprintReviewGenerator:
    def __init__(self, root: str = "."):
        self.root = Path(root)

    def generate(self, iteration: int) -> Path:
        """生成 sprint_review.md，返回文件路径。"""
        iter_dir = self.root / "Docs" / "iterations" / f"iter-{iteration}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        plan = self._load_plan(iter_dir)
        test_results = self._load_test_results(iteration)
        velocity = self._load_velocity()
        adrs = self._load_recent_adrs(iteration)

        content = self._render(iteration, plan, test_results, velocity, adrs)
        output = iter_dir / "sprint_review.md"
        output.write_text(content, encoding="utf-8")
        print(f"[sprint_review] 已生成: {output}")
        return output

    def _load_plan(self, iter_dir: Path) -> dict:
        plan_file = iter_dir / "PLAN.md"
        if not plan_file.exists():
            return {"goal": "（无迭代目标）", "features": [], "e2e_criteria": "（无验收标准）"}

        text = plan_file.read_text(encoding="utf-8", errors="ignore")
        goal_m = re.search(r'\*\*目标[：:]\*\*\s*(.+)', text)
        if not goal_m:
            goal_m = re.search(r'##\s*目标\s*\n+(.*)', text)
        goal = goal_m.group(1).strip() if goal_m else "（见 PLAN.md）"

        features = re.findall(r'-\s*(F\d+[^：\n]*)', text)
        e2e_m = re.search(r'E2E[^：:]*[：:]\s*\n+(.*?)(?:\n#|\Z)', text, re.DOTALL)
        e2e = e2e_m.group(1).strip()[:300] if e2e_m else "（见 PLAN.md）"

        return {"goal": goal, "features": features, "e2e_criteria": e2e}

    def _load_test_results(self, iteration: int) -> dict:
        result_file = self.root / ".lifecycle" / f"iter-{iteration}" / "test_results.json"
        if not result_file.exists():
            return {"pass": 0, "fail": 0, "total": 0}
        data = json.loads(result_file.read_text(encoding="utf-8"))
        raw_results = data.get("results", [])
        if isinstance(raw_results, dict):
            results = list(raw_results.values())
        elif isinstance(raw_results, list):
            results = raw_results
        else:
            results = []
        pass_count = sum(1 for r in results if r.get("status") == "pass")
        fail_count = sum(1 for r in results if r.get("status") == "fail")
        return {"pass": pass_count, "fail": fail_count, "total": len(results)}

    def _load_velocity(self) -> dict:
        vel_file = self.root / ".lifecycle" / "velocity.json"
        if not vel_file.exists():
            return {}
        return json.loads(vel_file.read_text(encoding="utf-8"))

    def _load_recent_adrs(self, iteration: int) -> list:
        registry = self.root / ".lifecycle" / "adr_registry.json"
        if not registry.exists():
            return []
        records = json.loads(registry.read_text(encoding="utf-8"))
        # 返回最近 3 条 Accepted ADR
        accepted = [r for r in records if r["status"] == "accepted"]
        return accepted[-3:]

    def _render(self, iteration: int, plan: dict, tests: dict,
                velocity: dict, adrs: list) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Velocity 段落
        iters = velocity.get("iterations", [])
        current_vel = next((i for i in iters if i["iteration"] == iteration), {})
        est_h = current_vel.get("estimated_hours", "N/A")
        act_h = current_vel.get("actual_hours")
        if act_h is not None:
            vel_line = f"{est_h}h 估算 / {act_h}h 实际"
        else:
            vel_line = f"{est_h}h 估算（进行中）"

        # Feature 列表
        feat_lines = "\n".join(f"- {f}" for f in plan["features"]) if plan["features"] else "- （见 PLAN.md）"

        # 测试结果
        test_line = f"✅ {tests['pass']} 通过 / ❌ {tests['fail']} 失败 / 共 {tests['total']} 用例"

        # ADR 段落
        if adrs:
            adr_lines = "\n".join(f"- **ADR-{a['num']:03d}** {a['title']}" for a in adrs)
        else:
            adr_lines = "（本迭代无新架构决策）"

        return f"""# Sprint Review — 迭代 {iteration}

> **日期**: {date_str} | **版本**: Iter-{iteration}

---

## 迭代目标

{plan['goal']}

## 本迭代完成功能

{feat_lines}

## E2E 验收结果

{plan['e2e_criteria']}

**测试执行**: {test_line}

## 工时追踪

{vel_line}

## 关键架构决策

{adr_lines}

## 下一迭代预告

> （请在此补充下个迭代的主要目标和功能点）

---

*本文档由 Product Lifecycle Orchestrator Phase 12 gate 自动生成，可直接发送给 Stakeholder。*
"""
