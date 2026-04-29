"""
Build publish packages from the repository source tree.

The repository keeps one runtime source. This module emits two package shapes:

- publish/claude-code/product-lifecycle-orchestrator
- publish/codex/product-lifecycle-orchestrator

Claude Code keeps the fuller repository-facing package. Codex receives a
minimal skill package with SKILL.md, agents metadata, references, scripts, and
the wrapper.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Dict


PACKAGE_NAME = "product-lifecycle-orchestrator"

IGNORED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".DS_Store",
}

IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
}

SOURCE_ONLY_DEV_DOCS = {
    "CODEX_ADAPTATION_PLAN.md",
    "LIFECYCLE_IMPLEMENTATION_PLAN.md",
    "OPTIMIZATION_DRAFT.md",
    "REPOSITORY_GOVERNANCE.md",
}

LEGACY_PUBLISH_ITEMS = [
    "orchestrator",
    "README.md",
    "README.zh-CN.md",
    "SKILL.md",
    "manifest.json",
    "skill_definition.json",
    "CHANGELOG.md",
    "LICENSE",
    "scripts",
    "docs",
]


def sync_publish_packages(
    source_root: str | Path,
    output_root: str | Path | None = None,
) -> Dict[str, str]:
    """Generate both publish packages and return their paths."""
    source = Path(source_root).resolve()
    output = Path(output_root).resolve() if output_root else source / "publish"
    _remove_legacy_publish_root_items(output)
    claude_code = sync_claude_code_package(source, output)
    codex = sync_codex_package(source, output)
    return {
        "claude_code": str(claude_code),
        "codex": str(codex),
    }


def sync_claude_code_package(source_root: Path, output_root: Path) -> Path:
    """Generate the Claude Code oriented package."""
    package_root = output_root / "claude-code" / PACKAGE_NAME
    _reset_dir(package_root)

    files = [
        "orchestrator",
        "README.md",
        "README.zh-CN.md",
        "SKILL.md",
        "manifest.json",
        "skill_definition.json",
        "CHANGELOG.md",
        "LICENSE",
    ]
    for rel in files:
        _copy_file(source_root / rel, package_root / rel)

    _copy_tree(source_root / "scripts", package_root / "scripts")
    _copy_tree(
        source_root / "docs" / "dev",
        package_root / "docs" / "dev",
        ignored_names=SOURCE_ONLY_DEV_DOCS,
    )
    return package_root


def sync_codex_package(source_root: Path, output_root: Path) -> Path:
    """Generate the Codex oriented minimal skill package."""
    package_root = output_root / "codex" / PACKAGE_NAME
    template_root = source_root / "packaging" / "codex"
    _reset_dir(package_root)

    _copy_file(template_root / "SKILL.md", package_root / "SKILL.md")
    _copy_file(source_root / "LICENSE", package_root / "LICENSE")
    _copy_file(source_root / "orchestrator", package_root / "orchestrator")
    _copy_tree(source_root / "scripts", package_root / "scripts")
    _copy_tree(template_root / "agents", package_root / "agents")
    _copy_tree(template_root / "references", package_root / "references")
    return package_root


def _copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing source file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree(src: Path, dst: Path, ignored_names: set[str] | None = None) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing source directory: {src}")
    shutil.copytree(
        src,
        dst,
        ignore=lambda directory, names: _ignore_generated(directory, names, ignored_names),
    )


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _remove_legacy_publish_root_items(output_root: Path) -> None:
    """Remove the old single-package publish layout before writing split packages."""
    output_root.mkdir(parents=True, exist_ok=True)
    for rel in LEGACY_PUBLISH_ITEMS:
        path = output_root / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _ignore_generated(
    _: str,
    names: list[str],
    ignored_names: set[str] | None = None,
) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if (
            name in IGNORED_NAMES
            or (ignored_names is not None and name in ignored_names)
            or any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES)
        ):
            ignored.add(name)
    return ignored


def main() -> int:
    parser = argparse.ArgumentParser(description="Build publish packages")
    parser.add_argument("--source-root", default=".", help="Repository source root")
    parser.add_argument("--output-root", default=None, help="Publish output root")
    args = parser.parse_args()

    packages = sync_publish_packages(args.source_root, args.output_root)
    for target, path in packages.items():
        print(f"{target}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
