"""分支名称到目录名的映射系统

处理 Git 分支名称中的特殊字符，将其映射为合法的目录名称。
支持默认映射规则和自定义映射。
"""

import re
from typing import Dict, List, Optional, Tuple
from gm.core.exceptions import (
    BranchMappingException,
    BranchMappingConflict,
    CircularMappingError,
    InvalidMappingError,
)
from gm.core.logger import get_logger


logger = get_logger("branch_name_mapper")


class ValidationError:
    """映射验证错误"""

    def __init__(self, error_type: str, message: str, details: Optional[Dict] = None):
        """初始化验证错误

        Args:
            error_type: 错误类型 (conflict, circular, invalid_char, etc.)
            message: 错误信息
            details: 额外详情
        """
        self.error_type = error_type
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """返回错误信息"""
        return f"{self.error_type}: {self.message}"

    def __repr__(self) -> str:
        """返回错误的字符串表示"""
        return f"ValidationError({self.error_type}, {self.message}, {self.details})"


class BranchNameMapper:
    """分支名称到目录名的映射器

    提供默认的字符映射规则和自定义映射支持。
    默认规则：
    - `/` → `-`  (feature/ui → feature-ui)
    - `(` → `-`  (fix(#123) → fix-123)
    - `)` → `` (移除)
    - `#` → `` (移除)
    - `@` → `-` (hotfix@v2 → hotfix-v2)
    - 其他特殊字符 → `-`
    - 连续多个 `-` → 单个 `-`
    - 去掉首尾的 `-`
    """

    # 默认字符映射规则
    DEFAULT_CHAR_MAPPINGS = {
        '/': '-',    # 分支路径分隔符
        '(': '-',    # 开括号
        ')': '',     # 关括号（移除）
        '#': '',     # 哈希符（移除）
        '@': '-',    # @ 符号
        ':': '-',    # 冒号
        '[': '-',    # 开方括号
        ']': '',     # 关方括号
        ' ': '-',    # 空格
        '.': '-',    # 点号
    }

    def __init__(self, custom_mappings: Optional[Dict[str, str]] = None):
        """初始化分支名称映射器

        Args:
            custom_mappings: 自定义映射规则，键为原分支名，值为映射后的目录名
        """
        self.custom_mappings = custom_mappings or {}
        logger.info(
            "BranchNameMapper initialized",
            custom_mappings_count=len(self.custom_mappings),
        )

    def map_branch_to_dir(self, branch_name: str) -> str:
        """将分支名映射到目录名

        首先检查自定义映射，如果没有则使用默认规则。

        Args:
            branch_name: 原始分支名

        Returns:
            映射后的目录名

        Raises:
            InvalidMappingError: 映射结果无效时抛出
        """
        if not branch_name:
            raise InvalidMappingError(
                "Branch name cannot be empty",
                details={"branch": branch_name},
            )

        # 先检查自定义映射
        if branch_name in self.custom_mappings:
            result = self.custom_mappings[branch_name]
            logger.debug(
                "Branch mapped using custom mapping",
                branch=branch_name,
                mapped_to=result,
            )
            return result

        # 使用默认规则映射
        result = self._apply_default_mapping(branch_name)

        logger.debug(
            "Branch mapped using default rules",
            branch=branch_name,
            mapped_to=result,
        )

        return result

    def map_dir_to_branch(self, dir_name: str) -> Optional[str]:
        """反向映射：从目录名到分支名

        尝试从自定义映射中反向查找原始分支名。
        注意：对于默认规则映射的分支，无法完全反向映射（因为信息丢失）。

        Args:
            dir_name: 目录名

        Returns:
            原始分支名，如果无法反向映射则返回 None
        """
        # 在自定义映射中查找
        for branch, mapped_dir in self.custom_mappings.items():
            if mapped_dir == dir_name:
                logger.debug(
                    "Directory mapped back to branch using custom mapping",
                    dir=dir_name,
                    branch=branch,
                )
                return branch

        logger.debug(
            "Cannot map directory back to branch (not in custom mappings)",
            dir=dir_name,
        )
        return None

    def add_mapping(self, branch: str, dir_name: str) -> None:
        """添加自定义映射

        Args:
            branch: 原始分支名
            dir_name: 映射后的目录名

        Raises:
            InvalidMappingError: 映射无效时抛出
        """
        if not branch:
            raise InvalidMappingError(
                "Branch name cannot be empty",
                details={"branch": branch, "dir": dir_name},
            )

        if not dir_name:
            raise InvalidMappingError(
                "Directory name cannot be empty",
                details={"branch": branch, "dir": dir_name},
            )

        # 验证目录名的合法性（不包含特殊字符）
        if not self._is_valid_dir_name(dir_name):
            raise InvalidMappingError(
                f"Directory name contains invalid characters: {dir_name}",
                details={"branch": branch, "dir": dir_name},
            )

        self.custom_mappings[branch] = dir_name
        logger.info(
            "Custom mapping added",
            branch=branch,
            mapped_to=dir_name,
        )

    def get_all_mappings(self) -> Dict[str, str]:
        """获取所有自定义映射

        Returns:
            自定义映射字典的深拷贝
        """
        logger.debug("Retrieved all custom mappings", count=len(self.custom_mappings))
        return self.custom_mappings.copy()

    def is_mapped(self, branch_name: str) -> bool:
        """检查分支是否有自定义映射

        Args:
            branch_name: 分支名

        Returns:
            有自定义映射返回 True，否则返回 False
        """
        return branch_name in self.custom_mappings

    def validate_mapping(self) -> List[ValidationError]:
        """验证映射配置

        检查：
        1. 没有两个不同分支映射到同一目录
        2. 没有循环映射
        3. 映射结果都是合法的目录名

        Returns:
            验证错误列表，如果没有错误则返回空列表
        """
        errors: List[ValidationError] = []

        # 检查冲突：多个分支映射到同一目录
        dir_to_branches: Dict[str, List[str]] = {}
        for branch, dir_name in self.custom_mappings.items():
            if dir_name not in dir_to_branches:
                dir_to_branches[dir_name] = []
            dir_to_branches[dir_name].append(branch)

        for dir_name, branches in dir_to_branches.items():
            if len(branches) > 1:
                error = ValidationError(
                    "conflict",
                    f"Multiple branches map to the same directory: {dir_name}",
                    {"dir": dir_name, "branches": branches},
                )
                errors.append(error)
                logger.warning(
                    "Branch mapping conflict detected",
                    dir=dir_name,
                    branches=branches,
                )

        # 检查循环映射（分支名被映射到另一个分支名）
        for branch, mapped_dir in self.custom_mappings.items():
            if mapped_dir in self.custom_mappings:
                error = ValidationError(
                    "circular",
                    f"Circular mapping detected: {branch} -> {mapped_dir} -> {self.custom_mappings[mapped_dir]}",
                    {"branch": branch, "intermediate": mapped_dir},
                )
                errors.append(error)
                logger.warning(
                    "Circular mapping detected",
                    branch=branch,
                    intermediate=mapped_dir,
                )

        # 检查目录名的合法性
        for branch, dir_name in self.custom_mappings.items():
            if not self._is_valid_dir_name(dir_name):
                error = ValidationError(
                    "invalid_char",
                    f"Directory name contains invalid characters: {dir_name}",
                    {"branch": branch, "dir": dir_name},
                )
                errors.append(error)
                logger.warning(
                    "Invalid directory name in mapping",
                    branch=branch,
                    dir=dir_name,
                )

        if errors:
            logger.error(
                "Mapping validation failed",
                error_count=len(errors),
            )
        else:
            logger.debug("Mapping validation passed")

        return errors

    def _apply_default_mapping(self, branch_name: str) -> str:
        """应用默认映射规则

        按以下顺序处理：
        1. 应用字符映射
        2. 处理连续的 `-`
        3. 去掉首尾的 `-`

        Args:
            branch_name: 原始分支名

        Returns:
            映射后的目录名
        """
        result = branch_name

        # 1. 应用字符映射
        for old_char, new_char in self.DEFAULT_CHAR_MAPPINGS.items():
            result = result.replace(old_char, new_char)

        # 2. 处理其他特殊字符（不在映射表中的）
        # 保留字母、数字、下划线、连字符
        result = re.sub(r'[^a-zA-Z0-9_-]', '-', result)

        # 3. 合并连续的 `-`
        result = re.sub(r'-+', '-', result)

        # 4. 去掉首尾的 `-`
        result = result.strip('-')

        return result

    @staticmethod
    def _is_valid_dir_name(dir_name: str) -> bool:
        """检查目录名是否合法

        合法的目录名：
        - 不为空
        - 只包含字母、数字、下划线、连字符
        - 不以 `.` 开头（避免隐藏目录）
        - 不为 `.` 或 `..`

        Args:
            dir_name: 目录名

        Returns:
            合法返回 True，否则返回 False
        """
        if not dir_name:
            return False

        if dir_name in ('.', '..'):
            return False

        if dir_name.startswith('.'):
            return False

        # 只允许字母、数字、下划线、连字符
        if not re.match(r'^[a-zA-Z0-9_-]+$', dir_name):
            return False

        return True

    def load_from_config(self, config_mappings: Dict[str, str]) -> None:
        """从配置加载自定义映射

        Args:
            config_mappings: 从 ConfigManager 获取的映射配置

        Raises:
            InvalidMappingError: 配置无效时抛出
        """
        if not isinstance(config_mappings, dict):
            raise InvalidMappingError(
                "Config mappings must be a dictionary",
                details={"type": type(config_mappings).__name__},
            )

        for branch, dir_name in config_mappings.items():
            self.add_mapping(branch, dir_name)

        logger.info(
            "Mappings loaded from config",
            count=len(config_mappings),
        )
