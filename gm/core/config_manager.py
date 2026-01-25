"""配置管理器

提供 .gm.yaml 配置文件的加载、验证、合并和保存功能。
支持配置值的合并策略（APPEND、DEEP_MERGE、OVERRIDE、SKIP）。
"""

import copy
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from gm.core.exceptions import ConfigException, ConfigIOError, ConfigParseError, ConfigValidationError
from gm.core.logger import get_logger

logger = get_logger("config_manager")


class MergeStrategy(Enum):
    """配置合并策略"""
    OVERRIDE = "override"      # 覆盖基础配置
    SKIP = "skip"              # 跳过，保留基础配置
    DEEP_MERGE = "deep_merge"  # 深度合并（对字典）
    APPEND = "append"          # 追加（对列表）


class ConfigManager:
    """配置管理器

    负责加载、验证、合并和保存 .gm.yaml 配置文件。
    """

    DEFAULT_CONFIG = {
        "worktree": {
            "naming_pattern": "{branch}",
            "auto_cleanup": True,
        },
        "display": {
            "colors": True,
            "default_verbose": False,
        },
        "shared_files": [".env", ".gitignore", "README.md"],
        "symlinks": {
            "strategy": "auto",
        },
        "branch_mapping": {},
    }

    CONFIG_FILENAME = ".gm.yaml"

    def __init__(self, project_root: Optional[Path] = None):
        """初始化配置管理器

        Args:
            project_root: 项目根目录，默认为当前目录
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._config: Optional[Dict[str, Any]] = None
        logger.info("ConfigManager initialized", project_root=str(self.project_root))

    @property
    def config_path(self) -> Path:
        """获取配置文件路径"""
        return self.project_root / self.CONFIG_FILENAME

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置

        Returns:
            默认配置字典的深拷贝
        """
        logger.debug("Returning default configuration")
        return copy.deepcopy(self.DEFAULT_CONFIG)

    def load_config(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """加载配置文件

        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径

        Returns:
            配置字典

        Raises:
            ConfigIOError: 文件读取失败时抛出
            ConfigParseError: YAML 解析失败时抛出
        """
        path = config_path or self.config_path

        logger.info("Loading configuration", path=str(path))

        # 如果文件不存在，返回默认配置
        if not path.exists():
            logger.warning("Configuration file not found, using defaults", path=str(path))
            self._config = self.get_default_config()
            return self._config

        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # 如果文件为空，使用默认配置
            if config_data is None:
                logger.info("Configuration file is empty, using defaults", path=str(path))
                config_data = self.get_default_config()
            else:
                # 合并默认配置和加载的配置
                config_data = self.merge_configs(
                    self.get_default_config(),
                    config_data,
                    strategy=MergeStrategy.DEEP_MERGE
                )

            self._config = config_data
            logger.info("Configuration loaded successfully", path=str(path))
            return self._config

        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML configuration", path=str(path), error=str(e))
            raise ConfigParseError(f"Failed to parse YAML configuration: {e}", details=str(e))
        except IOError as e:
            logger.error("Failed to read configuration file", path=str(path), error=str(e))
            raise ConfigIOError(f"Failed to read configuration file: {e}", details=str(e))

    def validate_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """验证配置结构和值

        Args:
            config: 配置字典，如果为 None 则验证当前加载的配置

        Returns:
            配置有效返回 True

        Raises:
            ConfigValidationError: 配置验证失败时抛出
        """
        cfg = config or self._config

        if cfg is None:
            logger.error("No configuration to validate")
            raise ConfigValidationError("No configuration loaded or provided")

        logger.info("Validating configuration")

        errors = []

        # 检查必需的顶级字段
        required_sections = ["worktree", "display", "shared_files"]
        for section in required_sections:
            if section not in cfg:
                errors.append(f"Missing required section: {section}")

        # 验证 worktree 配置
        if "worktree" in cfg:
            worktree = cfg["worktree"]
            if not isinstance(worktree, dict):
                errors.append("worktree must be a dictionary")
            else:
                if "naming_pattern" not in worktree or not isinstance(worktree["naming_pattern"], str):
                    errors.append("worktree.naming_pattern must be a non-empty string")
                if "auto_cleanup" in worktree and not isinstance(worktree["auto_cleanup"], bool):
                    errors.append("worktree.auto_cleanup must be a boolean")

        # 验证 display 配置
        if "display" in cfg:
            display = cfg["display"]
            if not isinstance(display, dict):
                errors.append("display must be a dictionary")
            else:
                if "colors" in display and not isinstance(display["colors"], bool):
                    errors.append("display.colors must be a boolean")
                if "default_verbose" in display and not isinstance(display["default_verbose"], bool):
                    errors.append("display.default_verbose must be a boolean")

        # 验证 shared_files 配置
        if "shared_files" in cfg:
            shared_files = cfg["shared_files"]
            if not isinstance(shared_files, list):
                errors.append("shared_files must be a list")
            else:
                for item in shared_files:
                    if not isinstance(item, str):
                        errors.append("All items in shared_files must be strings")
                        break

        # 验证 symlinks 配置
        if "symlinks" in cfg:
            symlinks = cfg["symlinks"]
            if not isinstance(symlinks, dict):
                errors.append("symlinks must be a dictionary")
            else:
                if "strategy" in symlinks:
                    strategy = symlinks["strategy"]
                    valid_strategies = ["auto", "symlink", "junction", "hardlink"]
                    if strategy not in valid_strategies:
                        errors.append(f"symlinks.strategy must be one of {valid_strategies}")

        # 验证 branch_mapping 配置
        if "branch_mapping" in cfg:
            branch_mapping = cfg["branch_mapping"]
            if not isinstance(branch_mapping, dict):
                errors.append("branch_mapping must be a dictionary")

        if errors:
            error_msg = "; ".join(errors)
            logger.error("Configuration validation failed", errors=errors)
            raise ConfigValidationError(f"Configuration validation failed: {error_msg}")

        logger.info("Configuration validated successfully")
        return True

    def merge_configs(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
        strategy: MergeStrategy = MergeStrategy.DEEP_MERGE,
    ) -> Dict[str, Any]:
        """合并配置

        Args:
            base: 基础配置
            override: 覆盖配置
            strategy: 合并策略

        Returns:
            合并后的配置
        """
        logger.debug("Merging configurations", strategy=strategy.value)

        if strategy == MergeStrategy.OVERRIDE:
            return copy.deepcopy(override)

        if strategy == MergeStrategy.SKIP:
            return copy.deepcopy(base)

        if strategy == MergeStrategy.APPEND:
            if isinstance(base, list) and isinstance(override, list):
                return base + override
            return copy.deepcopy(override)

        # DEEP_MERGE 策略
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result:
                base_value = result[key]

                # 如果两个值都是字典，递归合并
                if isinstance(base_value, dict) and isinstance(value, dict):
                    result[key] = self.merge_configs(base_value, value, strategy)
                # 如果两个值都是列表，追加
                elif isinstance(base_value, list) and isinstance(value, list):
                    result[key] = base_value + value
                # 否则覆盖
                else:
                    result[key] = copy.deepcopy(value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def save_config(self, config: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> None:
        """保存配置到文件

        Args:
            config: 配置字典，如果为 None 则保存当前配置
            path: 保存路径，如果为 None 则使用默认路径

        Raises:
            ConfigIOError: 文件写入失败时抛出
            ConfigValidationError: 配置验证失败时抛出
        """
        cfg = config or self._config
        save_path = path or self.config_path

        if cfg is None:
            logger.error("No configuration to save")
            raise ConfigException("No configuration to save")

        # 验证配置
        self.validate_config(cfg)

        logger.info("Saving configuration", path=str(save_path))

        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    cfg,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            logger.info("Configuration saved successfully", path=str(save_path))
            self._config = cfg

        except IOError as e:
            logger.error("Failed to write configuration file", path=str(save_path), error=str(e))
            raise ConfigIOError(f"Failed to write configuration file: {e}", details=str(e))

    def get_shared_files(self) -> List[str]:
        """获取共享文件列表

        Returns:
            共享文件名列表
        """
        if self._config is None:
            self.load_config()

        shared_files = self._config.get("shared_files", [])
        logger.debug("Retrieved shared files", count=len(shared_files))
        return shared_files

    def get_branch_mapping(self) -> Dict[str, str]:
        """获取分支名称映射

        分支映射用于将特殊字符的分支名映射到有效的目录名。

        Returns:
            分支映射字典，键为原分支名，值为映射后的名称
        """
        if self._config is None:
            self.load_config()

        branch_mapping = self._config.get("branch_mapping", {})
        logger.debug("Retrieved branch mapping", count=len(branch_mapping))
        return branch_mapping

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径

        例如: get("worktree.base_path") 返回 .gm

        Args:
            key_path: 配置路径，使用点号分隔（例如 "worktree.base_path"）
            default: 如果路径不存在的默认值

        Returns:
            配置值或默认值
        """
        if self._config is None:
            self.load_config()

        keys = key_path.split(".")
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.debug("Configuration key not found", key_path=key_path)
                return default

        logger.debug("Retrieved configuration value", key_path=key_path)
        return value

    def set(self, key_path: str, value: Any) -> None:
        """设置配置值，支持点号分隔的路径

        例如: set("worktree.base_path", ".gm") 设置 worktree.base_path 的值

        Args:
            key_path: 配置路径，使用点号分隔
            value: 要设置的值
        """
        if self._config is None:
            self.load_config()

        keys = key_path.split(".")
        target = self._config

        # 遍历到倒数第二个键
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        # 设置最后一个键的值
        target[keys[-1]] = value
        logger.debug("Set configuration value", key_path=key_path)

    def reload(self) -> Dict[str, Any]:
        """重新加载配置文件

        Returns:
            重新加载的配置字典
        """
        self._config = None
        logger.info("Reloading configuration")
        return self.load_config()

    def reset_to_defaults(self) -> None:
        """重置配置为默认值"""
        self._config = self.get_default_config()
        logger.info("Configuration reset to defaults")
