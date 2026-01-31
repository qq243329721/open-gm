"""配置管理器实现

提供 gm.yaml 配置文件的加载、验证和保存功能，实现 IConfigManager 接口。"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from gm.core.exceptions import ConfigIOError, ConfigParseError, ConfigValidationError
from gm.core.logger import get_logger
from gm.core.data_structures import GMConfig
from gm.core.interfaces.config import IConfigManager

logger = get_logger("config_manager")


class ConfigManager(IConfigManager):
    """配置管理器实现"""

    def __init__(self, project_root: Path):
        """初始化配置管理器"""
        self.project_root = project_root.resolve()
        # 使用 gm.yaml 作为项目级配置文件，以与你要求统一
        self.config_file = project_root / 'gm.yaml'
        self._config: Optional[GMConfig] = None
        logger.info("ConfigManager initialized", project_root=str(self.project_root))
    
    @property
    def config_path(self) -> Path:
        """获取配置路径"""
        return self.config_file

    def load_config(self) -> GMConfig:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        if not self.config_file.exists():
            self._config = GMConfig()
            return self._config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            self._config = self._parse_config(config_data)
            return self._config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise ConfigIOError(f"Failed to load config: {e}")

    def save_config(self, config: GMConfig) -> None:
        """保存配置"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(self._generate_yaml_with_comments(config))
            self._config = config
        except Exception as e:
            raise ConfigIOError(f"Failed to save config: {e}")

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置节"""
        config = self.load_config()
        if hasattr(config, section):
            return getattr(config, section).__dict__
        return {}

    def validate_config(self, config: GMConfig) -> List[str]:
        """验证配置有效性"""
        return []

    def get_branch_mapping(self) -> Dict[str, str]:
        """获取分支映射"""
        return self.load_config().branch_mapping
    
    def get_shared_files(self) -> List[str]:
        """获取共享文件列表"""
        return self.load_config().symlinks.shared_files

    def get_default_config(self) -> GMConfig:
        """获取默认配置"""
        return GMConfig()

    def _parse_config(self, data: Dict[str, Any]) -> GMConfig:
        """将字典解析为 GMConfig 对象"""
        # TODO: 实现完整的配置解析逻辑
        # 注意：这里应调用 data_structures 中的逻辑，这里简略处理
        config = GMConfig()
        # 解析基础字段
        if "initialized" in data:
            config.initialized = data["initialized"]
        if "project_name" in data:
            config.project_name = data["project_name"]
        if "home_path" in data:
            config.home_path = data["home_path"]
        if "remote_url" in data:
            config.remote_url = data["remote_url"]
        if "use_local_branch" in data:
            config.use_local_branch = data["use_local_branch"]
        if "main_branch" in data:
            config.main_branch = data["main_branch"]
        # 解析 worktree 配置
        if "worktree" in data:
            wt = data["worktree"]
            if "base_path" in wt:
                config.worktree.base_path = wt["base_path"]
            if "naming_pattern" in wt:
                config.worktree.naming_pattern = wt["naming_pattern"]
            if "auto_cleanup" in wt:
                config.worktree.auto_cleanup = wt["auto_cleanup"]
        # 解析 display 配置
        if "display" in data:
            disp = data["display"]
            if "colors" in disp:
                config.display.colors = disp["colors"]
            if "default_verbose" in disp:
                config.display.default_verbose = disp["default_verbose"]
        # 解析 symlinks 配置
        if "symlinks" in data:
            sym = data["symlinks"]
            if "strategy" in sym:
                config.symlinks.strategy = sym["strategy"]
            if "shared_files" in sym:
                config.symlinks.shared_files = sym["shared_files"]
        # 解析分支映射
        if "branch_mapping" in data:
            config.branch_mapping = data["branch_mapping"]
        # 解析 worktrees
        if "worktrees" in data:
            config.worktrees = data["worktrees"]
        return config

    def _serialize_config(self, config: GMConfig) -> Dict[str, Any]:
        """将 GMConfig 序列化为纯字典（递归处理子对象）"""
        def to_dict(obj):
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if hasattr(value, '__dict__'):
                        result[key] = to_dict(value)
                    elif isinstance(value, list):
                        result[key] = [to_dict(item) if hasattr(item, '__dict__') else item for item in value]
                    elif isinstance(value, dict):
                        result[key] = {k: to_dict(v) if hasattr(v, '__dict__') else v for k, v in value.items()}
                    else:
                        result[key] = value
                return result
            return obj

        return to_dict(config)

    def _generate_yaml_with_comments(self, config: GMConfig) -> str:
        """生成带详细注释的 YAML 配置内容

        Args:
            config: GM 配置对象

        Returns:
            带注释的 YAML 字符串
        """
        lines = []

        # 文件头注释
        lines.append("# GM (Git Worktree Manager) 项目配置文件")
        #lines.append("# 文档: https://github.com/yourusername/gm/blob/main/docs/CONFIGURATION.md")
        lines.append("")

        # 基础信息部分
        lines.append("# ==========================================")
        lines.append("# 基础项目信息")
        lines.append("# ==========================================")
        lines.append("")
        lines.append("# 项目名称 - 用于标识和显示")
        lines.append(f"project_name: {config.project_name or ''}")
        lines.append("")
        lines.append("# 项目根目录的绝对路径")
        lines.append(f"home_path: {config.home_path or ''}")
        lines.append("")
        lines.append("# 远程仓库 URL (自动从 git remote 获取)")
        lines.append(f"remote_url: {config.remote_url or ''}")
        lines.append("")
        lines.append("# GM 初始化状态 - 由系统自动管理，请勿手动修改")
        lines.append(f"initialized: {str(config.initialized).lower()}")
        lines.append("")
        lines.append("# 是否使用本地分支模式")
        lines.append("# true: 使用本地现有分支创建 worktree")
        lines.append("# false: 从远程分支创建 worktree")
        lines.append(f"use_local_branch: {str(config.use_local_branch).lower()}")
        lines.append("")
        lines.append("# 主分支名称 - 项目初始化时的默认分支")
        lines.append(f"main_branch: {config.main_branch or 'main'}")
        lines.append("")

        # Worktree 配置部分
        lines.append("# ==========================================")
        lines.append("# Worktree 配置")
        lines.append("# ==========================================")
        lines.append("")
        lines.append("worktree:")
        lines.append("  # worktree 基础路径")
        lines.append("  # '.': worktree 直接创建在项目根目录下")
        lines.append("  # '.gm': worktree 创建在 .gm/ 目录下 (推荐)")
        lines.append(f"  base_path: {config.worktree.base_path}")
        lines.append("")
        lines.append("  # worktree 目录命名模式")
        lines.append("  # 可用变量: {branch} - 分支名称")
        lines.append("  # 示例: 'wt-{branch}' 将生成为 'wt-feature-login'")
        lines.append(f"  naming_pattern: {config.worktree.naming_pattern}")
        lines.append("")
        lines.append("  # 删除 worktree 时自动清理空目录")
        lines.append("  # true: 自动清理残留文件和目录")
        lines.append("  # false: 保留目录，仅移除 worktree 链接")
        lines.append(f"  auto_cleanup: {str(config.worktree.auto_cleanup).lower()}")
        lines.append("")

        # 显示配置部分
        lines.append("# ==========================================")
        lines.append("# 显示配置")
        lines.append("# ==========================================")
        lines.append("")
        lines.append("display:")
        lines.append("  # 启用终端彩色输出")
        lines.append("  # true: 使用颜色区分不同状态 (推荐)")
        lines.append("  # false: 纯文本输出，适合日志记录")
        lines.append(f"  colors: {str(config.display.colors).lower()}")
        lines.append("")
        lines.append("  # 默认详细模式")
        lines.append("  # true: 显示完整信息 (分支状态、文件变更等)")
        lines.append("  # false: 简洁模式，仅显示关键信息")
        lines.append(f"  default_verbose: {str(config.display.default_verbose).lower()}")
        lines.append("")

        # 符号链接配置部分
        lines.append("# ==========================================")
        lines.append("# 共享文件配置 (符号链接)")
        lines.append("# ==========================================")
        lines.append("# GM 自动在主分支 worktree 和其他 worktree 之间")
        lines.append("# 创建符号链接，保持这些文件同步")
        lines.append("")
        lines.append("symlinks:")
        lines.append("  # 符号链接策略")
        lines.append("  # auto: 自动选择最佳策略 (推荐)")
        lines.append("  # symlink: 使用符号链接 (Linux/macOS)")
        lines.append("  # junction: 使用目录联接 (Windows)")
        lines.append("  # hardlink: 使用硬链接")
        lines.append(f"  strategy: {config.symlinks.strategy}")
        lines.append("")
        lines.append("  # 需要共享的文件列表")
        lines.append("  # 这些文件将符号链接到主分支的对应文件")
        lines.append("  # 修改任一副本的文件会自动同步到其他 worktree")
        lines.append("  shared_files:")
        for file in config.symlinks.shared_files:
            lines.append(f"    - {file}")
        lines.append("")

        # 分支映射部分
        lines.append("# ==========================================")
        lines.append("# 分支名称映射")
        lines.append("# ==========================================")
        lines.append("# 处理包含特殊字符的分支名称")
        lines.append("# 某些文件系统不支持的分支字符会被映射为安全名称")
        lines.append("# 格式: '原始分支名': '映射后的目录名'")
        lines.append("")
        lines.append("branch_mapping:")
        if config.branch_mapping:
            for original, mapped in config.branch_mapping.items():
                lines.append(f"  '{original}': '{mapped}'")
        else:
            lines.append("  # 示例: 'feature/fix(#123)': 'feature-fix-123'")
            lines.append("  # 示例: 'hotfix/bug@v2.0': 'hotfix-bug-v2.0'")
        lines.append("")

        # worktrees 部分
        lines.append("# ==========================================")
        lines.append("# Worktree 注册表 (由系统自动维护)")
        lines.append("# ==========================================")
        lines.append("# 此部分记录所有已创建的 worktree 信息")
        lines.append("# 请勿手动修改，除非您知道自己在做什么")
        lines.append("")
        lines.append("worktrees:")
        if config.worktrees:
            for branch, info in config.worktrees.items():
                lines.append(f"  {branch}:")
                for key, value in info.items():
                    lines.append(f"    {key}: {value}")
        else:
            lines.append("  # 空 - 尚无 worktree 被创建")
        lines.append("")

        return "\n".join(lines)
