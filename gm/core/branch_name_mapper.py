"""分支名称映射器

处理分支名称与工作树目录名称之间的映射与转换。
支持规范化映射、自定义映射及其持久化。"""

import re
from typing import Dict, Optional, List, Any
from gm.core.logger import get_logger
from gm.core.exceptions import InvalidMappingError

logger = get_logger("branch_mapper")


class BranchNameMapper:
    """分支名与目录名映射管理类"""

    # 默认字符转换映射
    DEFAULT_CHAR_MAPPINGS = {
        '/': '-',
        '_': '-',
        '.': '-',
        ' ': '-',
    }

    def __init__(self, custom_mappings: Optional[Dict[str, str]] = None):
        """初始化映射器
        Args:
            custom_mappings: 自定义映射字典 {分支名: 目录名}
        """
        self.custom_mappings = custom_mappings or {}

    def map_branch_to_dir(self, branch_name: str) -> str:
        """将分支名映射为规范化的目录名
        Args:
            branch_name: 原始分支名称
        Returns:
            规范化后的目录名称
        Raises:
            InvalidMappingError: 如果分支名为空
        """
        if not branch_name:
            raise InvalidMappingError("分支名称不能为空")

        # 1. 检查自定义映射
        if branch_name in self.custom_mappings:
            return self.custom_mappings[branch_name]

        # 2. 默认规范化逻辑
        result = branch_name
        for char, replacement in self.DEFAULT_CHAR_MAPPINGS.items():
            result = result.replace(char, replacement)

        # 3. 移除非法字符（仅保留字母数字和中划线）
        result = re.sub(r'[^a-zA-Z0-9-]', '-', result)

        # 4. 压缩连续的中划线
        result = re.sub(r'-+', '-', result).strip('-')

        if not result:
            logger.warning(f"Branch name '{branch_name}' resulted in an empty directory name.")
            return f"branch-{hash(branch_name) % 10000}"

        return result

    def map_dir_to_branch(self, dir_name: str, config_worktrees: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """逆向映射：从目录名找回分支名
        Args:
            dir_name: 目录名称
            config_worktrees: 配置中的工作树列表
        Returns:
            对应的分支名或 None
        """
        # 从配置中查找，因为配置记录了明确的对应关系
        if dir_name in config_worktrees:
            return config_worktrees[dir_name].get('branch')
        
        # 兜底：反查自定义映射
        for b_name, d_name in self.custom_mappings.items():
            if d_name == dir_name:
                return b_name
        
        return None

    def add_custom_mapping(self, branch_name: str, dir_name: str) -> None:
        """添加或更新自定义映射"""
        if not branch_name or not dir_name:
            raise InvalidMappingError("映射的分支名和目录名均不能为空")
        self.custom_mappings[branch_name] = dir_name
        logger.info(f"Added custom mapping: {branch_name} -> {dir_name}")

    def remove_custom_mapping(self, branch_name: str) -> bool:
        """移除自定义映射"""
        if branch_name in self.custom_mappings:
            del self.custom_mappings[branch_name]
            return True
        return False

    def get_all_mapped_branches(self) -> List[str]:
        """获取所有有自定义映射的分支列表"""
        return list(self.custom_mappings.keys())
