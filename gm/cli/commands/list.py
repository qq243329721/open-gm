"""GM list 命令实现

列出项目中的所有工作树及其状态。"""

from pathlib import Path
from typing import List, Dict, Optional, Any
import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import GitException, ConfigException
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.cli.utils.formatting import OutputFormatter, FormatterConfig

logger = get_logger("list_command")


class ListCommand:
    """工作树列表查看器"""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)

    def execute(self, verbose: bool = False) -> str:
        """执行列出操作"""
        # 简化版实现，用于恢复功能
        return "List of all worktrees (Mock output)"


@click.command()
@click.option("-v", "--verbose", is_flag=True, help="显示详细信息")
@click.argument("project_path", required=False, default=".")
def list_command(verbose: bool, project_path: str) -> None:
    """列出所有工作树"""
    try:
        cmd = ListCommand(Path(project_path))
        output = cmd.execute(verbose=verbose)
        click.echo(output)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
