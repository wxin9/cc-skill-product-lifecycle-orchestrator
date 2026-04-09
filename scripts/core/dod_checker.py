"""
dod_checker.py — 可配置的 Definition of Done 检查器。
从 .lifecycle/dod.json 读取规则，在迭代门控前执行。

dod.json 格式：
{
  "rules": [
    {"type": "tasks", "description": "所有任务必须 done"},
    {"type": "test_records", "description": "所有 TST 任务有测试记录"},
    {"type": "command", "cmd": "npm run lint", "description": "Lint 通过"},
    {"type": "command", "cmd": "pytest --tb=no -q", "description": "单元测试通过"},
    {"type": "coverage", "threshold": 80, "cmd": "pytest --cov=src --cov-report=term-missing -q",
     "description": "代码覆盖率 ≥ 80%"},
    {"type": "review", "description": "已完成代码审查", "manual": true}
  ]
}
"""
import json
import subprocess
import re
from pathlib import Path


class DoDChecker:
    DEFAULT_DOD = {
        "rules": [
            {"type": "tasks", "description": "所有 CHK/DEV/TST 任务状态为 done"},
            {"type": "test_records", "description": "所有 TST 任务有测试执行记录，fail 有 resolution"},
        ]
    }

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.dod_file = self.root / ".lifecycle" / "dod.json"

    def load_rules(self) -> dict:
        if self.dod_file.exists():
            return json.loads(self.dod_file.read_text())
        return self.DEFAULT_DOD

    def init(self, extra_rules: list = None):
        """初始化 dod.json，写入默认规则（+ 可选扩展规则）。"""
        dod = dict(self.DEFAULT_DOD)
        if extra_rules:
            dod["rules"].extend(extra_rules)
        self.dod_file.write_text(json.dumps(dod, ensure_ascii=False, indent=2))
        print(f"[dod] 已初始化 DoD 规则: {len(dod['rules'])} 条")

    def check_command(self, cmd: str) -> tuple[bool, str]:
        """运行 shell 命令，返回 (passed, output)。"""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=str(self.root), timeout=60
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "命令超时（>60s）"
        except Exception as e:
            return False, str(e)

    def check_coverage(self, cmd: str, threshold: int) -> tuple[bool, str]:
        """运行 coverage 命令，提取覆盖率数字判断是否达标。"""
        passed_run, output = self.check_command(cmd)
        # 从输出中提取 "TOTAL ... 80%" 之类的
        match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
        if match:
            pct = int(match.group(1))
            passed = pct >= threshold
            return passed, f"覆盖率: {pct}%（要求 ≥ {threshold}%）\n{output[:500]}"
        return passed_run, output[:500]

    def run_all(self, iteration: int = None, task_data: dict = None,
                test_results: dict = None) -> list[dict]:
        """运行所有 DoD 规则，返回检查结果列表。"""
        rules = self.load_rules()["rules"]
        results = []

        for rule in rules:
            rule_type = rule["type"]
            desc = rule.get("description", rule_type)

            if rule_type == "tasks":
                # 交由外部（artifact_validator 或 gate 命令）处理，这里标记为 deferred
                results.append({"rule": desc, "status": "deferred",
                                 "detail": "由门控命令统一检查"})

            elif rule_type == "test_records":
                results.append({"rule": desc, "status": "deferred",
                                 "detail": "由门控命令统一检查"})

            elif rule_type == "command":
                cmd = rule.get("cmd", "")
                if not cmd:
                    continue
                passed, output = self.check_command(cmd)
                results.append({
                    "rule": desc,
                    "status": "pass" if passed else "fail",
                    "detail": output[:300],
                })

            elif rule_type == "coverage":
                cmd = rule.get("cmd", "")
                threshold = rule.get("threshold", 80)
                if not cmd:
                    continue
                passed, detail = self.check_coverage(cmd, threshold)
                results.append({
                    "rule": desc,
                    "status": "pass" if passed else "fail",
                    "detail": detail,
                })

            elif rule_type == "review":
                if rule.get("manual"):
                    # 检查是否有手动 review 记录文件
                    review_file = self.root / ".lifecycle" / "review_records.json"
                    if iteration and review_file.exists():
                        records = json.loads(review_file.read_text())
                        iter_key = f"iter-{iteration}"
                        reviewed = records.get(iter_key, False)
                        results.append({
                            "rule": desc,
                            "status": "pass" if reviewed else "warn",
                            "detail": "已记录 review" if reviewed else "未找到代码审查记录（可用 ./lifecycle review record 添加）",
                        })
                    else:
                        results.append({"rule": desc, "status": "warn",
                                         "detail": "手动 review 规则，需人工确认"})

        return results

    def print_report(self, results: list[dict]) -> bool:
        """打印 DoD 报告，返回是否全部通过（warn 不阻断，fail 阻断）。"""
        print("\n=== Definition of Done 检查 ===")
        blocking_fails = []
        for r in results:
            status = r["status"]
            icon = {"pass": "✓", "fail": "✗", "warn": "⚠", "deferred": "○"}.get(status, "?")
            print(f"  {icon} [{status.upper():8}] {r['rule']}")
            if r.get("detail") and status in ("fail", "warn"):
                print(f"           → {r['detail'][:200]}")
            if status == "fail":
                blocking_fails.append(r["rule"])

        print()
        if blocking_fails:
            print(f"[dod] ✗ {len(blocking_fails)} 条规则未通过，门控阻断：")
            for f in blocking_fails:
                print(f"       - {f}")
            return False
        print("[dod] ✓ DoD 全部通过（deferred 项由门控统一验证）")
        return True
