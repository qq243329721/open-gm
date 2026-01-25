"""配置验证器

提供 .gm.yaml 配置的完整性和有效性验证。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from gm.core.exceptions import ConfigValidationError
from gm.core.logger import get_logger

logger = get_logger("config_validator")


class ErrorSeverity(Enum):
    """错误严重级别"""
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationError:
    """验证错误

    表示单个配置验证错误。
    """
    field: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """验证结果

    包含验证结果、错误和建议。
    """
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def add_error(self, field: str, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR) -> None:
        """添加验证错误

        Args:
            field: 错误所在字段
            message: 错误消息
            severity: 错误严重级别
        """
        error = ValidationError(field, message, severity)
        self.errors.append(error)

        # 如果是 ERROR 级别，标记为无效
        if severity == ErrorSeverity.ERROR:
            self.is_valid = False

    def add_warning(self, message: str) -> None:
        """添加警告消息

        Args:
            message: 警告消息
        """
        self.warnings.append(message)

    def add_suggestion(self, message: str) -> None:
        """添加建议

        Args:
            message: 建议消息
        """
        self.suggestions.append(message)

    def get_error_count(self) -> int:
        """获取错误数量

        Returns:
            ERROR 级别的错误数量
        """
        return sum(1 for e in self.errors if e.severity == ErrorSeverity.ERROR)

    def get_warning_count(self) -> int:
        """获取警告数量

        Returns:
            WARNING 级别的错误数量
        """
        return sum(1 for e in self.errors if e.severity == ErrorSeverity.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含验证结果的字典
        """
        return {
            'is_valid': self.is_valid,
            'errors': [{'field': e.field, 'message': e.message, 'severity': e.severity.value} for e in self.errors],
            'warnings': self.warnings,
            'suggestions': self.suggestions,
        }


