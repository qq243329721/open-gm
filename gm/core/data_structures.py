"""GM 核心数据结构定义

定义所有核心业务对象，包括 WorktreeInfo、GitStatus 等。"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path


class WorktreeStatus(Enum):
    """Worktree 状态枚举"""
    OK = "ok"
    MISSING = "missing"
    BROKEN = "broken"
    DETACHED = "detached"
    CONFLICT = "conflict"
    UNCLEAN = "unclean"


@dataclass
class GitStatus:
    """Git 状态信息"""
    staged: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    untracked: List[str] = field(default_factory=list)
    conflicted: List[str] = field(default_factory=list)
    
    @property
    def is_clean(self) -> bool:
        """是否为干净状态"""
        return not any([self.staged, self.modified, self.untracked, self.conflicted])
    
    @property
    def has_staged_changes(self) -> bool:
        """是否有已暂存的更改"""
        return len(self.staged) > 0
    
    @property
    def has_uncommitted_changes(self) -> bool:
        """是否有未提交的更改"""
        return any([self.staged, self.modified, self.conflicted])
    
    @property
    def has_conflicts(self) -> bool:
        """是否有冲突"""
        return len(self.conflicted) > 0


@dataclass
class RemoteStatus:
    """远程状态信息"""
    ahead: int = 0
    behind: int = 0
    tracking_branch: Optional[str] = None
    
    @property
    def needs_push(self) -> bool:
        """是否需要推送"""
        return self.ahead > 0
    
    @property
    def needs_pull(self) -> bool:
        """是否需要拉取"""
        return self.behind > 0
    
    @property
    def is_diverged(self) -> bool:
        """是否已分叉（领先且落后）"""
        return self.ahead > 0 and self.behind > 0
    
    @property
    def is_in_sync(self) -> bool:
        """是否与远程同步"""
        return self.ahead == 0 and self.behind == 0


@dataclass
class WorktreeInfo:
    """Worktree 信息"""
    name: str
    path: Path
    branch: str
    commit: str
    is_bare: bool = False
    is_detached: bool = False
    status: WorktreeStatus = WorktreeStatus.OK
    git_status: Optional[GitStatus] = None
    remote_status: Optional[RemoteStatus] = None
    last_update: Optional[datetime] = None
    size_mb: Optional[float] = None
    
    @property
    def is_clean(self) -> bool:
        """是否为干净状态"""
        if self.git_status is None:
            return True
        return self.git_status.is_clean
    
    @property
    def needs_sync(self) -> bool:
        """是否需要同步"""
        if self.remote_status is None:
            return False
        return not self.remote_status.is_in_sync
    
    @property
    def is_healthy(self) -> bool:
        """是否健康"""
        if self.status != WorktreeStatus.OK:
            return False
        
        if self.git_status is None:
            return True
            
        return not self.git_status.has_conflicts
    
    @property
    def display_name(self) -> str:
        """显示名称"""
        if self.is_detached:
            return f"{self.name} (detached)"
        elif self.needs_sync:
            sync_status = []
            if self.remote_status and self.remote_status.needs_push:
                sync_status.append("↑")
            if self.remote_status and self.remote_status.needs_pull:
                sync_status.append("↓")
            return f"{self.name} ({''.join(sync_status)})"
        return self.name
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'path': str(self.path),
            'branch': self.branch,
            'commit': self.commit,
            'is_bare': self.is_bare,
            'is_detached': self.is_detached,
            'status': self.status.value,
            'is_clean': self.is_clean,
            'needs_sync': self.needs_sync,
            'is_healthy': self.is_healthy,
            'git_status': {
                'staged_count': len(self.git_status.staged) if self.git_status else 0,
                'modified_count': len(self.git_status.modified) if self.git_status else 0,
                'untracked_count': len(self.git_status.untracked) if self.git_status else 0,
                'conflicted_count': len(self.git_status.conflicted) if self.git_status else 0,
            } if self.git_status else None,
            'remote_status': {
                'ahead': self.remote_status.ahead if self.remote_status else 0,
                'behind': self.remote_status.behind if self.remote_status else 0,
                'needs_push': self.remote_status.needs_push if self.remote_status else False,
                'needs_pull': self.remote_status.needs_pull if self.remote_status else False,
                'tracking_branch': self.remote_status.tracking_branch if self.remote_status else None,
            } if self.remote_status else None,
            'size_mb': self.size_mb,
            'last_update': self.last_update.isoformat() if self.last_update else None,
        }


# 配置相关数据结构
@dataclass
class WorktreeConfig:
    """Worktree 配置"""
    base_path: str = "."
    naming_pattern: str = "{branch}"
    auto_cleanup: bool = True


@dataclass
class DisplayConfig:
    """显示配置"""
    colors: bool = True
    default_verbose: bool = False


@dataclass
class SymlinksConfig:
    """符号链接配置"""
    strategy: str = "auto"
    shared_files: List[str] = field(default_factory=lambda: [".env", ".gitignore", "README.md"])


@dataclass
class GMConfig:
    """GM 完整配置"""
    worktree: WorktreeConfig = field(default_factory=WorktreeConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    symlinks: SymlinksConfig = field(default_factory=SymlinksConfig)
    branch_mapping: Dict[str, str] = field(default_factory=dict)
    worktrees: Dict[str, Dict[str, str]] = field(default_factory=dict)
    initialized: bool = False
    use_local_branch: bool = True
    main_branch: str = "main"
    # 新增项目信息字段
    project_name: Optional[str] = None
    home_path: Optional[str] = None
    remote_url: Optional[str] = None


# 类型别名
WorktreeList = List[WorktreeInfo]
ConfigDict = Dict[str, Any]
