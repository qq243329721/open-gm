"""共享文件管理器

负责管理 worktree 中的共享文件符号链接，确保文件同步和冲突处理。
"""

from pathlib import Path
from typing import Dict, List, Optional

from gm.core.symlink_manager import SymlinkManager
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    SymlinkException,
    SymlinkCreationError,
)
from gm.core.logger import get_logger

logger = get_logger("shared_file_manager")


class SharedFileManager:
    """共享文件管理器

    负责为 worktree 设置、同步和管理共享文件的符号链接。
    """

    def __init__(
        self,
        main_branch_path: Path,
        config_manager: Optional[ConfigManager] = None,
        symlink_manager: Optional[SymlinkManager] = None,
        logger_instance=None
    ):
        """初始化共享文件管理器

        Args:
            main_branch_path: 主分支路径
            config_manager: 配置管理器实例
            symlink_manager: 符号链接管理器实例
            logger_instance: 日志记录器实例
        """
        self.main_branch_path = Path(main_branch_path)
        self.config_manager = config_manager or ConfigManager(self.main_branch_path)
        self.symlink_manager = symlink_manager or SymlinkManager(strategy='auto')
        self.logger = logger_instance or logger

        logger.info(
            "SharedFileManager initialized",
            main_branch_path=str(self.main_branch_path)
        )

    def setup_shared_files(self, worktree_path: Path) -> bool:
        """为新 worktree 设置共享文件符号链接

        Args:
            worktree_path: worktree 路径

        Returns:
            设置成功返回 True

        Raises:
            SymlinkException: 设置失败时抛出
        """
        worktree_path = Path(worktree_path)

        logger.info(
            "Setting up shared files for worktree",
            worktree_path=str(worktree_path)
        )

        try:
            shared_files = self.config_manager.get_shared_files()

            logger.debug("Shared files configuration", count=len(shared_files))

            if not shared_files:
                logger.info("No shared files to setup")
                return True

            mappings = {}
            for file_name in shared_files:
                source_file = self.main_branch_path / file_name
                target_link = worktree_path / file_name

                if not source_file.exists():
                    logger.warning(
                        "Shared file not found in main branch",
                        file=file_name,
                        source=str(source_file)
                    )
                    continue

                if target_link.exists() or target_link.is_symlink():
                    logger.warning(
                        "Target link already exists",
                        file=file_name,
                        target=str(target_link)
                    )
                    continue

                mappings[source_file] = target_link

            # 批量创建符号链接
            results = self.symlink_manager.create_symlinks_batch(mappings)

            success_count = sum(1 for v in results.values() if v)
            logger.info(
                "Shared files setup completed",
                total=len(shared_files),
                success=success_count,
                failed=len(shared_files) - success_count
            )

            return success_count > 0

        except Exception as e:
            logger.error(
                "Failed to setup shared files",
                worktree_path=str(worktree_path),
                error=str(e)
            )
            raise SymlinkException(
                f"设置共享文件失败: {str(e)}",
                details={"worktree": str(worktree_path)}
            )

    def sync_shared_files(self, worktree_path: Path) -> Dict[str, bool]:
        """同步共享文件到最新版本

        检查 worktree 中的共享文件符号链接，验证其有效性，
        并修复所有破损的链接。

        Args:
            worktree_path: worktree 路径

        Returns:
            同步结果 {'file': sync_success}
        """
        worktree_path = Path(worktree_path)

        logger.info(
            "Syncing shared files for worktree",
            worktree_path=str(worktree_path)
        )

        try:
            shared_files = self.config_manager.get_shared_files()
            results = {}

            for file_name in shared_files:
                source_file = self.main_branch_path / file_name
                target_link = worktree_path / file_name

                try:
                    # 检查源文件是否存在
                    if not source_file.exists():
                        logger.warning(
                            "Shared file not found in main branch",
                            file=file_name,
                            source=str(source_file)
                        )
                        results[file_name] = False
                        continue

                    # 检查符号链接是否存在
                    if not target_link.exists() and not target_link.is_symlink():
                        logger.warning(
                            "Shared file link not found in worktree",
                            file=file_name,
                            target=str(target_link)
                        )
                        # 尝试创建
                        try:
                            self.symlink_manager.create_symlink(source_file, target_link)
                            results[file_name] = True
                        except Exception as e:
                            logger.warning(
                                "Failed to create missing shared file link",
                                file=file_name,
                                error=str(e)
                            )
                            results[file_name] = False
                        continue

                    # 验证符号链接有效性
                    try:
                        self.symlink_manager.verify_symlink(target_link)
                        results[file_name] = True
                        logger.debug("Shared file link is valid", file=file_name)
                    except Exception as verify_error:
                        logger.warning(
                            "Shared file link is broken, attempting repair",
                            file=file_name,
                            error=str(verify_error)
                        )
                        # 尝试修复
                        try:
                            self.symlink_manager.repair_symlink(target_link, source_file)
                            results[file_name] = True
                            logger.info("Shared file link repaired successfully", file=file_name)
                        except Exception as repair_error:
                            logger.error(
                                "Failed to repair shared file link",
                                file=file_name,
                                error=str(repair_error)
                            )
                            results[file_name] = False

                except Exception as e:
                    logger.error(
                        "Error processing shared file",
                        file=file_name,
                        error=str(e)
                    )
                    results[file_name] = False

            success_count = sum(1 for v in results.values() if v)
            logger.info(
                "Shared files sync completed",
                total=len(shared_files),
                success=success_count,
                failed=len(shared_files) - success_count
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to sync shared files",
                worktree_path=str(worktree_path),
                error=str(e)
            )
            raise SymlinkException(
                f"同步共享文件失败: {str(e)}",
                details={"worktree": str(worktree_path)}
            )

    def get_shared_files_status(self, worktree_path: Path) -> Dict:
        """获取共享文件的同步状态

        Args:
            worktree_path: worktree 路径

        Returns:
            包含状态信息的字典
        """
        worktree_path = Path(worktree_path)

        logger.info(
            "Getting shared files status for worktree",
            worktree_path=str(worktree_path)
        )

        try:
            shared_files = self.config_manager.get_shared_files()
            status = {
                "worktree": str(worktree_path),
                "total_files": len(shared_files),
                "files": {},
                "valid_count": 0,
                "broken_count": 0,
                "missing_count": 0,
            }

            for file_name in shared_files:
                source_file = self.main_branch_path / file_name
                target_link = worktree_path / file_name

                file_status = {
                    "name": file_name,
                    "source": str(source_file),
                    "target": str(target_link),
                    "source_exists": source_file.exists(),
                    "link_exists": target_link.exists() or target_link.is_symlink(),
                    "health": "unknown",
                }

                if not target_link.exists() and not target_link.is_symlink():
                    file_status["health"] = "missing"
                    status["missing_count"] += 1
                else:
                    try:
                        self.symlink_manager.verify_symlink(target_link)
                        file_status["health"] = "valid"
                        status["valid_count"] += 1
                    except Exception:
                        file_status["health"] = "broken"
                        status["broken_count"] += 1

                status["files"][file_name] = file_status

            logger.debug("Shared files status retrieved", **status)
            return status

        except Exception as e:
            logger.error(
                "Failed to get shared files status",
                worktree_path=str(worktree_path),
                error=str(e)
            )
            raise SymlinkException(
                f"获取共享文件状态失败: {str(e)}",
                details={"worktree": str(worktree_path)}
            )

    def handle_shared_file_conflict(self, file_path: Path) -> bool:
        """处理共享文件冲突

        当共享文件发生冲突时，尝试通过重新创建符号链接来解决。

        Args:
            file_path: 冲突文件路径

        Returns:
            冲突处理成功返回 True

        Raises:
            SymlinkException: 处理失败时抛出
        """
        file_path = Path(file_path)

        logger.info("Handling shared file conflict", file=str(file_path))

        try:
            # 找到对应的源文件
            shared_files = self.config_manager.get_shared_files()

            source_file = None
            for file_name in shared_files:
                if str(file_path).endswith(file_name):
                    source_file = self.main_branch_path / file_name
                    break

            if source_file is None:
                raise SymlinkException(
                    f"无法找到共享文件配置: {file_path}",
                    details={"file": str(file_path)}
                )

            # 删除冲突文件
            if file_path.exists():
                file_path.unlink()
                logger.info("Conflict file removed", file=str(file_path))

            # 重新创建符号链接
            self.symlink_manager.create_symlink(source_file, file_path)

            logger.info(
                "Shared file conflict resolved",
                file=str(file_path),
                source=str(source_file)
            )
            return True

        except SymlinkException:
            raise
        except Exception as e:
            logger.error(
                "Failed to handle shared file conflict",
                file=str(file_path),
                error=str(e)
            )
            raise SymlinkException(
                f"处理共享文件冲突失败: {str(e)}",
                details={"file": str(file_path)}
            )

    def cleanup_broken_links(self, worktree_path: Path) -> int:
        """清理 worktree 中所有破损的共享文件链接

        Args:
            worktree_path: worktree 路径

        Returns:
            清理的破损链接数量
        """
        worktree_path = Path(worktree_path)

        logger.info(
            "Cleaning up broken links in worktree",
            worktree_path=str(worktree_path)
        )

        try:
            shared_files = self.config_manager.get_shared_files()
            cleanup_count = 0

            for file_name in shared_files:
                target_link = worktree_path / file_name

                if not target_link.is_symlink():
                    continue

                try:
                    self.symlink_manager.verify_symlink(target_link)
                except Exception:
                    # 符号链接破损，删除它
                    try:
                        self.symlink_manager.remove_symlink(target_link)
                        cleanup_count += 1
                        logger.info("Broken link removed", link=str(target_link))
                    except Exception as e:
                        logger.warning(
                            "Failed to remove broken link",
                            link=str(target_link),
                            error=str(e)
                        )

            logger.info(
                "Cleanup completed",
                worktree_path=str(worktree_path),
                cleanup_count=cleanup_count
            )
            return cleanup_count

        except Exception as e:
            logger.error(
                "Failed to cleanup broken links",
                worktree_path=str(worktree_path),
                error=str(e)
            )
            raise SymlinkException(
                f"清理破损链接失败: {str(e)}",
                details={"worktree": str(worktree_path)}
            )
