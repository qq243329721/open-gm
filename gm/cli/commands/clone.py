"""GM clone 命令实现

克隆仓库并初始化为 .gm worktree 结构。
"""

import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click

from gm.cli.commands.init import InitCommand
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    TransactionRollbackError,
    GitCommandError,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction

logger = get_logger("clone_command")


class CloneCommand:
    """克隆命令处理器

    负责克隆 Git 仓库并初始化为 .gm 结构。
    """

    def __init__(
        self,
        repo_url: str,
        project_path: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        no_init: bool = False,
    ):
        """初始化克隆命令处理器

        Args:
            repo_url: 仓库 URL
            project_path: 克隆目标路径，默认使用仓库名称
            branch: 初始分支，默认为仓库默认分支
            depth: shallow clone 的深度，默认不使用 shallow clone
            no_init: 是否仅克隆不初始化，默认为 False
        """
        self.repo_url = repo_url
        self.project_path = Path(project_path) if project_path else None
        self.branch = branch
        self.depth = depth
        self.no_init = no_init
        self.cloned_path: Optional[Path] = None

    def validate_repo_url(self) -> bool:
        """验证仓库 URL 有效性

        Returns:
            True 如果 URL 有效

        Raises:
            GitException: 如果 URL 无效
        """
        try:
            # 验证 URL 格式
            if not self.repo_url:
                raise GitException("仓库 URL 不能为空")

            # 支持多种 URL 格式
            # https://github.com/user/repo.git
            # git@github.com:user/repo.git
            # /path/to/repo
            # file:///path/to/repo
            # C:\path\to\repo (Windows)

            parsed = urlparse(self.repo_url)

            # 检查是本地路径还是远程 URL
            # 支持 Unix 路径和 Windows 路径
            is_unix_path = self.repo_url.startswith("/")
            is_windows_path = (len(self.repo_url) > 1 and
                              self.repo_url[1] == ":" and
                              self.repo_url[0].isalpha())
            is_file_url = parsed.scheme == "file"
            is_no_scheme = not parsed.scheme

            is_local_path = (
                is_unix_path or is_windows_path or is_file_url or
                (is_no_scheme and not self.repo_url.startswith("git@"))
            )
            is_remote_url = parsed.scheme in ("http", "https", "git")
            is_ssh_url = self.repo_url.startswith("git@")

            if not (is_local_path or is_remote_url or is_ssh_url):
                raise GitException(f"无效的仓库 URL 格式：{self.repo_url}")

            logger.info("Repository URL validated", url=self.repo_url)
            return True

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to validate repository URL", url=self.repo_url, error=str(e))
            raise GitException(f"验证仓库 URL 失败：{str(e)}")

    def determine_target_path(self) -> Path:
        """确定目标路径

        如果未指定目标路径，从仓库 URL 提取仓库名称。

        Returns:
            目标路径

        Raises:
            GitException: 如果无法确定目标路径
        """
        try:
            if self.project_path:
                return self.project_path

            # 从 URL 提取仓库名称
            # https://github.com/user/repo.git -> repo
            # git@github.com:user/repo.git -> repo
            # /path/to/repo -> repo
            url_path = self.repo_url.rstrip("/")

            if url_path.endswith(".git"):
                url_path = url_path[:-4]

            # 获取最后一个部分
            repo_name = url_path.split("/")[-1]

            if not repo_name:
                raise GitException(f"无法从 URL 提取仓库名称：{self.repo_url}")

            target_path = Path.cwd() / repo_name
            logger.info("Target path determined", url=self.repo_url, path=str(target_path))
            return target_path

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to determine target path", url=self.repo_url, error=str(e))
            raise GitException(f"确定目标路径失败：{str(e)}")

    def validate_target_path(self, target_path: Path) -> bool:
        """验证目标路径有效性

        Returns:
            True 如果路径有效

        Raises:
            GitException: 如果路径已存在且非空
        """
        try:
            if target_path.exists():
                # 检查目录是否为空
                if target_path.is_dir():
                    items = list(target_path.iterdir())
                    if items:
                        logger.error(
                            "Target path is not empty",
                            path=str(target_path),
                            items_count=len(items),
                        )
                        raise GitException(
                            f"目标路径已存在且不为空：{target_path}"
                        )
                else:
                    logger.error("Target path exists and is not a directory", path=str(target_path))
                    raise GitException(
                        f"目标路径存在但不是目录：{target_path}"
                    )

            # 验证父目录是否可写
            parent_dir = target_path.parent
            if not parent_dir.exists():
                logger.warning("Parent directory does not exist, will be created", path=str(parent_dir))
            elif not parent_dir.is_dir():
                raise GitException(f"父目录不是目录：{parent_dir}")

            logger.info("Target path validated", path=str(target_path))
            return True

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to validate target path", path=str(target_path), error=str(e))
            raise GitException(f"验证目标路径失败：{str(e)}")

    def clone_repository(self, target_path: Path) -> None:
        """克隆 Git 仓库

        Args:
            target_path: 克隆目标路径

        Raises:
            GitCommandError: 克隆失败时抛出
        """
        try:
            # 确保父目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建 git clone 命令
            cmd = ["git", "clone"]

            if self.depth:
                cmd.extend(["--depth", str(self.depth)])

            if self.branch:
                cmd.extend(["--branch", self.branch])

            cmd.extend([self.repo_url, str(target_path)])

            # 使用 GitClient 执行命令
            git_client = GitClient()
            git_client.run_command(cmd)

            self.cloned_path = target_path
            logger.info(
                "Repository cloned successfully",
                url=self.repo_url,
                path=str(target_path),
                branch=self.branch,
            )

        except GitCommandError as e:
            logger.error("Failed to clone repository", url=self.repo_url, error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during cloning", url=self.repo_url, error=str(e))
            raise GitCommandError(f"克隆失败：{str(e)}") from e

    def initialize_gm(self, repo_path: Path) -> None:
        """初始化为 .gm 结构

        Args:
            repo_path: 仓库路径

        Raises:
            ConfigException: 初始化失败时抛出
        """
        try:
            # 创建 InitCommand 实例
            init_cmd = InitCommand(repo_path)

            # 验证项目
            init_cmd.validate_project()

            # 检查是否已初始化
            if init_cmd.check_already_initialized():
                raise ConfigException("项目已初始化")

            # 自动初始化，不进行交互
            # 使用本地分支，主分支为当前分支或 main
            try:
                current_branch = init_cmd.git_client.get_current_branch()
                use_local = True
                main_branch = current_branch
            except Exception:
                use_local = True
                main_branch = "main"

            # 使用事务确保原子操作
            tx = Transaction()

            try:
                # 添加操作到事务
                tx.add_operation(
                    execute_fn=init_cmd.create_directory_structure,
                    rollback_fn=init_cmd._rollback_directory,
                    description="Create .gm directory structure",
                )

                tx.add_operation(
                    execute_fn=lambda: init_cmd.create_config(use_local, main_branch),
                    rollback_fn=init_cmd._rollback_config,
                    description="Create .gm.yaml configuration",
                )

                tx.add_operation(
                    execute_fn=lambda: init_cmd.setup_shared_files(main_branch),
                    description="Setup shared files",
                )

                # 提交事务
                tx.commit()

                logger.info("Repository initialized as GM project", path=str(repo_path))

            except TransactionRollbackError as e:
                logger.error("Failed to initialize GM project, transaction rolled back", error=str(e))
                raise ConfigException(f"初始化失败并已回滚：{str(e)}")

        except ConfigException:
            raise
        except Exception as e:
            logger.error("Failed to initialize GM project", path=str(repo_path), error=str(e))
            raise ConfigException(f"初始化失败：{str(e)}") from e

    def cleanup_on_failure(self, target_path: Path) -> None:
        """在失败时清理克隆的仓库

        Args:
            target_path: 克隆的路径
        """
        try:
            if target_path.exists():
                logger.info("Cleaning up cloned repository", path=str(target_path))
                shutil.rmtree(target_path)
                logger.info("Cloned repository removed", path=str(target_path))
        except Exception as e:
            logger.error("Failed to cleanup cloned repository", path=str(target_path), error=str(e))

    def execute(self) -> Path:
        """执行克隆和初始化

        Returns:
            克隆的仓库路径

        Raises:
            GitException: 如果 git 操作失败
            ConfigException: 如果配置操作失败
        """
        logger.info("Starting clone operation", url=self.repo_url, no_init=self.no_init)

        try:
            # 1. 验证仓库 URL
            self.validate_repo_url()

            # 2. 确定目标路径
            target_path = self.determine_target_path()

            # 3. 验证目标路径
            self.validate_target_path(target_path)

            # 4. 克隆仓库
            self.clone_repository(target_path)

            # 5. 初始化为 .gm 结构（如果不跳过）
            if not self.no_init:
                try:
                    self.initialize_gm(target_path)
                except Exception as e:
                    # 初始化失败时清理克隆的仓库
                    logger.error("Initialization failed, cleaning up", error=str(e))
                    self.cleanup_on_failure(target_path)
                    raise

            logger.info(
                "Clone operation completed successfully",
                url=self.repo_url,
                path=str(target_path),
            )
            return target_path

        except (GitException, ConfigException):
            raise
        except Exception as e:
            logger.error("Unexpected error during clone operation", error=str(e))
            raise GitException(f"克隆失败：{str(e)}") from e


@click.command()
@click.argument("repo_url")
@click.argument("project_path", required=False)
@click.option(
    "-b",
    "--branch",
    type=str,
    default=None,
    help="克隆时指定的初始分支",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="使用 shallow clone 的深度",
)
@click.option(
    "--no-init",
    is_flag=True,
    default=False,
    help="仅克隆，不初始化为 .gm 结构",
)
def clone(
    repo_url: str,
    project_path: Optional[str],
    branch: Optional[str],
    depth: Optional[int],
    no_init: bool,
) -> None:
    """克隆仓库并初始化为 .gm worktree 结构

    \b
    使用示例:
    gm clone https://github.com/user/repo.git
    gm clone https://github.com/user/repo.git /path/to/project
    gm clone https://github.com/user/repo.git -b develop
    gm clone https://github.com/user/repo.git --no-init
    """
    try:
        cmd = CloneCommand(
            repo_url=repo_url,
            project_path=project_path,
            branch=branch,
            depth=depth,
            no_init=no_init,
        )

        cloned_path = cmd.execute()

        click.echo(f"✓ 仓库已从以下位置克隆：{repo_url}")
        click.echo(f"✓ 位置：{cloned_path}")

        if not no_init:
            click.echo(f"✓ 已初始化为 GM 项目")
            click.echo(f"✓ .gm/ 目录已创建")
            click.echo(f"✓ .gm.yaml 配置文件已生成")
            click.echo(f"✓ 准备使用 gm add [BRANCH] 添加 worktree")
        else:
            click.echo(f"✓ 仅克隆，未进行初始化")

    except GitException as e:
        click.echo(f"Git 错误：{e.message}", err=True)
        raise click.Exit(1)
    except ConfigException as e:
        click.echo(f"配置错误：{e.message}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"克隆失败：{str(e)}", err=True)
        raise click.Exit(1)
