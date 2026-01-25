# GM - Git Worktree Manager

一个企业级的 Git Worktree 管理工具，简化多分支开发工作流。

## 功能

- 🚀 快速初始化项目为 .gm 结构
- ➕ 智能添加 worktree（自动识别远程/本地分支）
- 🗑️ 灵活删除 worktree 和分支
- 📋 列出所有 worktree 及其状态
- 📊 查看 worktree 详细信息
- 🔗 自动管理符号链接
- 📝 完整的事务支持（原子操作、自动回滚）
- ⚙️ 灵活的项目级配置

## 安装

```bash
# 开发安装
pip install -e ".[dev]"

# 运行
gm --help
```

## 快速开始

### 初始化项目

```bash
gm init .
```

### 添加 worktree

```bash
gm add feature/new-ui      # 自动识别分支
gm add feature/local -l    # 强制创建本地分支
gm add feature/remote -r   # 强制使用远程分支
```

### 列出 worktree

```bash
gm list           # 简洁模式
gm list -v        # 详细彩色模式
```

### 查看状态

```bash
gm status                   # 当前或全局摘要
gm status feature/new-ui   # 指定 worktree 状态
```

### 删除 worktree

```bash
gm del feature/new-ui      # 仅删除 worktree
gm del feature/new-ui -D   # 同时删除分支
```

## 项目结构

```
gm-claude/
├── gm/                  # 主包
│   ├── cli/            # 命令行接口
│   │   ├── main.py    # CLI 入口
│   │   └── commands/  # 各命令实现
│   └── core/          # 核心逻辑
│       ├── exceptions.py        # 异常定义
│       ├── git_client.py        # Git 操作
│       ├── config_manager.py    # 配置管理
│       ├── worktree_manager.py  # Worktree 管理
│       ├── transaction.py       # 事务管理
│       └── ...
├── tests/             # 测试目录
├── pyproject.toml     # 项目配置
├── pytest.ini         # 测试配置
└── README.md          # 本文件
```

## 开发

### 运行测试

```bash
pytest                 # 运行所有测试
pytest -v             # 详细输出
pytest -cov           # 覆盖率
```

### 代码规范

```bash
black gm tests        # 格式化代码
ruff check gm tests   # 代码检查
mypy gm              # 类型检查
```

## 许可证

MIT License

## 贡献

欢迎提交 PR 和 Issue！
