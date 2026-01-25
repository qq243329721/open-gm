"""GM add 命令实现

添加新的 worktree 并关联分支。
支持自动检测分支、强制本地分支或强制远程分支。
"""

from pathlib import Path
from typing import Optional, Tuple

import click

from gm.core.branch_name_mapper import BranchNameMapper
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    WorktreeAlreadyExists,
    TransactionRollbackError,
    GitCommandError,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction

logger = get_logger("add_command")


class AddCommand:
    """添加 worktree 命令处理器

    负责添加新的 worktree 并关联分支。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化添加命令处理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.branch_mapper = None

    def validate_project_initialized(self) -> bool:
        """验证项目是否已初始化

        Returns:
            True 如果项目已初始化

        Raises:
            ConfigException: 如果项目未初始化
        """
        config_file = self.project_path / ".gm.yaml"

        if not config_file.exists():
            logger.error("Project not initialized", path=str(self.project_path))
            raise ConfigException(
                "项目尚未初始化。请先运行 gm init",
                details={"config_file": str(config_file)},
            )

        logger.info("Project verified as initialized", path=str(self.project_path))
        return True

    def check_branch_exists(self, branch_name: str, local: Optional[bool] = None) -> Tuple[bool, str]:
        """检查分支是否存在

        支持三种模式：
        1. local=None: 自动检测（优先远程分支）
        2. local=True: 仅检查本地分支
        3. local=False: 仅检查远程分支

        Args:
            branch_name: 分支名称
            local: 分支来源限制

        Returns:
            (exists, branch_type) 元组，branch_type 为 'local', 'remote' 或 None

        Raises:
            GitException: 如果分支既不存在于本地也不存在于远程
        """
        logger.info("Checking branch existence", branch=branch_name, local=local)

        # 检查本地分支
        local_exists = self.git_client.check_branch_exists(branch_name)
        logger.debug("Local branch check result", branch=branch_name, exists=local_exists)

        # 检查远程分支
        remote_exists = False
        try:
            remote_branches = self.git_client.get_branch_list(remote=True)
            # 远程分支列表通常包含 "origin/" 前缀
            remote_exists = any(
                b == f"origin/{branch_name}" or b == branch_name
                for b in remote_branches
            )
            logger.debug("Remote branch check result", branch=branch_name, exists=remote_exists)
        except GitException as e:
            logger.warning("Failed to check remote branches", error=str(e))

        # 根据 local 参数返回结果
        if local is True:
            # 仅检查本地分支
            if not local_exists:
                raise GitException(
                    f"本地分支不存在: {branch_name}",
                    details={"branch": branch_name, "type": "local"},
                )
            return True, "local"

        elif local is False:
            # 仅检查远程分支
            if not remote_exists:
                raise GitException(
                    f"远程分支不存在: {branch_name}",
                    details={"branch": branch_name, "type": "remote"},
                )
            # 如果仅指定远程，需要获取远程分支
            self.git_client.get_remote_branch(branch_name)
            return True, "remote"

        else:
            # 自动检测：优先使用远程分支
            if remote_exists:
                logger.info(
                    "Remote branch detected, fetching remote branch",
                    branch=branch_name,
                )
                self.git_client.get_remote_branch(branch_name)
                return True, "remote"

            if local_exists:
                logger.info("Local branch detected", branch=branch_name)
                return True, "local"

            # 分支不存在
            raise GitException(
                f"分支不存在（本地和远程均未找到）: {branch_name}",
                details={"branch": branch_name},
            )

    def map_branch_to_dir(self, branch_name: str) -> str:
        """将分支名映射到目录名

        Args:
            branch_name: 分支名称

        Returns:
            映射后的目录名

        Raises:
            Exception: 如果映射失败
        """
        # 初始化分支映射器（如果未初始化）
        if self.branch_mapper is None:
            branch_mappings = self.config_manager.get_branch_mapping()
            self.branch_mapper = BranchNameMapper(branch_mappings)

        mapped_name = self.branch_mapper.map_branch_to_dir(branch_name)
        logger.info(
            "Branch mapped to directory",
            branch=branch_name,
            mapped_to=mapped_name,
        )

        return mapped_name

    def get_worktree_path(self, dir_name: str) -> Path:
        """获取 worktree 的完整路径

        Args:
            dir_name: 目录名

        Returns:
            完整的 worktree 路径
        """
        base_path = self.config_manager.get("worktree.base_path", ".gm")
        worktree_path = self.project_path / base_path / dir_name

        logger.debug("Worktree path calculated", path=str(worktree_path))

        return worktree_path

    def check_worktree_not_exists(self, worktree_path: Path) -> bool:
        """检查 worktree 是否不存在

        Args:
            worktree_path: worktree 路径

        Returns:
            True 如果 worktree 不存在

        Raises:
            WorktreeAlreadyExists: 如果 worktree 已存在
        """
        if worktree_path.exists():
            logger.error("Worktree already exists", path=str(worktree_path))
            raise WorktreeAlreadyExists(
                f"Worktree 已存在: {worktree_path}",
                details={"path": str(worktree_path)},
            )

        logger.info("Verified worktree does not exist", path=str(worktree_path))
        return True

    def create_worktree(self, worktree_path: Path, branch_name: str) -> None:
        """创建 worktree

        Args:
            worktree_path: worktree 路径
            branch_name: 关联的分支名

        Raises:
            GitException: 如果创建失败
        """
        try:
            self.git_client.create_worktree(worktree_path, branch_name)
            logger.info(
                "Worktree created successfully",
                path=str(worktree_path),
                branch=branch_name,
            )
        except GitCommandError as e:
            logger.error(
                "Failed to create worktree",
                path=str(worktree_path),
                branch=branch_name,
                error=str(e),
            )
            raise

    def setup_symlinks(self, worktree_path: Path) -> None:
        """为 worktree 创建共享文件的符号链接

        Args:
            worktree_path: worktree 路径

        Raises:
            Exception: 如果符号链接创建失败
        """
        try:
            shared_files = self.config_manager.get_shared_files()

            logger.info(
                "Setting up symlinks",
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
                        "Shared file not found in main branch",
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
                    # 继续处理其他文件，不中断流程
                    continue

            logger.info("Symlinks setup completed")

        except Exception as e:
            logger.error("Failed to setup symlinks", error=str(e))
            raise

    def update_config(self, branch_name: str, dir_name: str, worktree_path: Path) -> None:
        """更新配置文件记录新的 worktree

        Args:
            branch_name: 分支名
            dir_name: 目录名
            worktree_path: worktree 路径

        Raises:
            ConfigException: 如果配置更新失败
        """
        try:
            # 加载当前配置
            current_config = self.config_manager.load_config()

            # 初始化 worktrees 配置
            if "worktrees" not in current_config:
                current_config["worktrees"] = {}

            # 记录新的 worktree
            current_config["worktrees"][dir_name] = {
                "branch": branch_name,
                "path": str(worktree_path),
            }

            # 保存更新后的配置
            self.config_manager.save_config(current_config)

            logger.info(
                "Configuration updated",
                branch=branch_name,
                dir=dir_name,
                path=str(worktree_path),
            )

        except ConfigException as e:
            logger.error("Failed to update configuration", error=str(e))
            raise

    def execute(
        self,
        branch_name: str,
        local: Optional[bool] = None,
    ) -> None:
        """执行添加 worktree 命令

        Args:
            branch_name: 要添加的分支名
            local: 分支来源限制（None=自动，True=本地，False=远程）

        Raises:
            ConfigException: 如果项目配置异常
            GitException: 如果 git 操作异常
            WorktreeAlreadyExists: 如果 worktree 已存在
            TransactionRollbackError: 如果事务回滚失败
        """
        logger.info(
            "Adding worktree",
            branch=branch_name,
            project_path=str(self.project_path),
            local=local,
        )

        try:
            # 1. 验证项目已初始化
            self.validate_project_initialized()

            # 2. 检查分支存在
            branch_exists, branch_type = self.check_branch_exists(branch_name, local)

            # 3. 将分支名映射为目录名
            dir_name = self.map_branch_to_dir(branch_name)

            # 4. 获取 worktree 完整路径
            worktree_path = self.get_worktree_path(dir_name)

            # 5. 检查 worktree 不存在
            self.check_worktree_not_exists(worktree_path)

            # 使用事务确保原子操作
            tx = Transaction()

            # 6. 添加创建 worktree 的操作
            tx.add_operation(
                execute_fn=lambda: self.create_worktree(worktree_path, branch_name),
                rollback_fn=lambda: self._rollback_worktree(worktree_path),
                description=f"Create worktree for branch {branch_name}",
            )

            # 7. 添加创建符号链接的操作
            tx.add_operation(
                execute_fn=lambda: self.setup_symlinks(worktree_path),
                description=f"Setup symlinks in worktree {dir_name}",
            )

            # 8. 添加更新配置的操作
            tx.add_operation(
                execute_fn=lambda: self.update_config(branch_name, dir_name, worktree_path),
                description=f"Update configuration for worktree {dir_name}",
            )

            # 9. 提交事务
            tx.commit()

            logger.info(
                "Worktree added successfully",
                branch=branch_name,
                dir=dir_name,
                path=str(worktree_path),
            )

        except (ConfigException, GitException, WorktreeAlreadyExists) as e:
            logger.error("Failed to add worktree", error=str(e))
            raise
        except TransactionRollbackError as e:
            logger.error("Transaction rolled back", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during add command", error=str(e))
            raise

    def _rollback_worktree(self, worktree_path: Path) -> None:
        """回滚 worktree 创建

        Args:
            worktree_path: worktree 路径
        """
        try:
            self.git_client.delete_worktree(worktree_path, force=True)
            logger.info("Worktree deleted during rollback", path=str(worktree_path))
        except GitCommandError as e:
            logger.error("Failed to rollback worktree", path=str(worktree_path), error=str(e))
            raise


@click.command()
@click.argument("branch")
@click.option(
    "-l",
    "--local",
    is_flag=True,
    help="强制使用本地分支",
)
@click.option(
    "-r",
    "--remote",
    is_flag=True,
    help="强制使用远程分支",
)
def add(branch: str, local: bool, remote: bool) -> None:
    """添加新的 worktree 并关联分支

    \b
    使用示例:
    gm add feature/new-ui       # 自动检测分支（优先远程）
    gm add feature/new-ui -l    # 强制使用本地分支
    gm add feature/new-ui -r    # 强制使用远程分支
    """
    try:
        # 确定分支来源
        branch_source = None
        if local and remote:
            click.echo("错误：不能同时指定 -l 和 -r", err=True)
            raise click.Exit(1)

        if local:
            branch_source = True
        elif remote:
            branch_source = False
        # 否则 branch_source 保持为 None，使用自动检测

        cmd = AddCommand()
        cmd.execute(branch, local=branch_source)

        # 获取映射后的目录名用于输出
        mapper = BranchNameMapper(cmd.config_manager.get_branch_mapping())
        dir_name = mapper.map_branch_to_dir(branch)

        click.echo("✓ 成功为分支添加 worktree")
        click.echo(f"✓ 分支: {branch}")
        click.echo(f"✓ Worktree 创建于: .gm/{dir_name}")
        click.echo(f"✓ 准备使用: cd .gm/{dir_name}")

    except ConfigException as e:
        click.echo(f"配置错误：{e.message}", err=True)
        raise click.Exit(1)
    except GitException as e:
        click.echo(f"Git 错误：{e.message}", err=True)
        raise click.Exit(1)
    except WorktreeAlreadyExists as e:
        click.echo(f"错误：{e.message}", err=True)
        raise click.Exit(1)
    except TransactionRollbackError as e:
        click.echo(f"错误：操作失败并已回滚。{str(e)}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"错误：{str(e)}", err=True)
        raise click.Exit(1)
