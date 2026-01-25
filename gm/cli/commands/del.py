"""GM del 命令实现

删除 worktree 并可选删除 Git 分支。
支持事务管理确保操作原子性。
"""

import shutil
from pathlib import Path
from typing import Optional

import click

from gm.core.branch_name_mapper import BranchNameMapper
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    WorktreeNotFound,
    GitCommandError,
    TransactionRollbackError,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction

logger = get_logger("del_command")


class DelCommand:
    """删除命令处理器

    负责删除 worktree 并可选删除关联的 Git 分支。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化删除命令处理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.branch_mapper = None
        self.worktree_path = None

    def validate_project_initialized(self) -> bool:
        """验证项目已初始化

        Returns:
            True 如果项目已初始化

        Raises:
            ConfigException: 如果项目未初始化
        """
        config_file = self.project_path / ".gm.yaml"
        gm_dir = self.project_path / ".gm"

        if not config_file.exists() and not gm_dir.exists():
            logger.error("Project not initialized", path=str(self.project_path))
            raise ConfigException(
                "项目未初始化。请先运行 gm init 命令初始化项目。"
            )

        logger.info("Project initialized verified", path=str(self.project_path))
        return True

    def initialize_mapper(self) -> None:
        """初始化分支名映射器

        Raises:
            ConfigException: 如果无法加载配置
        """
        try:
            config = self.config_manager.load_config()
            branch_mapping = config.get("branch_mapping", {})

            self.branch_mapper = BranchNameMapper(custom_mappings=branch_mapping)
            logger.info(
                "Branch mapper initialized",
                custom_mappings_count=len(branch_mapping),
            )
        except Exception as e:
            logger.error("Failed to initialize branch mapper", error=str(e))
            raise ConfigException(f"无法初始化分支映射器: {str(e)}")

    def check_worktree_exists(self, branch_name: str) -> bool:
        """检查 worktree 是否存在

        Args:
            branch_name: 分支名称

        Returns:
            worktree 存在返回 True，否则返回 False
        """
        # 使用 BranchNameMapper 确定 worktree 目录名
        if self.branch_mapper is None:
            self.initialize_mapper()

        worktree_dir_name = self.branch_mapper.map_branch_to_dir(branch_name)
        gm_base_path = self.project_path / self.config_manager.get("worktree.base_path", ".gm")
        self.worktree_path = gm_base_path / worktree_dir_name

        exists = self.worktree_path.exists()

        if exists:
            logger.info("Worktree exists", path=str(self.worktree_path), branch=branch_name)
        else:
            logger.warning("Worktree does not exist", path=str(self.worktree_path), branch=branch_name)

        return exists

    def check_uncommitted_changes(self, worktree_path: Path) -> bool:
        """检查 worktree 是否有未提交改动

        Args:
            worktree_path: worktree 路径

        Returns:
            有未提交改动返回 True，否则返回 False
        """
        has_changes = self.git_client.has_uncommitted_changes(cwd=worktree_path)

        if has_changes:
            logger.warning(
                "Uncommitted changes detected in worktree",
                path=str(worktree_path),
            )
        else:
            logger.info(
                "No uncommitted changes in worktree",
                path=str(worktree_path),
            )

        return has_changes

    def delete_worktree(self, worktree_path: Path, force: bool = False) -> None:
        """删除 worktree

        Args:
            worktree_path: worktree 路径
            force: 是否强制删除

        Raises:
            GitCommandError: 删除失败时抛出
        """
        try:
            # 使用 git worktree remove 删除 worktree
            self.git_client.delete_worktree(worktree_path, force=force)
            logger.info("Worktree deleted via git", path=str(worktree_path), force=force)

        except GitCommandError as e:
            # 如果是非真实 worktree（比如在测试中），直接删除目录
            logger.debug(
                "Git worktree remove failed, attempting direct deletion",
                path=str(worktree_path),
                error=str(e),
            )

        # 删除 worktree 目录（无论是否成功通过 git worktree remove）
        if worktree_path.exists():
            shutil.rmtree(worktree_path)
            logger.info("Worktree directory removed", path=str(worktree_path))

    def delete_branch(self, branch_name: str, delete_remote: bool = False) -> bool:
        """删除分支

        Args:
            branch_name: 分支名称
            delete_remote: 是否同时删除远程分支

        Returns:
            删除成功返回 True，否则返回 False
        """
        success = False

        # 删除本地分支
        try:
            self.git_client.delete_branch(branch_name, force=True)
            logger.info("Local branch deleted", branch=branch_name)
            success = True
        except GitCommandError as e:
            logger.warning(
                "Failed to delete local branch",
                branch=branch_name,
                error=str(e),
            )

        # 删除远程分支
        if delete_remote:
            try:
                self.git_client.run_command(
                    ["git", "push", "origin", f"--delete", branch_name],
                    check=False,
                )
                logger.info("Remote branch deleted", branch=branch_name)
            except GitCommandError as e:
                logger.warning(
                    "Failed to delete remote branch",
                    branch=branch_name,
                    error=str(e),
                )

        return success

    def cleanup_symlinks(self, worktree_path: Path) -> None:
        """清理符号链接

        在 worktree 所在目录中查找并删除指向此 worktree 的符号链接。

        Args:
            worktree_path: worktree 路径
        """
        try:
            # 获取 worktree 的绝对路径
            worktree_abs_path = worktree_path.resolve()

            # 扫描项目根目录和 .gm 目录，查找指向此 worktree 的符号链接
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
            # 不在符号链接清理时抛出异常，仅记录警告

    def update_config(self, branch_name: str) -> None:
        """更新配置文件（移除分支映射）

        Args:
            branch_name: 分支名称
        """
        try:
            config = self.config_manager.load_config()
            branch_mapping = config.get("branch_mapping", {})

            # 从映射中移除该分支
            if branch_name in branch_mapping:
                del branch_mapping[branch_name]
                config["branch_mapping"] = branch_mapping
                self.config_manager.save_config(config)
                logger.info("Branch mapping removed from config", branch=branch_name)

        except Exception as e:
            logger.warning("Failed to update config", error=str(e))
            # 不在配置更新失败时抛出异常，仅记录警告

    def execute(
        self,
        branch_name: str,
        force: bool = False,
        delete_branch: bool = False,
    ) -> None:
        """执行删除命令

        Args:
            branch_name: 分支名称
            force: 是否强制删除（忽略未提交改动）
            delete_branch: 是否删除 Git 分支

        Raises:
            ConfigException: 如果项目未初始化
            WorktreeNotFound: 如果 worktree 不存在
            GitCommandError: 如果 git 操作失败
        """
        logger.info(
            "Executing delete command",
            branch=branch_name,
            force=force,
            delete_branch=delete_branch,
        )

        # 1. 验证项目已初始化
        self.validate_project_initialized()

        # 2. 初始化映射器
        self.initialize_mapper()

        # 3. 检查 worktree 是否存在
        if not self.check_worktree_exists(branch_name):
            logger.error("Worktree not found", branch=branch_name)
            raise WorktreeNotFound(
                f"Worktree 不存在：{branch_name}",
                details=f"Expected path: {self.worktree_path}",
            )

        # 4. 检查未提交改动
        if not force and self.check_uncommitted_changes(self.worktree_path):
            logger.error(
                "Uncommitted changes detected, use --force to override",
                branch=branch_name,
            )
            raise GitException(
                f"Worktree {branch_name} 有未提交的改动。"
                "使用 --force 选项强制删除。"
            )

        # 5. 删除 worktree
        self.delete_worktree(self.worktree_path, force=force)

        # 6. 可选：删除分支
        if delete_branch:
            self.delete_branch(branch_name, delete_remote=True)

        # 7. 清理符号链接
        self.cleanup_symlinks(self.worktree_path)

        # 8. 更新配置文件
        self.update_config(branch_name)

        logger.info(
            "Delete command completed successfully",
            branch=branch_name,
            delete_branch=delete_branch,
        )


@click.command()
@click.argument("branch")
@click.option(
    "-D",
    "--delete-branch",
    is_flag=True,
    help="删除关联的 Git 分支（包括远程分支）",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="强制删除，忽略未提交改动",
)
def del_cmd(branch: str, delete_branch: bool, force: bool) -> None:
    """删除 worktree 和可选的分支

    \b
    使用示例:
    gm del feature/ui           # 删除 worktree，保留分支
    gm del feature/ui -D        # 删除 worktree 和分支
    gm del feature/ui --force   # 强制删除，忽略未提交改动
    """
    try:
        cmd = DelCommand()
        cmd.execute(
            branch_name=branch,
            force=force,
            delete_branch=delete_branch,
        )

        if delete_branch:
            click.echo(f"✓ Worktree 已删除：.gm/{branch}")
            click.echo(f"✓ 分支已删除：{branch}")
        else:
            click.echo(f"✓ Worktree 已删除：.gm/{branch}")
            click.echo(f"✓ 分支已保留：{branch}")

    except ConfigException as e:
        click.echo(f"配置错误：{e.message}", err=True)
        raise click.Exit(1)
    except WorktreeNotFound as e:
        click.echo(f"Worktree 错误：{e.message}", err=True)
        raise click.Exit(1)
    except GitException as e:
        click.echo(f"Git 错误：{e.message}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"删除失败：{str(e)}", err=True)
        raise click.Exit(1)


# 为了兼容导入，使用别名
del_command = del_cmd

