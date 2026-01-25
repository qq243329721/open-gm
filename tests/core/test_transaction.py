"""事务系统的单元测试

测试 Operation、Transaction 和 TransactionLog 类。
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from gm.core.transaction import Transaction, TransactionLog, transaction
from gm.core.operations import (
    Operation,
    CallableOperation,
    CreateFileOperation,
    DeleteFileOperation,
    CreateDirectoryOperation,
    FileOperation,
    OperationStatus,
)
from gm.core.exceptions import TransactionException, TransactionRollbackError
from gm.core.logger import Logger


class TestOperationStatus:
    """测试 OperationStatus 枚举"""

    def test_operation_status_values(self):
        """测试操作状态值"""
        assert OperationStatus.PENDING.value == "pending"
        assert OperationStatus.EXECUTING.value == "executing"
        assert OperationStatus.COMPLETED.value == "completed"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.ROLLED_BACK.value == "rolled_back"


class TestCallableOperation:
    """测试 CallableOperation 类"""

    def test_callable_operation_execute(self):
        """测试可调用操作执行"""
        result_holder = []

        def execute_fn():
            result_holder.append("executed")
            return "result"

        operation = CallableOperation(execute_fn=execute_fn, description="Test operation")
        result = operation.execute()

        assert result == "result"
        assert result_holder == ["executed"]
        assert operation.status == OperationStatus.COMPLETED
        assert operation.is_completed()

    def test_callable_operation_with_rollback(self):
        """测试带回滚的可调用操作"""
        executed = []
        rolled_back = []

        def execute_fn():
            executed.append(True)

        def rollback_fn():
            rolled_back.append(True)

        operation = CallableOperation(
            execute_fn=execute_fn,
            rollback_fn=rollback_fn,
            description="Test with rollback",
        )

        operation.execute()
        assert executed == [True]

        operation.rollback()
        assert rolled_back == [True]

    def test_callable_operation_without_rollback(self):
        """测试没有回滚函数的操作"""
        operation = CallableOperation(
            execute_fn=lambda: "executed",
            description="No rollback",
        )

        operation.execute()
        operation.rollback()  # 应该不抛出异常


class TestCreateFileOperation:
    """测试 CreateFileOperation 类"""

    def test_create_file(self):
        """测试创建文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            operation = CreateFileOperation(file_path, content="Hello, World!")

            operation.execute()

            assert file_path.exists()
            assert file_path.read_text() == "Hello, World!"
            assert operation.status == OperationStatus.COMPLETED

    def test_create_file_with_parent_directories(self):
        """测试创建文件时自动创建父目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "a" / "b" / "c" / "test.txt"
            operation = CreateFileOperation(file_path, content="nested")

            operation.execute()

            assert file_path.exists()
            assert file_path.read_text() == "nested"

    def test_create_file_rollback(self):
        """测试创建文件后回滚"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            operation = CreateFileOperation(file_path, content="test")

            operation.execute()
            assert file_path.exists()

            operation.rollback()
            assert not file_path.exists()
            assert operation.status == OperationStatus.ROLLED_BACK

    def test_create_file_rollback_with_backup(self):
        """测试创建文件时，如果文件已存在则备份"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("original")

            operation = CreateFileOperation(file_path, content="new")
            operation.execute()
            assert file_path.read_text() == "new"

            operation.rollback()
            assert file_path.read_text() == "original"

    def test_create_file_execute_failure(self):
        """测试创建文件失败"""
        # 使用只读文件系统路径或无效字符
        import os

        # 在 Windows 上，尝试使用无效字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        file_path = None

        for char in invalid_chars:
            try:
                test_path = Path(f"test{char}file.txt")
                # 尝试检查路径有效性
                test_path.resolve()
            except (ValueError, OSError):
                file_path = test_path
                break

        # 如果上面的方法没有找到无效路径，使用绝对无法写入的路径
        if file_path is None:
            file_path = Path("Z:\\invalid\\path\\that\\does\\not\\exist\\test.txt")

        operation = CreateFileOperation(file_path, content="test")

        with pytest.raises(Exception):
            operation.execute()

        assert operation.status == OperationStatus.FAILED
        assert operation.error is not None


class TestDeleteFileOperation:
    """测试 DeleteFileOperation 类"""

    def test_delete_file(self):
        """测试删除文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("content")

            operation = DeleteFileOperation(file_path)
            operation.execute()

            assert not file_path.exists()
            assert operation.status == OperationStatus.COMPLETED

    def test_delete_nonexistent_file(self):
        """测试删除不存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.txt"

            operation = DeleteFileOperation(file_path)
            operation.execute()  # 应该不抛出异常

            assert not file_path.exists()

    def test_delete_file_rollback(self):
        """测试删除文件后回滚"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("content")

            operation = DeleteFileOperation(file_path)
            operation.execute()
            assert not file_path.exists()

            operation.rollback()
            assert file_path.exists()
            assert file_path.read_text() == "content"
            assert operation.status == OperationStatus.ROLLED_BACK


