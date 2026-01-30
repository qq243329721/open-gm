"""事务管理系统

提供原子操作和自动回滚功能。支持上下文管理器，确保事务要么全部成功，要么全部回滚。"""

from typing import List, Optional, Callable, Any, Dict
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
from contextlib import contextmanager

from gm.core.operations import Operation, CallableOperation, OperationStatus
from gm.core.logger import get_logger
from gm.core.exceptions import TransactionException, TransactionRollbackError

logger = get_logger("transaction")


class TransactionLog:
    """事务日志

    记录事务的执行历史，支持恢复和重放。
    """

    def __init__(self, transaction_id: str):
        """初始化事务日志
        Args:
            transaction_id: 事务 ID
        """
        self.transaction_id = transaction_id
        self.entries: List[Dict[str, Any]] = []
        self.created_at = datetime.now(timezone.utc)

    def add_entry(self, operation_id: str, event: str, details: Optional[Dict] = None) -> None:
        """添加日志条目
        Args:
            operation_id: 操作 ID
            event: 事件类型 (e.g., "execute", "rollback", "error")
            details: 事件详情
        """
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'operation_id': operation_id,
            'event': event,
            'details': details or {},
        }
        self.entries.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'transaction_id': self.transaction_id,
            'created_at': self.created_at.isoformat(),
            'entries': self.entries,
        }


class Transaction:
    """事务管理器

    管理一组操作的原子执行，提供提交和回滚功能。
    """

    def __init__(
        self,
        transaction_id: Optional[str] = None,
    ):
        """初始化事务
        Args:
            transaction_id: 事务 ID，如果为 None 则自动生成
        """
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self.operations: List[Operation] = []
        self.executed_operations: List[Operation] = []
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.committed_at: Optional[datetime] = None
        self.rolled_back_at: Optional[datetime] = None
        self.log = TransactionLog(self.transaction_id)
        self.error: Optional[Exception] = None

    def add_operation(
        self,
        operation: Optional[Operation] = None,
        execute_fn: Optional[Callable[[], Any]] = None,
        rollback_fn: Optional[Callable[[], None]] = None,
        description: str = "",
    ) -> "Transaction":
        """添加操作到事务"""
        if self.status != "pending":
            raise TransactionException(f"Cannot add operation to {self.status} transaction")

        if operation is None:
            if execute_fn is None:
                raise TransactionException("Either operation or execute_fn must be provided")
            operation = CallableOperation(
                execute_fn=execute_fn,
                rollback_fn=rollback_fn,
                description=description,
            )

        self.operations.append(operation)
        return self

    def commit(self) -> None:
        """提交事务"""
        if self.status != "pending":
            raise TransactionException(f"Cannot commit {self.status} transaction")

        self.status = "executing"
        try:
            for operation in self.operations:
                operation.status = OperationStatus.EXECUTING
                operation.execute()
                self.executed_operations.append(operation)
                self.log.add_entry(operation.operation_id, "execute")
            
            self.status = "committed"
            self.committed_at = datetime.now(timezone.utc)
        except Exception as e:
            self.status = "failed"
            self.error = e
            self.rollback()
            raise TransactionRollbackError(f"Transaction failed, rolled back: {e}") from e

    def rollback(self) -> None:
        """回滚事务"""
        if self.status == "rolled_back":
            return

        for operation in reversed(self.executed_operations):
            try:
                operation.rollback()
                self.log.add_entry(operation.operation_id, "rollback")
            except Exception as e:
                logger.error(f"Rollback failed for operation {operation.operation_id}: {e}")

        self.status = "rolled_back"
        self.rolled_back_at = datetime.now(timezone.utc)

    def __enter__(self) -> "Transaction":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            if self.status in ("pending", "executing"):
                self.rollback()
            return False
        else:
            if self.status == "pending":
                self.commit()
            return True
