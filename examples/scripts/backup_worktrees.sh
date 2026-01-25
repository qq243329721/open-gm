#!/bin/bash

# 备份 worktree 脚本
# 定期备份所有活跃的 worktree

BACKUP_DIR="${1:-.backup}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/worktrees_backup_$TIMESTAMP.tar.gz"

echo "=== Worktree 备份脚本 ==="
echo "备份目录: $BACKUP_DIR"
echo "备份文件: $BACKUP_FILE"
echo

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 检查 .gm 目录是否存在
if [ ! -d ".gm" ]; then
    echo "错误: 未找到 .gm 目录"
    exit 1
fi

echo "正在压缩 worktree..."
tar -czf "$BACKUP_FILE" .gm/ .gm.yaml 2>/dev/null || {
    echo "错误: 备份失败"
    exit 1
}

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✓ 备份完成: $SIZE"
echo "  位置: $BACKUP_FILE"
echo

# 可选：列出最近的备份
echo "最近的备份:"
ls -lh "$BACKUP_DIR"/worktrees_backup_*.tar.gz 2>/dev/null | tail -5

echo
echo "恢复备份命令:"
echo "  tar -xzf $BACKUP_FILE"