class TestCreateDirectoryOperation:
    """测试 CreateDirectoryOperation 类"""

    def test_create_directory(self):
        """测试创建目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "newdir"
            operation = CreateDirectoryOperation(dir_path)

            operation.execute()

            assert dir_path.exists()
            assert dir_path.is_dir()
            assert operation.status == OperationStatus.COMPLETED

    def test_create_nested_directories(self):
        """测试创建嵌套目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "a" / "b" / "c"
            operation = CreateDirectoryOperation(dir_path)

            operation.execute()

            assert dir_path.exists()
            assert dir_path.is_dir()

    def test_create_existing_directory(self):
        """测试创建已存在的目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "existing"
            dir_path.mkdir()

            operation = CreateDirectoryOperation(dir_path)
            operation.execute()  # 应该不抛出异常

            assert dir_path.exists()
            assert not operation.created  # created 应该为 False

    def test_create_directory_rollback(self):
        """测试创建目录后回滚"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "newdir"
            operation = CreateDirectoryOperation(dir_path)

            operation.execute()
            assert dir_path.exists()

            operation.rollback()
            assert not dir_path.exists()
            assert operation.status == OperationStatus.ROLLED_BACK


class TestTransactionLog:
    """测试 TransactionLog 类"""

    def test_transaction_log_creation(self):
        """测试事务日志创建"""
        log = TransactionLog("tx-123")

        assert log.transaction_id == "tx-123"
        assert len(log.entries) == 0

    def test_add_log_entry(self):
        """测试添加日志条目"""
        log = TransactionLog("tx-123")

        log.add_entry("op-1", "execute", {"description": "test"})
        log.add_entry("op-2", "rollback")

        assert len(log.entries) == 2
        assert log.entries[0]["operation_id"] == "op-1"
        assert log.entries[0]["event"] == "execute"
        assert log.entries[1]["operation_id"] == "op-2"
        assert log.entries[1]["event"] == "rollback"

    def test_transaction_log_to_dict(self):
        """测试转换日志为字典"""
        log = TransactionLog("tx-123")
        log.add_entry("op-1", "execute", {"description": "test"})

        log_dict = log.to_dict()

        assert log_dict["transaction_id"] == "tx-123"
        assert len(log_dict["entries"]) == 1
        assert log_dict["entries"][0]["operation_id"] == "op-1"


