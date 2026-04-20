#!/bin/bash

# release.sh - 发布脚本
# 功能：同步文件到 publish/，提交 dev 分支，推送到 main 分支

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 错误处理
error_exit() {
    log_error "$1"
    exit 1
}

# 用户确认提示
confirm() {
    read -p "$1 (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 1
    fi
    return 0
}

# 检查 Git 状态
check_git_status() {
    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Git 工作区有未提交的更改"
        git status --short
        if ! confirm "是否继续？"; then
            error_exit "用户取消操作"
        fi
    else
        log_success "Git 工作区干净"
    fi
}

# 同步文件到 publish/
sync_files() {
    log_info "开始同步文件到 publish/..."

    # 确保 publish/ 目录存在
    mkdir -p "$PROJECT_ROOT/publish"

    # 复制文件
    local files=(
        "orchestrator"
        "README.md"
        "README.zh-CN.md"
        "SKILL.md"
        "manifest.json"
        "skill_definition.json"
        "CHANGELOG.md"
        "LICENSE"
    )

    for file in "${files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            cp "$PROJECT_ROOT/$file" "$PROJECT_ROOT/publish/$file"
            log_success "已复制: $file"
        else
            error_exit "文件不存在: $file"
        fi
    done

    # 同步 scripts/ 目录
    if [[ -d "$PROJECT_ROOT/scripts" ]]; then
        rm -rf "$PROJECT_ROOT/publish/scripts"
        cp -r "$PROJECT_ROOT/scripts" "$PROJECT_ROOT/publish/scripts"
        log_success "已同步: scripts/"
    else
        error_exit "scripts/ 目录不存在"
    fi

    log_success "文件同步完成"
}

# Git 操作
git_operations() {
    log_info "开始 Git 操作..."

    # 获取当前分支
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    log_info "当前分支: $current_branch"

    # 检查是否在 dev 分支
    if [[ "$current_branch" != "dev" ]]; then
        log_warning "当前不在 dev 分支"

        # 检查 dev 分支是否存在
        if ! git show-ref --verify --quiet refs/heads/dev; then
            log_info "dev 分支不存在，创建并切换..."
            git checkout -b dev
        else
            log_info "切换到 dev 分支..."
            git checkout dev
        fi
    fi

    # 添加更改
    log_info "添加更改到暂存区..."
    git add publish/

    # 检查是否有更改需要提交
    if git diff --cached --quiet; then
        log_warning "没有更改需要提交"
    else
        # 提交更改
        log_info "提交更改..."
        git commit -m "chore: sync publish directory

- Updated publish/ with latest files
- Timestamp: $(date '+%Y-%m-%d %H:%M:%S')

Co-Authored-By: release.sh <release@local>"
        log_success "已提交到 dev 分支"
    fi

    # 推送到 main 分支
    log_info "推送到 main 分支..."

    # 保存当前提交
    local dev_commit=$(git rev-parse HEAD)

    # 切换到 main 分支
    git checkout main

    # 从 publish/ 目录应用更改
    log_info "从 publish/ 应用更改到 main 分支..."

    # 删除 main 分支中的所有文件（除了 publish/ 和 .git）
    find . -maxdepth 1 -not -name '.' -not -name '.git' -not -name 'publish' -exec rm -rf {} +

    # 复制 publish/ 中的文件到根目录
    cp -r publish/* .

    # 添加所有更改
    git add -A

    # 提交
    if git diff --cached --quiet; then
        log_warning "没有更改需要提交到 main"
    else
        git commit -m "release: publish to main branch

- Published from dev branch: $dev_commit
- Timestamp: $(date '+%Y-%m-%d %H:%M:%S')

Co-Authored-By: release.sh <release@local>"
        log_success "已提交到 main 分支"

        # 推送到远程
        if confirm "是否推送到远程仓库？"; then
            git push origin main
            log_success "已推送到远程 main 分支"
        fi
    fi

    # 切换回 dev 分支
    git checkout dev
    log_success "已切换回 dev 分支"
}

# 主函数
main() {
    local sync_only=false

    # 解析参数
    if [[ "$1" == "--sync-only" ]]; then
        sync_only=true
    fi

    log_info "========================================="
    log_info "发布脚本启动"
    log_info "项目根目录: $PROJECT_ROOT"
    log_info "========================================="

    # 检查 Git 状态
    check_git_status

    # 同步文件
    sync_files

    if [[ "$sync_only" == true ]]; then
        log_success "同步完成（--sync-only 模式）"
        exit 0
    fi

    # Git 操作
    if confirm "是否执行 Git 操作（提交并推送）？"; then
        git_operations
    else
        log_warning "跳过 Git 操作"
    fi

    log_success "========================================="
    log_success "发布流程完成"
    log_success "========================================="
}

# 执行主函数
main "$@"
