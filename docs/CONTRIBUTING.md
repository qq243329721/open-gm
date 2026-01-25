# GM 贡献指南

感谢您对 GM 项目的兴趣！本指南将帮助您贡献代码。

## 目录

1. [开发环境设置](#开发环境设置)
2. [代码规范](#代码规范)
3. [提交流程](#提交流程)
4. [Pull Request 流程](#pull-request-流程)
5. [测试指南](#测试指南)
6. [文档指南](#文档指南)

## 开发环境设置

### 系统要求

- Python 3.9+
- Git 2.7.0+
- Pip 或 Poetry

### 克隆仓库

```bash
git clone https://github.com/yourusername/gm.git
cd gm
```

### 创建虚拟环境

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 验证环装

```bash
gm --version
pytest --version
```

## 代码规范

### Python 风格指南

遵循 PEP 8 标准：

```bash
# 格式化代码
black gm tests

# 检查风格
ruff check gm tests

# 类型检查
mypy gm
```

### 命名规范

- **模块名**: `snake_case` (例: `git_client.py`)
- **类名**: `PascalCase` (例: `GitClient`)
- **函数/方法**: `snake_case` (例: `get_branches()`)
- **常量**: `UPPER_SNAKE_CASE` (例: `DEFAULT_CONFIG`)
- **私有成员**: `_leading_underscore`

### 代码示例

```python
"""模块文档字符串

简要说明。

详细说明（如需要）。
"""

from typing import List, Optional, Dict, Any
from pathlib import Path

from gm.core.exceptions import GMException
from gm.core.logger import get_logger

logger = get_logger("module_name")


class MyClass:
    """类的文档字符串

    详细说明。
    """

    DEFAULT_VALUE = "default"

    def __init__(self, param: str) -> None:
        """初始化

        Args:
            param: 参数说明

        Raises:
            ValueError: 错误情况说明
        """
        self.param = param
        logger.info("Initialized", param=param)

    def public_method(self, arg: int) -> str:
        """公开方法

        Args:
            arg: 参数说明

        Returns:
            返回值说明

        Raises:
            GMException: 异常说明
        """
        result = self._private_method(arg)
        return result

    def _private_method(self, arg: int) -> str:
        """私有方法"""
        return str(arg)
```

### 类型提示

所有公开函数必须有类型提示：

```python
def process_data(
    data: List[str],
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """处理数据

    Args:
        data: 数据列表
        config: 可选配置字典

    Returns:
        处理是否成功
    """
    pass
```

### 日志记录

使用 structlog 进行日志记录：

```python
from gm.core.logger import get_logger

logger = get_logger(__name__)

logger.info("Operation started", branch="feature/new")
logger.debug("Detailed info", file_count=10)
logger.warning("Warning message", reason="slow")
logger.error("Error occurred", error="details")
```

### 异常处理

使用自定义异常：

```python
from gm.core.exceptions import GMException, GitCommandError

try:
    # 执行操作
    pass
except GitCommandError as e:
    logger.error("Git operation failed", error=e.details)
    raise
except Exception as e:
    logger.error("Unexpected error", error=str(e))
    raise GMException(f"Operation failed: {e}") from e
```

## 提交流程

### 创建功能分支

```bash
git checkout -b feature/my-feature
# 或
git checkout -b bugfix/my-bugfix
git checkout -b docs/my-docs
```

分支命名规范：
- `feature/` - 新功能
- `bugfix/` - 错误修复
- `docs/` - 文档更新
- `test/` - 测试相关
- `refactor/` - 代码重构

### 提交代码

```bash
# 添加更改
git add gm/ tests/ docs/

# 提交（使用有意义的消息）
git commit -m "feat: implement new feature

详细说明（如需要）

- 改动点 1
- 改动点 2

Fix #123
"
```

提交消息格式（Conventional Commits）：

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：
- `feat` - 新功能
- `fix` - 错误修复
- `docs` - 文档
- `style` - 代码风格（不改变逻辑）
- `refactor` - 代码重构
- `perf` - 性能优化
- `test` - 测试
- `chore` - 构建、工具等

示例：
```
feat(worktree): add concurrent operations support

Implement concurrent creation and deletion of multiple worktrees
to improve performance for large-scale operations.

- Add ThreadPoolExecutor for parallel operations
- Add progress reporting for batch operations
- Update WorktreeManager API

Fix #45, Closes #67
```

### 推送更改

```bash
# 首次推送
git push -u origin feature/my-feature

# 后续推送
git push
```

## Pull Request 流程

### 创建 PR

1. 在 GitHub 上创建 Pull Request
2. 填写 PR 模板：

```markdown
## 描述
简要说明这个 PR 的目的。

## 类型
- [ ] 新功能
- [ ] 错误修复
- [ ] 文档更新
- [ ] 代码重构

## 关闭的 Issue
修复 #123

## 更改清单
- [ ] 代码风格检查通过
- [ ] 添加了测试
- [ ] 文档已更新
- [ ] 所有测试通过

## 截图（如需要）
添加截图或日志输出。
```

### PR 检查

PR 必须满足：

1. **代码风格**
```bash
black --check gm tests
ruff check gm tests
```

2. **类型检查**
```bash
mypy gm
```

3. **测试覆盖**
```bash
pytest tests/ -v --cov=gm
```

4. **文档更新**
   - 更新相关文档
   - 添加 API 文档
   - 更新 CHANGELOG

### PR 审查

- 至少需要 1 个维护者的批准
- 所有 CI 检查必须通过
- 所有对话必须解决

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定文件
pytest tests/core/test_git_client.py -v

# 运行特定测试
pytest tests/core/test_git_client.py::TestGitClientInit::test_init_with_default_path -v

# 运行并显示覆盖率
pytest tests/ --cov=gm --cov-report=html
```

### 编写测试

```python
"""测试文件模板"""

import pytest
from unittest.mock import Mock, patch

from gm.core.git_client import GitClient
from gm.core.exceptions import GitCommandError


class TestGitClientInit:
    """测试 GitClient 初始化"""

    def test_init_with_default_path(self):
        """测试使用默认路径初始化"""
        client = GitClient()
        assert client.repo_path == Path.cwd()

    def test_init_with_custom_path(self):
        """测试使用自定义路径初始化"""
        custom_path = Path("/custom/path")
        client = GitClient(custom_path)
        assert client.repo_path == custom_path


class TestRunCommand:
    """测试 run_command 方法"""

    @patch("subprocess.run")
    def test_successful_command(self, mock_run):
        """测试成功执行命令"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        client = GitClient()
        result = client.run_command(["git", "status"])

        assert result == "output"
        mock_run.assert_called_once()

    def test_failed_command(self):
        """测试命令失败时抛出异常"""
        client = GitClient()

        with pytest.raises(GitCommandError):
            client.run_command(
                ["git", "checkout", "nonexistent"],
                check=True,
            )
```

### 测试最佳实践

1. **每个测试一个概念**
```python
def test_get_branches_returns_list(self):
    """测试返回列表"""
    branches = client.get_branches()
    assert isinstance(branches, list)
```

2. **使用有意义的测试名**
```python
# 好
def test_get_branches_returns_empty_list_for_new_repo(self):
    pass

# 不好
def test_branches(self):
    pass
```

3. **使用 Fixture 共享设置**
```python
@pytest.fixture
def git_client(tmp_path):
    return GitClient(tmp_path)

def test_something(self, git_client):
    assert git_client is not None
```

4. **Mock 外部依赖**
```python
@patch("subprocess.run")
def test_git_command(self, mock_run):
    mock_run.return_value = Mock(returncode=0, stdout="data")
    # 测试代码
```

## 文档指南

### 更新文档

1. **快速开始**：[QUICK_START.md](QUICK_START.md)
2. **用户手册**：[USER_MANUAL.md](USER_MANUAL.md)
3. **API 参考**：[API_REFERENCE.md](API_REFERENCE.md)
4. **配置指南**：[CONFIGURATION.md](CONFIGURATION.md)
5. **架构设计**：[ARCHITECTURE.md](ARCHITECTURE.md)

### 文档标准

- 使用 Markdown 格式
- 包含清晰的标题和目录
- 添加代码示例
- 提供明确的说明
- 检查拼写和语法

### 示例文档

```markdown
# 功能名称

一句话描述。

## 概述

详细说明（2-3 段）。

## 使用方法

### 基本用法

```bash
命令示例
```

### 高级用法

```bash
命令示例
```

## 示例

具体的使用示例。

## 相关

- [链接1](link1)
- [链接2](link2)
```

## 开发工作流

### 典型工作流

```bash
# 1. 创建分支
git checkout -b feature/my-feature

# 2. 进行更改和提交
git add .
git commit -m "feat: implement feature"

# 3. 运行测试
pytest tests/ -v

# 4. 代码检查
black gm tests
ruff check gm tests
mypy gm

# 5. 推送并创建 PR
git push -u origin feature/my-feature

# 6. 更新 PR（如需要）
git commit -m "fix: address review comments"
git push

# 7. 合并后清理
git checkout main
git pull
git branch -d feature/my-feature
```

## 获得帮助

- 查看 [Architecture](ARCHITECTURE.md) 了解系统设计
- 查看 [API Reference](API_REFERENCE.md) 了解 API
- 查看现有的 Issue 和 PR
- 提交 Discussion 进行讨论

## 行为准则

- 尊重其他贡献者
- 接受建设性批评
- 专注于对项目最好的结果
- 在评论中保持专业

## 许可证

通过贡献，您同意您的代码在 MIT 许可证下发布。

感谢您的贡献！