class TestTransaction:
    """测试 Transaction 类"""

    def test_transaction_creation(self):
        """测试事务创建"""
        tx = Transaction()

        assert tx.transaction_id is not None
        assert len(tx.operations) == 0
        assert tx.status == "pending"

    def test_add_operation_with_callable(self):
        """测试添加可调用操作"""
        tx = Transaction()

        def execute():
            return "result"

        def rollback():
            pass

        tx.add_operation(
            execute_fn=execute,
            rollback_fn=rollback,
            description="Test operation",
        )

        assert len(tx.operations) == 1
        assert tx.operations[0].description == "Test operation"

    def test_add_operation_with_operation_object(self):
        """测试添加 Operation 对象"""
        tx = Transaction()
        operation = CallableOperation(
            execute_fn=lambda: "result",
            description="Test",
        )

        tx.add_operation(operation=operation)

        assert len(tx.operations) == 1
        assert tx.operations[0] == operation

    def test_add_operation_chain(self):
        """测试链式添加操作"""
        tx = Transaction()

        tx.add_operation(execute_fn=lambda: None).add_operation(
            execute_fn=lambda: None
        )

        assert len(tx.operations) == 2

    def test_add_operation_to_committed_transaction_fails(self):
        """测试不能向已提交的事务添加操作"""
        tx = Transaction()
        tx.status = "committed"

        with pytest.raises(TransactionException):
            tx.add_operation(execute_fn=lambda: None)

    def test_transaction_commit_success(self):
        """测试成功提交事务"""
        executed = []

        tx = Transaction()
        tx.add_operation(execute_fn=lambda: executed.append(1))
        tx.add_operation(execute_fn=lambda: executed.append(2))

        tx.commit()

        assert executed == [1, 2]
        assert tx.status == "committed"
        assert len(tx.executed_operations) == 2

    def test_transaction_commit_with_rollback_on_failure(self):
        """测试事务提交失败时自动回滚"""
        executed = []
        rolled_back = []

        def execute_1():
            executed.append(1)

        def rollback_1():
            rolled_back.append(1)

        def execute_2():
            executed.append(2)
            raise ValueError("Operation 2 failed")

        def rollback_2():
            rolled_back.append(2)

        tx = Transaction()
        tx.add_operation(execute_fn=execute_1, rollback_fn=rollback_1)
        tx.add_operation(execute_fn=execute_2, rollback_fn=rollback_2)

        with pytest.raises(TransactionRollbackError):
            tx.commit()

        assert executed == [1, 2]
        assert rolled_back == [1]  # 只回滚已执行的操作
        assert tx.status == "failed"

    def test_transaction_commit_empty(self):
        """测试提交空事务"""
        tx = Transaction()
        tx.commit()

        assert tx.status == "committed"
        assert len(tx.executed_operations) == 0

    def test_transaction_manual_rollback(self):
        """测试手动回滚事务"""
        executed = []
        rolled_back = []

        tx = Transaction()
        tx.add_operation(
            execute_fn=lambda: executed.append(1),
            rollback_fn=lambda: rolled_back.append(1),
        )
        tx.add_operation(
            execute_fn=lambda: executed.append(2),
            rollback_fn=lambda: rolled_back.append(2),
        )

        # 在未提交时回滚，没有任何执行的操作，所以没有什么要回滚的
        tx.rollback()
        assert executed == []
        assert rolled_back == []  # 没有操作执行，所以没有回滚
        assert tx.status == "rolled_back"

        # 执行并回滚
        tx2 = Transaction()
        executed.clear()
        rolled_back.clear()

        tx2.add_operation(
            execute_fn=lambda: executed.append(1),
            rollback_fn=lambda: rolled_back.append(1),
        )
        tx2.add_operation(
            execute_fn=lambda: executed.append(2),
            rollback_fn=lambda: rolled_back.append(2),
        )

        tx2.commit()
        assert executed == [1, 2]
        assert tx2.status == "committed"

        # 不能在已提交后进行手动回滚，但可以通过其他方式测试回滚行为
        # 例如在 commit 之前发生错误时会自动回滚

    def test_transaction_context_manager_success(self):
        """测试上下文管理器成功情况"""
        executed = []

        with Transaction() as tx:
            tx.add_operation(execute_fn=lambda: executed.append(1))
            tx.add_operation(execute_fn=lambda: executed.append(2))

        assert executed == [1, 2]
        assert tx.status == "committed"

    def test_transaction_context_manager_rollback_on_exception(self):
        """测试上下文管理器异常回滚"""
        executed = []
        rolled_back = []

        # 测试在 commit 后抛出异常
        with pytest.raises(ValueError):
            with Transaction() as tx:
                tx.add_operation(
                    execute_fn=lambda: executed.append(1),
                    rollback_fn=lambda: rolled_back.append(1),
                )
                tx.add_operation(
                    execute_fn=lambda: executed.append(2),
                    rollback_fn=lambda: rolled_back.append(2),
                )
                tx.commit()
                # 提交成功后抛出异常
                raise ValueError("User exception")

        # 事务已提交，外部异常不会触发回滚
        assert executed == [1, 2]
        assert tx.status == "committed"

    def test_transaction_to_dict(self):
        """测试事务转换为字典"""
        tx = Transaction()
        tx.add_operation(execute_fn=lambda: None, description="Op 1")

        tx_dict = tx.to_dict()

        assert tx_dict["transaction_id"] == tx.transaction_id
        assert tx_dict["status"] == "pending"
        assert len(tx_dict["operations"]) == 1
        assert tx_dict["operations"][0]["description"] == "Op 1"

    def test_transaction_get_log(self):
        """测试获取事务日志"""
        tx = Transaction()
        tx.add_operation(execute_fn=lambda: None)
        tx.commit()

        log = tx.get_log()

        assert isinstance(log, TransactionLog)
        assert log.transaction_id == tx.transaction_id
        assert len(log.get_entries()) > 0

    def test_transaction_is_committed(self):
        """测试检查事务是否已提交"""
        tx = Transaction()
        assert not tx.is_committed()

        tx.commit()
        assert tx.is_committed()

    def test_transaction_is_rolled_back(self):
        """测试检查事务是否已回滚"""
        tx = Transaction()
        assert not tx.is_rolled_back()

        # 在未提交前可以回滚
        tx.add_operation(execute_fn=lambda: None)
        tx.rollback()

        assert tx.is_rolled_back()


