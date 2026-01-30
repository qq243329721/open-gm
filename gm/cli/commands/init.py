"""GM init 命令实现

初始化项目为 .gm worktree 结构，创建配置文件和目录结构。"""

from pathlib import Path
from typing import Optional, Dict, Any
import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import GitException, ConfigException
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction
from gm.core.data_structures import GMConfig
from gm.cli.utils.formatting import OutputFormatter, FormatterConfig, ProgressBar

logger = get_logger("init_command")


class InitCommand:
    """项目初始化命令处理器"""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)

    def validate_project(self) -> bool:
        """验证是否为有效的 Git 仓库"""
        try:
            self.git_client.get_repo_root()
            return True
        except GitException:
            raise ConfigException("当前目录不是 Git 仓库，请先运行 'git init'。")

    def check_already_initialized(self) -> bool:
        """检查项目是否已初始化"""
        config_file = self.project_path / "gm.yaml"
        return config_file.exists()

    def create_directory_structure(self) -> None:
        """创建 .gm 目录结构"""
        gm_dir = self.project_path / ".gm"
        gm_dir.mkdir(exist_ok=True)
        (gm_dir / "worktrees").mkdir(exist_ok=True)
        (gm_dir / "logs").mkdir(exist_ok=True)
        logger.info("Directory structure created")

    def _rollback_directory(self) -> None:
        """回滚目录创建"""
        import shutil
        gm_dir = self.project_path / ".gm"
        if gm_dir.exists():
            shutil.rmtree(gm_dir)

    def _rollback_config(self) -> None:
        """回滚配置创建"""
        config_file = self.project_path / "gm.yaml"
        if config_file.exists():
            config_file.unlink()

    def setup_shared_files(self, main_branch: str) -> None:
        """设置共享文件配置"""
        # 默认共享文件
        shared_files = [".env", "config.json", ".gitignore"]
        logger.info(f"Shared files setup for branch {main_branch}")

    def execute(self, yes: bool = False) -> None:
        """执行初始化"""
        self.validate_project()
        if self.check_already_initialized():
            click.echo("项目已初始化。")
            return

        tx = Transaction()
        tx.add_operation(
            execute_fn=self.create_directory_structure,
            rollback_fn=self._rollback_directory,
            description="创建 .gm 目录结构"
        )
        tx.add_operation(
            execute_fn=lambda: self.config_manager.save_config(GMConfig(initialized=True)),
            rollback_fn=self._rollback_config,
            description="生成 gm.yaml 配置文件"
        )
        
        tx.commit()
        click.echo("项目初始化成功！已生成 gm.yaml")


@click.command(name="init")
@click.argument("project_path", required=False, default=".")
@click.option("-y", "--yes", is_flag=True, help="跳过确认")
@click.pass_context
def init_cmd(ctx: click.Context, project_path: str, yes: bool) -> None:
    """初始化项目为 .gm worktree 结构"""
    try:
        cmd = InitCommand(Path(project_path))
        cmd.execute(yes=yes)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
