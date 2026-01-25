# GM API 参考

GM 核心模块和 API 的完整参考文档。

## 目录

1. [核心模块](#核心模块)
2. [GitClient](#gitclient)
3. [ConfigManager](#configmanager)
4. [WorktreeManager](#worktreemanager)
5. [异常处理](#异常处理)
6. [使用示例](#使用示例)

## 核心模块

GM 核心功能分布在以下模块中：

```
gm/
├── core/
│   ├── git_client.py         # Git 操作客户端
│   ├── config_manager.py     # 配置管理
│   ├── exceptions.py         # 异常定义
│   ├── logger.py            # 日志系统
│   ├── transaction.py       # 事务管理
│   └── ...
└── cli/
    ├── main.py              # CLI 入口
    └── commands/            # 命令实现
```

## GitClient

Git 操作的统一接口。

### 初始化

```python
from gm.core.git_client import GitClient
from pathlib import Path

# 使用默认路径（当前目录）
client = GitClient()

# 指定仓库路径
client = GitClient(Path("/path/to/repo"))

# 使用字符串路径
client = GitClient("/path/to/repo")
```

### 主要方法

#### run_command

执行任意 Git 命令。

```python
def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    check: bool = True,
) -> str
```

**参数**
- `cmd`: Git 命令列表
- `cwd`: 工作目录（默认使用 repo_path）
- `check`: 命令失败时是否抛出异常

**返回值**
- 命令输出字符串

**异常**
- `GitCommandError`: 命令执行失败

**示例**
```python
client = GitClient()

# 获取 Git 状态
status = client.run_command(["git", "status"])

# 不检查错误
result = client.run_command(["git", "status"], check=False)
```

#### get_version

获取 Git 版本。

```python
def get_version(self) -> str
```

**返回值**
- Git 版本号字符串

**示例**
```python
version = client.get_version()
print(f"Git version: {version}")
```

#### get_branches

获取所有分支列表。

```python
def get_branches(self, remote: bool = False) -> List[str]
```

**参数**
- `remote`: 是否列出远程分支

**返回值**
- 分支名称列表

**示例**
```python
# 本地分支
branches = client.get_branches()

# 远程分支
remote_branches = client.get_branches(remote=True)
```

#### get_current_branch

获取当前分支。

```python
def get_current_branch(self) -> Optional[str]
```

**返回值**
- 当前分支名称，无分支时返回 None

**示例**
```python
current = client.get_current_branch()
if current:
    print(f"Current branch: {current}")
```

#### get_commits

获取提交历史。

```python
def get_commits(
    self,
    branch: Optional[str] = None,
    max_count: Optional[int] = None,
) -> List[Dict[str, str]]
```

**参数**
- `branch`: 指定分支（默认当前分支）
- `max_count`: 返回的最大提交数

**返回值**
- 提交信息字典列表

**示例**
```python
# 获取最近 10 个提交
commits = client.get_commits(max_count=10)

# 获取特定分支的提交
commits = client.get_commits(branch="feature/new-ui", max_count=5)
```

#### branch_exists

检查分支是否存在。

```python
def branch_exists(self, branch: str, remote: bool = False) -> bool
```

**参数**
- `branch`: 分支名称
- `remote`: 是否检查远程分支

**返回值**
- True 如果分支存在，否则 False

**示例**
```python
if client.branch_exists("feature/new-ui"):
    print("Branch exists locally")

if client.branch_exists("feature/new-ui", remote=True):
    print("Branch exists on remote")
```

## ConfigManager

配置文件管理。

### 初始化

```python
from gm.core.config_manager import ConfigManager
from pathlib import Path

# 使用默认路径
manager = ConfigManager()

# 指定项目根目录
manager = ConfigManager(Path("/path/to/project"))
```

### 主要方法

#### load_config

加载配置文件。

```python
def load_config(self, config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]
```

**参数**
- `config_path`: 配置文件路径（默认使用 .gm.yaml）

**返回值**
- 配置字典，文件不存在时返回 None

**异常**
- `ConfigParseError`: 配置文件格式错误
- `ConfigIOError`: I/O 错误

**示例**
```python
config = manager.load_config()
if config:
    print(f"Base path: {config['worktree']['base_path']}")
```

#### save_config

保存配置文件。

```python
def save_config(
    self,
    config: Dict[str, Any],
    config_path: Optional[Path] = None,
) -> None
```

**参数**
- `config`: 配置字典
- `config_path`: 目标路径

**异常**
- `ConfigIOError`: I/O 错误

**示例**
```python
config = manager.get_default_config()
config['worktree']['base_path'] = '.custom_gm'
manager.save_config(config)
```

#### get_default_config

获取默认配置。

```python
def get_default_config(self) -> Dict[str, Any]
```

**返回值**
- 默认配置字典的深拷贝

**示例**
```python
config = manager.get_default_config()
print(config)
```

#### config_path

获取配置文件路径。

```python
@property
def config_path(self) -> Path
```

**示例**
```python
print(f"Config file: {manager.config_path}")
```

## WorktreeManager

Worktree 管理操作。

### 初始化

```python
from gm.core.worktree_manager import WorktreeManager

# 使用配置和 Git 客户端初始化
manager = WorktreeManager(
    git_client=client,
    config_manager=config_manager,
)
```

### 主要方法

#### create_worktree

创建新的 worktree。

```python
def create_worktree(
    self,
    branch: str,
    worktree_path: Path,
    force: bool = False,
) -> None
```

**参数**
- `branch`: 分支名称
- `worktree_path`: worktree 目录路径
- `force`: 如果目录已存在是否强制覆盖

**异常**
- `GitException`: Git 操作失败
- `GMException`: GM 相关错误

**示例**
```python
manager.create_worktree(
    branch="feature/new-ui",
    worktree_path=Path(".gm/feature/new-ui"),
)
```

#### remove_worktree

删除 worktree。

```python
def remove_worktree(
    self,
    worktree_path: Path,
    delete_branch: bool = False,
) -> None
```

**参数**
- `worktree_path`: worktree 目录路径
- `delete_branch`: 是否同时删除关联的分支

**异常**
- `GitException`: Git 操作失败

**示例**
```python
manager.remove_worktree(
    worktree_path=Path(".gm/feature/new-ui"),
    delete_branch=True,
)
```

#### list_worktrees

列出所有 worktree。

```python
def list_worktrees(self) -> List[Dict[str, Any]]
```

**返回值**
- worktree 信息字典列表

**示例**
```python
worktrees = manager.list_worktrees()
for wt in worktrees:
    print(f"{wt['branch']} @ {wt['path']}")
```

## 异常处理

### 异常类层级

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

### 使用异常

```python
from gm.core.exceptions import (
    GitCommandError,
    ConfigException,
    GMException,
)

try:
    client.run_command(["git", "checkout", "nonexistent"])
except GitCommandError as e:
    print(f"Git error: {e.details}")
except GMException as e:
    print(f"GM error: {e}")
```

## 使用示例

### 示例 1：初始化项目

```python
from pathlib import Path
from gm.core.git_client import GitClient
from gm.core.config_manager import ConfigManager

project_path = Path("/path/to/project")

# 初始化配置
config_mgr = ConfigManager(project_path)
config = config_mgr.get_default_config()
config_mgr.save_config(config)

# 创建 worktree 基础目录
worktree_base = project_path / config["worktree"]["base_path"]
worktree_base.mkdir(exist_ok=True)

print("Project initialized!")
```

### 示例 2：创建和管理 Worktree

```python
from pathlib import Path
from gm.core.git_client import GitClient
from gm.core.config_manager import ConfigManager

project_path = Path("/path/to/project")
git_client = GitClient(project_path)
config_mgr = ConfigManager(project_path)

# 获取配置
config = config_mgr.load_config()
base_path = project_path / config["worktree"]["base_path"]

# 创建 worktree 目录
worktree_name = "feature/new-ui"
worktree_path = base_path / worktree_name
worktree_path.mkdir(parents=True, exist_ok=True)

# 创建 worktree
git_client.run_command([
    "git", "worktree", "add",
    str(worktree_path),
    worktree_name,
])

print(f"Worktree created: {worktree_path}")
```

### 示例 3：获取项目状态

```python
from gm.core.git_client import GitClient
from pathlib import Path

git_client = GitClient(Path("/path/to/project"))

# 获取分支列表
branches = git_client.get_branches()
print(f"Local branches: {branches}")

# 获取当前分支
current = git_client.get_current_branch()
print(f"Current branch: {current}")

# 获取最近的提交
commits = git_client.get_commits(max_count=5)
for commit in commits:
    print(f"  {commit['hash'][:7]} - {commit['message']}")
```

### 示例 4：错误处理

```python
from gm.core.git_client import GitClient
from gm.core.exceptions import GitCommandError

git_client = GitClient()

try:
    # 尝试检出不存在的分支
    git_client.run_command(
        ["git", "checkout", "nonexistent-branch"],
        check=True,
    )
except GitCommandError as e:
    print(f"Error: {e.message}")
    print(f"Details: {e.details}")
```

### 示例 5：配置管理

```python
from gm.core.config_manager import ConfigManager
from pathlib import Path

config_mgr = ConfigManager()

# 加载配置
config = config_mgr.load_config()

# 修改配置
config['worktree']['auto_cleanup'] = False
config['display']['colors'] = False

# 保存配置
config_mgr.save_config(config)

# 验证保存
verified = config_mgr.load_config()
print(f"Config saved: {verified == config}")
```

## 日志记录

GM 使用 structlog 进行日志记录。

```python
from gm.core.logger import get_logger

logger = get_logger("my_module")

logger.info("Operation started", branch="feature/new-ui")
logger.debug("Processing details", file_count=10)
logger.warning("Potential issue detected", reason="slow_operation")
logger.error("Operation failed", error="command timeout")
```

## 进阶主题

### 自定义 GitClient

```python
from gm.core.git_client import GitClient
from pathlib import Path

class CustomGitClient(GitClient):
    def get_author_info(self):
        """获取提交者信息"""
        name = self.run_command(["git", "config", "user.name"])
        email = self.run_command(["git", "config", "user.email"])
        return {"name": name, "email": email}
```

### 事务支持

```python
from gm.core.transaction import Transaction

transaction = Transaction()

try:
    transaction.begin()
    # 执行操作...
    transaction.commit()
except Exception as e:
    transaction.rollback()
    raise
```

## 更多资源

- [快速开始](QUICK_START.md)
- [用户手册](USER_MANUAL.md)
- [配置指南](CONFIGURATION.md)
- [贡献指南](CONTRIBUTING.md)
