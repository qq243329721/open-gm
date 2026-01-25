"""Git 操作封装类

提供 Git 操作的统一接口，包括分支管理、worktree 操作、状态检查等。
使用 structlog 记录所有操作。
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from gm.core.exceptions import GitException, GitCommandError
from gm.core.logger import get_logger


logger = get_logger("git_client")


class GitClient:
    """Git 操作客户端

    提供 Git 命令的统一接口和异常处理。
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """初始化 GitClient

        Args:
            repo_path: Git 仓库路径，默认为当前目录
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        logger.info("GitClient initialized", repo_path=str(self.repo_path))

    def run_command(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> str:
        """运行 Git 命令

        Args:
            cmd: 命令列表
            cwd: 工作目录，默认使用 repo_path
            check: 是否在命令失败时抛出异常

        Returns:
            命令输出

        Raises:
            GitCommandError: 命令执行失败时抛出
        """
        cwd = cwd or self.repo_path

        logger.debug("Running git command", command=" ".join(cmd), cwd=str(cwd))

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )

            if check and result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(
                    "Git command failed",
                    command=" ".join(cmd),
                    return_code=result.returncode,
                    error=error_msg,
                )
                raise GitCommandError(
                    f"Git command failed: {' '.join(cmd)}",
                    details=error_msg,
                )

            output = result.stdout.strip()
            logger.debug("Git command succeeded", output_length=len(output))

            return output

        except subprocess.SubprocessError as e:
            logger.error(
                "Git command error",
                command=" ".join(cmd),
                error=str(e),
            )
            raise GitCommandError(f"Failed to execute git command: {e}") from e

    def get_version(self) -> str:
        """获取 Git 版本

        Returns:
            Git 版本号字符串
        """
        output = self.run_command(["git", "--version"])
        # 格式: "git version 2.x.x"
        version = output.replace("git version ", "")
        logger.info("Git version retrieved", version=version)
        return version

    def get_current_branch(self) -> str:
        """获取当前分支名

        Returns:
            当前分支名

        Raises:
            GitCommandError: 无法获取当前分支时抛出
        """
        try:
            branch = self.run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            logger.info("Current branch retrieved", branch=branch)
            return branch
        except GitCommandError as e:
            logger.error("Failed to get current branch")
            raise

    def check_branch_exists(self, branch_name: str) -> bool:
        """检查本地分支是否存在

        Args:
            branch_name: 分支名称

        Returns:
            分支存在返回 True，否则返回 False
        """
        try:
            self.run_command(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"])
            logger.info("Local branch exists", branch=branch_name)
            return True
        except GitCommandError:
            logger.debug("Local branch does not exist", branch=branch_name)
            return False

    def get_remote_branch(self, branch_name: str) -> bool:
        """从远程获取分支（git fetch）

        Args:
            branch_name: 分支名称

        Returns:
            分支获取成功返回 True，否则返回 False
        """
        try:
            # 尝试从远程获取分支
            self.run_command(
                ["git", "fetch", "origin", f"{branch_name}:{branch_name}"],
                check=False,
            )

            # 检查分支是否存在
            if self.check_branch_exists(branch_name):
                logger.info("Remote branch fetched successfully", branch=branch_name)
                return True

            logger.warning("Remote branch fetch may have failed", branch=branch_name)
            return False

        except GitCommandError as e:
            logger.error("Failed to fetch remote branch", branch=branch_name, error=str(e))
            return False

    def create_worktree(self, path: Path, branch: str) -> None:
        """创建 worktree

        Args:
            path: worktree 路径
            branch: 关联的分支名

        Raises:
            GitCommandError: 创建失败时抛出
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.run_command(["git", "worktree", "add", str(path), branch])
            logger.info(
                "Worktree created successfully",
                path=str(path),
                branch=branch,
            )
        except GitCommandError as e:
            logger.error(
                "Failed to create worktree",
                path=str(path),
                branch=branch,
                error=str(e),
            )
            raise

    def delete_worktree(self, path: Path, force: bool = False) -> None:
        """删除 worktree

        Args:
            path: worktree 路径
            force: 是否强制删除

        Raises:
            GitCommandError: 删除失败时抛出
        """
        cmd = ["git", "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(path))

        try:
            self.run_command(cmd)
            logger.info("Worktree deleted successfully", path=str(path), force=force)
        except GitCommandError as e:
            logger.error(
                "Failed to delete worktree",
                path=str(path),
                force=force,
                error=str(e),
            )
            raise

    def get_worktree_list(self) -> List[Dict[str, Any]]:
        """获取所有 worktree 列表

        Returns:
            worktree 信息列表，每个元素包含 path 和 branch 信息
        """
        try:
            output = self.run_command(
                ["git", "worktree", "list", "--porcelain"],
                check=False,
            )

            worktrees = []
            for line in output.split("\n"):
                if not line.strip():
                    continue

                # 格式: worktree /path/to/worktree
                #       branch /refs/heads/branch-name
                #       detached
                parts = line.split()

                if parts[0] == "worktree":
                    current_worktree = {"path": parts[1]}
                elif parts[0] == "branch" and current_worktree:
                    # 从 refs/heads/xxx 中提取分支名
                    branch_ref = parts[1]
                    branch_name = branch_ref.replace("refs/heads/", "")
                    current_worktree["branch"] = branch_name
                    worktrees.append(current_worktree)
                    current_worktree = {}
                elif parts[0] == "detached":
                    current_worktree["detached"] = True
                    current_worktree["branch"] = None
                    worktrees.append(current_worktree)
                    current_worktree = {}

            logger.info("Worktree list retrieved", count=len(worktrees))
            return worktrees

        except GitCommandError as e:
            logger.error("Failed to get worktree list", error=str(e))
            raise

    def delete_branch(self, branch: str, force: bool = False) -> None:
        """删除分支

        Args:
            branch: 分支名称
            force: 是否强制删除（使用 -D 而不是 -d）

        Raises:
            GitCommandError: 删除失败时抛出
        """
        cmd = ["git", "branch"]
        if force:
            cmd.append("-D")
        else:
            cmd.append("-d")
        cmd.append(branch)

        try:
            self.run_command(cmd)
            logger.info("Branch deleted successfully", branch=branch, force=force)
        except GitCommandError as e:
            logger.error(
                "Failed to delete branch",
                branch=branch,
                force=force,
                error=str(e),
            )
            raise

    def get_repo_root(self) -> Path:
        """获取仓库根路径

        Returns:
            仓库根路径

        Raises:
            GitCommandError: 获取失败时抛出
        """
        try:
            root_path = self.run_command(["git", "rev-parse", "--show-toplevel"])
            repo_root = Path(root_path)
            logger.info("Repository root retrieved", root=str(repo_root))
            return repo_root
        except GitCommandError as e:
            logger.error("Failed to get repository root", error=str(e))
            raise

    def get_branch_list(self, remote: bool = False) -> List[str]:
        """获取分支列表

        Args:
            remote: 是否获取远程分支列表

        Returns:
            分支名列表
        """
        cmd = ["git", "branch"]
        if remote:
            cmd.append("-r")

        try:
            output = self.run_command(cmd)
            branches = [line.strip().lstrip("*").strip() for line in output.split("\n") if line.strip()]
            logger.info("Branch list retrieved", count=len(branches), remote=remote)
            return branches
        except GitCommandError as e:
            logger.error("Failed to get branch list", remote=remote, error=str(e))
            return []

    def get_status(self, cwd: Optional[Path] = None) -> str:
        """获取 git 状态

        Args:
            cwd: 工作目录，默认使用 repo_path

        Returns:
            git status 输出
        """
        try:
            status = self.run_command(["git", "status", "--porcelain"], cwd=cwd)
            logger.debug("Git status retrieved", cwd=str(cwd or self.repo_path))
            return status
        except GitCommandError as e:
            logger.error("Failed to get git status", error=str(e))
            return ""

    def has_uncommitted_changes(self, cwd: Optional[Path] = None) -> bool:
        """检查是否有未提交的改动

        Args:
            cwd: 工作目录，默认使用 repo_path

        Returns:
            有未提交改动返回 True，否则返回 False
        """
        status = self.get_status(cwd)
        has_changes = bool(status.strip())

        if has_changes:
            logger.warning("Uncommitted changes detected", cwd=str(cwd or self.repo_path))
        else:
            logger.debug("No uncommitted changes", cwd=str(cwd or self.repo_path))

        return has_changes

    def get_commit_info(
        self,
        format_str: str = "%h|%s|%an|%ar",
        cwd: Optional[Path] = None,
        count: int = 1,
    ) -> str:
        """获取提交信息

        Args:
            format_str: 日志格式字符串
            cwd: 工作目录，默认使用 repo_path
            count: 获取的提交数量

        Returns:
            格式化的提交信息

        Raises:
            GitCommandError: 获取提交信息失败时抛出
        """
        try:
            output = self.run_command(
                ["git", "log", f"--format={format_str}", f"-{count}"],
                cwd=cwd,
            )
            logger.debug("Commit info retrieved", cwd=str(cwd or self.repo_path))
            return output
        except GitCommandError as e:
            logger.error("Failed to get commit info", error=str(e))
            return ""

    def get_ahead_behind(
        self,
        base_branch: str = "main",
        compare_branch: str = "HEAD",
        cwd: Optional[Path] = None,
    ) -> Tuple[int, int]:
        """获取分支相对于基础分支的领先/落后提交数

        Args:
            base_branch: 基础分支名称
            compare_branch: 比较分支名称（默认为 HEAD）
            cwd: 工作目录，默认使用 repo_path

        Returns:
            (ahead_count, behind_count) 的元组

        Raises:
            GitCommandError: 比较失败时抛出
        """
        try:
            output = self.run_command(
                ["git", "rev-list", "--left-right", "--count", f"{base_branch}...{compare_branch}"],
                cwd=cwd,
                check=False,
            )

            if not output.strip():
                return (0, 0)

            parts = output.strip().split()
            if len(parts) == 2:
                return (int(parts[1]), int(parts[0]))
            return (0, 0)

        except (GitCommandError, ValueError) as e:
            logger.debug("Failed to get ahead/behind counts", error=str(e))
            return (0, 0)
