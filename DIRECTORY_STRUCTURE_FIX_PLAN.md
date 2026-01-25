# 目录结构修复计划

## 问题概述

**当前（错误）:**
```
项目根目录/
├── .gm/
│   ├── feature-user-login/     ❌ worktree 嵌套在 .gm 下（错误！）
│   ├── feature-payment/
│   ├── bugfix-critical/
│   └── .gm.yaml
```

**应该改为（正确）:**
```
项目根目录/
├── .gm/                         ✅ 只存放元数据
│   ├── .git/                       （共享 git 目录）
│   └── 日志/状态文件
├── .gm.yaml                      ✅ 配置在根目录
├── feature-user-login/          ✅ worktree 在项目根目录
├── feature-payment/
├── bugfix-critical/
```

---

## 修复步骤

### 第 1 步：修改 WorktreeManager（核心路径计算）

**文件：** `gm/core/worktree_manager.py`

**改动点：**

1. 移除 `base_path` 的使用
2. 更新 worktree 路径计算逻辑
3. Worktree 直接创建在项目根目录

```python
# 当前（错误）
base_path = self.config_manager.get("worktree.base_path", ".gm")
worktree_path = self.project_path / base_path / dir_name

# 修改为（正确）
# worktree 直接在项目根目录下，使用分支名的目录表示
dir_name = self.branch_mapper.map_branch_to_dir(branch)
worktree_path = self.project_path / dir_name
```

**需要修改的方法：**
- `add_worktree()` - 第 94 行
- `delete_worktree()` - 第 177 行
- `get_worktree_list()` - 第 272 行

---

### 第 2 步：修改 ConfigManager（配置默认值）

**文件：** `gm/core/config_manager.py`

**改动点：**

1. 移除或修改 `base_path` 的默认值
2. 更新配置验证逻辑
3. 更新文档说明

```yaml
# 当前（配置中的 base_path）
worktree:
  base_path: .gm              # ❌ 不再使用

# 修改为（移除 base_path）
worktree:
  # base_path 已移除，worktree 总是在项目根目录
  naming_pattern: "{branch}"  # 用于目录命名
  auto_cleanup: true
```

**需要修改的地方：**
- 第 36 行：`get_default_config()` 的 `base_path` 默认值
- 第 161-162 行：验证逻辑中的 `base_path` 检查

---

### 第 3 步：更新 .gm.yaml.example

**文件：** `.gm.yaml.example`

```yaml
# 修改前
worktree:
  base_path: .gm              # ❌
  naming_pattern: "{branch}"
  auto_cleanup: true

# 修改后
worktree:
  naming_pattern: "{branch}"  # ✅ base_path 已移除
  auto_cleanup: true
```

---

### 第 4 步：更新配置文档

**文件：** `docs/CONFIGURATION.md`

需要说明：
- Worktree 现在直接在项目根目录创建
- `base_path` 配置已移除（或改为只读参考）
- 分支名映射用于确定目录名

---

### 第 5 步：更新架构文档

**文件：** `docs/ARCHITECTURE.md`

需要更新目录结构示例。

---

### 第 6 步：更新测试期望值

**受影响的测试文件：**
- `tests/core/test_worktree_manager.py` - 更新路径期望值
- `tests/cli/commands/test_add.py` - 验证 worktree 位置
- `tests/cli/commands/test_del.py` - 验证删除逻辑
- `tests/cli/commands/test_list.py` - 更新路径搜索
- `tests/cli/commands/test_status.py` - 更新路径检查
- `tests/core/test_config_manager.py` - 移除 base_path 测试

---

### 第 7 步：更新示例脚本

**文件：** `examples/basic_workflow.sh`、`examples/advanced_workflow.sh`

更新目录结构说明。

---

## 影响范围分析

### 代码影响
```
高影响:
├── gm/core/worktree_manager.py ⭐⭐⭐ (核心修改)
├── gm/core/config_manager.py ⭐⭐ (配置修改)
└── tests/core/test_worktree_manager.py ⭐⭐⭐ (测试期望值)

中影响:
├── tests/cli/commands/*.py ⭐⭐ (6 个测试文件)
├── .gm.yaml.example ⭐ (配置示例)
└── gm/core/config_validator.py (可选，验证逻辑更新)

低影响:
├── 文档更新 (不影响代码)
└── 示例脚本 (不影响代码)
```

### 测试影响
- 预期有 20-30 个测试会因为路径期望值不同而失败
- 这些都是正常的，改正期望值后会通过

---

## 修复顺序

1. ✅ 修改 `WorktreeManager` (最关键)
2. ✅ 修改 `ConfigManager` (配置相关)
3. ✅ 更新 `.gm.yaml.example`
4. ✅ 更新测试期望值
5. ✅ 运行测试验证
6. ✅ 更新文档
7. ✅ Git 提交

---

## 预期结果

修复后：
- ✅ Worktree 直接创建在项目根目录
- ✅ 符合 Git 原始 worktree 设计
- ✅ `.gm.yaml` 在项目根目录
- ✅ 配置更简单清晰
- ✅ 所有测试通过

---

## 开始修复 ✅

准备好开始第一步了吗？

