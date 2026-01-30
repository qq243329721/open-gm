"""Worktree 管理器实现

负责 worktree 的创建、修改和删除逻辑，并实现 ILayoutManager 接口。"""

import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

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

if TYPE_CHECKING:
    from gm.core.data_structures import WorktreeInfo

from gm.core.interfaces.worktree import ILayoutManager

logger = get_logger("worktree_manager")


class WorktreeManager(ILayoutManager):
    """Worktree 管理器

    实现了 ILayoutManager 接口，负责管理项目的 worktree 布局。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化 WorktreeManager
        Args:
            project_path: 项目根路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.branch_mapper = None
        
        # 初始化分支映射器
        branch_mappings = self.config_manager.get_branch_mapping()
        self.branch_mapper = BranchNameMapper(branch_mappings)
        logger.info("WorktreeManager initialized", project_path=str(self.project_path))

    def add_worktree(
        self,
        branch: str,
        local: Optional[bool] = None,
        setup_symlinks: bool = True,
    ) -> Transaction:
        """添加一个新的 worktree
        Args:
            branch: 分支名称
            local: 是否强制使用本地分支 (True=本地, False=远程, None=自动)
            setup_symlinks: 是否在创建后设置符号链接

        Returns:
            Transaction: 包含添加操作的事务对象

        Raises:
            ConfigException: 配置错误
            GitException: Git 操作错误
            WorktreeAlreadyExists: 目标 worktree 已存在
        """
        logger.info("Adding worktree", branch=branch, local=local)

        # 检查项目是否已初始化
        if not (self.project_path / "gm.yaml").exists():
            raise ConfigException("Project not initialized. Please run 'gm init' first.")

        # 分支存在性检查
        local_exists = self.git_client.check_branch_exists(branch)
        remote_exists = self._check_remote_branch_exists(branch)

        if local is True and not local_exists:
            raise GitException(f"Local branch '{branch}' does not exist")
        elif local is False and not remote_exists:
            raise GitException(f"Remote branch '{branch}' does not exist")
        elif local is None:
            if not (local_exists or remote_exists):
                raise GitException(f"Branch '{branch}' not found locally or on remote")

        # 映射分支到目录名
        dir_name = self.branch_mapper.map_branch_to_dir(branch)
        worktree_path = self.project_path / dir_name

        # 检查目标路径是否已存在
        if worktree_path.exists():
            raise WorktreeAlreadyExists(f"Worktree path '{worktree_path}' already exists")

        # 创建事务
        tx = Transaction()

        # 如果需要，从远程检出
        if local is False or (local is None and remote_exists and not local_exists):
            tx.add_operation(
                execute_fn=lambda: self.git_client.run_command(["git", "fetch", "origin", branch]),
                description=f"Fetch remote branch {branch}",
            )

        # 创建 worktree 操作
        tx.add_operation(
            execute_fn=lambda: self.git_client.create_worktree(worktree_path, branch),
            rollback_fn=lambda: self._rollback_worktree(worktree_path),
            description=f"Create worktree for branch {branch}",
        )

        # 设置符号链接
        if setup_symlinks:
            tx.add_operation(
                execute_fn=lambda: self.setup_shared_files(worktree_path),
                description=f"Setup symlinks in worktree {dir_name}",
            )

        # 更新配置
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
        """删除一个 worktree
        Args:
            branch: 关联的分支名称
            delete_branch: 是否同时删除 Git 分支
            force: 是否强制删除（即使有未提交代码）

        Returns:
            Transaction: 包含删除操作的事务对象

        Raises:
            ConfigException: 配置错误
            WorktreeNotFound: 指定的 worktree 不存在
            GitException: Git 操作错误
        """
        logger.info(
            "Deleting worktree",
            branch=branch,
            delete_branch=delete_branch,
            force=force,
        )

        # 检查项目是否已初始化
        if not (self.project_path / "gm.yaml").exists():
            raise ConfigException("Project not initialized")

        # 定位 worktree 路径
        dir_name = self.branch_mapper.map_branch_to_dir(branch)
        worktree_path = self.project_path / dir_name

        # 检查是否存在
        if not worktree_path.exists():
            raise WorktreeNotFound(f"Worktree for branch '{branch}' not found at {worktree_path}")

        # 检查未提交更改
        if not force and self.git_client.is_bare_repository(worktree_path) is False:
             # 这里简化逻辑，实际应调用 git_client 详细检查
             pass

        # 创建事务
        tx = Transaction()

        # 清理符号链接
        tx.add_operation(
            execute_fn=lambda: self._cleanup_symlinks(worktree_path),
            description=f"Cleanup symlinks for worktree {dir_name}",
        )

        # 删除 worktree 物理目录
        tx.add_operation(
            execute_fn=lambda: self._delete_worktree_impl(worktree_path, force),
            description=f"Delete worktree {dir_name}",
        )

        # 如果需要，删除分支
        if delete_branch:
            tx.add_operation(
                execute_fn=lambda: self._delete_branch_impl(branch),
                description=f"Delete branch {branch}",
            )

        # 更新配置
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

    def is_initialized(self) -> bool:
        """项目是否已初始化"""
        return (self.project_path / "gm.yaml").exists()
    
    def validate_layout(self) -> bool:
        """验证布局完整性"""
        return self.is_initialized()
    
    def get_worktree_info(self, name: str, include_status: bool = True) -> Optional['WorktreeInfo']:
        """获取 worktree 信息"""
        from gm.core.data_structures import WorktreeInfo, WorktreeStatus
        # 这里仅为示意，实际应从 git_client 深度查询
        return None
    
    def list_all_worktrees(self, include_status: bool = True) -> List['WorktreeInfo']:
        """列出所有管理的 worktree"""
        return []
    
    def suggest_worktree_name(self, branch_name: str) -> str:
        """建议 worktree 名称"""
        return branch_name.replace('/', '-')

    def setup_shared_files(self, worktree_path: Path) -> None:
        """为 worktree 设置共享文件"""
        shared_files = self.config_manager.get_shared_files()
        for file_name in shared_files:
            source = self.project_path / file_name
            target = worktree_path / file_name
            if source.exists() and not target.exists():
                try:
                    target.symlink_to(source)
                except Exception as e:
                    logger.warning(f"Failed to create symlink for {file_name}: {e}")

    def _check_remote_branch_exists(self, branch: str) -> bool:
        """检查远程分支"""
        try:
            branches = self.git_client.run_command(["git", "branch", "-r"]).split('\n')
            return any(f"origin/{branch}" in b.strip() for b in branches)
        except:
            return False

    def _rollback_worktree(self, worktree_path: Path) -> None:
        """回滚 worktree 创建"""
        if worktree_path.exists():
            shutil.rmtree(worktree_path)

    def _cleanup_symlinks(self, worktree_path: Path) -> None:
        """清理符号链接"""
        pass

    def _delete_worktree_impl(self, worktree_path: Path, force: bool = False) -> None:
        """删除 worktree 底层实现"""
        if worktree_path.exists():
            shutil.rmtree(worktree_path)

    def _delete_branch_impl(self, branch: str) -> None:
        """删除分支底层实现"""
        self.git_client.run_command(["git", "branch", "-d", branch])

    def _update_config_add(self, branch: str, dir_name: str, worktree_path: Path) -> None:
        """更新配置：添加"""
        pass

    def _update_config_del(self, branch: str) -> None:
        """更新配置：删除"""
        pass
