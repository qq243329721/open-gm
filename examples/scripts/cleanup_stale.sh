#!/bin/bash

# 清理过期 worktree 脚本
# 删除超过指定天数未更新的 worktree

DAYS_OLD="${1:-30}"
DRY_RUN="${2:-false}"

echo "=== 清理过期 Worktree 脚本 ==="
echo "删除超过 $DAYS_OLD 天未更新的 worktree"
echo

# 检查 .gm 目录是否存在
if [ ! -d ".gm" ]; then
    echo "错误: 未找到 .gm 目录"
    exit 1
fi

# 计算时间戳
THRESHOLD=$(($(date +%s) - DAYS_OLD * 86400))

echo "扫描 worktree..."
DELETED_COUNT=0

# 遍历所有 worktree
for wt_path in .gm/*/; do
    if [ ! -d "$wt_path" ]; then
        continue
    fi

    # 获取最后修改时间
    LAST_MODIFIED=$(stat -f%m "$wt_path" 2>/dev/null || stat -c%Y "$wt_path" 2>/dev/null)

    if [ "$LAST_MODIFIED" -lt "$THRESHOLD" ]; then
        BRANCH=$(basename "$wt_path")
        DAYS_SINCE=$(( ($(date +%s) - LAST_MODIFIED) / 86400 ))

        echo "找到旧 worktree: $BRANCH ($DAYS_SINCE 天前)"

        if [ "$DRY_RUN" = "true" ]; then
            echo "  [DRY RUN] 将删除: gm del $BRANCH"
        else
            echo "  删除中..."
            gm del "$BRANCH" 2>/dev/null && {
                echo "  ✓ 已删除"
                ((DELETED_COUNT++))
            } || {
                echo "  ✗ 删除失败"
            }
        fi
    fi
done

echo
if [ "$DRY_RUN" = "true" ]; then
    echo "DRY RUN: 没有实际删除任何 worktree"
else
    echo "已清理 $DELETED_COUNT 个过期的 worktree"
fi

echo
echo "使用方法:"
echo "  $0 [DAYS] [DRY_RUN]"
echo "  $0 30      # 删除 30 天前的 worktree"
echo "  $0 7 true  # 显示将删除的 7 天前的 worktree（不实际删除）"
