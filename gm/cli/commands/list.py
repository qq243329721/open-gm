"""GM list 命令实现

列出所有 worktree 及其状态。
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import GitException, ConfigException
from gm.core.git_client import GitClient
from gm.core.logger import get_logger

logger = get_logger("list_command")


class WorktreeInfo:
    """Worktree 信息类"""

    def __init__(self, path: str, branch: str, is_active: bool = False):
        """初始化 Worktree 信息

        Args:
            path: worktree 路径
            branch: 关联的分支名
            is_active: 是否为活跃 worktree（主分支）
        """
        self.path = path
        self.branch = branch
        self.is_active = is_active
        self.status = "active" if is_active else "clean"
        self.is_dirty = False
        self.is_detached = False
        self.ahead_count = 0
        self.behind_count = 0
        self.last_commit_hash = ""
        self.last_commit_message = ""
        self.last_commit_author = ""
        self.last_commit_time = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "path": self.path,
            "branch": self.branch,
            "status": self.status,
            "is_active": self.is_active,
            "is_dirty": self.is_dirty,
            "is_detached": self.is_detached,
            "ahead_count": self.ahead_count,
            "behind_count": self.behind_count,
            "last_commit_hash": self.last_commit_hash,
            "last_commit_message": self.last_commit_message,
            "last_commit_author": self.last_commit_author,
            "last_commit_time": self.last_commit_time,
        }


class ListCommand:
    """列表命令处理器

    负责列出所有 worktree 及其状态。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化列表命令处理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.worktrees: List[WorktreeInfo] = []

    def validate_project(self) -> bool:
        """验证项目是否已初始化

        Returns:
            True 如果项目已初始化

        Raises:
            GitException: 如果不是有效的 git 仓库
            ConfigException: 如果项目未初始化
        """
        try:
            self.git_client.get_repo_root()
            logger.info("Project validated as git repository")
        except GitException as e:
            logger.error("Failed to validate project", error=str(e))
            raise GitException("不是有效的 Git 仓库。", details=str(e))

        # 检查项目是否已初始化
        gm_dir = self.project_path / ".gm"
        config_file = self.project_path / ".gm.yaml"

        if not gm_dir.exists() and not config_file.exists():
            raise ConfigException("项目未初始化。请先运行 'gm init'。")

        return True

    def get_worktree_list(self) -> List[WorktreeInfo]:
        """获取所有 worktree 列表

        Returns:
            WorktreeInfo 对象列表
        """
        try:
            worktree_list = self.git_client.get_worktree_list()

            # 获取配置中的主分支
            config = self.config_manager.load_config()
            main_branch = config.get("main_branch", "main")

            # 获取 .gm 目录路径
            gm_dir = self.project_path / ".gm"

            # 处理每个 worktree
            worktrees = []
            for wt in worktree_list:
                path = wt.get("path")
                branch = wt.get("branch")

                # 判断是否为活跃 worktree（主分支在 .gm 目录）
                is_active = str(path) == str(self.project_path) or (
                    branch == main_branch and Path(path).parent == gm_dir
                )

                info = WorktreeInfo(path, branch, is_active)

                # 收集 worktree 信息
                self._collect_worktree_info(info)

                worktrees.append(info)

            self.worktrees = worktrees
            logger.info("Worktree list retrieved", count=len(worktrees))

            return worktrees

        except GitException as e:
            logger.error("Failed to get worktree list", error=str(e))
            raise

    def _collect_worktree_info(self, info: WorktreeInfo) -> None:
        """收集 worktree 详细信息

        Args:
            info: WorktreeInfo 对象
        """
        try:
            worktree_path = Path(info.path)

            # 检查 worktree 是否存在
            if not worktree_path.exists():
                info.status = "orphaned"
                logger.warning("Orphaned worktree detected", path=info.path)
                return

            # 检查是否有未提交的改动
            is_dirty = self.git_client.has_uncommitted_changes(worktree_path)
            info.is_dirty = is_dirty

            if info.status != "active":
                info.status = "dirty" if is_dirty else "clean"

            # 获取提交信息
            try:
                commit_info = self.git_client.get_commit_info(cwd=worktree_path)
                if commit_info:
                    parts = commit_info.split("|")
                    if len(parts) >= 4:
                        info.last_commit_hash = parts[0]
                        info.last_commit_message = parts[1]
                        info.last_commit_author = parts[2]
                        info.last_commit_time = parts[3]
            except Exception as e:
                logger.debug("Failed to get commit info", path=info.path, error=str(e))

            # 获取领先/落后信息
            try:
                config = self.config_manager.load_config()
                main_branch = config.get("main_branch", "main")
                ahead, behind = self.git_client.get_ahead_behind(
                    base_branch=main_branch,
                    compare_branch="HEAD",
                    cwd=worktree_path,
                )
                info.ahead_count = ahead
                info.behind_count = behind
            except Exception as e:
                logger.debug("Failed to get ahead/behind counts", error=str(e))

        except Exception as e:
            logger.warning("Error collecting worktree info", path=info.path, error=str(e))

    def format_simple_output(self) -> str:
        """格式化简洁模式输出

        Returns:
            格式化的表格字符串
        """
        if not self.worktrees:
            return "没有 worktree。"

        # 构建表格数据
        lines = []
        header = "BRANCH".ljust(24) + "STATUS".ljust(10) + "PATH"
        lines.append(header)
        lines.append("─" * 60)

        for wt in self.worktrees:
            branch = wt.branch if wt.branch else "(detached)"
            status = wt.status
            path = Path(wt.path).name if wt.path != str(self.project_path) else ".gm"

            line = branch.ljust(24) + status.ljust(10) + path
            lines.append(line)

        return "\n".join(lines)

    def format_detailed_output(self) -> str:
        """格式化详细模式输出

        Returns:
            格式化的详细信息字符串
        """
        if not self.worktrees:
            return "没有 worktree。"

        lines = []

        for i, wt in enumerate(self.worktrees, 1):
            # 构建边框
            border_top = "┌─ Worktree " + str(i) + " " + "─" * (40 - len(str(i)))
            border_bottom = "└" + "─" * 51 + "┘"

            lines.append(border_top)

            # 分支信息
            branch = wt.branch if wt.branch else "(detached HEAD)"
            lines.append(f"│ 分支:       {branch:<40} │")

            # 状态信息
            status_info = wt.status
            if wt.ahead_count > 0 or wt.behind_count > 0:
                status_parts = []
                if wt.ahead_count > 0:
                    status_parts.append(f"领先 {wt.ahead_count} 个提交")
                if wt.behind_count > 0:
                    status_parts.append(f"落后 {wt.behind_count} 个提交")
                if status_parts:
                    status_info += f" ({', '.join(status_parts)})"

            lines.append(f"│ 状态:       {status_info:<40} │")

            # 路径信息
            path_display = (
                Path(wt.path).name if wt.path != str(self.project_path) else ".gm"
            )
            lines.append(f"│ 路径:       {path_display:<40} │")

            # 最后提交信息
            commit_msg = (
                wt.last_commit_message[:37] + "..."
                if len(wt.last_commit_message) > 40
                else wt.last_commit_message
            )
            lines.append(f"│ 最后提交:   {commit_msg:<40} │")

            # 作者信息
            author = (
                wt.last_commit_author[:37] + "..."
                if len(wt.last_commit_author) > 40
                else wt.last_commit_author
            )
            lines.append(f"│ 作者:       {author:<40} │")

            # 修改时间
            lines.append(f"│ 修改时间:   {wt.last_commit_time:<40} │")

            lines.append(border_bottom)
            lines.append("")

        return "\n".join(lines).rstrip()

    def execute(self, verbose: bool = False) -> None:
        """执行列表命令

        Args:
            verbose: 是否使用详细模式

        Raises:
            GitException: 如果 git 操作失败
            ConfigException: 如果项目配置有问题
        """
        logger.info("Executing list command", verbose=verbose)

        try:
            # 1. 验证项目
            self.validate_project()

            # 2. 获取 worktree 列表
            self.get_worktree_list()

            # 3. 格式化并输出
            if verbose:
                output = self.format_detailed_output()
            else:
                output = self.format_simple_output()

            click.echo(output)

            logger.info("List command executed successfully", worktree_count=len(self.worktrees))

        except ConfigException as e:
            logger.error("Configuration error", error=str(e))
            click.echo(f"错误：{e.message}", err=True)
            raise click.Exit(1)
        except GitException as e:
            logger.error("Git error", error=str(e))
            click.echo(f"Git 错误：{e.message}", err=True)
            raise click.Exit(1)
        except Exception as e:
            logger.error("Unexpected error", error=str(e))
            click.echo(f"未知错误：{str(e)}", err=True)
            raise click.Exit(1)


@click.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="详细模式，显示更多信息和彩色输出",
)
@click.argument("project_path", required=False, default=".")
def list_command(verbose: bool, project_path: str) -> None:
    """列出所有 worktree 及其状态

    \b
    使用示例:
    gm list              # 列出所有 worktree（简洁模式）
    gm list -v           # 列出所有 worktree（详细模式）
    gm list -v /path    # 在指定路径列出 worktree
    """
    try:
        cmd = ListCommand(project_path)
        cmd.execute(verbose=verbose)
    except click.Exit:
        raise
    except Exception as e:
        click.echo(f"错误：{str(e)}", err=True)
        raise click.Exit(1)
