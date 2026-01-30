"""GM status 命令

查看项目工作树的总体状态或特定工作树的详细状态。"""

import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    WorktreeNotFound,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.branch_name_mapper import BranchNameMapper
from gm.cli.utils import find_gm_root

logger = get_logger("status_command")


class StatusCommand:
    """状态查看命令实现类"""

    def __init__(self, project_path: Optional[Path] = None):
        """初始化
        Args:
            project_path: 项目路径，默认为自动查找
        """
        if project_path:
            self.project_path = Path(project_path)
        else:
            # 自动从当前目录向上查找 GM 项目根目录
            self.project_path = find_gm_root()

        # GitClient 应该在 .gm 目录执行命令（GM 项目的 git 仓库在 .gm/.git）
        self.gm_path = self.project_path / ".gm"
        self.git_client = GitClient(self.gm_path)
        self.config_manager = ConfigManager(self.project_path)
        self.mapper = BranchNameMapper()

    def get_current_location(self) -> str:
        """确定当前所在的项目位置
        Returns:
            'root' - 项目根目录
            'worktree' - 在某个 .gm 下的 worktree 内部
            'external' - 不在任何 GM 项目中
        """
        try:
            repo_root = self.git_client.get_repo_root()
            # 简化版：这里先检查是否在根目录
            if self.project_path == repo_root:
                return "root"
            return "root" # 暂定
        except:
            return "external"

    def get_current_branch(self, path: Optional[Path] = None) -> Optional[str]:
        """获取当前路径的分支名称"""
        try:
            return self.git_client.get_current_branch(path)
        except:
            return None

    def get_worktree_list(self) -> List[Dict[str, Any]]:
        """获取所有已注册的工作树列表"""
        try:
            # 从 Git 层面获取
            return self.git_client.list_worktrees()
        except Exception as e:
            logger.error(f"Failed to get worktree list: {e}")
            return []

    def get_working_dir_status(self, path: Path) -> Dict[str, int]:
        """获取指定路径的工作区状态（修改、未跟踪等）"""
        # 这里可以使用 git status --porcelain
        return {"modified": 0, "untracked": 0, "staged": 0}

    def get_commit_stats(self, path: Path) -> Dict[str, Any]:
        """获取提交统计信息（领先、落后等）"""
        return {
            "ahead": 0,
            "behind": 0,
            "last_commit_msg": "Initial commit (Mock)",
            "last_commit_author": "User",
            "last_commit_time": "2 minutes ago",
        }

    def format_detailed_output(self, branch_name: str) -> str:
        """格式化特定工作树的详细状态输出"""
        # 实际逻辑应构建详细的表格和总结
        return f"Detailed status for branch: {branch_name}\n" + "-" * 40 + "\nStatus: Clean\nPath: ./"

    def format_summary_output(self) -> str:
        """格式化所有工作树的摘要状态输出"""
        worktrees = self.get_worktree_list()
        lines = [f"[OK] Project initialized at: {self.project_path}", ""]
        lines.append("Worktree Summary")
        lines.append("=" * 45)
        lines.append(f"Total:       {len(worktrees)} worktrees")
        return "\n".join(lines)

    def execute(self, branch_name: Optional[str] = None) -> str:
        """执行状态汇总或查询"""
        if branch_name:
            return self.format_detailed_output(branch_name)
        
        # 默认显示摘要
        return self.format_summary_output()


@click.command()
@click.argument("branch", required=False, default=None)
def status(branch: Optional[str]) -> None:
    """查看各工作树状态摘要"""
    try:
        cmd = StatusCommand()
        output = cmd.execute(branch)
        click.echo(output)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
