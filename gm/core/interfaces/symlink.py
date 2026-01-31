"""符号链接相关接口定义"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from pathlib import Path


class ISymlinkManager(ABC):
    """符号链接管理器接口"""
    
    @abstractmethod
    def create_symlink(self, target: Path, link: Path) -> bool:
        """创建符号链接"""
        pass
    
    @abstractmethod
    def is_valid_symlink(self, link: Path) -> bool:
        """是否为有效的符号链接"""
        pass
    
    @abstractmethod
    def create_shared_symlinks(self, worktree_path: Path, 
                            shared_files: List[str],
                            project_root: Path) -> List[Path]:
        """为 worktree 创建共享文件的符号链接"""
        pass
    
    @abstractmethod
    def repair_symlinks(self, worktree_path: Path,
                      shared_files: List[str], 
                      project_root: Path) -> None:
        """修复受损的符号链接"""
        pass