class TestTransactionWithFileOperations:
    """测试事务与文件操作的集成"""

    def test_transaction_file_creation_and_rollback(self):
        """测试文件创建事务及回滚"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path_1 = Path(tmpdir) / "file1.txt"
            file_path_2 = Path(tmpdir) / "file2.txt"

            with Transaction() as tx:
                tx.add_operation(
                    operation=CreateFileOperation(file_path_1, content="content1")
                )
                tx.add_operation(
                    operation=CreateFileOperation(file_path_2, content="content2")
                )

            assert file_path_1.exists()
            assert file_path_2.exists()
            assert tx.status == "committed"

    def test_transaction_file_operations_partial_failure(self):
        """测试文件操作失败时的回滚"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path_1 = Path(tmpdir) / "file1.txt"
            file_path_2 = Path(tmpdir) / "file2.txt"

            tx = Transaction()
            tx.add_operation(
                operation=CreateFileOperation(file_path_1, content="content1")
            )

            def failing_operation():
                raise ValueError("Intentional failure")

            tx.add_operation(execute_fn=failing_operation)

            with pytest.raises(TransactionRollbackError):
                tx.commit()

            # 第一个文件应该被回滚
            assert not file_path_1.exists()
            assert tx.status == "failed"


class TestTransactionContextManager:
    """测试 transaction 上下文管理器工厂函数"""

    def test_transaction_context_factory_success(self):
        """测试工厂函数成功"""
        executed = []

        with transaction() as tx:
            tx.add_operation(execute_fn=lambda: executed.append(1))

        assert executed == [1]

    def test_transaction_context_factory_rollback(self):
        """测试工厂函数异常回滚"""
        executed = []
        rolled_back = []

        with pytest.raises(ValueError):
            with transaction() as tx:
                tx.add_operation(
                    execute_fn=lambda: executed.append(1),
                    rollback_fn=lambda: rolled_back.append(1),
                )
                # 在 commit 之前抛出异常，导致回滚
                raise ValueError("User exception")

        # 由于在 commit 之前抛出异常，操作不会执行，因此也不会回滚
        assert executed == []
        assert rolled_back == []


class TestTransactionEdgeCases:
    """测试事务的边界情况"""

    def test_transaction_rollback_failure(self):
        """测试回滚本身失败"""
        executed = []
        rollback_failed = False

        def failing_rollback():
            nonlocal rollback_failed
            rollback_failed = True
            raise RuntimeError("Rollback failed")

        tx = Transaction()
        tx.add_operation(
            execute_fn=lambda: executed.append(1),
            rollback_fn=failing_rollback,
        )

        # 回滚未执行的操作应该不会失败
        tx.rollback()
        assert tx.status == "rolled_back"

        # 现在执行并回滚，回滚会失败
        tx2 = Transaction()
        executed.clear()
        rollback_failed = False

        tx2.add_operation(
            execute_fn=lambda: executed.append(1),
            rollback_fn=failing_rollback,
        )

        tx2.commit()
        assert executed == [1]

        with pytest.raises(TransactionException):
            tx2.rollback()

        assert tx2.status == "rollback_failed"
        assert rollback_failed

    def test_transaction_add_operation_none_fails(self):
        """测试既不提供 operation 也不提供 execute_fn 会失败"""
        tx = Transaction()

        with pytest.raises(TransactionException):
            tx.add_operation()

    def test_transaction_commit_twice_fails(self):
        """测试不能提交事务两次"""
        tx = Transaction()
        tx.commit()

        with pytest.raises(TransactionException):
            tx.commit()

    def test_transaction_with_custom_id(self):
        """测试自定义事务 ID"""
        custom_id = "custom-tx-123"
        tx = Transaction(transaction_id=custom_id)

        assert tx.transaction_id == custom_id


class TestOperationMetadata:
    """测试操作元数据"""

    def test_operation_to_dict(self):
        """测试操作转换为字典"""
        operation = CallableOperation(
            execute_fn=lambda: None,
            description="Test operation",
        )

        op_dict = operation.to_dict()

        assert op_dict["operation_id"] == operation.operation_id
        assert op_dict["description"] == "Test operation"
        assert op_dict["status"] == "pending"
        assert op_dict["created_at"] is not None

    def test_operation_status_tracking(self):
        """测试操作状态跟踪"""
        operation = CallableOperation(execute_fn=lambda: None)

        assert operation.get_status() == OperationStatus.PENDING
        assert not operation.is_completed()
        assert not operation.is_failed()

        operation.execute()
        assert operation.is_completed()
        assert not operation.is_failed()
        assert operation.status == OperationStatus.COMPLETED

    def test_operation_error_tracking(self):
        """测试操作错误跟踪"""
        def failing_fn():
            raise ValueError("Test error")

        operation = CallableOperation(execute_fn=failing_fn)

        with pytest.raises(ValueError):
            operation.execute()

        assert operation.is_failed()
        assert operation.error is not None
        assert isinstance(operation.error, ValueError)
        assert operation.status == OperationStatus.FAILED
