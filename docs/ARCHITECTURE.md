# GM 架构设计

GM 系统架构、设计模式和扩展点的详细文档。

## 目录

1. [架构概览](#架构概览)
2. [分层设计](#分层设计)
3. [核心模块](#核心模块)
4. [数据流](#数据流)
5. [设计模式](#设计模式)
6. [扩展点](#扩展点)

## 架构概览

GM 采用分层架构设计，包含三个主要层级：

```
┌─────────────────────────────────┐
│      CLI 层 (Presentation)       │
│  main.py, commands/*             │
├─────────────────────────────────┤
│   Core 业务逻辑层 (Business)     │
│  git_client, config_manager,     │
│  worktree_manager, transaction   │
├─────────────────────────────────┤
│ Infrastructure 基础设施层        │
│  logger, cache, exceptions       │
└─────────────────────────────────┘
```

### 设计原则

1. **分离关注点** - 每个模块有明确的职责
2. **依赖注入** - 易于测试和扩展
3. **单一责任** - 一个类一个职责
4. **开闭原则** - 对扩展开放，对修改关闭
5. **接口隔离** - 依赖于抽象而不是具体

## 分层设计

### 1. CLI 层（表示层）

职责：
- 解析命令行参数
- 格式化输出
- 用户交互

主要文件：
- `gm/cli/main.py` - CLI 入口点
- `gm/cli/commands/*.py` - 各命令实现

示例：
```python
# gm/cli/commands/add.py
@click.command()
@click.argument('branch')
@click.option('-l', '--local', is_flag=True)
def add_command(branch, local):
    """添加 worktree 命令"""
    # 验证输入
    # 调用业务逻辑
    # 格式化输出
```

### 2. Core 业务逻辑层

职责：
- 实现核心业务逻辑
- 管理 Git 操作
- 配置和状态管理

主要模块：

#### GitClient
- Git 命令执行
- 分支管理
- 提交历史

#### ConfigManager
- 配置文件加载/保存
- 配置验证
- 配置合并

#### WorktreeManager
- worktree 创建/删除
- 符号链接管理
- 状态检查

#### Transaction
- 事务开始/提交/回滚
- 操作日志记录

### 3. Infrastructure 基础设施层

职责：
- 日志记录
- 缓存管理
- 异常处理

主要模块：
- `logger.py` - 结构化日志
- `cache_manager.py` - 缓存系统
- `exceptions.py` - 异常定义

## 核心模块

### GitClient

```python
class GitClient:
    """Git 操作客户端"""

    def run_command(cmd, cwd, check) -> str
    def get_branches(remote) -> List[str]
    def get_current_branch() -> Optional[str]
    def get_commits(branch, max_count) -> List[Dict]
    def branch_exists(branch, remote) -> bool
```

**特点**：
- 统一的 Git 命令接口
- 错误处理和日志记录
- 支持自定义工作目录

### ConfigManager

```python
class ConfigManager:
    """配置管理器"""

    def load_config() -> Optional[Dict]
    def save_config(config) -> None
    def get_default_config() -> Dict
    def merge_config(base, override) -> Dict
```

**特点**：
- YAML 格式支持
- 配置验证
- 合并策略支持

### WorktreeManager

```python
class WorktreeManager:
    """Worktree 管理器"""

    def create_worktree(branch, path) -> None
    def remove_worktree(path, delete_branch) -> None
    def list_worktrees() -> List[Dict]
    def get_worktree_status(path) -> Dict
```

**特点**：
- 自动创建/删除符号链接
- 事务支持
- 状态跟踪

### Transaction

```python
class Transaction:
    """事务管理器"""

    def begin() -> None
    def commit() -> None
    def rollback() -> None
    def add_operation(op) -> None
```

**特点**：
- 原子操作
- 自动回滚
- 操作日志

## 数据流

### 添加 Worktree 流程

```
CLI 层 (add command)
    ↓ 验证输入
Core 层 (WorktreeManager)
    ↓ 开始事务
    ├→ GitClient 检查分支
    ├→ ConfigManager 获取配置
    ├→ 创建 worktree 目录
    ├→ GitClient 创建 worktree
    ├→ 创建符号链接
    └→ 提交事务
    ↓ 事务完成
CLI 层 (输出结果)
    ↓ 显示成功消息
```

### 删除 Worktree 流程

```
CLI 层 (del command)
    ↓ 验证输入
Core 层 (WorktreeManager)
    ↓ 开始事务
    ├→ 验证 worktree 存在
    ├→ GitClient 删除 worktree
    ├→ 删除符号链接
    ├→ 删除目录
    ├→ 可选：删除分支
    └→ 提交事务
    ↓ 事务完成
CLI 层 (输出结果)
    ↓ 显示成功消息
```

### 查询状态流程

```
CLI 层 (status command)
    ↓ 验证输入
Core 层 (WorktreeManager)
    ├→ ConfigManager 获取配置
    ├→ 枚举 worktree 目录
    ├→ 对每个 worktree：
    │   ├→ GitClient 获取分支
    │   ├→ GitClient 获取状态
    │   ├→ GitClient 获取提交差异
    │   └→ 收集信息
    └→ 返回状态列表
    ↓ 格式化输出
CLI 层 (输出结果)
    ↓ 表格/JSON 格式显示
```

## 设计模式

### 1. Factory 模式

配置管理器工厂：

```python
class ConfigManagerFactory:
    @staticmethod
    def create(project_root: Path) -> ConfigManager:
        """创建配置管理器"""
        return ConfigManager(project_root)
```

### 2. Strategy 模式

符号链接策略：

```python
class SymlinkStrategy:
    def create_symlinks(self) -> None: pass

class AutoSymlinkStrategy(SymlinkStrategy):
    def create_symlinks(self) -> None: ...

class ManualSymlinkStrategy(SymlinkStrategy):
    def create_symlinks(self) -> None: ...
```

### 3. Command 模式

CLI 命令实现：

```python
class Command:
    def execute(self) -> None: pass

class AddCommand(Command):
    def execute(self) -> None: ...
```

### 4. Observer 模式

事务监听器：

```python
class TransactionListener:
    def on_begin(self) -> None: pass
    def on_commit(self) -> None: pass
    def on_rollback(self) -> None: pass
```

### 5. Singleton 模式

日志系统：

```python
logger = get_logger("module_name")  # 返回相同实例
```

## 扩展点

### 1. 自定义命令

添加新命令：

```python
# gm/cli/commands/custom.py
@click.command()
def custom_command():
    """自定义命令"""
    pass

# gm/cli/main.py
@click.group()
def cli():
    pass

cli.add_command(custom_command, name='custom')
```

### 2. 自定义符号链接策略

```python
# gm/core/symlink_strategy.py
class CustomSymlinkStrategy(SymlinkStrategy):
    def create_symlinks(self) -> None:
        # 实现自定义逻辑
        pass
```

### 3. 自定义配置验证

```python
# gm/core/config_validator.py
class CustomValidator(ConfigValidator):
    def validate(self, config: Dict) -> None:
        super().validate(config)
        # 添加自定义验证规则
```

### 4. 自定义 Git 客户端

```python
# 扩展 GitClient
class CustomGitClient(GitClient):
    def custom_method(self) -> str:
        # 实现自定义方法
        pass
```

### 5. 插件系统

未来计划实现插件系统，允许加载第三方扩展。

## 错误处理

异常层级结构：

```
GMException (基类)
├── GitException
│   └── GitCommandError
├── ConfigException
│   ├── ConfigIOError
│   ├── ConfigParseError
│   └── ConfigValidationError
├── WorktreeException
│   ├── WorktreeAlreadyExists
│   ├── WorktreeNotFound
│   └── WorktreeOperationFailed
└── TransactionException
    ├── TransactionFailed
    ├── RollbackFailed
    └── CommitFailed
```

处理异常的最佳实践：

```python
try:
    worktree_manager.create_worktree(branch, path)
except WorktreeAlreadyExists as e:
    # 处理特定错误
    logger.error("Worktree already exists", branch=branch)
except GMException as e:
    # 处理通用错误
    logger.error("Operation failed", error=str(e))
except Exception as e:
    # 处理意外错误
    logger.error("Unexpected error", error=str(e))
```

## 性能考虑

### 缓存策略

```python
@cache_manager.cached(ttl=300)
def get_branches(self) -> List[str]:
    """缓存 5 分钟"""
    return self.run_command(["git", "branch"])
```

### 并发操作

使用线程安全的操作：

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)
futures = [
    executor.submit(process_worktree, wt)
    for wt in worktrees
]
results = [f.result() for f in futures]
```

## 测试架构

### 单元测试

```
tests/core/
├── test_git_client.py
├── test_config_manager.py
├── test_worktree_manager.py
└── test_transaction.py
```

### 集成测试

```
tests/integration/
├── test_e2e.py
└── test_workflows.py
```

### CLI 测试

```
tests/cli/
├── commands/
│   ├── test_add.py
│   ├── test_del.py
│   ├── test_list.py
│   └── test_status.py
└── test_main.py
```

## 部署架构

### 本地开发

```bash
pip install -e ".[dev]"
```

### 生产安装

```bash
pip install gm
```

### Docker 部署

```dockerfile
FROM python:3.9
RUN pip install gm
WORKDIR /workspace
ENTRYPOINT ["gm"]
```

## 未来扩展

1. **RESTful API** - 通过 HTTP 接口访问 GM
2. **Web UI** - 基于 Web 的管理界面
3. **插件系统** - 支持第三方扩展
4. **集群管理** - 管理多个仓库
5. **性能优化** - 使用 Rust 重写 Hot Path
6. **GUI 应用** - 图形化用户界面

## 贡献指南

贡献新功能时应遵循架构：

1. 在 Core 层实现业务逻辑
2. 如需要，在 CLI 层添加命令
3. 添加必要的单元和集成测试
4. 更新文档
5. 遵循代码规范

## 相关文档

- [贡献指南](CONTRIBUTING.md)
- [API 参考](API_REFERENCE.md)
- [配置指南](CONFIGURATION.md)
