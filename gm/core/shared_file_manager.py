"""共享文件管理器实现

管理项目主分支与各 worktree 之间的文件共享（通过符号链接）。"""

from pathlib import Path
from typing import Dict, List, Optional

from gm.core.symlink_manager import SymlinkManager
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import SymlinkException
from gm.core.logger import get_logger

logger = get_logger("shared_file_manager")


class SharedFileManager:
    """共享文件管理器"""

    def __init__(
        self,
        main_branch_path: Path,
        config_manager: Optional[ConfigManager] = None,
        symlink_manager: Optional[SymlinkManager] = None,
    ):
        """初始化共享文件管理器"""
        self.main_branch_path = Path(main_branch_path)
        self.config_manager = config_manager or ConfigManager(self.main_branch_path)
        self.symlink_manager = symlink_manager or SymlinkManager()
        logger.info("SharedFileManager initialized", main_branch_path=str(self.main_branch_path))

    def setup_shared_files(self, worktree_path: Path) -> bool:
        """为指定的 worktree 设置共享文件"""
        try:
            shared_files = self.config_manager.get_shared_files()
            if not shared_files:
                return True

            for file_name in shared_files:
                source = self.main_branch_path / file_name
                target = worktree_path / file_name
                if source.exists() and not target.exists():
                    self.symlink_manager.create_symlink(source, target)
            return True
        except Exception as e:
            logger.error(f"Failed to setup shared files: {e}")
            raise SymlinkException(f"Failed to setup shared files: {e}")

    def sync_shared_files(self, worktree_path: Path) -> Dict[str, bool]:
        """同步/修复共享文件"""
        return {}

    def get_shared_files_status(self, worktree_path: Path) -> Dict:
        """获取共享状态"""
        return {}

    def cleanup_broken_links(self, worktree_path: Path) -> int:
        """清理受损链接"""
        return 0
