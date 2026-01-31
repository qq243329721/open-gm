# GM - Git Worktree Manager

一个 Git Worktree 管理工具，简化多分支开发包管理的问题。

## 概览

GM 提供了强大而易用的命令行工具，用于管理 Git worktree。它自动处理复杂的 worktree 创建、删除、配置和符号链接管理，让开发者专注于代码实现。

### 核心特性

- **🚀 快速初始化** - 一键初始化项目为 GM 管理的结构
- **➕ 智能添加** - 自动识别远程/本地分支，创建 worktree
- **🗑️ 灵活删除** - 删除 worktree 同时可选删除关联分支
- **📋 完整列表** - 显示所有 worktree 及其状态（简洁/详细模式）
- **📊 详细状态** - 查看 worktree 的分支状态、提交差异、文件变化
- **🔗 自动符号链接** - 自动管理共享文件的符号链接
- **📝 事务支持** - 所有操作都是原子的，支持自动回滚
- **⚙️ 灵活配置** - 项目级 `.gm.yaml` 配置文件
- **🔒 安全操作** - 完整的错误处理和日志记录
- **📦 克隆集成** - 支持在克隆时直接初始化 GM

## 安装

### 系统要求

- Python 3.9+
- Git 2.7.0+
- 支持的操作系统：Linux、macOS、Windows

### 从源码安装（开发模式）

```bash
git clone https://github.com/qq243329721/open-gm.git
cd gm
pip install -e ".[dev]"
```

### 从 PyPI 安装

```bash
pip install gm
```

### 验证安装

```bash
gm --version
gm --help
```

## 快速开始

### 初始化项目

在 Git 仓库中运行：

```bash
gm init
```

这将创建：
- `.gm/` - worktree 基础目录
- `.gm.yaml` - 项目配置文件

### 添加 Worktree

```bash
# 自动检测分支类型
gm add feature/user-login

# 使用本地分支
gm add feature/local -l

# 使用远程分支
gm add origin/feature/remote -r
```

### 查看所有 Worktree

```bash
# 简洁模式
gm list

# 详细模式（带颜色和详细信息）
gm list -v
```

### 检查状态

```bash
# 所有 worktree 的状态
gm status

# 特定 worktree 的状态
gm status feature/user-login
```

### 删除 Worktree

```bash
# 仅删除 worktree（保留分支）
gm del feature/user-login

# 同时删除 worktree 和分支
gm del feature/user-login -D
```

## 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `gm init` | 初始化项目 | `gm init --base-path .gm` |
| `gm add` | 添加 worktree | `gm add feature/new-ui -r` |
| `gm del` | 删除 worktree | `gm del feature/new-ui -D` |
| `gm list` | 列出 worktree | `gm list -v` |
| `gm status` | 查看状态 | `gm status` |
| `gm clone` | 克隆并初始化 | `gm clone <url>` |



## 工作流示例

### 并行开发多个功能

```bash
# 1. 初始化
gm init

# 2. 为不同功能创建 worktree
gm add feature/auth
gm add feature/payment
gm add feature/analytics

# 3. 在不同的终端中工作
# 终端 1
cd .gm/feature/auth
# 开发认证...

# 终端 2
cd .gm/feature/payment
# 开发支付...

# 4. 查看进度
gm status

# 5. 完成后清理
gm del feature/auth -D
gm del feature/payment -D
gm del feature/analytics -D
```

### 紧急修复工作流

```bash
# 快速创建修复分支
gm add hotfix/critical-bug

# 进行修复
cd .gm/hotfix/critical-bug
git add .
git commit -m "Fix critical bug"
git push origin hotfix/critical-bug

# 完成后删除
cd ../..
gm del hotfix/critical-bug -D
```

## 项目结构

