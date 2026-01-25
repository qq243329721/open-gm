# GM 发布指南

版本管理和发布流程。

## 目录

1. [版本管理](#版本管理)
2. [发布流程](#发布流程)
3. [变更日志](#变更日志)
4. [发布检查清单](#发布检查清单)

## 版本管理

### 版本号格式

GM 使用语义版本控制（Semantic Versioning）：

```
MAJOR.MINOR.PATCH

例: 1.0.0
```

- **MAJOR**: 主要版本，包含不兼容的 API 更改
- **MINOR**: 次要版本，包含新功能，向后兼容
- **PATCH**: 补丁版本，包含错误修复

### 版本更新规则

| 更改类型 | 版本号 | 示例 |
|---------|--------|------|
| 新功能 | MINOR | 1.0.0 → 1.1.0 |
| 错误修复 | PATCH | 1.1.0 → 1.1.1 |
| 不兼容更改 | MAJOR | 1.1.0 → 2.0.0 |

### 当前版本

当前版本在 `pyproject.toml` 中定义：

```toml
[project]
version = "0.1.0"
```

## 发布流程

### 1. 准备发布

#### 更新版本号

编辑 `pyproject.toml`：

```toml
[project]
version = "0.2.0"
```

#### 更新变更日志

编辑 `CHANGELOG.md`（如存在）。

#### 运行测试

```bash
pytest tests/ -v --cov=gm
```

确保所有测试通过。

### 2. 创建发布分支

```bash
git checkout main
git pull origin main
git checkout -b release/v0.2.0
```

### 3. 提交更改

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to 0.2.0"
```

### 4. 创建 Pull Request

将发布分支推送到 GitHub 并创建 PR：

```bash
git push -u origin release/v0.2.0
```

在 GitHub 上创建 PR，等待审批。

### 5. 合并到 main

PR 被批准后，合并到 main 分支：

```bash
git checkout main
git pull origin main
```

### 6. 创建标签

```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

### 7. 创建发布

在 GitHub 上创建发布：

1. 转到 Releases 页面
2. 点击 "Create a new release"
3. 选择标签 v0.2.0
4. 填写发布标题和说明
5. 发布

### 8. 发布到 PyPI

#### 构建包

```bash
pip install build twine
python -m build
```

#### 上传到 PyPI

```bash
twine upload dist/*
```

或者上传到 TestPyPI 进行测试：

```bash
twine upload --repository testpypi dist/*
```

### 9. 验证发布

```bash
# 从 PyPI 安装
pip install --upgrade gm

# 验证版本
gm --version
```

## 变更日志

### 格式

变更日志应记录每个版本的所有显著更改。

#### 示例：CHANGELOG.md

```markdown
# 变更日志

所有对此项目的显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)，
该项目遵循 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)。

## [0.2.0] - 2024-01-25

### 新增
- 支持并发 worktree 操作
- 添加缓存管理系统
- 新的符号链接策略配置

### 修改
- 改进错误消息
- 优化性能

### 修复
- 修复 Windows 上的路径问题
- 修复配置加载错误

### 安全
- 更新依赖版本

## [0.1.0] - 2024-01-01

### 新增
- 初始版本
- 基本的 worktree 管理功能
- 命令行界面
```

### 分类

变更日志应该按以下分类组织：

- **新增** (Added) - 新功能
- **修改** (Changed) - 现有功能的更改
- **修复** (Fixed) - 错误修复
- **删除** (Removed) - 删除的功能
- **安全** (Security) - 安全问题修复
- **已弃用** (Deprecated) - 即将删除的功能

## 发布检查清单

在发布新版本前，检查以下项目：

### 代码检查
- [ ] 所有测试通过
- [ ] 代码风格检查通过 (black, ruff)
- [ ] 类型检查通过 (mypy)
- [ ] 代码覆盖率达到要求 (>80%)

### 文档更新
- [ ] 更新 README.md（如需要）
- [ ] 更新 CHANGELOG.md
- [ ] 更新 API 文档
- [ ] 检查所有文档链接
- [ ] 检查拼写和语法

### 版本和元数据
- [ ] 更新 pyproject.toml 中的版本号
- [ ] 更新 gm/__init__.py 中的 __version__（如存在）
- [ ] 验证所有依赖版本正确

### 构建和发布
- [ ] 构建包成功：`python -m build`
- [ ] 包内容检查：`twine check dist/*`
- [ ] TestPyPI 上传成功（可选）
- [ ] 从 PyPI 安装和运行成功

### 发布
- [ ] 创建 git 标签：`git tag -a v*.*.* -m "..."`
- [ ] 推送标签：`git push origin v*.*.*`
- [ ] 在 GitHub 上创建发布
- [ ] 最终验证安装

## 发布后

### 监控

- 监控 Issue 和错误报告
- 响应用户反馈
- 准备补丁版本（如需要）

### 宣传

- 发布博客文章或文章
- 在社交媒体上分享
- 通知相关社区

## 补丁版本

对于紧急的错误修复：

```bash
# 创建补丁分支
git checkout -b hotfix/v0.2.1

# 修复错误并提交
git commit -m "fix: critical issue"

# 更新版本号和变更日志
# ... 更新 pyproject.toml 和 CHANGELOG.md ...

# 合并和发布（与标准流程相同）
```

## CI/CD 集成

### GitHub Actions 示例

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

## 版本号决策树

```
发生了什么变化？
├─ 不兼容的 API 更改? → MAJOR
├─ 新功能? → MINOR
├─ 错误修复? → PATCH
└─ 仅文档/配置? → PATCH
```

## 常见问题

### Q: 如何回滚发布？

A: 您不能撤销 PyPI 上的发布，但可以：
1. 删除本地标签：`git tag -d v0.2.0`
2. 删除远程标签：`git push origin :refs/tags/v0.2.0`
3. 发布新的补丁版本：v0.2.1

### Q: 如何处理 API 不兼容性？

A: 为了最小化中断：
1. 先发布新的 API（保留旧的）
2. 标记旧 API 为已弃用
3. 在主要版本中删除旧 API

### Q: 是否应该发布测试版本？

A: 对于主要版本，建议：
1. 发布 alpha/beta 版本：v1.0.0-alpha.1
2. 获得反馈
3. 发布最终版本：v1.0.0

## 相关资源

- [语义版本化 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [PEP 440 版本识别和依赖规范](https://www.python.org/dev/peps/pep-0440/)
