"""插件系统相关接口定义"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


class IPlugin(ABC):
    """插件基础接口"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
    
    @abstractmethod
    def initialize(self, config_manager: 'IConfigManager') -> None:
        """初始化插件"""
        pass


class IWorktreePlugin(IPlugin):
    """Worktree 插件接口"""
    
    @abstractmethod
    def on_worktree_created(self, worktree_info: 'WorktreeInfo') -> None:
        """worktree 创建事件回调"""
        pass
    
    @abstractmethod
    def on_worktree_removed(self, worktree_info: 'WorktreeInfo') -> None:
        """worktree 删除事件回调"""
        pass
    
    @abstractmethod
    def on_worktree_updated(self, worktree_info: 'WorktreeInfo') -> None:
        """worktree 更新事件回调"""
        pass


if TYPE_CHECKING:
    from gm.core.interfaces.config import IConfigManager
    from gm.core.data_structures import WorktreeInfo
