#!/bin/bash

# 基础工作流脚本示例
# 演示 GM 的基本使用流程

set -e

echo "=== GM 基础工作流示例 ==="
echo

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. 初始化项目
echo -e "${BLUE}1. 初始化项目${NC}"
echo "$ gm init"
gm init || echo "项目已初始化"
echo

# 2. 创建功能分支的 worktree
echo -e "${BLUE}2. 创建功能分支 worktree${NC}"
BRANCH="feature/example-$(date +%s)"
echo "$ gm add $BRANCH"
gm add "$BRANCH" || echo "Worktree 已存在或创建失败"
echo

# 3. 列出所有 worktree
echo -e "${BLUE}3. 列出所有 worktree${NC}"
echo "$ gm list -v"
gm list -v || echo "没有 worktree"
echo

# 4. 查看状态
echo -e "${BLUE}4. 查看状态${NC}"
echo "$ gm status"
gm status || echo "获取状态失败"
echo

# 5. 在 worktree 中工作
echo -e "${BLUE}5. 在 worktree 中进行更改${NC}"
WORKTREE_PATH=".gm/$BRANCH"
if [ -d "$WORKTREE_PATH" ]; then
    echo "进入 worktree: $WORKTREE_PATH"
    cd "$WORKTREE_PATH"

    # 创建示例文件
    echo "Creating example file..."
    echo "# Example File" > example.txt
    echo "Example content" >> example.txt

    # 查看状态
    echo
    echo "$ git status"
    git status || echo "查看状态失败"

    # 返回项目根目录
    cd - > /dev/null
fi
echo

# 6. 删除 worktree
echo -e "${BLUE}6. 删除 worktree${NC}"
echo "$ gm del $BRANCH"
gm del "$BRANCH" || echo "删除失败"
echo

echo -e "${GREEN}=== 基础工作流示例完成 ===${NC}"
