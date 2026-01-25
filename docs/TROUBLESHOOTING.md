# GM 故障排除指南

常见问题及解决方案。

## 目录

1. [安装相关](#安装相关)
2. [初始化问题](#初始化问题)
3. [Worktree 操作](#worktree-操作)
4. [Git 命令错误](#git-命令错误)
5. [配置问题](#配置问题)
6. [权限问题](#权限问题)
7. [符号链接问题](#符号链接问题)
8. [性能问题](#性能问题)

## 安装相关

### "command not found: gm"

**症状**: 安装后无法运行 `gm` 命令

**解决方案**:

1. 验证安装
```bash
pip list | grep gm
```

2. 重新安装
```bash
pip install -e .
```

3. 检查 Python 路径
```bash
which python
which python3
```

4. 尝试完整路径
```bash
python -m gm.cli.main --help
```

### "Python version not supported"

**症状**: 安装时报告 Python 版本错误

**解决方案**:

1. 检查 Python 版本
```bash
python --version
```

2. 需要 Python 3.9+，如果版本过低：
   - 升级 Python
   - 或使用虚拟环境

3. 创建虚拟环境
```bash
python3.9 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -e .
```

### "ModuleNotFoundError"

**症状**: 运行 GM 时出现模块导入错误

**解决方案**:

1. 检查安装
```bash
pip install -e ".[dev]"
```

2. 验证包结构
```bash
ls -la gm/
```

3. 检查 `__init__.py` 文件存在
```bash
ls gm/__init__.py
ls gm/core/__init__.py
ls gm/cli/__init__.py
```

## 初始化问题

### "fatal: not a git repository"

**症状**: 运行 `gm init` 时出现此错误

**原因**: 当前目录不是 Git 仓库

**解决方案**:

```bash
# 初始化为 Git 仓库
git init

# 配置 Git 用户
git config user.email "your@example.com"
git config user.name "Your Name"

# 创建初始提交
echo "# Project" > README.md
git add README.md
git commit -m "Initial commit"

# 现在可以初始化 GM
gm init
```

### "Permission denied"

**症状**: 初始化时报告权限错误

**原因**: 没有对项目目录的写权限

**解决方案**:

```bash
# 检查权限
ls -la

# 修改权限
chmod u+w .

# 或使用 sudo（不推荐）
sudo gm init
```

### ".gm directory already exists"

**症状**: 初始化时报告 .gm 已存在

**解决方案**:

```bash
# 选项 1: 使用 --force 覆盖
gm init --force

# 选项 2: 手动删除后重新初始化
rm -rf .gm
gm init

# 选项 3: 自定义基础路径
gm init --base-path ./worktrees
```

## Worktree 操作

### "worktree already exists"

**症状**: 创建 worktree 时报告已存在

**解决方案**:

```bash
# 检查现有 worktree
gm list -v

# 选项 1: 删除后重新创建
gm del feature/new-ui
gm add feature/new-ui

# 选项 2: 强制创建
gm add feature/new-ui -f
```

### "failed to lock the index"

**症状**: 在 worktree 中执行 Git 操作时出现锁定错误

**原因**: 另一个 Git 进程正在使用相同的索引

**解决方案**:

```bash
# 选项 1: 删除锁定文件
rm .git/index.lock

# 选项 2: 等待其他进程完成
sleep 5
git status

# 选项 3: 删除并重建 worktree
gm del feature/new-ui
gm add feature/new-ui
```

### "branch not found"

**症状**: 创建 worktree 时找不到分支

**原因**: 指定的分支不存在

**解决方案**:

```bash
# 查看可用分支
gm status
gm list -v

# 查看本地分支
git branch

# 查看远程分支
git branch -r

# 创建新分支
git checkout -b feature/new-ui

# 现在可以创建 worktree
gm add feature/new-ui
```

### "cannot remove worktree, directory not empty"

**症状**: 删除 worktree 时失败

**原因**: worktree 目录中有未提交的更改或其他文件

**解决方案**:

```bash
# 选项 1: 检查状态并提交更改
cd .gm/feature/new-ui
git status
git add .
git commit -m "Save changes"
cd ../..

# 选项 2: 丢弃更改
cd .gm/feature/new-ui
git checkout .
cd ../..

# 选项 3: 强制删除
gm del feature/new-ui -f
```

## Git 命令错误

### "fatal: ambiguous argument"

**症状**: Git 命令无法识别参数

**原因**: 分支名称不明确或不存在

**解决方案**:

```bash
# 检查分支名称
git branch -a

# 使用完整的分支名称
gm add origin/feature/new-ui
```

### "fatal: reference is not a tree"

**症状**: Git 无法检出分支

**原因**: 分支名称或引用无效

**解决方案**:

```bash
# 获取最新的远程引用
git fetch origin

# 列出所有可用的引用
git show-ref

# 使用正确的分支名称
gm add feature/new-ui
```

### "fatal: your current branch is behind"

**症状**: worktree 分支落后于远程

**原因**: 本地分支未与远程同步

**解决方案**:

```bash
cd .gm/feature/new-ui

# 获取最新代码
git fetch origin

# 重新基于远程分支
git rebase origin/feature/new-ui

# 或强制推送（谨慎使用）
git push -f origin feature/new-ui

cd ../..
```

## 配置问题

### "Configuration validation failed"

**症状**: 配置文件验证失败

**原因**: 配置文件格式或值无效

**解决方案**:

```bash
# 检查 YAML 格式
cat .gm.yaml

# 验证 YAML
python -c "import yaml; yaml.safe_load(open('.gm.yaml'))"

# 或重置为默认配置
rm .gm.yaml
gm init
```

### "config file not found"

**症状**: 找不到配置文件

**原因**: `.gm.yaml` 未创建或位置不对

**解决方案**:

```bash
# 检查文件是否存在
ls -la .gm.yaml

# 重新初始化
gm init

# 或手动创建最小配置
cat > .gm.yaml << 'EOF'
worktree:
  base_path: .gm
shared_files: []
EOF
```

### "invalid key in configuration"

**症状**: 配置中包含无效的键

**原因**: 使用了不支持的配置选项

**解决方案**:

1. 检查文档中的有效键
2. 查看示例配置
3. 重置并使用默认配置

## 权限问题

### "Permission denied (publickey)"

**症状**: Git 操作时报告 SSH 权限拒绝

**原因**: SSH 密钥配置不正确

**解决方案**:

```bash
# 检查 SSH 密钥
ssh-keygen -l -f ~/.ssh/id_rsa

# 测试 SSH 连接
ssh -T git@github.com

# 添加 SSH 密钥到 SSH agent
ssh-add ~/.ssh/id_rsa

# 或使用 HTTPS（需要凭据）
git remote set-url origin https://github.com/user/repo.git
```

### "fatal: could not create work tree dir"

**症状**: 无法创建 worktree 目录

**原因**: 权限不足或磁盘满

**解决方案**:

```bash
# 检查权限
ls -la .gm/

# 修改权限
chmod 755 .gm/

# 检查磁盘空间
df -h

# 检查配置的基础路径
cat .gm.yaml | grep base_path
```

## 符号链接问题

### "broken symlink"

**症状**: 符号链接已损坏

**原因**: 共享文件已移动或删除

**解决方案**:

```bash
# 列出符号链接
ls -la .gm/*/

# 检查目标是否存在
cat .gm.yaml | grep shared_files

# 重新创建 worktree
gm del feature/broken
gm add feature/new-branch
```

### "symlink not created"

**症状**: 符号链接未自动创建

**原因**: 符号链接策略设置为 "manual" 或 "none"

**解决方案**:

1. 修改配置
```yaml
symlinks:
  strategy: auto
```

2. 删除并重新创建 worktree
```bash
gm del feature/new-ui
gm add feature/new-ui
```

## 性能问题

### "gm list is slow"

**症状**: `gm list` 命令执行缓慢

**原因**: 仓库或 worktree 较大

**解决方案**:

```bash
# 检查是否有大型文件
du -sh .gm/*/

# 检查是否有缓存问题
rm -rf .gm/.cache

# 使用简洁模式
gm list

# 检查 Git 配置
git config --list
```

### "High CPU usage"

**症状**: GM 命令占用大量 CPU

**原因**: 可能是频繁的 Git 操作或大型仓库

**解决方案**:

```bash
# 检查后台进程
ps aux | grep gm

# 更新 Git
git --version
git update-git-for-windows  # Windows

# 优化 Git 配置
git gc --aggressive
```

## 调试技巧

### 启用详细输出

```bash
# 设置调试环境变量
export GM_DEBUG=1
gm add feature/test

# 或设置 Git 调试
export GIT_TRACE=1
gm list
```

### 查看日志

```bash
# 查看 GM 日志目录
ls -la ~/.gm/logs/

# 查看最近的日志
tail -f ~/.gm/logs/gm.log
```

### 获取系统信息

```bash
# 系统信息
uname -a

# Python 信息
python --version
python -m pip list | grep gm

# Git 信息
git --version
git config --global --list
```

## 获得帮助

1. **查看文档**
   - [快速开始](QUICK_START.md)
   - [用户手册](USER_MANUAL.md)
   - [API 参考](API_REFERENCE.md)

2. **提交 Issue**
   - 描述问题和复现步骤
   - 包括系统信息和 GM 版本
   - 附加相关日志

3. **社区支持**
   - 查看现有的 Issue
   - 查看 Discussion 讨论

## 常见问题汇总表

| 问题 | 解决方案 | 文档 |
|-----|--------|------|
| command not found | 重新安装 | 本节 |
| not a git repository | 初始化 Git | 本节 |
| Permission denied | 检查权限 | 本节 |
| branch not found | 列出分支 | 本节 |
| broken symlink | 重新创建 worktree | 本节 |
| slow performance | 检查仓库大小 | 本节 |
