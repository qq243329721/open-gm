"""GM 异常体系"""


class GMException(Exception):
    """基础异常类"""
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


# Worktree 相关异常
class WorktreeException(GMException):
    """Worktree 操作异常"""
    pass


class WorktreeAlreadyExists(WorktreeException):
    """Worktree 已存在"""
    pass


class WorktreeNotFound(WorktreeException):
    """Worktree 不存在"""
    pass


class OrphanedWorktree(WorktreeException):
    """孤立的 worktree"""
    pass


# 配置相关异常
class ConfigException(GMException):
    """配置异常"""
    pass


class ConfigParseError(ConfigException):
    """配置解析失败"""
    pass


class ConfigIOError(ConfigException):
    """配置文件读写失败"""
    pass


class ConfigValidationError(ConfigException):
    """配置验证失败"""
    pass


# 符号链接异常
class SymlinkException(GMException):
    """符号链接异常"""
    pass


class SymlinkCreationError(SymlinkException):
    """符号链接创建失败"""
    pass


class BrokenSymlinkError(SymlinkException):
    """符号链接损坏"""
    pass


# Git 操作异常
class GitException(GMException):
    """Git 操作异常"""
    pass


class GitCommandError(GitException):
    """Git 命令执行失败"""
    pass


# 事务异常
class TransactionException(GMException):
    """事务异常"""
    pass


class TransactionRollbackError(TransactionException):
    """事务回滚失败"""
    def __init__(self, message: str, executed_ops=None):
        super().__init__(message)
        self.executed_ops = executed_ops or []


# 分支名映射异常
class BranchMappingException(GMException):
    """分支名映射异常"""
    pass


class BranchMappingConflict(BranchMappingException):
    """分支映射冲突"""
    pass


class CircularMappingError(BranchMappingException):
    """循环映射错误"""
    pass


class InvalidMappingError(BranchMappingException):
    """无效的映射"""
    pass


# 其他异常
class DiskSpaceError(GMException):
    """磁盘空间不足"""
    pass


class PermissionError(GMException):
    """权限不足"""
    pass
