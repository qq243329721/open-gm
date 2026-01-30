"""符号链接管理器实现

支持多种符号链接策略（auto, symlink, junction, hardlink），并处理跨平台差异。"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from enum import Enum

from gm.core.exceptions import (
    SymlinkException,
    SymlinkCreationError,
    BrokenSymlinkError,
    SymlinkPermissionError,
)
from gm.core.logger import get_logger

# 接口导入
from gm.core.interfaces.symlink import ISymlinkManager

logger = get_logger("symlink_manager")


class SymlinkStrategy(Enum):
    """符号链接策略"""
    AUTO = "auto"
    SYMLINK = "symlink"
    JUNCTION = "junction"
    HARDLINK = "hardlink"


class SymlinkManager(ISymlinkManager):
    """符号链接管理器

    实现 ISymlinkManager 接口，提供跨平台的符号链接管理。
    """

    def __init__(self, strategy: str = 'auto', logger_instance=None):
        """初始化符号链接管理器
        Args:
            strategy: 链接策略 ('auto', 'symlink', 'junction', 'hardlink')
            logger_instance: 可选的日志实例
        """
        try:
            self.strategy = SymlinkStrategy(strategy)
        except ValueError:
            raise SymlinkException(
                f"Invalid strategy: {strategy}",
                details=f"Supported strategies: {', '.join([s.value for s in SymlinkStrategy])}"
            )

        self.logger = logger_instance or logger
        self._is_windows = sys.platform == 'win32'

        self.logger.info(
            "SymlinkManager initialized",
            strategy=strategy,
            platform=sys.platform
        )

    def is_valid_symlink(self, link: Path) -> bool:
        """检查是否为有效的符号链接"""
        link = Path(link)
        if not link.is_symlink():
            return False
        try:
            return link.resolve().exists()
        except:
            return False

    def create_symlink(self, target: Path, link: Path) -> bool:
        """创建符号链接"""
        target = Path(target).resolve()
        link = Path(link)

        self.logger.info("Creating symlink", source=str(target), target=str(link))

        if not target.exists():
            raise SymlinkCreationError(f"Source not found: {target}")

        if link.exists() or link.is_symlink():
            # 这里简化处理，如果已存在则报错或略过
            return False

        try:
            if self._is_windows:
                if target.is_dir():
                    self._create_symlink_junction(target, link)
                else:
                    self._create_symlink_hardlink(target, link)
            else:
                link.symlink_to(target)
            return True
        except Exception as e:
            raise SymlinkCreationError(f"Failed to create symlink: {e}")

    def create_shared_symlinks(self, worktree_path: Path, 
                            shared_files: List[str],
                            project_root: Path) -> List[Path]:
        """批量创建共享文件链接"""
        created = []
        for file in shared_files:
            source = project_root / file
            target = worktree_path / file
            if self.create_symlink(source, target):
                created.append(target)
        return created

    def repair_symlinks(self, worktree_path: Path,
                      shared_files: List[str], 
                      project_root: Path) -> None:
        """修复受损链接"""
        for file in shared_files:
            target = worktree_path / file
            if target.is_symlink() and not target.exists():
                target.unlink()
                source = project_root / file
                self.create_symlink(source, target)

    def _create_symlink_junction(self, source: Path, target: Path) -> None:
        """Windows Junction"""
        subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(source)], check=True)

    def _create_symlink_hardlink(self, source: Path, target: Path) -> None:
        """Windows/Linux Hardlink"""
        if self._is_windows:
            subprocess.run(["cmd", "/c", "mklink", "/H", str(target), str(source)], check=True)
        else:
            os.link(source, target)
