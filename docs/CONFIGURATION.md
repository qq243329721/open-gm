# GM 配置指南

.gm.yaml 配置文件的完整参考。

## 目录

1. [配置文件位置](#配置文件位置)
2. [默认配置](#默认配置)
3. [配置选项](#配置选项)
4. [示例配置](#示例配置)
5. [验证配置](#验证配置)

## 配置文件位置

配置文件位置：`<项目根目录>/.gm.yaml`

示例：
```
my-project/
├── .gm.yaml          # 配置文件
├── .gm/              # Worktree 基础目录
├── src/
└── package.json
```

## 默认配置

首次初始化时，GM 会创建默认配置：

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

## 配置选项

### worktree 配置

#### base_path

Worktree 基础目录的位置。

**类型**: string
**默认值**: `.gm`
**示例**:
```yaml
worktree:
  base_path: .gm
  # 或自定义位置
  # base_path: ./worktrees
  # base_path: /var/worktrees
```

#### naming_pattern

Worktree 命名模式。支持的占位符：
- `{branch}` - 分支名称
- `{branch_name}` - 简化的分支名称

**类型**: string
**默认值**: `{branch}`
**示例**:
```yaml
worktree:
  naming_pattern: "{branch}"
  # 结果: feature/new-ui -> feature/new-ui

  # 其他模式
  # naming_pattern: "wt_{branch}"
  # 结果: feature/new-ui -> wt_feature/new-ui
```

#### auto_cleanup

是否在删除 worktree 时自动清理相关资源。

**类型**: boolean
**默认值**: `true`
**示例**:
```yaml
worktree:
  auto_cleanup: true
```

### display 配置

#### colors

在列表和状态输出中使用颜色。

**类型**: boolean
**默认值**: `true`
**示例**:
```yaml
display:
  colors: true
```

#### default_verbose

列表命令的默认详细级别。

**类型**: boolean
**默认值**: `false`
**示例**:
```yaml
display:
  default_verbose: false
  # false: 简洁模式
  # true: 详细模式（等同于 gm list -v）
```

### shared_files

共享文件列表。这些文件将在 worktree 中通过符号链接指向项目根目录的版本。

**类型**: list of strings
**默认值**: `[.env, .gitignore, README.md]`
**示例**:
```yaml
shared_files:
  - .env
  - .gitignore
  - README.md
  - package-lock.json
  - yarn.lock
```

### symlinks 配置

#### strategy

符号链接创建策略。

**类型**: string
**可选值**:
- `auto` - 自动创建符号链接
- `manual` - 手动管理符号链接
- `none` - 不创建符号链接

**默认值**: `auto`
**示例**:
```yaml
symlinks:
  strategy: auto
```

### branch_mapping

分支名称映射。用于在 worktree 名称和实际分支名称之间建立关系。

**类型**: object/dict
**默认值**: `{}`
**示例**:
```yaml
branch_mapping:
  feature: features
  bugfix: fixes
  release: releases
  # 用法: gm add bugfix/issue-123
  # 会创建: fixes/issue-123 分支
```

## 示例配置

### 简单配置

最小化的配置文件：

```yaml
worktree:
  base_path: .gm

shared_files:
  - .env
  - .gitignore
```

### 标准配置

适用于大多数项目的配置：

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
  - .env.local
  - .gitignore
  - README.md
  - package-lock.json
  - yarn.lock

symlinks:
  strategy: auto

branch_mapping: {}
```

### 高级配置

包含分支映射和自定义设置：

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
  - .env.local
  - .gitignore
  - README.md
  - package-lock.json
  - Makefile
  - .eslintrc.json
  - tsconfig.json

symlinks:
  strategy: auto

branch_mapping:
  feature: features
  bugfix: fixes
  release: releases
  hotfix: hotfixes
  docs: documentation
```

### 企业级配置

适用于大型团队项目：

```yaml
worktree:
  base_path: .gm
  naming_pattern: "wt_{branch}"
  auto_cleanup: true

display:
  colors: true
  default_verbose: true

shared_files:
  - .env
  - .env.local
  - .env.*.local
  - .gitignore
  - README.md
  - CONTRIBUTING.md
  - package-lock.json
  - yarn.lock
  - Makefile
  - docker-compose.yml
  - .eslintrc.json
  - .prettierrc.json
  - tsconfig.json
  - babel.config.js

symlinks:
  strategy: auto

branch_mapping:
  feature: features
  bugfix: fixes
  release: releases
  hotfix: hotfixes
  chore: maintenance
  docs: documentation
  test: testing
```

## 验证配置

### 手动验证

```bash
# 检查配置文件是否存在
cat .gm.yaml

# 验证 YAML 格式
python -c "import yaml; yaml.safe_load(open('.gm.yaml'))"
```

### 通过 GM 验证

```bash
# GM 会在初始化或操作时验证配置
gm init

# 列出时会验证配置
gm list
```

## 常见配置场景

### 场景 1：Node.js 项目

```yaml
shared_files:
  - .env
  - .env.local
  - .gitignore
  - README.md
  - package-lock.json
  - .eslintrc.json
  - .prettierrc.json
  - tsconfig.json
```

### 场景 2：Python 项目

```yaml
shared_files:
  - .env
  - .env.local
  - .gitignore
  - README.md
  - requirements.txt
  - setup.py
  - pyproject.toml
```

### 场景 3：Docker 项目

```yaml
shared_files:
  - .env
  - .env.local
  - .gitignore
  - docker-compose.yml
  - Dockerfile
  - .dockerignore
```

### 场景 4：多语言项目

```yaml
shared_files:
  - .env
  - .env.local
  - .gitignore
  - README.md
  - Makefile
  - docker-compose.yml
  - package-lock.json
  - requirements.txt
  - Gemfile.lock
```

## 配置继承

GM 支持配置继承：

1. 全局配置（用户级）
2. 项目配置（`.gm.yaml`）

项目配置会覆盖全局配置的对应设置。

## 验证失败

如果配置无法验证，GM 会显示错误信息：

```
Error: Configuration validation failed
  - worktree.base_path: Value must be a non-empty string
  - display.colors: Value must be a boolean
```

## 重置配置

要重置为默认配置：

```bash
# 删除 .gm.yaml
rm .gm.yaml

# 重新初始化
gm init
```

## 配置最佳实践

1. **提交配置文件** - 将 `.gm.yaml` 提交到仓库以共享团队配置
2. **使用相对路径** - `base_path` 建议使用相对路径
3. **明确分支映射** - 为团队约定的分支前缀配置映射
4. **添加共享文件** - 列出所有需要在 worktree 间共享的文件
5. **定期审查** - 定期检查和更新配置

## 配置文件大小和性能

- 配置文件通常 < 1KB
- GM 会缓存已加载的配置
- 对性能几乎没有影响

## 更多资源

- [快速开始](QUICK_START.md)
- [用户手册](USER_MANUAL.md)
- [API 参考](API_REFERENCE.md)
- [贡献指南](CONTRIBUTING.md)
