"""事务管理系统

提供原子操作和自动回滚功能。支持上下文管理器，确保事务要么全部成功，
要么全部回滚。
"""

from typing import List, Optional, Callable, Any, Dict
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
from contextlib import contextmanager

from gm.core.operations import Operation, CallableOperation, OperationStatus
from gm.core.logger import Logger
from gm.core.exceptions import TransactionException, TransactionRollbackError


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
        """转换为字典

        Returns:
            包含日志信息的字典
        """
        return {
            'transaction_id': self.transaction_id,
            'created_at': self.created_at.isoformat(),
            'entries': self.entries,
        }

    def get_entries(self) -> List[Dict[str, Any]]:
        """获取所有日志条目

        Returns:
            日志条目列表
        """
        return self.entries.copy()


class Transaction:
    """事务管理器

    管理一组操作的原子执行，提供提交和回滚功能。
    """

    def __init__(
        self,
        transaction_id: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """初始化事务

        Args:
            transaction_id: 事务 ID，如果为 None 则自动生成
            logger: 日志记录器实例
        """
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self.logger = logger or Logger()
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
        """添加操作到事务

        支持两种方式：
        1. 传入 Operation 对象
        2. 传入 execute_fn 和可选的 rollback_fn

        Args:
            operation: Operation 对象
            execute_fn: 执行函数
            rollback_fn: 回滚函数
            description: 操作描述

        Returns:
            返回 self 以支持链式调用

        Raises:
            TransactionException: 如果事务已提交或回滚
        """
        if self.status != "pending":
            raise TransactionException(
                f"Cannot add operation to {self.status} transaction"
            )

        if operation is None:
            if execute_fn is None:
                raise TransactionException("Either operation or execute_fn must be provided")
            operation = CallableOperation(
                execute_fn=execute_fn,
                rollback_fn=rollback_fn,
                description=description,
                logger=self.logger,
            )

        self.operations.append(operation)
        self.logger.debug(
            "operation_added",
            transaction_id=self.transaction_id,
            operation_id=operation.operation_id,
            description=operation.description,
        )
        return self

    def commit(self) -> None:
        """提交事务

        按顺序执行所有操作。如果任何操作失败，会自动回滚已执行的操作。

        Raises:
            TransactionException: 如果事务已提交或回滚
            TransactionRollbackError: 如果操作执行失败且回滚也失败
        """
        if self.status != "pending":
            raise TransactionException(
                f"Cannot commit {self.status} transaction"
            )

        self.status = "executing"
        self.logger.info(
            "transaction_commit_started",
            transaction_id=self.transaction_id,
            operations_count=len(self.operations),
        )

        try:
            # 执行所有操作
            for operation in self.operations:
                try:
                    operation.status = OperationStatus.EXECUTING
                    result = operation.execute()
                    self.executed_operations.append(operation)
                    self.log.add_entry(
                        operation.operation_id,
                        "execute",
                        {'description': operation.description},
                    )
                    self.logger.info(
                        "operation_executed",
                        transaction_id=self.transaction_id,
                        operation_id=operation.operation_id,
                    )
                except Exception as e:
                    operation.error = e
                    operation.status = OperationStatus.FAILED
                    self.log.add_entry(
                        operation.operation_id,
                        "error",
                        {'error': str(e)},
                    )
                    self.logger.error(
                        "operation_failed",
                        transaction_id=self.transaction_id,
                        operation_id=operation.operation_id,
                        error=str(e),
                    )
                    # 回滚已执行的操作
                    self._rollback_executed_operations()
                    self.status = "failed"
                    self.error = e
                    raise TransactionRollbackError(
                        f"Transaction failed at operation {operation.operation_id}: {str(e)}",
                        executed_ops=self.executed_operations,
                    ) from e

            # 所有操作成功执行
            self.status = "committed"
            self.committed_at = datetime.now(timezone.utc)
            self.logger.info(
                "transaction_committed",
                transaction_id=self.transaction_id,
                operations_count=len(self.operations),
            )

        except TransactionRollbackError:
            raise
        except Exception as e:
            self.status = "failed"
            self.error = e
            self.logger.error(
                "transaction_failed",
                transaction_id=self.transaction_id,
                error=str(e),
            )
            raise TransactionException(f"Transaction failed: {str(e)}") from e

    def rollback(self) -> None:
        """手动回滚事务

        回滚所有已执行的操作。

        Raises:
            TransactionException: 如果事务尚未提交或已回滚
        """
        if self.status == "rolled_back":
            raise TransactionException("Transaction is already rolled back")

        if self.status == "rollback_failed":
            raise TransactionException("Transaction rollback has already failed")

        self.logger.info(
            "transaction_rollback_started",
            transaction_id=self.transaction_id,
        )

        try:
            self._rollback_executed_operations()
            self.status = "rolled_back"
            self.rolled_back_at = datetime.now(timezone.utc)
            self.logger.info(
                "transaction_rolled_back",
                transaction_id=self.transaction_id,
                operations_count=len(self.executed_operations),
            )
        except Exception as e:
            self.status = "rollback_failed"
            self.error = e
            self.logger.error(
                "transaction_rollback_failed",
                transaction_id=self.transaction_id,
                error=str(e),
            )
            raise TransactionException(f"Transaction rollback failed: {str(e)}") from e

    def _rollback_executed_operations(self) -> None:
        """回滚已执行的操作

        按逆序回滚操作。

        Raises:
            TransactionRollbackError: 如果任何操作回滚失败
        """
        rollback_errors = []

        # 按逆序回滚
        for operation in reversed(self.executed_operations):
            try:
                operation.rollback()
                self.log.add_entry(
                    operation.operation_id,
                    "rollback",
                    {'description': operation.description},
                )
                self.logger.info(
                    "operation_rolled_back",
                    transaction_id=self.transaction_id,
                    operation_id=operation.operation_id,
                )
            except Exception as e:
                rollback_errors.append((operation.operation_id, e))
                self.log.add_entry(
                    operation.operation_id,
                    "rollback_error",
                    {'error': str(e)},
                )
                self.logger.error(
                    "operation_rollback_failed",
                    transaction_id=self.transaction_id,
                    operation_id=operation.operation_id,
                    error=str(e),
                )

        if rollback_errors:
            error_messages = "; ".join(
                [f"{op_id}: {str(e)}" for op_id, e in rollback_errors]
            )
            raise TransactionRollbackError(
                f"Rollback failed for operations: {error_messages}",
                executed_ops=self.executed_operations,
            )

    def __enter__(self) -> "Transaction":
        """进入上下文管理器

        Returns:
            Transaction 实例本身
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出上下文管理器

        如果有异常发生，自动回滚事务。
        否则，自动提交事务。

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯

        Returns:
            False，表示异常将继续传播
        """
        if exc_type is not None:
            # 有异常发生，回滚事务（如果未提交）
            if self.status in ("pending", "executing", "failed"):
                try:
                    if self.status in ("pending", "executing"):
                        self.rollback()
                except Exception as e:
                    self.logger.error(
                        "context_exit_rollback_failed",
                        transaction_id=self.transaction_id,
                        error=str(e),
                    )
            return False
        else:
            # 没有异常，提交事务
            if self.status == "pending":
                try:
                    self.commit()
                except Exception as e:
                    self.logger.error(
                        "context_exit_commit_failed",
                        transaction_id=self.transaction_id,
                        error=str(e),
                    )
                    raise
            return True

    def is_committed(self) -> bool:
        """检查事务是否已提交

        Returns:
            True 如果事务已提交
        """
        return self.status == "committed"

    def is_rolled_back(self) -> bool:
        """检查事务是否已回滚

        Returns:
            True 如果事务已回滚
        """
        return self.status == "rolled_back"

    def get_log(self) -> TransactionLog:
        """获取事务日志

        Returns:
            事务日志对象
        """
        return self.log

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含事务信息的字典
        """
        return {
            'transaction_id': self.transaction_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'committed_at': self.committed_at.isoformat() if self.committed_at else None,
            'rolled_back_at': self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            'operations': [op.to_dict() for op in self.operations],
            'executed_operations': [op.to_dict() for op in self.executed_operations],
            'error': str(self.error) if self.error else None,
            'log': self.log.to_dict(),
        }


class TransactionPersistence:
    """事务持久化和恢复管理器

    支持将事务日志保存到文件，用于故障恢复。
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """初始化持久化管理器

        Args:
            log_dir: 日志目录，默认为 .gm/.transaction-logs
        """
        if log_dir is None:
            log_dir = Path.cwd() / ".gm" / ".transaction-logs"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def save_transaction(self, tx: "Transaction") -> None:
        """保存事务日志到文件

        Args:
            tx: 事务对象
        """
        try:
            log_file = self.log_dir / f"{tx.transaction_id}.json"

            log_data = {
                "transaction_id": tx.transaction_id,
                "status": tx.status,
                "created_at": tx.created_at.isoformat(),
                "committed_at": tx.committed_at.isoformat() if tx.committed_at else None,
                "rolled_back_at": tx.rolled_back_at.isoformat() if tx.rolled_back_at else None,
                "operations": [op.to_dict() for op in tx.operations],
                "executed_operations": [op.to_dict() for op in tx.executed_operations],
                "error": str(tx.error) if tx.error else None,
                "log": tx.log.to_dict(),
            }

            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            # 记录保存失败，但不抛出异常以避免影响事务本身
            pass

    def load_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """从文件加载事务日志

        Args:
            transaction_id: 事务 ID

        Returns:
            事务数据字典，或 None 如果文件不存在
        """
        try:
            log_file = self.log_dir / f"{transaction_id}.json"

            if not log_file.exists():
                return None

            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception:
            return None

    def get_incomplete_transactions(self) -> List[str]:
        """获取所有未完成的事务 ID

        Returns:
            未完成的事务 ID 列表
        """
        incomplete = []

        try:
            if self.log_dir.exists():
                for log_file in self.log_dir.glob("*.json"):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            status = data.get("status")
                            if status in ("pending", "executing", "failed"):
                                incomplete.append(data.get("transaction_id"))
                    except Exception:
                        pass

        except Exception:
            pass

        return incomplete

    def cleanup_transaction_log(self, transaction_id: str) -> None:
        """清理事务日志文件

        Args:
            transaction_id: 事务 ID
        """
        try:
            log_file = self.log_dir / f"{transaction_id}.json"
            if log_file.exists():
                log_file.unlink()
        except Exception:
            pass


@contextmanager
def transaction(
    transaction_id: Optional[str] = None,
    logger: Optional[Logger] = None,
):
    """事务上下文管理器工厂函数

    Args:
        transaction_id: 事务 ID
        logger: 日志记录器

    Yields:
        Transaction 实例
    """
    tx = Transaction(transaction_id=transaction_id, logger=logger)
    try:
        yield tx
        if tx.status == "pending":
            tx.commit()
    except Exception:
        if tx.status in ("pending", "executing"):
            try:
                tx.rollback()
            except Exception:
                pass
        raise
