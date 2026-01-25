"""操作系统 - 支持事务管理的原子操作

提供基础操作类和具体的操作实现，包括文件、Git、符号链接等操作。
所有操作都支持执行和回滚，并可被事务管理。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional, Any, Dict
from pathlib import Path
from datetime import datetime, timezone
import uuid

from gm.core.logger import Logger


class OperationStatus(Enum):
    """操作状态枚举"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Operation(ABC):
    """操作基类

    所有具体操作都应继承此类，实现 execute() 和 rollback() 方法。
    """

    def __init__(
        self,
        operation_id: Optional[str] = None,
        description: str = "",
        logger: Optional[Logger] = None,
    ):
        """初始化操作

        Args:
            operation_id: 操作 ID，如果为 None 则自动生成
            description: 操作描述
            logger: 日志记录器实例
        """
        self.operation_id = operation_id or str(uuid.uuid4())
        self.description = description
        self.logger = logger or Logger()
        self.status = OperationStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.executed_at: Optional[datetime] = None
        self.rolled_back_at: Optional[datetime] = None
        self.error: Optional[Exception] = None

    @abstractmethod
    def execute(self) -> Any:
        """执行操作

        Returns:
            操作执行结果

        Raises:
            Exception: 操作执行失败时抛出异常
        """
        pass

    @abstractmethod
    def rollback(self) -> None:
        """回滚操作

        Raises:
            Exception: 回滚失败时抛出异常
        """
        pass

    def get_status(self) -> OperationStatus:
        """获取操作状态

        Returns:
            当前操作状态
        """
        return self.status

    def is_completed(self) -> bool:
        """检查操作是否已完成

        Returns:
            True 如果操作已完成，False 否则
        """
        return self.status == OperationStatus.COMPLETED

    def is_failed(self) -> bool:
        """检查操作是否失败

        Returns:
            True 如果操作失败，False 否则
        """
        return self.status == OperationStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含操作信息的字典
        """
        return {
            'operation_id': self.operation_id,
            'description': self.description,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'rolled_back_at': self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            'error': str(self.error) if self.error else None,
        }


class CallableOperation(Operation):
    """基于可调用对象的操作

    使用 lambda 或函数作为操作的执行和回滚逻辑。
    """

    def __init__(
        self,
        execute_fn: Callable[[], Any],
        rollback_fn: Optional[Callable[[], None]] = None,
        operation_id: Optional[str] = None,
        description: str = "",
        logger: Optional[Logger] = None,
    ):
        """初始化可调用操作

        Args:
            execute_fn: 执行函数
            rollback_fn: 回滚函数，如果为 None 则回滚为无操作
            operation_id: 操作 ID
            description: 操作描述
            logger: 日志记录器实例
        """
        super().__init__(operation_id, description, logger)
        self.execute_fn = execute_fn
        self.rollback_fn = rollback_fn or (lambda: None)

    def execute(self) -> Any:
        """执行操作"""
        self.status = OperationStatus.EXECUTING
        try:
            result = self.execute_fn()
            self.executed_at = datetime.now(timezone.utc)
            self.status = OperationStatus.COMPLETED
            return result
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            raise

    def rollback(self) -> None:
        """回滚操作"""
        try:
            self.rollback_fn()
            self.rolled_back_at = datetime.now(timezone.utc)
            self.status = OperationStatus.ROLLED_BACK
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            raise


class FileOperation(Operation):
    """文件操作基类"""

    def __init__(
        self,
        file_path: Path,
        operation_id: Optional[str] = None,
        description: str = "",
        logger: Optional[Logger] = None,
    ):
        """初始化文件操作

        Args:
            file_path: 文件路径
            operation_id: 操作 ID
            description: 操作描述
            logger: 日志记录器实例
        """
        super().__init__(operation_id, description, logger)
        self.file_path = Path(file_path)


class CreateFileOperation(FileOperation):
    """创建文件操作"""

    def __init__(
        self,
        file_path: Path,
        content: str = "",
        operation_id: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """初始化创建文件操作

        Args:
            file_path: 文件路径
            content: 文件内容
            operation_id: 操作 ID
            logger: 日志记录器实例
        """
        super().__init__(
            file_path,
            operation_id,
            description=f"Create file {file_path}",
            logger=logger,
        )
        self.content = content
        self.backup_content: Optional[str] = None

    def execute(self) -> None:
        """创建文件"""
        self.status = OperationStatus.EXECUTING
        try:
            # 验证路径有效性
            try:
                # 尝试解析路径，检查是否有无效字符或权限问题
                parent_path = self.file_path.parent
                # 在 Windows 上验证驱动器是否存在
                if parent_path.drive and not Path(parent_path.drive).exists():
                    raise IOError(f"Drive {parent_path.drive} does not exist")
            except (ValueError, OSError) as e:
                raise IOError(f"Invalid file path: {str(self.file_path)}") from e

            # 如果文件已存在，备份内容
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.backup_content = f.read()

            # 创建父目录
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.content)

            self.executed_at = datetime.now(timezone.utc)
            self.status = OperationStatus.COMPLETED
            self.logger.info("file_created", file_path=str(self.file_path))
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            self.logger.error("file_creation_failed", file_path=str(self.file_path), error=str(e))
            raise

    def rollback(self) -> None:
        """回滚文件创建"""
        try:
            if self.backup_content is not None:
                # 恢复备份内容
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(self.backup_content)
                self.logger.info("file_restored", file_path=str(self.file_path))
            elif self.file_path.exists():
                # 删除新创建的文件
                self.file_path.unlink()
                self.logger.info("file_deleted", file_path=str(self.file_path))

            self.rolled_back_at = datetime.now(timezone.utc)
            self.status = OperationStatus.ROLLED_BACK
        except Exception as e:
            self.error = e
            self.logger.error("file_rollback_failed", file_path=str(self.file_path), error=str(e))
            raise


class DeleteFileOperation(FileOperation):
    """删除文件操作"""

    def __init__(
        self,
        file_path: Path,
        operation_id: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """初始化删除文件操作

        Args:
            file_path: 文件路径
            operation_id: 操作 ID
            logger: 日志记录器实例
        """
        super().__init__(
            file_path,
            operation_id,
            description=f"Delete file {file_path}",
            logger=logger,
        )
        self.backup_content: Optional[str] = None

    def execute(self) -> None:
        """删除文件"""
        self.status = OperationStatus.EXECUTING
        try:
            if self.file_path.exists():
                # 备份内容以便回滚
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.backup_content = f.read()

                # 删除文件
                self.file_path.unlink()

            self.executed_at = datetime.now(timezone.utc)
            self.status = OperationStatus.COMPLETED
            self.logger.info("file_deleted", file_path=str(self.file_path))
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            self.logger.error("file_deletion_failed", file_path=str(self.file_path), error=str(e))
            raise

    def rollback(self) -> None:
        """回滚文件删除"""
        try:
            if self.backup_content is not None:
                # 恢复文件
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(self.backup_content)
                self.logger.info("file_restored", file_path=str(self.file_path))

            self.rolled_back_at = datetime.now(timezone.utc)
            self.status = OperationStatus.ROLLED_BACK
        except Exception as e:
            self.error = e
            self.logger.error("file_rollback_failed", file_path=str(self.file_path), error=str(e))
            raise


class CreateDirectoryOperation(FileOperation):
    """创建目录操作"""

    def __init__(
        self,
        directory_path: Path,
        operation_id: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """初始化创建目录操作

        Args:
            directory_path: 目录路径
            operation_id: 操作 ID
            logger: 日志记录器实例
        """
        super().__init__(
            directory_path,
            operation_id,
            description=f"Create directory {directory_path}",
            logger=logger,
        )
        self.created = False

    def execute(self) -> None:
        """创建目录"""
        self.status = OperationStatus.EXECUTING
        try:
            if not self.file_path.exists():
                self.file_path.mkdir(parents=True, exist_ok=True)
                self.created = True

            self.executed_at = datetime.now(timezone.utc)
            self.status = OperationStatus.COMPLETED
            self.logger.info("directory_created", path=str(self.file_path))
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            self.logger.error("directory_creation_failed", path=str(self.file_path), error=str(e))
            raise

    def rollback(self) -> None:
        """回滚目录创建"""
        try:
            if self.created and self.file_path.exists():
                # 尽量删除目录（如果为空）
                try:
                    self.file_path.rmdir()
                    self.logger.info("directory_deleted", path=str(self.file_path))
                except OSError:
                    # 目录不为空，只记录日志
                    self.logger.warning("directory_not_empty", path=str(self.file_path))

            self.rolled_back_at = datetime.now(timezone.utc)
            self.status = OperationStatus.ROLLED_BACK
        except Exception as e:
            self.error = e
            self.logger.error("directory_rollback_failed", path=str(self.file_path), error=str(e))
            raise


class GitOperation(Operation):
    """Git 操作基类"""

    def __init__(
        self,
        repo_path: Path,
        operation_id: Optional[str] = None,
        description: str = "",
        logger: Optional[Logger] = None,
    ):
        """初始化 Git 操作

        Args:
            repo_path: 仓库路径
            operation_id: 操作 ID
            description: 操作描述
            logger: 日志记录器实例
        """
        super().__init__(operation_id, description, logger)
        self.repo_path = Path(repo_path)


class SymlinkOperation(Operation):
    """符号链接操作基类"""

    def __init__(
        self,
        link_path: Path,
        target_path: Path,
        operation_id: Optional[str] = None,
        description: str = "",
        logger: Optional[Logger] = None,
    ):
        """初始化符号链接操作

        Args:
            link_path: 符号链接路径
            target_path: 目标路径
            operation_id: 操作 ID
            description: 操作描述
            logger: 日志记录器实例
        """
        super().__init__(operation_id, description, logger)
        self.link_path = Path(link_path)
        self.target_path = Path(target_path)
