# GM - 安装指南

**项目状态**: v0.1.0 开发版本
**发布状态**: 未发布到 PyPI（本地开发项目）

---

## 📋 安装方式说明

### 当前可用的安装方式

#### ✅ 方式 1: 开发模式安装 (推荐用于开发)

在项目根目录执行：

```bash
# 进入项目目录
cd D:\workspace_project\gm-claude

# 安装项目为可编辑模式（开发模式）
pip install -e .

# 如果需要开发工具（pytest, mypy, black等）
pip install -e ".[dev]"
```

**优点:**
- ✅ 可以立即使用 `gm` 命令
- ✅ 代码改动会立即生效（不需要重新安装）
- ✅ 适合开发人员

**安装后验证:**
```bash
gm --help          # 应该显示帮助信息
gm --version       # 应该显示 v0.1.0
```

#### ❌ 方式 2: `pip install gm` (暂不可用)

**为什么不可用?**
- ❌ 项目还未发布到 PyPI 官方仓库
- ❌ 暂时没有 wheel 分发包
- ❌ 项目仍在开发阶段

**如何才能支持 `pip install gm`?**

需要完成以下步骤：

1. **准备发布**
   ```bash
   # 检查项目配置
   python -m build --sdist --wheel
   # 生成 dist/ 目录中的发布包
   ```

2. **上传到 PyPI**
   ```bash
   # 安装 twine
   pip install twine

   # 上传到 PyPI (需要账户)
   twine upload dist/*
   ```

3. **之后用户就可以**
   ```bash
   pip install gm
   ```

---

## 🔧 不同场景的安装指南

### 场景 1: 我是最终用户（想使用 GM 工具）

**当前（v0.1.0）:**
```bash
# 本地安装（需要项目源代码）
cd /path/to/gm-claude
pip install -e .

# 验证安装
gm init /path/to/your/project
gm --help
```

**将来（发布到 PyPI 后）:**
```bash
# 直接安装，无需项目源代码
pip install gm

# 立即使用
gm init /path/to/your/project
```

### 场景 2: 我是开发者（想修改或贡献代码）

**安装开发环境:**
```bash
# 1. 克隆或进入项目目录
cd D:\workspace_project\gm-claude

# 2. 安装开发依赖
pip install -e ".[dev]"

# 3. 运行测试
pytest

# 4. 运行代码检查
black gm tests
ruff check gm tests
mypy gm
```

### 场景 3: 我想从源代码构建

**手动构建和安装:**
```bash
# 1. 安装构建工具
pip install build twine

# 2. 构建项目
cd D:\workspace_project\gm-claude
python -m build

# 3. 查看生成的包
ls dist/

# 4. 本地安装生成的包（可选）
pip install dist/gm-0.1.0-py3-none-any.whl
```

---

## 📦 发布 GM 到 PyPI 的完整步骤

