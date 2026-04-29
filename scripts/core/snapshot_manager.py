"""
snapshot_manager.py — 文档自动快照管理
validate 通过时自动建快照；change 命令自动读最新快照做 diff，无需 --old 参数。
"""
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path


class SnapshotManager:
    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.snapshot_dir = self.root / ".lifecycle" / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.snapshot_dir / "index.json"
        self._lock = threading.Lock()

    def _load_index(self) -> dict:
        if self.index_file.exists():
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        return {}

    def _save_index(self, index: dict):
        self.index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def take(self, doc_path: str, alias: str = None, label: str = None) -> Path:
        """对文档建快照，返回快照路径。"""
        src = self.root / doc_path
        if not src.exists():
            raise FileNotFoundError(f"文档不存在: {src}")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        doc_key = doc_path.replace("/", "_").replace(".", "_")
        snapshot_name = f"{doc_key}_{ts}.md"
        dst = self.snapshot_dir / snapshot_name

        with self._lock:
            shutil.copy2(src, dst)

            # 同时更新 <doc_key>_latest.md 指针
            latest = self.snapshot_dir / f"{doc_key}_latest.md"
            shutil.copy2(src, latest)

            # 更新索引
            index = self._load_index()
            if doc_key not in index:
                index[doc_key] = []
            index[doc_key].append({
                "timestamp": ts,
                "file": snapshot_name,
                "label": label or "",
                "source": doc_path,
                "size": dst.stat().st_size,
            })
            self._save_index(index)

        print(f"[snapshot] 已建快照: {snapshot_name}")

        # 如果提供了 alias，额外写一份固定名 latest 文件（供 phases.py artifact 验证使用）
        if alias:
            alias_path = self.snapshot_dir / f"{alias}_latest.md"
            shutil.copy2(src, alias_path)

        return dst

    def latest(self, doc_path: str) -> Path:
        """获取文档最新快照路径，不存在则返回 None。"""
        doc_key = doc_path.replace("/", "_").replace(".", "_")
        latest = self.snapshot_dir / f"{doc_key}_latest.md"
        return latest if latest.exists() else None

    def latest_by_alias(self, alias: str):
        """通过固定别名获取最新快照路径，不存在则返回 None。"""
        path = self.snapshot_dir / f"{alias}_latest.md"
        return path if path.exists() else None

    def list_snapshots(self, doc_path: str = None) -> list:
        """列出快照历史，按时间倒序。doc_path=None 则列出所有文档。"""
        with self._lock:
            index = self._load_index()
        results = []
        for key, entries in index.items():
            if doc_path and doc_path.replace("/", "_").replace(".", "_") != key:
                continue
            for e in reversed(entries):
                results.append({**e, "doc_key": key})
        return results

    def diff(self, doc_path: str) -> str:
        """与最新快照做文本 diff，返回 unified diff 字符串。"""
        import difflib
        current = self.root / doc_path
        snapshot = self.latest(doc_path)
        if not snapshot:
            return f"[snapshot] 无历史快照，无法对比: {doc_path}"
        a = snapshot.read_text(encoding="utf-8").splitlines(keepends=True)
        b = current.read_text(encoding="utf-8").splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            a, b,
            fromfile=f"snapshot/{snapshot.name}",
            tofile=f"current/{doc_path}",
        ))
        return "".join(diff) if diff else "(无变化)"
