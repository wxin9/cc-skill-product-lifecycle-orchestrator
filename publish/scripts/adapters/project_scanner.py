"""
Project scanner — scans an existing project directory and maps it to the
standard Docs/ structure.

Detects:
  - Existing documentation (README, requirements, design docs, etc.)
  - Tech stack (from package.json, requirements.txt, go.mod, etc.)
  - Existing Docs/ or .lifecycle/ folders

Usage:
  python scripts/adapters/project_scanner.py scan --path /path/to/project
  python scripts/adapters/project_scanner.py normalize --path /path/to/project [--dry-run]
"""
from __future__ import annotations
import re
import sys
import json
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# --------------------------------------------------------------------------
# Document type detection
# --------------------------------------------------------------------------

_DOC_PATTERNS = [
    # (pattern in filename/content, doc_type, confidence)
    (re.compile(r"(prd|product.?requirement|需求文档|产品需求)", re.IGNORECASE), "prd", 0.9),
    (re.compile(r"(architecture|arch|技术架构|系统设计)", re.IGNORECASE), "arch", 0.9),
    (re.compile(r"(design|设计|ui|ux|交互)", re.IGNORECASE), "design", 0.8),
    (re.compile(r"(requirement|需求|spec|规格)", re.IGNORECASE), "requirements", 0.75),
    (re.compile(r"(test|测试|qa)", re.IGNORECASE), "test", 0.8),
    (re.compile(r"(iteration|sprint|迭代|版本规划)", re.IGNORECASE), "iteration", 0.8),
    (re.compile(r"(changelog|change.log|CHANGELOG|变更)", re.IGNORECASE), "changelog", 0.7),
    (re.compile(r"(readme|概述|overview)", re.IGNORECASE), "overview", 0.6),
]

_TECH_STACK_FILES = {
    "package.json": "Node.js/JavaScript",
    "package-lock.json": "Node.js/JavaScript",
    "yarn.lock": "Node.js/JavaScript",
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "pyproject.toml": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "pubspec.yaml": "Dart/Flutter",
    "CMakeLists.txt": "C/C++",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
}

_DOC_EXTENSIONS = {".md", ".txt", ".rst", ".pdf", ".docx", ".doc"}

_TARGET_PATHS = {
    "prd": "Docs/product/PRD.md",
    "arch": "Docs/tech/ARCH.md",
    "design": "Docs/product/",
    "requirements": "Docs/product/requirements/",
    "test": "Docs/tests/",
    "iteration": "Docs/iterations/",
    "overview": "Docs/product/",
    "changelog": "Docs/",
}

_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".lifecycle"}


# --------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------

def scan_project(root_path: str) -> dict:
    """
    Scan a project directory and detect existing documentation.

    Returns ProjectScan dict.
    """
    root = Path(root_path).resolve()
    detected_docs: List[dict] = []
    tech_stack: List[str] = []
    total_files = 0
    conflicts: List[str] = []

    has_docs_folder = (root / "Docs").exists()
    has_lifecycle_folder = (root / ".lifecycle").exists()

    # Walk directory (skip ignored dirs)
    for path in root.rglob("*"):
        if any(ignored in path.parts for ignored in _IGNORE_DIRS):
            continue
        if not path.is_file():
            continue

        total_files += 1

        # Tech stack detection
        if path.name in _TECH_STACK_FILES:
            stack = _TECH_STACK_FILES[path.name]
            if stack not in tech_stack:
                tech_stack.append(stack)

        # Documentation detection
        if path.suffix.lower() in _DOC_EXTENSIONS:
            detected = _classify_doc(path, root)
            if detected:
                detected_docs.append(detected)

    # Check for conflicts (multiple files of same type)
    prd_docs = [d for d in detected_docs if d["doc_type"] == "prd"]
    arch_docs = [d for d in detected_docs if d["doc_type"] == "arch"]
    if len(prd_docs) > 1:
        conflicts.append(f"发现多个 PRD 文档: {[d['path'] for d in prd_docs]}")
    if len(arch_docs) > 1:
        conflicts.append(f"发现多个架构文档: {[d['path'] for d in arch_docs]}")

    return {
        "root_path": str(root),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_files": total_files,
        "detected_docs": detected_docs,
        "inferred_tech_stack": tech_stack,
        "has_docs_folder": has_docs_folder,
        "has_lifecycle_folder": has_lifecycle_folder,
        "conflicts": conflicts,
    }


def _classify_doc(path: Path, root: Path) -> Optional[dict]:
    """Classify a file as a documentation type. Returns None if not a doc."""
    rel = str(path.relative_to(root))
    name = path.stem.lower()

    best_type = "unknown"
    best_confidence = 0.0

    for pattern, doc_type, confidence in _DOC_PATTERNS:
        if pattern.search(name) or pattern.search(rel):
            if confidence > best_confidence:
                best_type = doc_type
                best_confidence = confidence

    if best_confidence < 0.6:
        # Check first 500 chars of file content
        try:
            content_preview = path.read_text(encoding="utf-8", errors="replace")[:500]
        except Exception:
            return None

        for pattern, doc_type, confidence in _DOC_PATTERNS:
            if pattern.search(content_preview):
                if confidence * 0.8 > best_confidence:
                    best_type = doc_type
                    best_confidence = confidence * 0.8

    if best_confidence < 0.5:
        return None

    suggested_target = _TARGET_PATHS.get(best_type, "Docs/")
    if suggested_target.endswith("/"):
        suggested_target += path.name

    return {
        "path": str(path.relative_to(root)),
        "doc_type": best_type,
        "confidence": round(best_confidence, 2),
        "suggested_target": suggested_target,
    }


