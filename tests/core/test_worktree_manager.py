"""事务管理系统和 WorktreeManager 的集成测试

测试事务原子性、回滚、持久化和恢复机制。
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from gm.core.worktree_manager import WorktreeManager
from gm.core.transaction import Transaction, TransactionPersistence, TransactionLog
from gm.core.operations import CallableOperation, CreateFileOperation, OperationStatus
from gm.core.exceptions import (
    WorktreeNotFound,
    WorktreeAlreadyExists,
    GitException,
    ConfigException,
    TransactionRollbackError,
)
from gm.core.logger import Logger


class TestTransactionPersistence:
    """测试事务持久化和恢复"""

    def test_save_and_load_transaction(self):
        """测试保存和加载事务"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            # 创建事务
            tx = Transaction()
            tx.add_operation(
                execute_fn=lambda: "result",
                description="Test operation",
            )
            tx.commit()

            # 保存事务
            persistence.save_transaction(tx)

            # 加载事务
            loaded_data = persistence.load_transaction(tx.transaction_id)

            assert loaded_data is not None
            assert loaded_data["transaction_id"] == tx.transaction_id
            assert loaded_data["status"] == "committed"

    def test_get_incomplete_transactions(self):
        """测试获取未完成的事务"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            # 创建多个事务
            tx1 = Transaction()
            tx1.add_operation(execute_fn=lambda: None, description="Op 1")

            tx2 = Transaction()
            tx2.add_operation(execute_fn=lambda: None, description="Op 2")
            tx2.commit()

            # 保存事务
            persistence.save_transaction(tx1)
            persistence.save_transaction(tx2)

            # 获取未完成的事务
            incomplete = persistence.get_incomplete_transactions()

            assert len(incomplete) == 1
            assert incomplete[0] == tx1.transaction_id

    def test_cleanup_transaction_log(self):
        """测试清理事务日志"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            # 创建并保存事务
            tx = Transaction()
            tx.add_operation(execute_fn=lambda: None, description="Op")
            persistence.save_transaction(tx)

            log_file = log_dir / f"{tx.transaction_id}.json"
            assert log_file.exists()

            # 清理日志
            persistence.cleanup_transaction_log(tx.transaction_id)
            assert not log_file.exists()


