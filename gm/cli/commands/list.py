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
from gm.cli.utils.project_utils import find_gm_root

logger = get_logger("list_command")


class ListCommand:
    """工作树列表查看器"""

    def __init__(self, project_path: Optional[Path] = None):
        if project_path:
            self.project_path = Path(project_path)
        else:
            # 自动从当前目录向上查找 GM 项目根目录
            self.project_path = find_gm_root()

        # GitClient 应该在 .gm 目录执行命令（GM 项目的 git 仓库在 .gm/.git）
        self.gm_path = self.project_path / ".gm"
        self.git_client = GitClient(self.gm_path)
        self.config_manager = ConfigManager(self.project_path)

    def execute(self, verbose: bool = False) -> str:
        """执行列出操作
        
        使用 git worktree list 命令获取所有 worktree 并格式化输出。
        """
        try:
            # 从 git 获取 worktree 列表
            worktrees = self.git_client.list_worktrees()
            
            if not worktrees:
                return "没有找到任何 worktree。"
            
            # 格式化输出
            lines = []
            lines.append(f"GM Worktree 列表 ({len(worktrees)} 个)")
            lines.append("=" * 50)
            
            for wt in worktrees:
                path = wt.get("path", "未知")
                branch = wt.get("branch", "未知分支")
                head = wt.get("HEAD", "")[:8]  # 简短 hash
                
                # 解析分支名称（从 refs/heads/xxx 中提取）
                if branch and "refs/heads/" in branch:
                    branch = branch.replace("refs/heads/", "")
                
                lines.append(f"\n📁 {path}")
                if verbose:
                    lines.append(f"   分支: {branch}")
                    lines.append(f"   HEAD: {head}")
                else:
                    lines.append(f"   └─ {branch}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error("Failed to list worktrees", error=str(e))
            return f"获取 worktree 列表失败: {e}"


@click.command()
@click.option("-v", "--verbose", is_flag=True, help="显示详细信息")
@click.argument("project_path", required=False, default=".")
@click.pass_context
def list_command(ctx: click.Context, verbose: bool, project_path: str) -> None:
    """列出所有工作树"""
    try:
        cmd = ListCommand(Path(project_path))
        output = cmd.execute(verbose=verbose)
        click.echo(output)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)
