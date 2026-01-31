"""Worktree 布局接口定义"""

from abc import ABC, abstractmethod
from typing import Optional, List
from pathlib import Path


class ILayoutManager(ABC):
    """Worktree 布局管理器接口"""
    
    @abstractmethod
    def is_initialized(self) -> bool:
        """检查项目是否已初始化为 .gm 结构"""
        pass
    
    @abstractmethod
    def validate_layout(self) -> bool:
        """验证当前布局的完整性"""
        pass
    
    @abstractmethod
    def get_worktree_info(self, name: str, include_status: bool = True) -> Optional['WorktreeInfo']:
        """获取特定 worktree 的信息"""
        pass
    
    @abstractmethod
    def list_all_worktrees(self, include_status: bool = True) -> List['WorktreeInfo']:
        """列出所有管理的 worktree"""
        pass
    
    @abstractmethod
    def suggest_worktree_name(self, branch_name: str) -> str:
        """根据分支名建议 worktree 名称"""
        pass


# 类型提示支持
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gm.core.data_structures import WorktreeInfo
