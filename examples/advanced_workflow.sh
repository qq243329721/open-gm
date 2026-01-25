#!/bin/bash

# 高级工作流脚本示例
# 演示 GM 的高级使用场景

set -e

echo "=== GM 高级工作流示例 ==="
echo

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：创建多个 worktree
create_multiple_worktrees() {
    echo -e "${BLUE}创建多个 worktree（模拟并行开发）${NC}"

    local branches=(
        "feature/auth"
        "feature/payment"
        "feature/analytics"
    )

    for branch in "${branches[@]}"; do
        echo "创建 worktree: $branch"
        gm add "$branch" || echo "  $branch 已存在"
    done
    echo
}

# 函数：查看所有 worktree 状态
show_all_status() {
    echo -e "${BLUE}查看所有 worktree 的状态${NC}"
    gm status
    echo
}

# 函数：在多个 worktree 中进行操作
work_in_worktrees() {
    echo -e "${BLUE}在 worktree 中进行操作${NC}"

    local branches=(
        "feature/auth"
        "feature/payment"
        "feature/analytics"
    )

    for branch in "${branches[@]}"; do
        local wt_path=".gm/$branch"
        if [ -d "$wt_path" ]; then
            echo "在 $wt_path 中工作"
            cd "$wt_path"

            # 模拟工作
            echo "# $branch features" > "${branch##*/}.txt"
            git add "${branch##*/}.txt"
            git commit -m "Add ${branch##*/} implementation" 2>/dev/null || true

            # 返回项目根
            cd - > /dev/null
        fi
    done
    echo
}

# 函数：清理 worktree
cleanup_worktrees() {
    echo -e "${BLUE}清理 worktree${NC}"

    local branches=(
        "feature/auth"
        "feature/payment"
        "feature/analytics"
    )

    for branch in "${branches[@]}"; do
        echo "删除 worktree: $branch"
        gm del "$branch" || echo "  $branch 删除失败"
    done
    echo
}

# 主程序
main() {
    echo "初始化项目..."
    gm init || echo "项目已初始化"
    echo

    # 执行各个阶段
    create_multiple_worktrees
    echo "$ gm list -v"
    gm list -v || echo "没有 worktree"
    echo

    show_all_status

    work_in_worktrees

    echo "$ gm list -v"
    gm list -v || echo "没有 worktree"
    echo

    # 可选清理
    read -p "是否清理 worktree? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup_worktrees
        echo -e "${GREEN}=== 高级工作流示例完成（已清理）===${NC}"
    else
        echo -e "${GREEN}=== 高级工作流示例完成 ===${NC}"
    fi
}

main
