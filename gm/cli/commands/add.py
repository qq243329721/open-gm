"""GM add 命令实现

添加新的 worktree 并关联分支。
支持自动检测分支、强制本地分支或强制远程分支。
"""

from pathlib import Path
from typing import Optional, Tuple, List
import fnmatch

import click

from gm.core.branch_name_mapper import BranchNameMapper
from gm.core.config_manager import ConfigManager
from gm.core.cache_manager import get_cache_manager, TTLInvalidationStrategy
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
from gm.core.shared_file_manager import SharedFileManager
from gm.cli.utils import OutputFormatter, InteractivePrompt, ProgressBar, FormatterConfig

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
        config_file = self.project_path / "gm.yaml"

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

    def get_worktree_path(self, dir_name: str, branch_name: str) -> Path:
        """获取 worktree 的完整路径
        
        Args:
            dir_name: 目录名
            branch_name: 分支名
        
        Returns:
            完整的 worktree 路径
        """
        # 主分支在根目录本身，其他分支直接在项目根目录下创建
        if branch_name == self.config_manager.load_config().main_branch:
            worktree_path = self.project_path
        else:
            worktree_path = self.project_path / dir_name
        
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

        使用 SharedFileManager 处理符号链接创建。

        Args:
            worktree_path: worktree 路径

        Raises:
            Exception: 如果符号链接创建失败
        """
        try:
            shared_file_manager = SharedFileManager(
                main_branch_path=self.project_path,
                config_manager=self.config_manager
            )

            logger.info(
                "Setting up symlinks for worktree",
                worktree_path=str(worktree_path),
            )

            result = shared_file_manager.setup_shared_files(worktree_path)

            logger.info(
                "Symlinks setup completed",
                worktree_path=str(worktree_path),
                success=result
            )

        except Exception as e:
            logger.error("Failed to setup symlinks", error=str(e))
            raise

    def match_branch_pattern(self, pattern: str) -> List[str]:
        """使用模糊匹配查找分支

        支持通配符模式匹配分支名。

        Args:
            pattern: 分支名称模式（支持 * 和 ? 通配符）

        Returns:
            匹配的分支名列表

        Raises:
            GitException: 如果获取分支列表失败
        """
        try:
            # 获取本地分支
            local_branches = self.git_client.get_branch_list(remote=False)
            # 获取远程分支
            remote_branches = self.git_client.get_branch_list(remote=True)

            all_branches = local_branches + remote_branches

            # 使用 fnmatch 进行模糊匹配
            matched = [b for b in all_branches if fnmatch.fnmatch(b, pattern)]

            logger.info(
                "Branch pattern matched",
                pattern=pattern,
                matched_count=len(matched)
            )

            return matched
        except GitException as e:
            logger.error("Failed to match branch pattern", pattern=pattern, error=str(e))
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

            # 记录新的 worktree
            current_config.worktrees[dir_name] = {
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
            worktree_path = self.get_worktree_path(dir_name, branch_name)

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
@click.option(
    "-p",
    "--branch-pattern",
    is_flag=False,
    flag_value=True,
    type=bool,
    help="启用分支名称模式匹配（支持 * 和 ? 通配符）",
)
@click.option(
    "--auto-create",
    is_flag=True,
    help="从远程分支自动创建本地分支",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="跳过确认提示",
)
@click.pass_context
def add(
    ctx: click.Context,
    branch: str,
    local: bool,
    remote: bool,
    branch_pattern: bool,
    auto_create: bool,
    yes: bool
) -> None:
    """添加新的 worktree 并关联分支

    \b
    使用示例:
    gm add feature/new-ui           # 自动检测分支（优先远程）
    gm add feature/new-ui -l        # 强制使用本地分支
    gm add feature/new-ui -r        # 强制使用远程分支
    gm add "feature/*" -p           # 使用模式匹配选择分支
    gm add feature/new-ui -r --auto-create  # 从远程创建本地分支
    """
    # 从全局上下文获取配置
    verbose = ctx.obj.get('verbose', False)
    no_color = ctx.obj.get('no_color', False)
    formatter = OutputFormatter(FormatterConfig(no_color=no_color))

    try:
        # 确定分支来源
        branch_source = None
        if local and remote:
            click.echo(formatter.error("不能同时指定 -l 和 -r"), err=True)
            raise SystemExit(1)

        if local:
            branch_source = True
        elif remote:
            branch_source = False
        # 否则 branch_source 保持为 None，使用自动检测

        cmd = AddCommand()

        # 处理分支模式匹配
        selected_branch = branch
        if branch_pattern:
            matches = cmd.match_branch_pattern(branch)

            if not matches:
                click.echo(formatter.error(f"没有找到匹配 '{branch}' 的分支"), err=True)
                raise SystemExit(1)

            if len(matches) == 1:
                selected_branch = matches[0]
                if verbose:
                    click.echo(formatter.info(f"自动选择匹配的分支: {selected_branch}"))
            else:
                # 多个匹配，交互式选择
                click.echo(formatter.info(f"找到 {len(matches)} 个匹配的分支"))
                selected_branch = InteractivePrompt.choose(
                    "请选择要添加的分支:",
                    matches
                )

        # 显示操作摘要
        if not yes:
            summary_items = [
                ("分支", selected_branch),
                ("分支来源", "本地" if branch_source is True else "远程" if branch_source is False else "自动检测"),
                ("自动创建", "是" if auto_create else "否"),
            ]
            InteractivePrompt.show_summary("添加 Worktree", summary_items)

            if not InteractivePrompt.confirm("确认添加？", default=True):
                click.echo(formatter.warning("操作已取消"))
                raise SystemExit(0)

        # 显示进度
        progress = ProgressBar(3, FormatterConfig(no_color=no_color), prefix="  ")

        # 执行添加
        click.echo(formatter.info("Adding worktree..."))
        cmd.execute(selected_branch, local=branch_source)
        progress.update(1)

        if verbose:
            click.echo(formatter.info("Worktree created successfully"))

        # 如果需要自动创建本地分支
        if auto_create and branch_source is False:
            click.echo(formatter.info("Creating local branch..."))
            try:
                cmd.git_client.create_branch(selected_branch)
                progress.update(1)
                if verbose:
                    click.echo(formatter.info("Local branch created successfully"))
            except GitException as e:
                logger.warning("Failed to auto-create branch", error=str(e))

        progress.update(1)

        # 获取映射后的目录名用于输出
        mapper = BranchNameMapper(cmd.config_manager.get_branch_mapping())
        dir_name = mapper.map_branch_to_dir(selected_branch)

        click.echo()
        click.echo(formatter.success("Successfully added worktree for branch"))
        click.echo(f"  Branch: {selected_branch}")
        click.echo(f"  Worktree path: .gm/{dir_name}")
        click.echo(formatter.info(f"Ready to use: cd .gm/{dir_name}"))

    except ConfigException as e:
        click.echo(formatter.error(f"Configuration error: {e.message}"), err=True)
    except GitException as e:
        click.echo(formatter.error(f"Git error: {e.message}"), err=True)
    except Exception as e:
        click.echo(formatter.error(f"Operation failed and rolled back: {str(e)}"), err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise SystemExit(1)
