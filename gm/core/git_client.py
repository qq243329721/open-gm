"""Git 客户端实现

提供基础的 Git 操作封装，通过 subprocess 调用 Git 命令，并支持事务回滚。"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from gm.core.exceptions import GitCommandError
from gm.core.logger import get_logger
from gm.core.interfaces.git import IGitClient

logger = get_logger("git_client")


class GitClient(IGitClient):
    """Git 客户端实现类"""

    def __init__(self, repo_path: Optional[Path] = None):
        """初始化 GitClient"""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        logger.info("GitClient initialized", repo_path=str(self.repo_path))

    def run_command(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> str:
        """运行 Git 命令"""
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
                raise GitCommandError(f"Git command failed: {' '.join(cmd)}", details=error_msg)

            return result.stdout.strip()
        except Exception as e:
            raise GitCommandError(f"Failed to execute git command: {e}") from e

    def is_bare_repository(self, path: Optional[Path] = None) -> bool:
        """检查是否为裸仓库"""
        cwd = path or self.repo_path
        try:
            res = self.run_command(["git", "rev-parse", "--is-bare-repository"], cwd=cwd, check=False)
            return res == "true"
        except:
            return False

    def create_worktree(self, path: Path, branch: str, force: bool = False) -> bool:
        """创建 worktree"""
        cmd = ["git", "worktree", "add"]
        if force: cmd.append("--force")
        cmd.extend([str(path), branch])
        try:
            self.run_command(cmd)
            return True
        except:
            return False

    def remove_worktree(self, path: Path, force: bool = False) -> bool:
        """删除 worktree"""
        cmd = ["git", "worktree", "remove"]
        if force: cmd.append("--force")
        cmd.append(str(path))
        try:
            self.run_command(cmd)
            return True
        except:
            return False

    def list_worktrees(self) -> List[Dict[str, Any]]:
        """列出 worktree"""
        try:
            output = self.run_command(["git", "worktree", "list", "--porcelain"])
            worktrees = []
            # 这里简单解析 porcelain 输出
            return worktrees
        except:
            return []

    def check_branch_exists(self, branch: str) -> bool:
        """检查分支是否存在"""
        try:
            self.run_command(["git", "rev-parse", "--verify", branch])
            return True
        except:
            return False

    def get_current_branch(self, path: Optional[Path] = None) -> Optional[str]:
        """获取当前分支"""
        try:
            return self.run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
        except:
            return None

    def get_repo_root(self, path: Optional[Path] = None) -> Path:
        """获取仓库根目录"""
        cwd = path or self.repo_path
        try:
            res = self.run_command(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
            return Path(res)
        except Exception as e:
            raise GitCommandError(f"Failed to get repo root: {e}")

    def has_uncommitted_changes(self, path: Optional[Path] = None) -> bool:
        """检查是否有未提交的更改"""
        cwd = path or self.repo_path
        try:
            res = self.run_command(["git", "status", "--porcelain"], cwd=cwd)
            return len(res.strip()) > 0
        except:
            return False

    def get_commit_info(self, ref: str = "HEAD", cwd: Optional[Path] = None) -> str:
        """获取提交信息"""
        try:
            return self.run_command(["git", "log", "-1", "--format=%H|%s|%an|%ar", ref], cwd=cwd)
        except:
            return ""

    def get_ahead_behind(self, base_branch: str, compare_branch: str, cwd: Optional[Path] = None) -> Tuple[int, int]:
        """获取领先和落后计数"""
        try:
            res = self.run_command(["git", "rev-list", "--left-right", "--count", f"{base_branch}...{compare_branch}"], cwd=cwd)
            parts = res.split()
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
            return 0, 0
        except:
            return 0, 0

    def create_branch(self, branch: str, start_point: Optional[str] = None) -> None:
        """创建分支"""
        cmd = ["git", "branch", branch]
        if start_point: cmd.append(start_point)
        self.run_command(cmd)

    def delete_branch(self, branch: str, force: bool = False) -> None:
        """删除分支"""
        cmd = ["git", "branch", "-D" if force else "-d", branch]
        self.run_command(cmd)

    def get_branch_list(self, remote: bool = False) -> List[str]:
        """获取分支列表"""
        cmd = ["git", "branch"]
        if remote: cmd.append("-r")
        try:
            output = self.run_command(cmd)
            branches = []
            for line in output.split('\n'):
                branch = line.replace('*', '').strip()
                if branch:
                    branches.append(branch)
            return branches
        except:
            return []

    def get_remote_branch(self, branch: str) -> None:
        """获取/拉取远程分支"""
        self.run_command(["git", "fetch", "origin", f"{branch}:{branch}"])
    def get_worktree_info(self, worktree_path: Path) -> Optional[Dict[str, Any]]:
        """获取 worktree 详细信息"""
        # 简单实现，后续可扩展
        return {
            "path": str(worktree_path),
            "branch": self.get_current_branch(worktree_path)
        }