class ConfigValidator:
    """配置验证器

    验证 .gm.yaml 配置的完整性和有效性。
    """

    # 支持的符号链接策略
    VALID_SYMLINK_STRATEGIES = {"auto", "symlink", "junction", "hardlink"}

    # 预期的顶级配置字段
    REQUIRED_SECTIONS = {"worktree", "display", "shared_files"}

    # 可选的顶级配置字段
    OPTIONAL_SECTIONS = {"symlinks", "branch_mapping"}

    def __init__(self, strict: bool = False, project_root: Optional[Path] = None):
        """初始化配置验证器

        Args:
            strict: 是否使用严格模式（将警告视为错误）
            project_root: 项目根目录，用于验证路径
        """
        self.strict = strict
        self.project_root = project_root or Path.cwd()
        self.result: Optional[ValidationResult] = None
        logger.debug("ConfigValidator initialized", strict=strict, project_root=str(self.project_root))

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """验证完整配置

        Args:
            config: 配置字典

        Returns:
            验证结果
        """
        self.result = ValidationResult()

        if not isinstance(config, dict):
            self.result.add_error("config", "配置必须是字典类型")
            return self.result

        logger.debug("Starting configuration validation")

        # 检查必需的部分
        self._validate_required_sections(config)

        # 验证各个配置部分
        if "worktree" in config:
            self._validate_worktree_config(config["worktree"])

        if "display" in config:
            self._validate_display_config(config["display"])

        if "shared_files" in config:
            self._validate_shared_files(config["shared_files"])

        if "symlinks" in config:
            self._validate_symlink_config(config["symlinks"])

        if "branch_mapping" in config:
            self._validate_branch_mapping(config["branch_mapping"])

        # 检查额外的未知字段
        known_sections = self.REQUIRED_SECTIONS | self.OPTIONAL_SECTIONS
        for key in config.keys():
            if key not in known_sections:
                self.result.add_warning(f"发现未知的配置部分: {key}")

        # 检查严格模式
        if self.strict and self.result.warnings:
            for warning in self.result.warnings:
                self.result.add_error("config", warning, ErrorSeverity.WARNING)

        log_level = "info" if self.result.is_valid else "error"
        getattr(logger, log_level)(
            "Configuration validation completed",
            is_valid=self.result.is_valid,
            error_count=self.result.get_error_count(),
            warning_count=self.result.get_warning_count(),
        )

        return self.result

    def _validate_required_sections(self, config: Dict[str, Any]) -> None:
        """验证必需的配置段

        Args:
            config: 配置字典
        """
        missing_sections = self.REQUIRED_SECTIONS - set(config.keys())
        for section in missing_sections:
            self.result.add_error("config", f"缺少必需的配置部分: {section}")

    def validate_section(self, section_name: str, section_data: Any) -> ValidationResult:
        """验证特定配置段

        Args:
            section_name: 段名称
            section_data: 段数据

        Returns:
            验证结果
        """
        self.result = ValidationResult()

        if section_name == "worktree":
            self._validate_worktree_config(section_data)
        elif section_name == "display":
            self._validate_display_config(section_data)
        elif section_name == "shared_files":
            self._validate_shared_files(section_data)
        elif section_name == "symlinks":
            self._validate_symlink_config(section_data)
        elif section_name == "branch_mapping":
            self._validate_branch_mapping(section_data)
        else:
            self.result.add_error("section", f"未知的配置部分: {section_name}")

        return self.result

    def _validate_worktree_config(self, worktree: Any) -> None:
        """验证 worktree 配置

        Args:
            worktree: worktree 配置数据
        """
        if not isinstance(worktree, dict):
            self.result.add_error("worktree", "worktree 配置必须是字典类型")
            return

        # 验证 base_path
        if "base_path" in worktree:
            base_path = worktree["base_path"]
            if not isinstance(base_path, str):
                self.result.add_error("worktree.base_path", "base_path 必须是字符串")
            elif not base_path.strip():
                self.result.add_error("worktree.base_path", "base_path 不能为空字符串")
            else:
                # 检查路径有效性
                try:
                    path = Path(base_path)
                    if path.is_absolute():
                        self.result.add_suggestion("建议使用相对路径作为 base_path")
                except Exception as e:
                    self.result.add_warning(f"base_path 可能无效: {e}")
        else:
            self.result.add_warning("worktree.base_path 未指定，将使用默认值 '.gm'")

        # 验证 naming_pattern
        if "naming_pattern" in worktree:
            pattern = worktree["naming_pattern"]
            if not isinstance(pattern, str):
                self.result.add_error("worktree.naming_pattern", "naming_pattern 必须是字符串")
            elif not pattern.strip():
                self.result.add_error("worktree.naming_pattern", "naming_pattern 不能为空字符串")
            elif "{branch}" not in pattern:
                self.result.add_warning("naming_pattern 中不包含 {branch} 占位符，这可能导致所有分支共享同一个目录")
        else:
            self.result.add_warning("worktree.naming_pattern 未指定，将使用默认值 '{branch}'")

        # 验证 auto_cleanup
        if "auto_cleanup" in worktree:
            if not isinstance(worktree["auto_cleanup"], bool):
                self.result.add_error("worktree.auto_cleanup", "auto_cleanup 必须是布尔值")

        # 检查额外字段
        valid_fields = {"base_path", "naming_pattern", "auto_cleanup"}
        extra_fields = set(worktree.keys()) - valid_fields
        if extra_fields:
            self.result.add_warning(f"worktree 中发现未知字段: {', '.join(extra_fields)}")

    def _validate_display_config(self, display: Any) -> None:
        """验证 display 配置

        Args:
            display: display 配置数据
        """
        if not isinstance(display, dict):
            self.result.add_error("display", "display 配置必须是字典类型")
            return

        # 验证 colors
        if "colors" in display:
            if not isinstance(display["colors"], bool):
                self.result.add_error("display.colors", "colors 必须是布尔值")

        # 验证 default_verbose
        if "default_verbose" in display:
            if not isinstance(display["default_verbose"], bool):
                self.result.add_error("display.default_verbose", "default_verbose 必须是布尔值")

        # 检查额外字段
        valid_fields = {"colors", "default_verbose"}
        extra_fields = set(display.keys()) - valid_fields
        if extra_fields:
            self.result.add_warning(f"display 中发现未知字段: {', '.join(extra_fields)}")

    def _validate_shared_files(self, shared_files: Any) -> None:
        """验证 shared_files 配置

        Args:
            shared_files: shared_files 配置数据
        """
        if not isinstance(shared_files, list):
            self.result.add_error("shared_files", "shared_files 必须是列表类型")
            return

        if not shared_files:
            self.result.add_warning("shared_files 列表为空")
            return

        # 验证列表中的每个元素
        for idx, item in enumerate(shared_files):
            if not isinstance(item, str):
                self.result.add_error(
                    f"shared_files[{idx}]",
                    f"列表中的每一项必须是字符串，当前为 {type(item).__name__}"
                )
            elif not item.strip():
                self.result.add_error(f"shared_files[{idx}]", "文件路径不能为空字符串")

    def _validate_symlink_config(self, symlinks: Any) -> None:
        """验证 symlinks 配置

        Args:
            symlinks: symlinks 配置数据
        """
        if not isinstance(symlinks, dict):
            self.result.add_error("symlinks", "symlinks 配置必须是字典类型")
            return

        # 验证 strategy
        if "strategy" in symlinks:
            strategy = symlinks["strategy"]
            if not isinstance(strategy, str):
                self.result.add_error("symlinks.strategy", "strategy 必须是字符串")
            elif strategy not in self.VALID_SYMLINK_STRATEGIES:
                valid_strategies = ", ".join(self.VALID_SYMLINK_STRATEGIES)
                self.result.add_error(
                    "symlinks.strategy",
                    f"strategy 必须是以下之一: {valid_strategies}，当前为 '{strategy}'"
                )
        else:
            self.result.add_warning("symlinks.strategy 未指定，将使用默认值 'auto'")

        # 检查额外字段
        valid_fields = {"strategy"}
        extra_fields = set(symlinks.keys()) - valid_fields
        if extra_fields:
            self.result.add_warning(f"symlinks 中发现未知字段: {', '.join(extra_fields)}")

    def _validate_branch_mapping(self, branch_mapping: Any) -> None:
        """验证 branch_mapping 配置

        Args:
            branch_mapping: branch_mapping 配置数据
        """
        if not isinstance(branch_mapping, dict):
            self.result.add_error("branch_mapping", "branch_mapping 必须是字典类型")
            return

        if not branch_mapping:
            # 空映射是允许的
            return

        # 验证每个键值对
        for key, value in branch_mapping.items():
            if not isinstance(key, str):
                self.result.add_error(
                    f"branch_mapping[{key}]",
                    f"分支名称必须是字符串，当前为 {type(key).__name__}"
                )
            elif not key.strip():
                self.result.add_error("branch_mapping", "分支名称不能为空字符串")

            if not isinstance(value, str):
                self.result.add_error(
                    f"branch_mapping[{key}]",
                    f"映射目标必须是字符串，当前为 {type(value).__name__}"
                )
            elif not value.strip():
                self.result.add_error(
                    f"branch_mapping[{key}]",
                    "映射目标不能为空字符串"
                )

            # 检查特殊字符
            if isinstance(value, str) and value.strip():
                if self._contains_invalid_path_chars(value):
                    self.result.add_warning(
                        f"branch_mapping[{key}] 的映射目标包含可能的无效路径字符"
                    )

    def _contains_invalid_path_chars(self, path: str) -> bool:
        """检查路径是否包含无效字符

        Args:
            path: 路径字符串

        Returns:
            True 如果包含无效字符，False 否则
        """
        # Windows 不允许的字符
        invalid_chars = r'<>:"|?*'
        return any(char in path for char in invalid_chars)

    def validate_worktree_config(self, worktree_config: Dict[str, Any]) -> ValidationResult:
        """验证 worktree 配置（方法别名）

        Args:
            worktree_config: worktree 配置

        Returns:
            验证结果
        """
        return self.validate_section("worktree", worktree_config)

    def validate_display_config(self, display_config: Dict[str, Any]) -> ValidationResult:
        """验证 display 配置（方法别名）

        Args:
            display_config: display 配置

        Returns:
            验证结果
        """
        return self.validate_section("display", display_config)

    def validate_shared_files(self, shared_files: List[str]) -> ValidationResult:
        """验证 shared_files 配置（方法别名）

        Args:
            shared_files: shared_files 配置

        Returns:
            验证结果
        """
        return self.validate_section("shared_files", shared_files)

    def validate_symlink_strategy(self, strategy: str) -> ValidationResult:
        """验证符号链接策略

        Args:
            strategy: 策略字符串

        Returns:
            验证结果
        """
        self.result = ValidationResult()

        if not isinstance(strategy, str):
            self.result.add_error("strategy", f"策略必须是字符串，当前为 {type(strategy).__name__}")
        elif strategy not in self.VALID_SYMLINK_STRATEGIES:
            valid_strategies = ", ".join(self.VALID_SYMLINK_STRATEGIES)
            self.result.add_error(
                "strategy",
                f"策略必须是以下之一: {valid_strategies}，当前为 '{strategy}'"
            )

        return self.result

    def validate_branch_mapping(self, branch_mapping: Dict[str, str]) -> ValidationResult:
        """验证 branch_mapping 配置（方法别名）

        Args:
            branch_mapping: branch_mapping 配置

        Returns:
            验证结果
        """
        return self.validate_section("branch_mapping", branch_mapping)

    def get_validation_result(self) -> Optional[ValidationResult]:
        """获取最后的验证结果

        Returns:
            最后一次验证的结果，如果没有验证过返回 None
        """
        return self.result

    def suggest_fixes(self) -> List[str]:
        """建议修复措施

        基于验证错误提供修复建议。

        Returns:
            建议列表
        """
        if not self.result:
            return []

        suggestions = self.result.suggestions.copy()

        # 根据错误类型添加更多建议
        for error in self.result.errors:
            if "必须是字典" in error.message and "worktree" in error.field:
                suggestions.append("确保 worktree 配置在 YAML 中是以冒号开头的缩进结构")
            elif "缺少必需的配置部分" in error.message:
                suggestions.append(f"请在配置文件中添加 {error.field} 部分")
            elif "不能为空字符串" in error.message:
                suggestions.append(f"请为 {error.field} 提供非空值")

        return suggestions