### 前置条件
- 有 PyPI 账户 (https://pypi.org/account/register/)
- 或者使用 TestPyPI 测试 (https://test.pypi.org/account/register/)

### 步骤 1: 准备项目

```bash
# 验证 pyproject.toml 配置正确
cat pyproject.toml | grep -A 5 "\[project\]"

# 检查所需字段：
# ✓ name = "gm"
# ✓ version = "0.1.0"
# ✓ description = "..."
# ✓ readme = "README.md"
# ✓ license = {text = "MIT"}
```

### 步骤 2: 更新版本号和 CHANGELOG

```bash
# 更新 pyproject.toml 中的版本
# version = "0.2.0"  # 使用语义化版本

# 创建或更新 CHANGELOG.md
# 记录此版本的更改
```

### 步骤 3: 构建发布包

```bash
# 安装构建工具
pip install build twine

# 清理旧的构建
rm -rf build/ dist/ *.egg-info

# 构建 wheel 和 sdist
python -m build

# 验证包内容
twine check dist/*
```

### 步骤 4: 发布到测试环境（推荐首次）

```bash
# 发布到 TestPyPI
twine upload --repository testpypi dist/*

# 测试安装
pip install -i https://test.pypi.org/simple/ gm==0.1.0

# 验证功能
gm --version
gm --help
```

### 步骤 5: 发布到正式 PyPI

```bash
# 发布到正式 PyPI
twine upload dist/*

# 等待几分钟后测试
pip install gm

# 验证
gm --version
```

### 步骤 6: 发布 GitHub Release

```bash
# 创建 git 标签
git tag v0.1.0

# 推送标签
git push origin v0.1.0

# 在 GitHub 上创建 Release
# 1. 进入 https://github.com/user/gm-claude/releases
# 2. 点击 "Draft a new release"
# 3. 选择标签 v0.1.0
# 4. 填写 Release Notes
# 5. 上传 dist/ 中的文件
# 6. 发布
```

---

## 🔐 安全性注意事项

### PyPI 凭证管理

**使用 .pypirc 文件 (不推荐)**
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5...  # PyPI token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5...  # TestPyPI token
```

**使用环境变量 (推荐)**
```bash
# Linux/macOS
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEIcHlwaS5...

# Windows PowerShell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-AgEIcHlwaS5..."

# 使用 twine
twine upload dist/*
```

**最佳实践:**
- ✅ 使用 PyPI API Token (不是用户密码)
- ✅ 使用环境变量或密钥管理工具
- ✅ 永远不要提交凭证到 Git
- ✅ 定期轮换 token

---

## 📊 pyproject.toml 核心配置

```toml
[project]
name = "gm"                    # PyPI 上的包名
version = "0.1.0"             # 语义化版本
description = "Git Worktree Manager"
readme = "README.md"          # 包描述来源
requires-python = ">=3.9"     # Python 版本要求
authors = [
    {name = "GM Team", email = "dev@gm-tool.io"},
]
license = {text = "MIT"}      # 许可证

dependencies = [              # 运行时依赖
    "click>=8.0.0",
    "pyyaml>=6.0",
    "structlog>=22.0.0",
]

[project.optional-dependencies]
dev = [                        # 开发依赖
    "pytest>=7.0.0",
    "pytest-mock>=3.6.0",
    "pytest-cov>=3.0.0",
    "mypy>=0.950",
    "black>=22.0.0",
    "ruff>=0.0.200",
]

[project.scripts]
gm = "gm.cli.main:cli"        # 命令行入口点
```

---

## 🚀 发布时间表

### v0.1.0 (当前版本，已准备好)
- ✅ 代码完成
- ✅ 测试通过
- ✅ 文档完整
- ✅ 配置就绪
- ⏳ 等待发布

**何时发布:**
- 建议: 得到初期用户反馈后发布
- 或: 经过额外的手工测试后发布

### 发布前检查清单

- [ ] 所有单元测试通过
- [ ] 代码检查无警告 (black, ruff, mypy)
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新
- [ ] 在 TestPyPI 上测试成功
- [ ] 在多个 Python 版本上测试 (3.9, 3.10, 3.11, 3.12)
- [ ] README 和例子验证无误
- [ ] 许可证文件包含在分发包中

---

## ❓ 常见问题

### Q: 现在能 `pip install gm` 吗?
**A:** 不能。项目还未发布到 PyPI。目前只能 `pip install -e .` 本地安装。

### Q: 什么时候能发布到 PyPI?
**A:** 项目已经完全准备好了！配置、代码、测试都完成了。随时可以发布。

### Q: 如何为项目做贡献?
**A:**
1. Clone 项目
2. `pip install -e ".[dev]"`
3. 做出改动
4. 运行测试 `pytest`
5. 提交 Pull Request

### Q: 支持哪些 Python 版本?
**A:** 目前支持 Python 3.9+。测试环境是 3.7，但配置要求 3.9+。

### Q: 如何卸载?
**A:**
```bash
pip uninstall gm
```

---

## 📚 更多资源

- [PyPI 官方文档](https://packaging.python.org/tutorials/packaging-projects/)
- [Setuptools 文档](https://setuptools.pypa.io/)
- [Python Packaging Guide](https://python-packaging-guide.readthedocs.io/)
- [Twine 文档](https://twine.readthedocs.io/)

---

**总结**: GM 项目已完全准备好发布！当前只能本地开发模式安装，发布到 PyPI 后用户就能直接 `pip install gm`。