```
gm/
├── gm/                      # 主包
│   ├── cli/                 # 命令行接口
│   │   ├── main.py         # CLI 入口点
│   │   ├── commands/       # 命令实现
│   │   │   ├── add.py
│   │   │   ├── del.py
│   │   │   ├── init.py
│   │   │   ├── list.py
│   │   │   ├── status.py
│   │   │   └── clone.py
│   │   └── __init__.py
│   ├── core/                # 核心逻辑
│   │   ├── git_client.py    # Git 操作封装
│   │   ├── config_manager.py # 配置管理
│   │   ├── worktree_manager.py # Worktree 管理
│   │   ├── transaction.py   # 事务管理
│   │   ├── exceptions.py    # 异常定义
│   │   ├── logger.py        # 日志系统
│   │   └── ...
│   └── __init__.py
├── tests/                   # 测试
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   └── cli/                # CLI 测试
├── docs/                   # 文档
│   ├── QUICK_START.md      # 快速开始
│   ├── USER_MANUAL.md      # 用户手册
│   ├── API_REFERENCE.md    # API 参考
│   ├── CONFIGURATION.md    # 配置指南
│   ├── ARCHITECTURE.md     # 架构设计
│   ├── CONTRIBUTING.md     # 贡献指南
│   ├── TROUBLESHOOTING.md  # 故障排除
│   └── RELEASE.md          # 发布指南
├── examples/               # 示例
│   ├── basic_workflow.sh   # 基础工作流
│   ├── advanced_workflow.sh # 高级工作流
│   ├── config_examples/    # 配置示例
│   └── scripts/            # 辅助脚本
├── pyproject.toml         # 项目配置
├── pytest.ini             # 测试配置
└── README.md              # 本文件
```

## 配置

GM 使用 `.gm.yaml` 进行项目级配置。默认配置：

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
  - README.md

symlinks:
  strategy: auto

branch_mapping: {}
```



## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/core/test_git_client.py -v

# 显示覆盖率
pytest tests/ --cov=gm --cov-report=html
```

### 代码规范检查

```bash
# 格式化
black gm tests

# 检查风格
ruff check gm tests

# 类型检查
mypy gm
```

### 生成覆盖率报告

```bash
pytest tests/ --cov=gm --cov-report=html
open htmlcov/index.html
```

## 架构

GM 采用分层架构：

```
┌──────────────────────────┐
│   CLI 层 (Commands)      │
├──────────────────────────┤
│ Core 层 (Business Logic) │
├──────────────────────────┤
│ Infrastructure 层        │
└──────────────────────────┘
```



## 常见问题

### Q: Worktree 会修改原始仓库吗？

A: 不会。每个 worktree 都是独立的工作目录，共享 Git 对象库但有独立的索引和工作树。

### Q: 我可以同时使用多少个 worktree？

A: 理论上没有限制，但建议不超过 10-20 个，取决于系统资源。

### Q: 如何删除 worktree 而不删除分支？

A: 使用 `gm del <branch>` 而不加 `-D` 选项。分支将保留在 Git 中。

### Q: 我应该提交 `.gm` 目录吗？

A: 不应该。将 `.gm` 添加到 `.gitignore`。但建议提交 `.gm.yaml` 以共享团队配置。



## 文档

- **[核心实现](docs/core-implementation.md)** - 详细的设计与实现文档

## 性能

- **初始化**: < 100ms
- **添加 worktree**: < 500ms
- **删除 worktree**: < 300ms
- **列表**: < 200ms
- **状态查询**: < 1s（取决于仓库大小）

## 许可证

MIT License

## 贡献

欢迎贡献！请提交 Pull Request。

### 贡献流程

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 支持

- 📖 查看 [文档](docs/)
- 🐛 报告 Bug：创建 Issue
- 💡 功能建议：创建 Discussion
- 💬 讨论：参与 Discussions

## 相关项目

- [Git](https://git-scm.com/) - 版本控制
- [Click](https://click.palletsprojects.com/) - CLI 框架
- [PyYAML](https://pyyaml.org/) - YAML 处理

## 路线图

- [ ] Web UI 界面
- [ ] RESTful API
- [ ] 插件系统
- [ ] 集群管理
- [ ] 性能优化（Rust 扩展）


## 作者

- **GM Team** - 初始工作

## 致谢

感谢所有为 GM 做出贡献的人。

---

**快速链接**:
- [核心实现](docs/core-implementation.md)
