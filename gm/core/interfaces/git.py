"""Git 操作相关接口定义"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path


class IGitClient(ABC):
    """Git 客户端接口"""
    
    @abstractmethod
    def is_bare_repository(self, path: Optional[Path] = None) -> bool:
        """检查是否为裸仓库"""
        pass
    
    @abstractmethod
    def create_worktree(self, path: Path, branch: str, force: bool = False) -> bool:
        """创建 worktree"""
        pass
    
    @abstractmethod
    def remove_worktree(self, path: Path, force: bool = False) -> bool:
        """删除 worktree"""
        pass
    
    @abstractmethod
    def list_worktrees(self) -> List[Dict[str, Any]]:
        """列出所有 worktree"""
        pass
    
    @abstractmethod
    def check_branch_exists(self, branch: str) -> bool:
        """检查分支是否存在"""
        pass
    
    @abstractmethod
    def get_current_branch(self, path: Optional[Path] = None) -> Optional[str]:
        """获取当前分支"""
        pass
    
    @abstractmethod
    def get_worktree_info(self, worktree_path: Path) -> Optional[Dict[str, Any]]:
        """获取 worktree 信息"""
        pass

    @abstractmethod
    def get_repo_root(self, path: Optional[Path] = None) -> Path:
        """获取项目根目录"""
        pass
