"""GM init 命令实现

初始化项目为 .gm worktree 结构。
"""

from pathlib import Path
from typing import Optional, Tuple

import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    TransactionRollbackError,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction

logger = get_logger("init_command")


class InitCommand:
    """初始化命令处理器

    负责初始化项目为 .gm worktree 结构。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化命令处理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)

    def validate_project(self) -> bool:
        """验证项目是否为 git 仓库

        Returns:
            True 如果是有效的 git 仓库

        Raises:
            GitException: 如果不是有效的 git 仓库
        """
        try:
            repo_root = self.git_client.get_repo_root()
            logger.info("Project validated as git repository", path=str(repo_root))
            return True
        except GitException as e:
            logger.error("Failed to validate project", error=str(e))
            raise GitException("不是有效的 Git 仓库。请在 Git 仓库中运行此命令。", details=str(e))

    def check_already_initialized(self) -> bool:
        """检查项目是否已初始化

        Returns:
            True 如果已初始化，False 如果未初始化
        """
        gm_dir = self.project_path / ".gm"
        config_file = self.project_path / ".gm.yaml"

        is_initialized = gm_dir.exists() or config_file.exists()

        if is_initialized:
            logger.warning("Project already initialized", path=str(self.project_path))

        return is_initialized

    def get_branch_config(self) -> Tuple[bool, str]:
        """交互式获取分支配置

        Returns:
            (use_local_branch, main_branch_name) 的元组
            - use_local_branch: 是否使用本地分支
            - main_branch_name: 主分支名称
        """
        # 询问是否使用本地分支
        use_local = click.confirm("是否使用本地分支？", default=True)

        # 获取主分支名称
        if use_local:
            # 对于本地分支，获取当前分支或询问
            try:
                current_branch = self.git_client.get_current_branch()
                default_branch = current_branch
            except Exception:
                default_branch = "main"
        else:
            default_branch = "main"

        main_branch = click.prompt(
            "请输入主分支名称",
            type=str,
            default=default_branch,
        )

        logger.info(
            "Branch configuration obtained",
            use_local=use_local,
            main_branch=main_branch,
        )

        return use_local, main_branch

    def create_directory_structure(self) -> None:
        """创建 .gm 目录结构

        Raises:
            Exception: 如果目录创建失败
        """
        gm_dir = self.project_path / ".gm"

        try:
            gm_dir.mkdir(parents=True, exist_ok=True)
            logger.info(".gm directory created", path=str(gm_dir))
        except OSError as e:
            logger.error("Failed to create .gm directory", error=str(e))
            raise

    def create_config(self, use_local: bool, main_branch: str) -> None:
        """生成 .gm.yaml 配置文件

        Args:
            use_local: 是否使用本地分支
            main_branch: 主分支名称

        Raises:
            ConfigException: 如果配置创建失败
        """
        try:
            # 加载默认配置
            config = self.config_manager.get_default_config()

            # 添加初始化配置
            config["initialized"] = True
            config["use_local_branch"] = use_local
            config["main_branch"] = main_branch

            # 保存配置
            self.config_manager.save_config(config)

            logger.info(
                "Configuration file created",
                path=str(self.config_manager.config_path),
                use_local=use_local,
                main_branch=main_branch,
            )
        except ConfigException as e:
            logger.error("Failed to create configuration", error=str(e))
            raise

    def setup_shared_files(self, main_branch: str) -> None:
        """初始化共享文件符号链接

        从主分支获取初始共享文件列表。

        Args:
            main_branch: 主分支名称
        """
        try:
            shared_files = self.config_manager.get_shared_files()

            logger.info(
                "Setting up shared files",
                count=len(shared_files),
                branch=main_branch,
            )

            # 注意：实际的符号链接创建将由后续的命令处理
            # 这里仅记录设置了哪些共享文件

            logger.info("Shared files configured", count=len(shared_files))
        except Exception as e:
            logger.error("Failed to setup shared files", error=str(e))
            raise

    def execute(self) -> None:
        """执行初始化命令

        Raises:
            GitException: 如果 git 操作失败
            ConfigException: 如果配置操作失败
            TransactionRollbackError: 如果事务回滚失败
        """
        logger.info("Initializing project", path=str(self.project_path))

        # 1. 验证项目
        self.validate_project()

        # 2. 检查是否已初始化
        if self.check_already_initialized():
            raise Exception("项目已初始化。如果要重新初始化，请手动删除 .gm 目录和 .gm.yaml 文件。")

        # 使用事务确保原子操作
        tx = Transaction()

        try:
            # 3. 交互式获取分支配置
            use_local, main_branch = self.get_branch_config()

            # 4. 添加操作到事务
            tx.add_operation(
                execute_fn=self.create_directory_structure,
                rollback_fn=self._rollback_directory,
                description="Create .gm directory structure",
            )

            tx.add_operation(
                execute_fn=lambda: self.create_config(use_local, main_branch),
                rollback_fn=self._rollback_config,
                description="Create .gm.yaml configuration",
            )

            tx.add_operation(
                execute_fn=lambda: self.setup_shared_files(main_branch),
                description="Setup shared files",
            )

            # 5. 提交事务
            tx.commit()

            logger.info("Project initialized successfully", path=str(self.project_path))

        except TransactionRollbackError as e:
            logger.error("Transaction rolled back", error=str(e))
            click.echo(f"错误：初始化失败并已回滚。{str(e)}")
            raise
        except Exception as e:
            logger.error("Initialization failed", error=str(e))
            raise

    def _rollback_directory(self) -> None:
        """回滚目录创建"""
        gm_dir = self.project_path / ".gm"
        if gm_dir.exists():
            import shutil
            shutil.rmtree(gm_dir)
            logger.info(".gm directory removed", path=str(gm_dir))

    def _rollback_config(self) -> None:
        """回滚配置文件"""
        config_file = self.project_path / ".gm.yaml"
        if config_file.exists():
            config_file.unlink()
            logger.info("Configuration file removed", path=str(config_file))


@click.command()
@click.argument("project_path", required=False, default=".")
def init(project_path: str) -> None:
    """初始化项目为 .gm worktree 结构

    \b
    使用示例:
    gm init              # 初始化当前目录
    gm init /path/to/project  # 初始化指定目录
    """
    try:
        cmd = InitCommand(project_path)
        cmd.execute()

        click.echo("✓ 项目初始化成功")
        click.echo(f"✓ .gm/ 目录已创建")
        click.echo(f"✓ .gm.yaml 配置文件已生成")
        click.echo(f"✓ 准备使用 gm add [BRANCH] 添加 worktree")

    except GitException as e:
        click.echo(f"Git 错误：{e.message}", err=True)
        raise click.Exit(1)
    except ConfigException as e:
        click.echo(f"配置错误：{e.message}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"初始化失败：{str(e)}", err=True)
        raise click.Exit(1)
