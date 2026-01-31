"""配置验证器

负责验证 gm.yaml 配置文件的结构、类型及逻辑正确性。"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from gm.core.exceptions import ConfigValidationError
from gm.core.logger import get_logger

logger = get_logger("config_validator")


class ErrorSeverity(Enum):
    """验证错误严重程度"""
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationError:
    """单个验证错误信息"""
    field: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """整体验证结果集"""
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, field: str, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR) -> None:
        """添加错误或警告"""
        self.errors.append(ValidationError(field, message, severity))
        if severity == ErrorSeverity.ERROR:
            self.is_valid = False


class ConfigValidator:
    """配置验证执行类"""

    def __init__(self, strict: bool = False, project_root: Optional[Path] = None):
        """初始化
        Args:
            strict: 是否开启严格模式
            project_root: 项目根路径，用于路径存在性验证
        """
        self.strict = strict
        self.project_root = project_root or Path.cwd()
        self.result = ValidationResult()

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """验证整个配置字典
        Args:
            config: 配置字典
        Returns:
            验证结果对象
        """
        self.result = ValidationResult()

        if not isinstance(config, dict):
            self.result.add_error("config", "配置内容必须是字典格式")
            return self.result

        logger.debug("Starting configuration validation")

        # 1. 验证必需的主配置项
        self._validate_required_sections(config)

        # 2. 验证各个子模块
        if "worktree" in config:
            self._validate_worktree_config(config["worktree"])
        
        if "shared_files" in config:
            self._validate_shared_files_config(config["shared_files"])
        
        if "plugins" in config:
            self._validate_plugin_config(config["plugins"])

        logger.info(f"Validation finished. Valid: {self.result.is_valid}, Errors: {len(self.result.errors)}")
        return self.result

    def _validate_required_sections(self, config: Dict[str, Any]) -> None:
        """验证必需的配置节是否存在"""
        required = ["worktree", "shared_files"]
        for section in required:
            if section not in config:
                self.result.add_error("config", f"缺失必需的配置节: '{section}'")

    def _validate_worktree_config(self, wt_config: Any) -> None:
        """验证 worktree 配置节"""
        if not isinstance(wt_config, dict):
            self.result.add_error("worktree", "worktree 配置必须是字典")
            return

        # 检查必需字段
        if "base_path" in wt_config:
            base_path = Path(wt_config["base_path"])
            if self.strict and not base_path.is_absolute():
                self.result.add_error("worktree.base_path", "严格模式下 base_path 必须是绝对路径", ErrorSeverity.WARNING)

    def _validate_shared_files_config(self, shared_config: Any) -> None:
        """验证 shared_files 配置节"""
        if not isinstance(shared_config, list):
            self.result.add_error("shared_files", "shared_files 必须是列表格式")
            return

        for i, item in enumerate(shared_config):
            if not isinstance(item, str):
                self.result.add_error(f"shared_files[{i}]", f"配置项必须是字符串: {item}")

    def _validate_plugin_config(self, plugin_config: Any) -> None:
        """验证 plugins 配置节"""
        if not isinstance(plugin_config, dict):
            self.result.add_error("plugins", "plugins 配置必须是字典")
            return
        
        for name, config in plugin_config.items():
            if not isinstance(config, dict):
                self.result.add_error(f"plugins.{name}", "插件配置详情必须是字典")
