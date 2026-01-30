"""GM 核心模块接口定义"""

from .worktree import ILayoutManager
from .symlink import ISymlinkManager
from .git import IGitClient
from .config import IConfigManager
from .plugin import IPlugin, IWorktreePlugin

__all__ = [
    'ILayoutManager',
    'ISymlinkManager', 
    'IGitClient',
    'IConfigManager',
    'IPlugin',
    'IWorktreePlugin',
]
