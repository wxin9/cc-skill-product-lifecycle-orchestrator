"""
velocity_tracker.py — 迭代速度追踪。
记录每个迭代的估计工时 vs 实际工时，生成 ASCII 趋势图。
"""
import json
from datetime import datetime
from pathlib import Path


class VelocityTracker:
    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.velocity_file = self.root / ".lifecycle" / "velocity.json"
        self.velocity_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if self.velocity_file.exists():
            return json.loads(self.velocity_file.read_text())
        return {"iterations": [], "baseline_hours": None}

    def _save(self, data: dict):
        self.velocity_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def start_iteration(self, iteration: int, estimated_hours: float):
        """记录迭代开始 + 估算工时。"""
        data = self._load()
        # 避免重复
        existing = [i for i in data["iterations"] if i["iteration"] == iteration]
        if existing:
            existing[0]["estimated_hours"] = estimated_hours
            existing[0]["started_at"] = datetime.now().isoformat()
        else:
            data["iterations"].append({
                "iteration": iteration,
                "estimated_hours": estimated_hours,
                "actual_hours": None,
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
            })
        self._save(data)
        print(f"[velocity] 迭代 {iteration} 开始，估算工时: {estimated_hours}h")

    def complete_iteration(self, iteration: int, actual_hours: float):
        """记录迭代完成 + 实际工时。"""
        data = self._load()
        entry = next((i for i in data["iterations"] if i["iteration"] == iteration), None)
        if not entry:
            entry = {"iteration": iteration, "estimated_hours": None}
            data["iterations"].append(entry)
        entry["actual_hours"] = actual_hours
        entry["completed_at"] = datetime.now().isoformat()

        # 更新基准（平均实际工时）
        completed = [i for i in data["iterations"] if i["actual_hours"] is not None]
        if completed:
            data["baseline_hours"] = sum(i["actual_hours"] for i in completed) / len(completed)

        self._save(data)
        print(f"[velocity] 迭代 {iteration} 完成，实际工时: {actual_hours}h")

    def suggest_next(self) -> float:
        """基于历史数据，建议下一个迭代的工时估算。"""
        data = self._load()
        completed = [i for i in data["iterations"] if i["actual_hours"] is not None]
        if not completed:
            return 8.0  # 默认 8h

        # 加权平均（最近的迭代权重更高）
        weights = list(range(1, len(completed) + 1))
        weighted_sum = sum(w * i["actual_hours"] for w, i in zip(weights, completed))
        return round(weighted_sum / sum(weights), 1)

    def report(self) -> str:
        """生成 ASCII 趋势图 + 统计摘要。"""
        data = self._load()
        iters = data["iterations"]
        if not iters:
            return "[velocity] 暂无迭代数据"

        lines = ["", "=== Velocity 趋势 ===", ""]
        lines.append(f"{'迭代':>4}  {'估算(h)':>8}  {'实际(h)':>8}  {'偏差%':>7}  图示")
        lines.append("-" * 55)

        for it in sorted(iters, key=lambda x: x["iteration"]):
            n = it["iteration"]
            est = it.get("estimated_hours")
            act = it.get("actual_hours")

            est_str = f"{est:.1f}" if est else "  N/A"
            act_str = f"{act:.1f}" if act else "  N/A"

            if est and act:
                pct = (act - est) / est * 100
                pct_str = f"{pct:+.0f}%"
                bar_len = min(int(act), 20)
                bar = "█" * bar_len
                color = "▲" if pct > 20 else ("▼" if pct < -20 else "●")
                lines.append(f"{n:>4}  {est_str:>8}  {act_str:>8}  {pct_str:>7}  {color} {bar}")
            else:
                lines.append(f"{n:>4}  {est_str:>8}  {act_str:>8}  {'  ---':>7}")

        lines.append("-" * 55)
        baseline = data.get("baseline_hours")
        suggestion = self.suggest_next()
        if baseline:
            lines.append(f"平均实际工时: {baseline:.1f}h | 下一迭代建议估算: {suggestion}h")
        lines.append("")
        return "\n".join(lines)
