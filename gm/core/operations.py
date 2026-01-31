"""操作类定义

基础的操作类体系，支持执行和回滚，是事务系统的基础单元。"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional, Any, Dict
from pathlib import Path
from datetime import datetime, timezone
import uuid

from gm.core.logger import get_logger

logger = get_logger("operations")


class OperationStatus(Enum):
    """操作状态枚举"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Operation(ABC):
    """抽象操作基类"""

    def __init__(
        self,
        operation_id: Optional[str] = None,
        description: str = "",
    ):
        """初始化操作
        Args:
            operation_id: 操作唯一 ID
            description: 操作描述
        """
        self.operation_id = operation_id or str(uuid.uuid4())
        self.description = description
        self.status = OperationStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.executed_at: Optional[datetime] = None
        self.rolled_back_at: Optional[datetime] = None
        self.error: Optional[Exception] = None

    @abstractmethod
    def execute(self) -> Any:
        """执行操作"""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """回滚操作"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'operation_id': self.operation_id,
            'description': self.description,
            'status': self.status.value,
        }


class CallableOperation(Operation):
    """基于回调函数的通用操作"""

    def __init__(
        self,
        execute_fn: Callable[[], Any],
        rollback_fn: Optional[Callable[[], None]] = None,
        operation_id: Optional[str] = None,
        description: str = "",
    ):
        super().__init__(operation_id, description)
        self.execute_fn = execute_fn
        self.rollback_fn = rollback_fn or (lambda: None)

    def execute(self) -> Any:
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
        try:
            self.rollback_fn()
            self.rolled_back_at = datetime.now(timezone.utc)
            self.status = OperationStatus.ROLLED_BACK
        except Exception as e:
            self.error = e
            raise


class FileOperation(Operation):
    """文件系统操作基类"""

    def __init__(
        self,
        file_path: Path,
        operation_id: Optional[str] = None,
        description: str = "",
    ):
        super().__init__(operation_id, description)
        self.file_path = Path(file_path)


class CreateFileOperation(FileOperation):
    """创建文件操作"""

    def __init__(
        self,
        file_path: Path,
        content: str = "",
        operation_id: Optional[str] = None,
    ):
        super().__init__(file_path, operation_id, f"Create file {file_path}")
        self.content = content
        self.backup_content: Optional[str] = None

    def execute(self) -> None:
        self.status = OperationStatus.EXECUTING
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.backup_content = f.read()

            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.content)

            self.executed_at = datetime.now(timezone.utc)
            self.status = OperationStatus.COMPLETED
        except Exception as e:
            self.error = e
            self.status = OperationStatus.FAILED
            raise

    def rollback(self) -> None:
        if self.backup_content is not None:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.backup_content)
        elif self.file_path.exists():
            self.file_path.unlink()
        self.status = OperationStatus.ROLLED_BACK