# --------------------------------------------------------------------------
# Normalizer
# --------------------------------------------------------------------------

def normalize_structure(scan: dict, target_root: Optional[str] = None) -> dict:
    """
    Generate a migration plan to move detected docs to Docs/ structure.

    Args:
        scan: Output of scan_project().
        target_root: Target root for Docs/ (defaults to scan['root_path']).

    Returns MigrationPlan dict.
    """
    root = target_root or scan["root_path"]
    moves: List[dict] = []
    creates: List[str] = []
    conflicts: List[str] = []

    # Required Docs subdirectories
    required_dirs = [
        "Docs/product/requirements",
        "Docs/product/user_flows",
        "Docs/tech/components",
        "Docs/iterations",
        "Docs/tests/cases",
        ".lifecycle",
    ]
    for d in required_dirs:
        full_path = str(Path(root) / d)
        creates.append(full_path)

    # Map detected docs to target paths
    seen_targets: dict[str, str] = {}
    for doc in scan["detected_docs"]:
        src = str(Path(scan["root_path"]) / doc["path"])
        tgt = str(Path(root) / doc["suggested_target"])

        if tgt in seen_targets:
            conflicts.append(
                f"目标路径冲突: {tgt} ← {src} (已被 {seen_targets[tgt]} 占用)"
            )
        else:
            seen_targets[tgt] = src
            if src != tgt:
                moves.append({"from": src, "to": tgt})

    return {
        "moves": moves,
        "creates": creates,
        "conflicts": scan.get("conflicts", []) + conflicts,
    }


def execute_migration(plan: dict, dry_run: bool = True) -> dict:
    """
    Execute a migration plan (or print what would happen in dry_run mode).

    Returns: {'created': [...], 'moved': [...], 'skipped': [...], 'errors': [...]}
    """
    created: List[str] = []
    moved: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    # Create directories
    for dir_path in plan.get("creates", []):
        p = Path(dir_path)
        if p.exists():
            skipped.append(f"已存在: {dir_path}")
        elif dry_run:
            print(f"  [DRY-RUN] mkdir -p {dir_path}")
            created.append(dir_path)
        else:
            try:
                p.mkdir(parents=True, exist_ok=True)
                created.append(dir_path)
            except Exception as e:
                errors.append(f"创建目录失败 {dir_path}: {e}")

    # Move files
    for move in plan.get("moves", []):
        src, tgt = move["from"], move["to"]
        if not Path(src).exists():
            skipped.append(f"源文件不存在: {src}")
            continue
        if Path(tgt).exists():
            skipped.append(f"目标已存在，跳过: {tgt}")
            continue
        if dry_run:
            print(f"  [DRY-RUN] mv {src} → {tgt}")
            moved.append(f"{src} → {tgt}")
        else:
            try:
                Path(tgt).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tgt)
                moved.append(f"{src} → {tgt}")
            except Exception as e:
                errors.append(f"移动文件失败 {src}: {e}")

    return {"created": created, "moved": moved, "skipped": skipped, "errors": errors}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project structure scanner")
    sub = parser.add_subparsers(dest="cmd")

    scan_p = sub.add_parser("scan", help="Scan project directory")
    scan_p.add_argument("--path", required=True)
    scan_p.add_argument("--output", help="Write scan JSON to file")

    norm_p = sub.add_parser("normalize", help="Generate migration plan")
    norm_p.add_argument("--path", required=True)
    norm_p.add_argument("--dry-run", action="store_true", default=True)
    norm_p.add_argument("--execute", action="store_true", help="Actually move files")

    args = parser.parse_args()

    if args.cmd == "scan":
        result = scan_project(args.path)
        out = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"✓ 扫描结果已保存: {args.output}")
        else:
            print(out)
        print(f"\n扫描摘要: {result['total_files']} 个文件，"
              f"发现 {len(result['detected_docs'])} 个文档，"
              f"技术栈: {result['inferred_tech_stack']}")
        if result["conflicts"]:
            print("⚠ 冲突:")
            for c in result["conflicts"]:
                print(f"  - {c}")

    elif args.cmd == "normalize":
        scan = scan_project(args.path)
        plan = normalize_structure(scan)
        dry_run = not args.execute
        print(f"{'[DRY-RUN] ' if dry_run else ''}迁移计划:")
        result = execute_migration(plan, dry_run=dry_run)
        print(f"\n结果: {len(result['created'])} 个目录创建，"
              f"{len(result['moved'])} 个文件移动，"
              f"{len(result['skipped'])} 个跳过")
        if result["errors"]:
            print("错误:")
            for e in result["errors"]:
                print(f"  ✗ {e}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)
