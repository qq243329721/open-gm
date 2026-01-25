"""GM list 命令实现

列出所有 worktree 及其状态。
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import GitException, ConfigException
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.cli.utils import OutputFormatter, TableExporter, FormatterConfig

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

    def sort_worktrees(self, by: str = "branch") -> None:
        """对 worktree 列表进行排序

        Args:
            by: 排序方式 ("branch", "status", "date")
        """
        if by == "branch":
            self.worktrees.sort(key=lambda w: w.branch or "")
            logger.info("Worktrees sorted by branch")
        elif by == "status":
            status_order = {"active": 0, "clean": 1, "dirty": 2, "orphaned": 3}
            self.worktrees.sort(
                key=lambda w: (status_order.get(w.status, 99), w.branch or "")
            )
            logger.info("Worktrees sorted by status")
        elif by == "date":
            # 按最后提交时间排序
            self.worktrees.sort(
                key=lambda w: w.last_commit_time,
                reverse=True
            )
            logger.info("Worktrees sorted by date")

    def filter_worktrees(
        self,
        status_filter: Optional[str] = None,
        branch_filter: Optional[str] = None
    ) -> List[WorktreeInfo]:
        """过滤 worktree 列表

        Args:
            status_filter: 状态过滤器 ("clean", "dirty" 等)
            branch_filter: 分支名过滤器（支持模式匹配）

        Returns:
            过滤后的 worktree 列表
        """
        filtered = self.worktrees

        if status_filter:
            filtered = [w for w in filtered if w.status == status_filter]
            logger.info("Worktrees filtered by status", status=status_filter, count=len(filtered))

        if branch_filter:
            import fnmatch
            filtered = [
                w for w in filtered
                if fnmatch.fnmatch(w.branch or "", branch_filter)
            ]
            logger.info("Worktrees filtered by branch", pattern=branch_filter, count=len(filtered))

        return filtered

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
@click.option(
    "-s",
    "--sort",
    type=click.Choice(["branch", "status", "date"]),
    default="branch",
    help="排序方式",
)
@click.option(
    "-f",
    "--filter",
    type=str,
    help="过滤条件 (例如: status=clean, branch=feature/*)",
)
@click.option(
    "-e",
    "--export",
    type=click.Choice(["json", "csv", "tsv"]),
    help="导出格式",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="禁用彩色输出",
)
@click.argument("project_path", required=False, default=".")
def list_command(
    verbose: bool,
    sort: str,
    filter: Optional[str],
    export: Optional[str],
    no_color: bool,
    project_path: str
) -> None:
    """列出所有 worktree 及其状态

    \b
    使用示例:
    gm list                                # 列出所有 worktree（简洁模式）
    gm list -v                             # 列出所有 worktree（详细模式）
    gm list -v /path                       # 在指定路径列出 worktree
    gm list -s status                      # 按状态排序
    gm list -f "status=clean"              # 过滤清洁状态的 worktree
    gm list -e json                        # 导出为 JSON 格式
    """
    formatter = OutputFormatter(FormatterConfig(no_color=no_color))

    try:
        cmd = ListCommand(project_path)
        cmd.execute(verbose=verbose)

        # 解析过滤条件
        status_filter = None
        branch_filter = None
        if filter:
            if "=" in filter:
                key, value = filter.split("=", 1)
                if key.strip() == "status":
                    status_filter = value.strip()
                elif key.strip() == "branch":
                    branch_filter = value.strip()
            else:
                # 假设没有 = 的是分支过滤
                branch_filter = filter

        # 应用排序
        cmd.sort_worktrees(by=sort)
        logger.info("Worktrees sorted", sort_by=sort)

        # 应用过滤
        filtered_worktrees = cmd.filter_worktrees(
            status_filter=status_filter,
            branch_filter=branch_filter
        )

        # 如果需要导出
        if export:
            # 构建表格数据
            headers = ["Branch", "Status", "Path", "Modified Files", "Last Commit"]
            rows = []

            for wt in filtered_worktrees:
                branch = wt.branch if wt.branch else "(detached)"
                path = Path(wt.path).name if wt.path != str(cmd.project_path) else ".gm"
                modified = wt.ahead_count + wt.behind_count

                rows.append([
                    branch,
                    wt.status,
                    path,
                    modified,
                    wt.last_commit_message[:30] + "..." if len(wt.last_commit_message) > 30 else wt.last_commit_message
                ])

            # 导出
            if export == "json":
                output = TableExporter.to_json(headers, rows)
            elif export == "csv":
                output = TableExporter.to_csv(headers, rows)
            elif export == "tsv":
                output = TableExporter.to_tsv(headers, rows)

            click.echo(output)
        else:
            # 正常输出
            if not filtered_worktrees:
                click.echo(formatter.warning("没有 worktree 匹配过滤条件"))
                return

            # 显示过滤信息
            if filter:
                click.echo(formatter.info(f"已应用过滤: {filter} (找到 {len(filtered_worktrees)} 个结果)"))
                click.echo()

            if verbose:
                # 详细模式：显示详细信息
                for i, wt in enumerate(filtered_worktrees, 1):
                    border_top = f"┌─ Worktree {i} " + "─" * (40 - len(str(i)))
                    border_bottom = "└" + "─" * 51 + "┘"

                    click.echo(border_top)
                    click.echo(f"│ 分支:       {wt.branch or '(detached)':<40} │")

                    status_info = wt.status
                    if wt.ahead_count > 0 or wt.behind_count > 0:
                        status_parts = []
                        if wt.ahead_count > 0:
                            status_parts.append(f"领先 {wt.ahead_count} 个提交")
                        if wt.behind_count > 0:
                            status_parts.append(f"落后 {wt.behind_count} 个提交")
                        if status_parts:
                            status_info += f" ({', '.join(status_parts)})"

                    click.echo(f"│ 状态:       {status_info:<40} │")

                    path_display = (
                        Path(wt.path).name if wt.path != str(cmd.project_path) else ".gm"
                    )
                    click.echo(f"│ 路径:       {path_display:<40} │")

                    commit_msg = (
                        wt.last_commit_message[:37] + "..."
                        if len(wt.last_commit_message) > 40
                        else wt.last_commit_message
                    )
                    click.echo(f"│ 最后提交:   {commit_msg:<40} │")

                    author = (
                        wt.last_commit_author[:37] + "..."
                        if len(wt.last_commit_author) > 40
                        else wt.last_commit_author
                    )
                    click.echo(f"│ 作者:       {author:<40} │")
                    click.echo(f"│ 修改时间:   {wt.last_commit_time:<40} │")
                    click.echo(border_bottom)

                    if i < len(filtered_worktrees):
                        click.echo()
            else:
                # 简洁模式：显示简单表格
                headers = ["BRANCH", "STATUS", "PATH"]
                rows = []

                for wt in filtered_worktrees:
                    branch = wt.branch if wt.branch else "(detached)"
                    path = Path(wt.path).name if wt.path != str(cmd.project_path) else ".gm"
                    rows.append([branch, wt.status, path])

                output = formatter.format_table(headers, rows, column_widths=[24, 10, 20])
                click.echo(output)

                # 显示统计信息
                click.echo()
                total = len(filtered_worktrees)
                clean = len([w for w in filtered_worktrees if w.status == "clean"])
                dirty = len([w for w in filtered_worktrees if w.status == "dirty"])
                click.echo(f"总计: {total} | 清洁: {clean} | 脏: {dirty}")

    except click.Exit:
        raise
    except Exception as e:
        click.echo(formatter.error(f"{str(e)}"), err=True)
        raise click.Exit(1)
