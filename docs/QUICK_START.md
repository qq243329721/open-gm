# GM 快速开始

欢迎使用 GM（Git Worktree Manager）！本指南将帮助您快速上手。

## 什么是 GM？

GM 是一个企业级的 Git Worktree 管理工具，用于简化多分支开发工作流。它自动管理 Git worktree、符号链接和项目配置，让您专注于代码开发。

## 安装

### 系统要求

- Python 3.9+
- Git 2.7.0+
- 支持的操作系统：Linux、macOS、Windows

### 安装方式

**当前版本 (v0.1.0) - 开发模式安装:**

```bash
# 进入项目目录
cd D:\workspace_project\gm-claude

# 安装到本地（开发模式）
pip install -e .
```

> 📝 **注意**: v0.1.0 还未发布到 PyPI，所以暂不支持 `pip install gm`。
>
> 发布到 PyPI 后，用户可以直接执行 `pip install gm`。
>
> 详见 [完整安装指南](INSTALLATION.md)

### 验证安装

```bash
gm --version
gm --help
```

## 5 分钟快速开始

### 1. 初始化项目

在现有的 Git 仓库中运行：

```bash
cd /path/to/your/project
gm init
```

这将创建：
- `.gm/` - worktree 基础目录
- `.gm.yaml` - 项目配置文件

### 2. 添加第一个 Worktree

```bash
# 自动检测分支并创建 worktree
gm add feature/user-login

# 指定使用本地分支
gm add feature/local -l

# 指定使用远程分支
gm add feature/remote -r
```

### 3. 查看所有 Worktree

```bash
# 简洁模式
gm list

# 详细模式（带颜色和详细信息）
gm list -v
```

### 4. 在 Worktree 中工作

```bash
# 进入 worktree 目录
cd .gm/feature/user-login

# 进行更改和提交
git add .
git commit -m "Implement user login"
git push origin feature/user-login
```

### 5. 查看状态

```bash
# 查看所有 worktree 的状态
gm status

# 查看特定 worktree 的状态
gm status feature/user-login
```

### 6. 删除 Worktree

```bash
# 仅删除 worktree（保留分支）
gm del feature/user-login

# 同时删除 worktree 和分支
gm del feature/user-login -D
```

## 常见命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `gm init` | 初始化项目为 .gm 结构 | `gm init` |
| `gm add` | 添加 worktree | `gm add feature/new-ui` |
| `gm del` | 删除 worktree | `gm del feature/new-ui` |
| `gm list` | 列出所有 worktree | `gm list -v` |
| `gm status` | 查看状态 | `gm status` |
| `gm clone` | 克隆仓库并初始化 | `gm clone <repo_url>` |

## 命令行选项

### gm add

```bash
gm add <branch_name> [OPTIONS]

选项：
  -l, --local              使用本地分支
  -r, --remote             使用远程分支
  -f, --force              强制创建（如果目录已存在）
  -h, --help               显示帮助
```

### gm del

```bash
gm del <branch_name> [OPTIONS]

选项：
  -D                       同时删除关联的分支
  -f, --force              强制删除
  -h, --help               显示帮助
```

### gm list

```bash
gm list [OPTIONS]

选项：
  -v, --verbose            显示详细信息
  --format {table,json}    输出格式
  -h, --help               显示帮助
```

### gm status

```bash
gm status [<branch_name>] [OPTIONS]

选项：
  -h, --help               显示帮助
```

## 常见问题

### Q: 什么是 worktree？

A: Git worktree 允许您在同一个仓库中同时处理多个分支。每个 worktree 是一个独立的工作目录。

### Q: Worktree 会修改原始仓库吗？

A: 不会。每个 worktree 都是独立的，在一个 worktree 中的更改不会影响其他 worktree 或主仓库。

### Q: 我可以同时使用多少个 worktree？

A: 理论上没有限制，但实际取决于您的系统资源。推荐不超过 10-20 个并发 worktree。

### Q: 如何在 worktree 之间切换？

A: 简单地切换到不同 worktree 的目录即可：
```bash
cd .gm/feature/user-login
cd .gm/feature/user-registration
```

### Q: 删除 worktree 会删除我的代码吗？

A: 不会。删除 worktree 仅删除物理目录。您的代码在 Git 分支中是安全的。要完全清除，使用 `-D` 选项删除分支。

## 最佳实践

### 1. 规范分支名称

使用清晰的分支名称，便于识别：
```bash
feature/user-login        # 功能分支
bugfix/memory-leak        # 修复分支
docs/api-reference        # 文档分支
release/v1.0.0           # 发布分支
```

### 2. 定期清理

```bash
# 列出所有 worktree
gm list

# 删除不再使用的 worktree
gm del feature/old-feature -D
```

### 3. 共享文件管理

在 `.gm.yaml` 中配置共享文件：
```yaml
shared_files:
  - .env
  - .gitignore
  - package-lock.json
```

### 4. 使用配置文件

创建项目级配置 `.gm.yaml`：
```yaml
worktree:
  base_path: .gm
  naming_pattern: "{branch}"
  auto_cleanup: true

display:
  colors: true
  default_verbose: false

shared_files:
  - .env
  - .gitignore

symlinks:
  strategy: auto
```

## 获取帮助

- 查看完整文档：[用户手册](USER_MANUAL.md)
- 查看 API 参考：[API 参考](API_REFERENCE.md)
- 配置指南：[配置指南](CONFIGURATION.md)
- 遇到问题？[故障排除](TROUBLESHOOTING.md)

## 下一步

- 阅读 [用户手册](USER_MANUAL.md) 了解更多高级功能
- 查看 [配置指南](CONFIGURATION.md) 自定义项目配置
- 查看 [示例](../examples) 了解更多用法

## 获得支持

如有问题或建议，请：
- 查看 [故障排除指南](TROUBLESHOOTING.md)
- 提交 Issue 到项目仓库
- 查看 [贡献指南](CONTRIBUTING.md)
