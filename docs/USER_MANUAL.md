# GM 用户手册

完整的 GM（Git Worktree Manager）用户指南。

## 目录

1. [基本概念](#基本概念)
2. [安装和设置](#安装和设置)
3. [命令参考](#命令参考)
4. [工作流示例](#工作流示例)
5. [配置管理](#配置管理)
6. [常见问题](#常见问题)
7. [故障排除](#故障排除)

## 基本概念

### 什么是 Git Worktree？

Git worktree 是 Git 的一个功能，允许您在一个仓库中同时处理多个分支。每个 worktree 有自己的工作目录和索引，但共享同一个 Git 对象库。

### GM 的核心概念

- **Worktree**：一个独立的工作目录，关联到一个 Git 分支
- **Worktree 基础目录**：存放所有 worktree 的目录（默认为 `.gm`）
- **配置文件**：`.gm.yaml` 项目级配置文件
- **符号链接**：自动创建的共享文件链接

### 工作原理

```
项目根目录/
├── .gm/                      # Worktree 基础目录
│   ├── feature/user-login/   # Worktree 1
│   ├── feature/payment/      # Worktree 2
│   └── bugfix/critical/      # Worktree 3
├── .gm.yaml                  # 项目配置
├── src/                      # 共享源代码
└── package.json              # 共享配置
```

## 安装和设置

### 系统要求

- Python 3.9 或更高版本
- Git 2.7.0 或更高版本
- 至少 100MB 空闲磁盘空间
- 对项目目录的读写权限

### 安装步骤

1. 通过 pip 安装

```bash
pip install gm
```

2. 验证安装

```bash
gm --version
```

3. 初始化项目

```bash
cd /path/to/your/project
gm init
```

### 更新 GM

```bash
pip install --upgrade gm
```

## 命令参考

### gm init - 初始化项目

初始化项目为 GM 管理的结构。

**语法**
```bash
gm init [OPTIONS]
```

**选项**
```
  --base-path TEXT    Worktree 基础目录（默认：.gm）
  --force             强制初始化（覆盖现有配置）
  -h, --help          显示帮助
```

**示例**
```bash
# 标准初始化
gm init

# 自定义 worktree 基础目录
gm init --base-path ./worktrees

# 强制重新初始化
gm init --force
```

### gm add - 添加 Worktree

创建新的 worktree。

**语法**
```bash
gm add <branch_name> [OPTIONS]
```

**选项**
```
  -l, --local         使用本地分支
  -r, --remote        使用远程分支
  -f, --force         强制创建（覆盖现有）
  -h, --help          显示帮助
```

**示例**
```bash
# 自动检测分支
gm add feature/new-ui

# 使用本地分支
gm add feature/local -l

# 使用远程分支
gm add feature/remote -r

# 强制创建
gm add feature/force -f
```

### gm del - 删除 Worktree

删除 worktree。

**语法**
```bash
gm del <branch_name> [OPTIONS]
```

**选项**
```
  -D                  同时删除分支
  -f, --force         强制删除
  -h, --help          显示帮助
```

**示例**
```bash
# 仅删除 worktree
gm del feature/new-ui

# 删除 worktree 和分支
gm del feature/new-ui -D

# 强制删除
gm del feature/new-ui -f
```

### gm list - 列表 Worktree

列出所有 worktree。

**语法**
```bash
gm list [OPTIONS]
```

**选项**
```
  -v, --verbose       显示详细信息
  --format FORMAT     输出格式 (table|json)
  -h, --help          显示帮助
```

**示例**
```bash
# 简洁列表
gm list

# 详细列表
gm list -v

# JSON 格式
gm list --format json
```

**输出示例**
```
Worktree 列表：
feature/user-login      @ .gm/feature/user-login     [up to date]
feature/payment         @ .gm/feature/payment        [ahead 3 commits]
bugfix/critical         @ .gm/bugfix/critical        [behind 2 commits]
```

### gm status - 查看状态

查看 worktree 的状态。

**语法**
```bash
gm status [<branch_name>] [OPTIONS]
```

**选项**
```
  -j, --json          JSON 格式输出
  -h, --help          显示帮助
```

**示例**
```bash
# 查看所有 worktree 状态
gm status

# 查看特定 worktree 状态
gm status feature/user-login

# JSON 格式
gm status -j
```

**输出示例**
```
Worktree 状态：

feature/user-login:
  路径: .gm/feature/user-login
  分支: feature/user-login
  状态: up to date
  未追踪文件: 0
  提交差异: 0 ahead, 0 behind

feature/payment:
  路径: .gm/feature/payment
  分支: feature/payment
  状态: ahead
  未追踪文件: 2
  提交差异: 3 ahead, 0 behind
```

### gm clone - 克隆仓库

克隆仓库并初始化为 GM 结构。

**语法**
```bash
gm clone <repository> [<directory>] [OPTIONS]
```

**选项**
```
  --base-path TEXT    Worktree 基础目录
  -h, --help          显示帮助
```

**示例**
```bash
# 克隆到当前目录
gm clone https://github.com/example/repo.git

# 克隆到特定目录
gm clone https://github.com/example/repo.git my-project

# 自定义 worktree 基础目录
gm clone https://github.com/example/repo.git --base-path ./worktrees
```

## 工作流示例

### 示例 1：单功能分支开发

```bash
# 1. 初始化项目
cd my-project
gm init

# 2. 创建功能分支的 worktree
gm add feature/dark-mode

# 3. 在 worktree 中工作
cd .gm/feature/dark-mode
# 进行更改...
git add .
git commit -m "Implement dark mode"
git push origin feature/dark-mode

# 4. 列出所有 worktree
cd ../..
gm list -v

# 5. 删除 worktree
gm del feature/dark-mode -D
```

### 示例 2：并行多分支开发

```bash
# 1. 创建多个功能分支
gm add feature/user-auth
gm add feature/payment-integration
gm add feature/analytics

# 2. 同时在多个分支上工作
# 终端 1
cd .gm/feature/user-auth
# 进行认证相关工作

# 终端 2
cd .gm/feature/payment-integration
# 进行支付集成工作

# 终端 3
cd .gm/feature/analytics
# 进行分析工作

# 3. 查看所有分支的状态
gm status

# 4. 清理完成的工作
gm del feature/user-auth -D
gm del feature/payment-integration -D
gm del feature/analytics -D
```

### 示例 3：紧急修复工作流

```bash
# 1. 在主分支创建修复分支
git checkout main
git checkout -b bugfix/critical-issue

# 2. 为修复创建 worktree
gm add bugfix/critical-issue

# 3. 快速修复
cd .gm/bugfix/critical-issue
# 进行修复...
git add .
git commit -m "Fix critical issue"
git push origin bugfix/critical-issue

# 4. 创建 PR 和合并后，清理
cd ../..
gm del bugfix/critical-issue -D
```

### 示例 4：处理旧分支

```bash
# 1. 查看当前 worktree
gm list -v

# 2. 检查分支状态（落后的分支）
gm status

# 3. 更新旧分支
cd .gm/feature/old-feature
git fetch origin
git rebase origin/main
git push -f origin feature/old-feature

# 4. 验证状态
cd ../..
gm status feature/old-feature
```

## 配置管理

详见 [CONFIGURATION.md](CONFIGURATION.md)

主要配置选项：
- 工作树基础路径
- 工作树命名模式
- 共享文件列表
- 符号链接策略
- 分支名称映射

## 常见问题

### 我应该提交 .gm 目录吗？

不应该。`.gm` 目录包含本地工作树，不应该被版本控制。建议在 `.gitignore` 中添加：
```
.gm/
.gm.yaml
```

### 如何处理共享文件的冲突？

配置 `shared_files` 列表，这些文件将创建符号链接回项目根目录：
```yaml
shared_files:
  - .env
  - package-lock.json
```

### 我可以在不同的分支上使用相同的 worktree 吗？

不可以。每个 worktree 必须关联一个分支。要切换分支，请删除并重新创建 worktree。

### 如何在团队中共享 GM 配置？

将 `.gm.yaml` 文件提交到仓库（如果所有团队成员都使用 GM）。使用配置管理来共享：
```bash
git add .gm.yaml
git commit -m "Add GM configuration"
```

## 故障排除

详见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

常见问题解决方案：
- Permission denied（权限错误）
- Git command failed（Git 命令失败）
- Symlink broken（符号链接损坏）
- Config validation error（配置验证错误）

## 高级主题

### 自定义命名规则

在 `.gm.yaml` 中配置：
```yaml
worktree:
  naming_pattern: "{branch}"  # 使用分支名
```

### 符号链接策略

```yaml
symlinks:
  strategy: auto              # 自动创建符号链接
```

### 分支名称映射

用于在 worktree 名称和实际分支名称之间建立映射：
```yaml
branch_mapping:
  feature: features
  bugfix: fixes
```

## 获得帮助

- 快速开始：[QUICK_START.md](QUICK_START.md)
- API 参考：[API_REFERENCE.md](API_REFERENCE.md)
- 配置指南：[CONFIGURATION.md](CONFIGURATION.md)
- 故障排除：[TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
