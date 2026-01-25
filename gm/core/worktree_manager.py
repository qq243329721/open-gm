"""统一的 Worktree 管理器

支持原子操作和事务管理，确保 worktree 操作的原子性和一致性。
"""

import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from gm.core.git_client import GitClient
from gm.core.config_manager import ConfigManager
from gm.core.branch_name_mapper import BranchNameMapper
from gm.core.exceptions import (
    WorktreeNotFound,
    WorktreeAlreadyExists,
    GitException,
    ConfigException,
)
from gm.core.transaction import Transaction
from gm.core.logger import get_logger

logger = get_logger("worktree_manager")


class WorktreeManager:
    """统一的 Worktree 管理器

    提供原子的 worktree 操作，支持事务管理和自动回滚。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化 Worktree 管理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.branch_mapper = None
        logger.info("WorktreeManager initialized", project_path=str(self.project_path))

    def _init_branch_mapper(self) -> None:
        """初始化分支映射器"""
        if self.branch_mapper is None:
            branch_mappings = self.config_manager.get_branch_mapping()
            self.branch_mapper = BranchNameMapper(branch_mappings)

    def add_worktree(
        self,
        branch: str,
        local: Optional[bool] = None,
        setup_symlinks: bool = True,
    ) -> Transaction:
        """添加 worktree，返回事务对象

        Args:
            branch: 分支名称
            local: 分支来源（None=自动，True=本地，False=远程）
            setup_symlinks: 是否创建符号链接

        Returns:
            事务对象

        Raises:
            ConfigException: 如果项目未初始化
            GitException: 如果分支不存在或创建失败
            WorktreeAlreadyExists: 如果 worktree 已存在
        """
        logger.info("Adding worktree", branch=branch, local=local)

        # 验证项目已初始化
        if not (self.project_path / ".gm.yaml").exists():
            raise ConfigException("项目未初始化。请先运行 gm init")

        # 初始化分支映射器
        self._init_branch_mapper()

        # 检查分支存在
        local_exists = self.git_client.check_branch_exists(branch)
        remote_exists = self._check_remote_branch_exists(branch)

        if local is True and not local_exists:
            raise GitException(f"本地分支不存在：{branch}")
        elif local is False and not remote_exists:
            raise GitException(f"远程分支不存在：{branch}")
        elif local is None:
            if not (local_exists or remote_exists):
                raise GitException(f"分支不存在（本地和远程均未找到）：{branch}")

        # 获取 worktree 路径
        # worktree 现在直接在项目根目录下（而不是 .gm 子目录）
        dir_name = self.branch_mapper.map_branch_to_dir(branch)
        worktree_path = self.project_path / dir_name

        # 检查 worktree 不存在
        if worktree_path.exists():
            raise WorktreeAlreadyExists(f"Worktree 已存在：{worktree_path}")

        # 创建事务
        tx = Transaction()

        # 添加获取远程分支的操作（如果需要）
        if local is False or (local is None and remote_exists):
            tx.add_operation(
                execute_fn=lambda: self.git_client.get_remote_branch(branch),
                description=f"Fetch remote branch {branch}",
            )

        # 添加创建 worktree 的操作
        tx.add_operation(
            execute_fn=lambda: self.git_client.create_worktree(worktree_path, branch),
            rollback_fn=lambda: self._rollback_worktree(worktree_path),
            description=f"Create worktree for branch {branch}",
        )

        # 添加符号链接操作
        if setup_symlinks:
            tx.add_operation(
                execute_fn=lambda: self.setup_shared_files(worktree_path),
                description=f"Setup symlinks in worktree {dir_name}",
            )

        # 添加配置更新操作
        tx.add_operation(
            execute_fn=lambda: self._update_config_add(branch, dir_name, worktree_path),
            description=f"Update configuration for worktree {dir_name}",
        )

        logger.info(
            "Worktree add transaction created",
            branch=branch,
            dir_name=dir_name,
            worktree_path=str(worktree_path),
        )

        return tx

    def delete_worktree(
        self,
        branch: str,
        delete_branch: bool = False,
        force: bool = False,
    ) -> Transaction:
        """删除 worktree，返回事务对象

        Args:
            branch: 分支名称
            delete_branch: 是否删除 Git 分支
            force: 是否强制删除

        Returns:
            事务对象

        Raises:
            ConfigException: 如果项目未初始化
            WorktreeNotFound: 如果 worktree 不存在
            GitException: 如果有未提交的改动且未指定 force
        """
        logger.info(
            "Deleting worktree",
            branch=branch,
            delete_branch=delete_branch,
            force=force,
        )

        # 验证项目已初始化
        if not (self.project_path / ".gm.yaml").exists():
            raise ConfigException("项目未初始化")

        # 初始化分支映射器
        self._init_branch_mapper()

        # 获取 worktree 路径
        # worktree 现在直接在项目根目录下（而不是 .gm 子目录）
        dir_name = self.branch_mapper.map_branch_to_dir(branch)
        worktree_path = self.project_path / dir_name

        # 检查 worktree 存在
        if not worktree_path.exists():
            raise WorktreeNotFound(f"Worktree 不存在：{branch}")

        # 检查未提交的改动
        if not force and self.git_client.has_uncommitted_changes(cwd=worktree_path):
            raise GitException(
                f"Worktree {branch} 有未提交的改动。使用 --force 选项强制删除。"
            )

        # 创建事务
        tx = Transaction()

        # 添加清理符号链接的操作
        tx.add_operation(
            execute_fn=lambda: self._cleanup_symlinks(worktree_path),
            description=f"Cleanup symlinks for worktree {dir_name}",
        )

        # 添加删除 worktree 的操作
        tx.add_operation(
            execute_fn=lambda: self._delete_worktree_impl(worktree_path, force),
            description=f"Delete worktree {dir_name}",
        )

        # 添加删除分支的操作
        if delete_branch:
            tx.add_operation(
                execute_fn=lambda: self._delete_branch_impl(branch),
                description=f"Delete branch {branch}",
            )

        # 添加配置更新操作
        tx.add_operation(
            execute_fn=lambda: self._update_config_del(branch),
            description=f"Update configuration after deleting worktree {dir_name}",
        )

        logger.info(
            "Worktree delete transaction created",
            branch=branch,
            worktree_path=str(worktree_path),
        )

        return tx

    def get_worktrees(self) -> List[Dict[str, Any]]:
        """获取所有 worktree 列表

        Returns:
            Worktree 信息列表
        """
        try:
            config = self.config_manager.load_config()
            worktrees_config = config.get("worktrees", {})

            worktrees = []
            for dir_name, info in worktrees_config.items():
                base_path = self.config_manager.get("worktree.base_path", ".gm")
                path = Path(info.get("path", ""))

                # 检查路径是否存在
                exists = path.exists() if path.is_absolute() else (self.project_path / path).exists()

                worktrees.append({
                    "directory": dir_name,
                    "branch": info.get("branch", "unknown"),
                    "path": str(path),
                    "exists": exists,
                })

            logger.info("Worktrees retrieved", count=len(worktrees))
            return worktrees

        except Exception as e:
            logger.error("Failed to get worktrees", error=str(e))
            return []

    def get_worktree_status(self, branch: str) -> Dict[str, Any]:
        """获取 worktree 状态

        Args:
            branch: 分支名称

        Returns:
            Worktree 状态信息
        """
        try:
            self._init_branch_mapper()

            # 获取 worktree 路径
            dir_name = self.branch_mapper.map_branch_to_dir(branch)
            base_path = self.config_manager.get("worktree.base_path", ".gm")
            worktree_path = self.project_path / base_path / dir_name

            status = {
                "branch": branch,
                "directory": dir_name,
                "path": str(worktree_path),
                "exists": worktree_path.exists(),
                "has_changes": False,
            }

            # 如果 worktree 存在，检查是否有未提交的改动
            if status["exists"]:
                status["has_changes"] = self.git_client.has_uncommitted_changes(
                    cwd=worktree_path
                )

            logger.info("Worktree status retrieved", branch=branch)
            return status

        except Exception as e:
            logger.error("Failed to get worktree status", branch=branch, error=str(e))
            return {
                "branch": branch,
                "exists": False,
                "has_changes": False,
                "error": str(e),
            }

    def setup_shared_files(self, worktree_path: Path) -> None:
        """为 worktree 设置共享文件的符号链接

        Args:
            worktree_path: worktree 路径

        Raises:
            Exception: 如果符号链接创建失败
        """
        try:
            shared_files = self.config_manager.get_shared_files()

            logger.info(
                "Setting up shared files",
                worktree_path=str(worktree_path),
                count=len(shared_files),
            )

            for file_name in shared_files:
                # 获取源文件路径（主分支中的文件）
                source_file = self.project_path / file_name
                # 获取目标链接路径（worktree 中的链接）
                target_link = worktree_path / file_name

                # 如果源文件不存在，跳过
                if not source_file.exists():
                    logger.warning(
                        "Shared file not found",
                        file=file_name,
                        path=str(source_file),
                    )
                    continue

                # 如果目标链接已存在，跳过
                if target_link.exists():
                    logger.warning(
                        "Target link already exists",
                        file=file_name,
                        path=str(target_link),
                    )
                    continue

                # 创建符号链接
                try:
                    # 使用相对路径以便于移植
                    relative_source = source_file.relative_to(target_link.parent.parent)
                    target_link.symlink_to(relative_source)
                    logger.info(
                        "Symlink created",
                        file=file_name,
                        source=str(relative_source),
                        target=str(target_link),
                    )
                except OSError as e:
                    logger.error(
                        "Failed to create symlink",
                        file=file_name,
                        source=str(source_file),
                        target=str(target_link),
                        error=str(e),
                    )
                    continue

            logger.info("Shared files setup completed")

        except Exception as e:
            logger.error("Failed to setup shared files", error=str(e))
            raise

    def cleanup_worktree(self, worktree_path: Path) -> None:
        """清理 worktree（删除目录和符号链接）

        Args:
            worktree_path: worktree 路径

        Raises:
            Exception: 如果清理失败
        """
        try:
            # 清理符号链接
            self._cleanup_symlinks(worktree_path)

            # 删除 worktree 目录
            if worktree_path.exists():
                shutil.rmtree(worktree_path)
                logger.info("Worktree directory removed", path=str(worktree_path))

        except Exception as e:
            logger.error("Failed to cleanup worktree", path=str(worktree_path), error=str(e))
            raise

    # 辅助方法

    def _check_remote_branch_exists(self, branch: str) -> bool:
        """检查远程分支是否存在

        Args:
            branch: 分支名称

        Returns:
            True 如果远程分支存在
        """
        try:
            remote_branches = self.git_client.get_branch_list(remote=True)
            return any(
                b == f"origin/{branch}" or b == branch
                for b in remote_branches
            )
        except Exception:
            return False

    def _rollback_worktree(self, worktree_path: Path) -> None:
        """回滚 worktree 创建

        Args:
            worktree_path: worktree 路径
        """
        try:
            self.git_client.delete_worktree(worktree_path, force=True)
            logger.info("Worktree deleted during rollback", path=str(worktree_path))
        except Exception as e:
            logger.error("Failed to rollback worktree", path=str(worktree_path), error=str(e))
            raise

    def _cleanup_symlinks(self, worktree_path: Path) -> None:
        """清理符号链接

        Args:
            worktree_path: worktree 路径
        """
        try:
            worktree_abs_path = worktree_path.resolve()
            search_dirs = [self.project_path, self.project_path / ".gm"]

            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue

                for item in search_dir.iterdir():
                    if item.is_symlink():
                        try:
                            target = item.resolve()
                            if target == worktree_abs_path or target.parent == worktree_abs_path:
                                item.unlink()
                                logger.info("Symlink removed", path=str(item))
                        except (OSError, ValueError):
                            logger.debug("Failed to check/remove symlink", path=str(item))

            logger.info("Symlinks cleanup completed", worktree=str(worktree_path))

        except Exception as e:
            logger.warning("Error during symlinks cleanup", error=str(e))

    def _delete_worktree_impl(self, worktree_path: Path, force: bool = False) -> None:
        """实现 worktree 删除

        Args:
            worktree_path: worktree 路径
            force: 是否强制删除
        """
        try:
            self.git_client.delete_worktree(worktree_path, force=force)
            logger.info("Worktree deleted via git", path=str(worktree_path), force=force)
        except Exception as e:
            logger.debug("Git worktree remove failed, attempting direct deletion", error=str(e))

        # 删除 worktree 目录
        if worktree_path.exists():
            shutil.rmtree(worktree_path)
            logger.info("Worktree directory removed", path=str(worktree_path))

    def _delete_branch_impl(self, branch: str) -> None:
        """实现分支删除

        Args:
            branch: 分支名称
        """
        try:
            self.git_client.delete_branch(branch, force=True)
            logger.info("Local branch deleted", branch=branch)
        except Exception as e:
            logger.warning("Failed to delete local branch", branch=branch, error=str(e))

        # 尝试删除远程分支
        try:
            self.git_client.run_command(
                ["git", "push", "origin", "--delete", branch],
                check=False,
            )
            logger.info("Remote branch deleted", branch=branch)
        except Exception as e:
            logger.warning("Failed to delete remote branch", branch=branch, error=str(e))

    def _update_config_add(self, branch: str, dir_name: str, worktree_path: Path) -> None:
        """更新配置文件以记录新的 worktree

        Args:
            branch: 分支名称
            dir_name: 目录名
            worktree_path: worktree 路径
        """
        try:
            config = self.config_manager.load_config()

            if "worktrees" not in config:
                config["worktrees"] = {}

            config["worktrees"][dir_name] = {
                "branch": branch,
                "path": str(worktree_path),
            }

            self.config_manager.save_config(config)
            logger.info(
                "Configuration updated",
                branch=branch,
                dir=dir_name,
                path=str(worktree_path),
            )

        except Exception as e:
            logger.error("Failed to update configuration", error=str(e))
            raise

    def _update_config_del(self, branch: str) -> None:
        """删除配置文件中的 worktree 记录

        Args:
            branch: 分支名称
        """
        try:
            config = self.config_manager.load_config()
            worktrees = config.get("worktrees", {})

            # 找到并删除该分支对应的 worktree
            for dir_name in list(worktrees.keys()):
                if worktrees[dir_name].get("branch") == branch:
                    del worktrees[dir_name]
                    break

            config["worktrees"] = worktrees
            self.config_manager.save_config(config)
            logger.info("Worktree removed from configuration", branch=branch)

        except Exception as e:
            logger.warning("Failed to update configuration", error=str(e))
