# GM 目录结构设计问题分析

## 当前实现（不正确）❌

```
项目根目录/
├── .gm/                          # 元数据目录
│   ├── .git/                     # Git worktree 共享目录
│   ├── feature/
│   │   ├── user-login/           # worktree 1 (WRONG!)
│   │   └── payment/              # worktree 2 (WRONG!)
│   ├── bugfix/
│   │   └── critical/             # worktree 3 (WRONG!)
│   └── .gm.yaml                  # 配置（这里也不对）
├── src/                          # 共享源代码
└── package.json
```

## 你建议的结构（正确）✅

```
项目根目录/
├── .gm/                          # 元数据和控制目录
│   ├── .git/                     # Git worktree 共享目录
│   └── （其他内部文件）
├── .gm.yaml                      # 项目配置（在根目录！）
├── feature/
│   ├── user-login/               # worktree 1 (CORRECT!)
│   └── payment/                  # worktree 2 (CORRECT!)
├── bugfix/
│   └── critical/                 # worktree 3 (CORRECT!)
├── src/                          # 共享源代码
└── package.json
```

## 为什么你的方案更好？

### 原因 1: 符合 Git Worktree 原始设计
```
git worktree add ../feature/user-login feature
# worktree 应该在项目同级，而不是嵌套在 .gm 下
```

### 原因 2: 符合常见约定
- `.gitignore` → 根目录
- `.env` → 根目录
- `.github/` → 根目录
- **`.gm.yaml` → 根目录** （而不是 `.gm/` 下）

配置文件应该在最容易找到的地方（项目根目录），而不是隐藏在控制目录下。

### 原因 3: 更灵活的目录结构
用户可以组织 worktree：
```
项目根目录/
├── .gm/
├── features/
│   ├── user-login/
│   └── payment/
├── bugfixes/
│   ├── critical/
│   └── performance/
├── releases/
│   ├── v1.0/
│   └── v1.1/
```

### 原因 4: 避免混淆
- worktree 不是 `.gm` 的"子项"，而是独立的工作目录
- `.gm` 只是配置和元数据的存储位置

## 当前代码中的问题

### 问题 1: worktree_path 计算错误
**文件**: `gm/core/worktree_manager.py` 第 94 行
```python
# 当前（错误）
worktree_path = self.project_path / base_path / dir_name
# 这会导致: .gm/feature-user-login/

# 应该改为
worktree_path = self.project_path / branch_to_dir(branch)
# 这样会导致: feature/user-login/ (在项目根目录下)
```

### 问题 2: base_path 的语义不对
```yaml
worktree:
  base_path: .gm  # 这里意味着 worktree 放在 .gm 下，这是错的

# 应该改为
worktree:
  base_path: .    # 或者移除这个配置，默认就在项目根目录
```

### 问题 3: 文档中的示例错误
多个文档示例显示 worktree 在 `.gm` 下，这需要更正。

## 修复方案

### 修复 1: 更新 WorktreeManager

```python
# 当前
worktree_path = self.project_path / base_path / dir_name
# 新建：
# 获取分支对应的目录名（处理特殊字符）
worktree_dir = self.branch_mapper.map_branch_to_dir(branch)
# 根据分支的命名空间创建嵌套目录（可选）
worktree_path = self.project_path / worktree_dir
# 如果想要分组（features/bugfixes 等），可以在分支名中使用约定
```

### 修复 2: 更新配置结构

```yaml
# 新的 .gm.yaml
worktree:
  # 移除 base_path 或改为根目录
  naming_pattern: "{branch}"
  auto_cleanup: true
  # 可选：指定命名前缀
  # namespace_mapping:
  #   "feature/*": "features/"
  #   "bugfix/*": "bugfixes/"
  #   "release/*": "releases/"

display:
  colors: true
  default_verbose: false

shared_files:
  - .env
  - .gitignore
  - README.md

symlinks:
  strategy: auto

branch_mapping:
  # 自定义分支名映射（处理特殊字符）
```

### 修复 3: 更新 .gm.yaml 位置

```
项目根目录/
├── .gm/                          # 只存放:
│   ├── .git/                     # - 共享的 git 目录
│   ├── .gm.yaml                  # - 项目配置（或移到根目录）
│   └── .gm.log                   # - 日志文件
├── feature/
│   └── user-login/
```

或者更好的方案：

```
项目根目录/
├── .gm/                          # 只存放元数据:
│   ├── .git/                     # - 共享的 git 目录
│   └── .gm.log                   # - 日志文件
├── .gm.yaml                      # 配置在根目录（更易见）
├── feature/
│   └── user-login/
```

## 影响范围

需要修改以下文件：
- [ ] `gm/core/worktree_manager.py` - 修复 worktree_path 计算
- [ ] `gm/core/config_manager.py` - 更新 base_path 默认值和说明
- [ ] `docs/CONFIGURATION.md` - 更新配置文档
- [ ] `docs/ARCHITECTURE.md` - 更新架构说明
- [ ] `docs/QUICK_START.md` - 更新示例
- [ ] `.gm.yaml.example` - 更新配置示例
- [ ] 所有相关测试 - 更新目录结构期望值

## 实现步骤

1. **第一步**: 明确最终的目录结构设计
   - [ ] 确认 worktree 在项目根目录（同级）
   - [ ] 确认 `.gm` 只包含元数据
   - [ ] 决定 `.gm.yaml` 的位置（根目录还是 `.gm/` 下）

2. **第二步**: 更新核心代码
   - [ ] 修改 `worktree_manager.py`
   - [ ] 更新配置管理器
   - [ ] 修改路径计算逻辑

3. **第三步**: 更新文档和示例
   - [ ] 修复所有文档中的目录结构示例
   - [ ] 更新配置示例
   - [ ] 更新架构说明

4. **第四步**: 测试和验证
   - [ ] 运行现有测试（会失败，需要更新期望值）
   - [ ] 手工测试完整工作流
   - [ ] 验证 worktree 创建在正确位置

## 建议

你的建议非常正确！这个修改虽然影响范围大，但是：
- ✅ 符合 Git 原始设计
- ✅ 更符合直觉
- ✅ 更灵活可扩展
- ✅ 更清晰的逻辑

建议：**现在就修复这个问题，因为项目还在 v0.1.0，改动成本最低。**