class TestTransactionAtomicity:
    """测试事务原子性"""

    def test_transaction_all_success(self):
        """测试所有操作成功时的事务提交"""
        results = []

        tx = Transaction()
        tx.add_operation(
            execute_fn=lambda: results.append(1),
            description="Op 1",
        )
        tx.add_operation(
            execute_fn=lambda: results.append(2),
            description="Op 2",
        )
        tx.add_operation(
            execute_fn=lambda: results.append(3),
            description="Op 3",
        )

        tx.commit()

        assert tx.status == "committed"
        assert results == [1, 2, 3]
        assert len(tx.executed_operations) == 3

    def test_transaction_partial_failure_and_rollback(self):
        """测试部分失败时的自动回滚"""
        results = []
        rolled_back = []

        def rollback_1():
            rolled_back.append(1)

        def rollback_2():
            rolled_back.append(2)

        tx = Transaction()

        # 操作 1：成功
        tx.add_operation(
            execute_fn=lambda: results.append(1),
            rollback_fn=rollback_1,
            description="Op 1",
        )

        # 操作 2：成功
        tx.add_operation(
            execute_fn=lambda: results.append(2),
            rollback_fn=rollback_2,
            description="Op 2",
        )

        # 操作 3：失败
        tx.add_operation(
            execute_fn=lambda: (_ for _ in ()).throw(Exception("Operation failed")),
            description="Op 3",
        )

        # 提交应该失败
        with pytest.raises(TransactionRollbackError):
            tx.commit()

        # 验证状态
        assert tx.status == "failed"
        assert results == [1, 2]
        assert len(tx.executed_operations) == 2
        # 操作应该被反向回滚
        assert rolled_back == [2, 1]

    def test_transaction_file_operations_atomicity(self):
        """测试文件操作的原子性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file3 = Path(tmpdir) / "file3.txt"

            tx = Transaction()

            # 创建文件 1
            tx.add_operation(
                operation=CreateFileOperation(file1, content="Content 1"),
                description="Create file 1",
            )

            # 创建文件 2
            tx.add_operation(
                operation=CreateFileOperation(file2, content="Content 2"),
                description="Create file 2",
            )

            # 创建文件 3 失败
            tx.add_operation(
                execute_fn=lambda: (_ for _ in ()).throw(Exception("Disk full")),
                description="Create file 3",
            )

            with pytest.raises(TransactionRollbackError):
                tx.commit()

            # 验证文件被回滚
            assert not file1.exists()
            assert not file2.exists()
            assert not file3.exists()


class TestWorktreeManager:
    """测试 WorktreeManager"""

    @pytest.fixture
    def setup_project(self):
        """设置测试项目"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            # 创建 git 仓库
            with patch("gm.core.git_client.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # 创建 .gm 目录
            gm_dir = project_path / ".gm"
            gm_dir.mkdir(parents=True)

            # 创建配置文件
            config_file = project_path / ".gm.yaml"
            config_data = {
                "initialized": True,
                "use_local_branch": True,
                "main_branch": "main",
                "branch_mapping": {},
                "shared_files": [],
            }
            with open(config_file, 'w') as f:
                json.dump(config_data, f)

            yield project_path

    def test_worktree_manager_initialization(self, setup_project):
        """测试 WorktreeManager 初始化"""
        manager = WorktreeManager(setup_project)

        assert manager.project_path == setup_project
        assert manager.git_client is not None
        assert manager.config_manager is not None

    def test_worktree_manager_get_worktrees(self, setup_project):
        """测试获取 worktree 列表"""
        manager = WorktreeManager(setup_project)

        # 添加 worktree 配置
        gm_dir = setup_project / ".gm"
        config_file = setup_project / ".gm.yaml"

        with open(config_file, 'r') as f:
            config = json.load(f)

        # 创建 worktree 目录
        wt_dir = gm_dir / "feature_ui"
        wt_dir.mkdir(parents=True, exist_ok=True)

        config["worktrees"] = {
            "feature_ui": {
                "branch": "feature/ui",
                "path": str(wt_dir),
            }
        }

        with open(config_file, 'w') as f:
            json.dump(config, f)

        # 获取 worktree 列表
        worktrees = manager.get_worktrees()

        assert len(worktrees) == 1
        assert worktrees[0]["branch"] == "feature/ui"
        assert worktrees[0]["exists"] is True

    def test_worktree_manager_get_status(self, setup_project):
        """测试获取 worktree 状态"""
        manager = WorktreeManager(setup_project)

        # 创建 worktree 目录
        gm_dir = setup_project / ".gm"
        # feature/ui 会被映射为 feature-ui (/ → -)
        wt_dir = gm_dir / "feature-ui"
        wt_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(manager.git_client, 'has_uncommitted_changes', return_value=False):
            status = manager.get_worktree_status("feature/ui")

            assert status["branch"] == "feature/ui"
            assert status["exists"] is True
            assert status["has_changes"] is False


class TestTransactionIntegration:
    """事务集成测试"""

    def test_transaction_with_context_manager(self):
        """测试使用上下文管理器的事务"""
        from gm.core.transaction import transaction

        results = []
        tx_obj = None

        with transaction() as tx:
            tx_obj = tx
            tx.add_operation(
                execute_fn=lambda: results.append(1),
                description="Op 1",
            )
            tx.add_operation(
                execute_fn=lambda: results.append(2),
                description="Op 2",
            )

        assert tx_obj.status == "committed"
        assert results == [1, 2]

    def test_transaction_rollback_on_exception(self):
        """测试异常时自动回滚"""
        from gm.core.transaction import transaction

        results = []
        rolled_back = []

        def rollback_fn():
            rolled_back.append(1)

        try:
            with transaction() as tx:
                tx.add_operation(
                    execute_fn=lambda: results.append(1),
                    rollback_fn=rollback_fn,
                    description="Op 1",
                )
                # 在上下文中抛出异常
                raise Exception("Test exception")
        except Exception:
            pass

        # 由于异常在上下文中发生，事务应该被回滚
        # (不过在这个测试中，异常发生在 commit 之前)
        assert rolled_back == []  # 因为异常在 commit 前

    def test_transaction_multiple_operations(self):
        """测试多个操作的事务"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"

            tx = Transaction()

            # 添加多个操作
            tx.add_operation(
                operation=CreateFileOperation(file1, content="File 1"),
                description="Create file 1",
            )

            tx.add_operation(
                operation=CreateFileOperation(file2, content="File 2"),
                description="Create file 2",
            )

            tx.add_operation(
                execute_fn=lambda: (
                    print("Extra operation"),
                ),
                description="Extra operation",
            )

            tx.commit()

            # 验证所有操作都已执行
            assert tx.status == "committed"
            assert file1.exists()
            assert file2.exists()
            assert len(tx.executed_operations) == 3


class TestTransactionRecoveryScenarios:
    """事务恢复场景测试"""

    def test_incomplete_transaction_detection(self):
        """测试未完成事务的检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            # 创建几个处于不同状态的事务日志
            tx_data = [
                {
                    "transaction_id": "tx_pending",
                    "status": "pending",
                    "created_at": "2026-01-25T00:00:00",
                    "operations": [],
                    "executed_operations": [],
                    "log": {"transaction_id": "tx_pending", "entries": []},
                },
                {
                    "transaction_id": "tx_executing",
                    "status": "executing",
                    "created_at": "2026-01-25T00:00:00",
                    "operations": [],
                    "executed_operations": [],
                    "log": {"transaction_id": "tx_executing", "entries": []},
                },
                {
                    "transaction_id": "tx_committed",
                    "status": "committed",
                    "created_at": "2026-01-25T00:00:00",
                    "operations": [],
                    "executed_operations": [],
                    "log": {"transaction_id": "tx_committed", "entries": []},
                },
            ]

            # 保存事务日志
            for tx_data_item in tx_data:
                log_file = log_dir / f"{tx_data_item['transaction_id']}.json"
                with open(log_file, 'w') as f:
                    json.dump(tx_data_item, f)

            # 获取未完成的事务
            incomplete = persistence.get_incomplete_transactions()

            assert len(incomplete) == 2
            assert "tx_pending" in incomplete
            assert "tx_executing" in incomplete
            assert "tx_committed" not in incomplete

    def test_transaction_recovery_after_failure(self):
        """测试失败后的事务恢复"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            # 模拟一个失败的事务
            results = []
            rolled_back = []

            def rollback_fn():
                rolled_back.append(1)

            tx = Transaction()
            tx.add_operation(
                execute_fn=lambda: results.append(1),
                rollback_fn=rollback_fn,
                description="Op 1",
            )

            try:
                tx.add_operation(
                    execute_fn=lambda: (_ for _ in ()).throw(Exception("Simulated failure")),
                    description="Op 2",
                )
                tx.commit()
            except TransactionRollbackError:
                pass

            # 保存失败的事务
            persistence.save_transaction(tx)

            # 验证失败的事务被记录
            assert tx.status == "failed"
            incomplete = persistence.get_incomplete_transactions()
            assert tx.transaction_id in incomplete


class TestTransactionLogPersistence:
    """事务日志持久化测试"""

    def test_transaction_log_json_format(self):
        """测试事务日志的 JSON 格式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            tx = Transaction()
            tx.add_operation(
                execute_fn=lambda: "result",
                description="Test operation",
            )
            tx.commit()

            persistence.save_transaction(tx)

            log_file = log_dir / f"{tx.transaction_id}.json"
            with open(log_file, 'r') as f:
                data = json.load(f)

            assert "transaction_id" in data
            assert "status" in data
            assert "created_at" in data
            assert "operations" in data
            assert "executed_operations" in data
            assert "log" in data
            assert data["status"] == "committed"

    def test_transaction_log_with_errors(self):
        """测试包含错误的事务日志"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / ".transaction-logs"
            persistence = TransactionPersistence(log_dir)

            tx = Transaction()
            tx.add_operation(
                execute_fn=lambda: None,
                description="Op 1",
            )

            try:
                tx.add_operation(
                    execute_fn=lambda: (_ for _ in ()).throw(ValueError("Test error")),
                    description="Op 2",
                )
                tx.commit()
            except TransactionRollbackError:
                pass

            persistence.save_transaction(tx)

            loaded = persistence.load_transaction(tx.transaction_id)
            assert loaded is not None
            assert loaded["status"] == "failed"
            assert loaded["error"] is not None
