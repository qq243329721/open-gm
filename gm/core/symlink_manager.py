"""符号链接管理器

提供跨平台的符号链接管理功能，支持多种策略：
- auto: 根据平台自动选择最佳方式
- symlink: Unix 风格符号链接
- junction: Windows 目录连接
- hardlink: 硬链接（文件）
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

from gm.core.exceptions import (
    SymlinkException,
    SymlinkCreationError,
    BrokenSymlinkError,
    SymlinkPermissionError,
)
from gm.core.logger import get_logger

logger = get_logger("symlink_manager")


class SymlinkStrategy(Enum):
    """符号链接策略"""
    AUTO = "auto"
    SYMLINK = "symlink"
    JUNCTION = "junction"
    HARDLINK = "hardlink"


class SymlinkManager:
    """符号链接管理器

    负责创建、删除、验证和修复符号链接，支持跨平台兼容性。
    """

    def __init__(self, strategy: str = 'auto', logger_instance=None):
        """初始化符号链接管理器

        Args:
            strategy: 链接策略，可选值：'auto', 'symlink', 'junction', 'hardlink'
            logger_instance: 日志记录器实例
        """
        try:
            self.strategy = SymlinkStrategy(strategy)
        except ValueError:
            raise SymlinkException(
                f"不支持的符号链接策略: {strategy}",
                details=f"支持的策略: {', '.join([s.value for s in SymlinkStrategy])}"
            )

        self.logger = logger_instance or logger
        self._is_windows = sys.platform == 'win32'
        self._is_mac = sys.platform == 'darwin'
        self._is_linux = sys.platform == 'linux'

        logger.info(
            "SymlinkManager initialized",
            strategy=strategy,
            platform=sys.platform
        )

    def create_symlink(self, source: Path, target: Path) -> bool:
        """创建符号链接

        Args:
            source: 源文件/目录路径
            target: 目标链接路径

        Returns:
            创建成功返回 True

        Raises:
            SymlinkException: 创建失败时抛出
        """
        source = Path(source).resolve()
        target = Path(target)

        logger.info(
            "Creating symlink",
            source=str(source),
            target=str(target),
            strategy=self.strategy.value
        )

        # 验证源路径存在
        if not source.exists():
            raise SymlinkCreationError(
                f"源文件不存在: {source}",
                details={"source": str(source)}
            )

        # 确保目标目录存在
        target.parent.mkdir(parents=True, exist_ok=True)

        # 如果目标已存在，抛出异常
        if target.exists() or target.is_symlink():
            raise SymlinkCreationError(
                f"目标链接已存在: {target}",
                details={"target": str(target)}
            )

        try:
            if self.strategy == SymlinkStrategy.AUTO:
                self._create_symlink_auto(source, target)
            elif self.strategy == SymlinkStrategy.SYMLINK:
                self._create_symlink_unix(source, target)
            elif self.strategy == SymlinkStrategy.JUNCTION:
                if not source.is_dir():
                    raise SymlinkCreationError(
                        "Junction 只能用于目录",
                        details={"source": str(source)}
                    )
                self._create_symlink_junction(source, target)
            elif self.strategy == SymlinkStrategy.HARDLINK:
                self._create_symlink_hardlink(source, target)

            logger.info(
                "Symlink created successfully",
                source=str(source),
                target=str(target)
            )
            return True

        except PermissionError as e:
            raise SymlinkPermissionError(
                f"权限不足：无法创建符号链接",
                details={"error": str(e), "target": str(target)}
            )
        except Exception as e:
            raise SymlinkCreationError(
                f"创建符号链接失败: {str(e)}",
                details={"source": str(source), "target": str(target), "error": str(e)}
            )

    def create_symlinks_batch(self, mappings: Dict[Path, Path]) -> Dict[Path, bool]:
        """批量创建符号链接

        Args:
            mappings: 源到目标的映射字典 {source: target}

        Returns:
            每个目标的创建结果 {target: success}
        """
        logger.info("Creating symlinks in batch", count=len(mappings))

        results = {}
        for source, target in mappings.items():
            try:
                self.create_symlink(source, target)
                results[target] = True
            except Exception as e:
                logger.warning(
                    "Failed to create symlink",
                    source=str(source),
                    target=str(target),
                    error=str(e)
                )
                results[target] = False

        return results

    def remove_symlink(self, link: Path) -> bool:
        """删除符号链接

        Args:
            link: 符号链接路径

        Returns:
            删除成功返回 True

        Raises:
            SymlinkException: 删除失败时抛出
        """
        link = Path(link)

        logger.info("Removing symlink", link=str(link))

        if not link.exists() and not link.is_symlink():
            logger.warning("Symlink does not exist", link=str(link))
            return False

        try:
            if link.is_symlink():
                link.unlink()
            elif link.is_dir():
                # 对于 junction（Windows 目录链接），使用 rmdir
                if self._is_windows:
                    try:
                        os.rmdir(link)
                    except OSError:
                        # 如果不是 junction，尝试删除
                        shutil.rmtree(link)
                else:
                    shutil.rmtree(link)
            else:
                link.unlink()

            logger.info("Symlink removed successfully", link=str(link))
            return True

        except Exception as e:
            raise SymlinkException(
                f"删除符号链接失败: {str(e)}",
                details={"link": str(link), "error": str(e)}
            )

    def remove_symlinks_batch(self, links: List[Path]) -> Dict[Path, bool]:
        """批量删除符号链接

        Args:
            links: 符号链接路径列表

        Returns:
            每个链接的删除结果 {link: success}
        """
        logger.info("Removing symlinks in batch", count=len(links))

        results = {}
        for link in links:
            try:
                results[link] = self.remove_symlink(link)
            except Exception as e:
                logger.warning(
                    "Failed to remove symlink",
                    link=str(link),
                    error=str(e)
                )
                results[link] = False

        return results

    def verify_symlink(self, link: Path) -> bool:
        """验证符号链接

        检查符号链接是否有效（存在且目标可访问）

        Args:
            link: 符号链接路径

        Returns:
            链接有效返回 True

        Raises:
            BrokenSymlinkError: 链接破损
        """
        link = Path(link)

        logger.debug("Verifying symlink", link=str(link))

        if not link.exists() and not link.is_symlink():
            raise BrokenSymlinkError(
                f"符号链接不存在: {link}",
                details={"link": str(link)}
            )

        if not link.is_symlink() and not link.is_dir() and not link.is_file():
            raise BrokenSymlinkError(
                f"路径既不是符号链接也不是有效文件: {link}",
                details={"link": str(link)}
            )

        # 如果是符号链接，检查目标是否存在
        if link.is_symlink():
            try:
                target = link.resolve(strict=True)
                if not target.exists():
                    raise BrokenSymlinkError(
                        f"符号链接目标不存在: {link} -> {target}",
                        details={"link": str(link), "target": str(target)}
                    )
            except (OSError, RuntimeError) as e:
                raise BrokenSymlinkError(
                    f"符号链接破损: {link}",
                    details={"link": str(link), "error": str(e)}
                )

        return True

    def check_symlinks_health(self, links: List[Path]) -> Dict[Path, str]:
        """检查一组符号链接的健康状态

        Args:
            links: 符号链接路径列表

        Returns:
            每个链接的状态 {link: status}
            status 可能的值: 'valid', 'broken', 'missing'
        """
        logger.info("Checking symlinks health", count=len(links))

        results = {}
        for link in links:
            try:
                self.verify_symlink(link)
                results[link] = "valid"
            except BrokenSymlinkError:
                results[link] = "broken"
            except Exception:
                results[link] = "missing"

        return results

    def repair_symlink(self, link: Path, source: Path) -> bool:
        """修复破损的符号链接

        Args:
            link: 符号链接路径
            source: 新的源文件路径

        Returns:
            修复成功返回 True

        Raises:
            SymlinkException: 修复失败时抛出
        """
        link = Path(link)
        source = Path(source)

        logger.info(
            "Repairing broken symlink",
            link=str(link),
            source=str(source)
        )

        try:
            # 删除旧的符号链接
            self.remove_symlink(link)

            # 创建新的符号链接
            self.create_symlink(source, link)

            logger.info(
                "Symlink repaired successfully",
                link=str(link),
                source=str(source)
            )
            return True

        except Exception as e:
            raise SymlinkException(
                f"修复符号链接失败: {str(e)}",
                details={"link": str(link), "source": str(source)}
            )

    def repair_all_broken_symlinks(self, directory: Path) -> Dict[Path, bool]:
        """修复目录中所有破损的符号链接

        Args:
            directory: 搜索目录

        Returns:
            修复结果 {link: success}
        """
        directory = Path(directory)

        logger.info("Repairing all broken symlinks in directory", path=str(directory))

        results = {}
        for item in directory.rglob('*'):
            if item.is_symlink():
                try:
                    self.verify_symlink(item)
                except BrokenSymlinkError:
                    logger.warning("Found broken symlink", path=str(item))
                    # 注意：这里我们只标记为破损，不能修复因为不知道原始源
                    results[item] = False

        return results

    def get_symlink_target(self, link: Path) -> Path:
        """获取符号链接的目标

        Args:
            link: 符号链接路径

        Returns:
            目标路径

        Raises:
            SymlinkException: 如果不是符号链接或获取失败
        """
        link = Path(link)

        logger.debug("Getting symlink target", link=str(link))

        if not link.is_symlink():
            raise SymlinkException(
                f"不是符号链接: {link}",
                details={"link": str(link)}
            )

        try:
            target = link.resolve()
            logger.debug("Symlink target resolved", link=str(link), target=str(target))
            return target
        except Exception as e:
            raise SymlinkException(
                f"无法获取符号链接目标: {str(e)}",
                details={"link": str(link)}
            )

    def list_symlinks(self, directory: Path) -> List[Path]:
        """列出目录中的所有符号链接

        Args:
            directory: 搜索目录

        Returns:
            符号链接路径列表
        """
        directory = Path(directory)

        logger.debug("Listing symlinks in directory", path=str(directory))

        symlinks = []
        if directory.exists():
            for item in directory.rglob('*'):
                if item.is_symlink():
                    symlinks.append(item)

        logger.debug("Symlinks found", count=len(symlinks))
        return symlinks

    def get_symlink_status(self, link: Path) -> Dict:
        """获取符号链接的详细状态

        Args:
            link: 符号链接路径

        Returns:
            包含状态信息的字典
        """
        link = Path(link)

        logger.debug("Getting symlink status", link=str(link))

        status = {
            "path": str(link),
            "exists": link.exists(),
            "is_symlink": link.is_symlink(),
            "is_file": link.is_file(),
            "is_dir": link.is_dir(),
        }

        if link.is_symlink():
            try:
                target = link.resolve()
                status["target"] = str(target)
                status["target_exists"] = target.exists()
                status["health"] = "valid" if target.exists() else "broken"
            except Exception as e:
                status["target"] = None
                status["target_exists"] = False
                status["health"] = "broken"
                status["error"] = str(e)

        return status

    # 私有方法

    def _create_symlink_auto(self, source: Path, target: Path) -> None:
        """Auto 模式：根据平台自动选择最佳方式"""
        if self._is_windows:
            # Windows: 优先使用 hardlink（文件）或 junction（目录）
            if source.is_dir():
                self._create_symlink_junction(source, target)
            else:
                self._create_symlink_hardlink(source, target)
        else:
            # macOS 和 Linux: 使用 symlink
            self._create_symlink_unix(source, target)

    def _create_symlink_unix(self, source: Path, target: Path) -> None:
        """创建 Unix 风格符号链接"""
        try:
            # 尝试使用相对路径
            try:
                relative_source = source.relative_to(target.parent.parent)
                target.symlink_to(relative_source)
            except ValueError:
                # 如果无法计算相对路径，使用绝对路径
                target.symlink_to(source)
        except OSError as e:
            if e.errno == 13:  # Permission denied
                raise PermissionError(f"权限不足：需要管理员权限或开发者模式")
            raise

    def _create_symlink_junction(self, source: Path, target: Path) -> None:
        """创建 Windows Junction（目录连接）"""
        if not self._is_windows:
            raise SymlinkException(
                "Junction 只支持 Windows 平台",
                details={"platform": sys.platform}
            )

        try:
            # 使用 mklink /J 命令
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                if "拒绝访问" in result.stderr or "Access is denied" in result.stderr:
                    raise PermissionError("权限不足：需要管理员权限")
                raise OSError(f"创建 junction 失败: {result.stderr}")

        except Exception as e:
            if isinstance(e, PermissionError):
                raise
            raise OSError(f"创建 junction 失败: {str(e)}")

    def _create_symlink_hardlink(self, source: Path, target: Path) -> None:
        """创建硬链接"""
        try:
            if source.is_dir():
                # 目录使用 xcopy（Windows）或 cp（Unix）
                if self._is_windows:
                    subprocess.run(
                        ["xcopy", str(source), str(target), "/E", "/I", "/Y"],
                        capture_output=True,
                        check=True
                    )
                else:
                    subprocess.run(
                        ["cp", "-r", str(source), str(target)],
                        capture_output=True,
                        check=True
                    )
            else:
                # 文件使用硬链接
                if self._is_windows:
                    subprocess.run(
                        ["cmd", "/c", "mklink", "/H", str(target), str(source)],
                        capture_output=True,
                        check=True
                    )
                else:
                    os.link(source, target)

        except subprocess.CalledProcessError as e:
            raise OSError(f"创建硬链接失败: {e.stderr}")
        except OSError as e:
            raise OSError(f"创建硬链接失败: {str(e)}")
