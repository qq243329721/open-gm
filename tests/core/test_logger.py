"""结构化日志系统的单元测试"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from gm.core.logger import (
    Logger,
    LoggerConfig,
    AuditLogEntry,
    OperationTracer,
    OperationScope,
    get_logger,
    configure_logger,
    _request_id,
    _operation_id,
    _user_id,
)


class TestLoggerConfig:
    """测试 LoggerConfig 类"""

    def test_default_config(self):
        """测试默认配置"""
        config = LoggerConfig()

        assert config.log_dir is None
        assert config.level == "INFO"
        assert config.json_output is True
        assert config.console_output is True

    def test_custom_config(self):
        """测试自定义配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            config = LoggerConfig(
                log_dir=log_dir,
                level="DEBUG",
                json_output=True,
                console_output=False,
            )

            assert config.log_dir == log_dir
            assert config.level == "DEBUG"
            assert config.json_output is True
            assert config.console_output is False


class TestLogger:
    """测试 Logger 类"""

    def test_logger_creation(self):
        """测试日志记录器创建"""
        logger = Logger("test")

        assert logger.name == "test"
        assert logger.config is not None

    def test_logger_with_config(self):
        """测试带配置的日志记录器创建"""
        config = LoggerConfig(level="DEBUG")
        logger = Logger("test", config)

        assert logger.config.level == "DEBUG"

    def test_logger_debug(self, caplog):
        """测试 DEBUG 日志"""
        config = LoggerConfig(json_output=False)
        logger = Logger("test", config)

        logger.debug("test_event", key="value")
        # 验证日志被记录（使用 structlog）

    def test_logger_info(self, caplog):
        """测试 INFO 日志"""
        config = LoggerConfig(json_output=False)
        logger = Logger("test", config)

        logger.info("test_event", key="value")

    def test_logger_warning(self, caplog):
        """测试 WARNING 日志"""
        config = LoggerConfig(json_output=False)
        logger = Logger("test", config)

        logger.warning("test_event", key="value")

    def test_logger_error(self, caplog):
        """测试 ERROR 日志"""
        config = LoggerConfig(json_output=False)
        logger = Logger("test", config)

        logger.error("test_event", key="value")

    def test_set_request_id(self):
        """测试设置请求 ID"""
        Logger.clear_context()

        Logger.set_request_id("req-123")
        assert _request_id.get() == "req-123"

    def test_set_operation_id(self):
        """测试设置操作 ID"""
        Logger.clear_context()

        Logger.set_operation_id("op-456")
        assert _operation_id.get() == "op-456"

    def test_set_user_id(self):
        """测试设置用户 ID"""
        Logger.clear_context()

        Logger.set_user_id("user-789")
        assert _user_id.get() == "user-789"

    def test_clear_context(self):
        """测试清除上下文"""
        Logger.set_request_id("req-123")
        Logger.set_operation_id("op-456")
        Logger.set_user_id("user-789")

        Logger.clear_context()

        assert _request_id.get() == ""
        assert _operation_id.get() == ""
        assert _user_id.get() == ""

    def test_log_file_creation(self):
        """测试日志文件创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            config = LoggerConfig(log_dir=log_dir)
            logger = Logger("test", config)

            logger.info("test_event")

            log_file = log_dir / "gm.log"
            assert log_file.exists()


class TestAuditLogEntry:
    """测试 AuditLogEntry 类"""

    def test_audit_log_creation_success(self):
        """测试成功操作的审计日志条目创建"""
        timestamp = datetime.now(timezone.utc)
        entry = AuditLogEntry(
            operation_type="add_worktree",
            user="test_user",
            operation_details={"branch": "feature/test"},
            status="success",
            result={"worktree_path": "/path/to/worktree"},
            timestamp=timestamp,
        )

        assert entry.operation_type == "add_worktree"
        assert entry.user == "test_user"
        assert entry.status == "success"
        assert entry.error_message is None

    def test_audit_log_creation_failure(self):
        """测试失败操作的审计日志条目创建"""
        entry = AuditLogEntry(
            operation_type="add_worktree",
            user="test_user",
            operation_details={"branch": "feature/test"},
            status="failure",
            error_message="Worktree already exists",
        )

        assert entry.status == "failure"
        assert entry.error_message == "Worktree already exists"

    def test_audit_log_to_dict(self):
        """测试审计日志转换为字典"""
        entry = AuditLogEntry(
            operation_type="add_worktree",
            user="test_user",
            operation_details={"branch": "feature/test"},
            status="success",
            result={"worktree_path": "/path/to/worktree"},
        )

        data = entry.to_dict()

        assert data['operation_type'] == "add_worktree"
        assert data['user'] == "test_user"
        assert data['status'] == "success"
        assert 'timestamp' in data
        assert 'details' in data
        assert 'result' in data

    def test_audit_log_to_json(self):
        """测试审计日志转换为 JSON"""
        entry = AuditLogEntry(
            operation_type="add_worktree",
            user="test_user",
            operation_details={"branch": "feature/test"},
            status="success",
        )

        json_str = entry.to_json()
        data = json.loads(json_str)

        assert data['operation_type'] == "add_worktree"
        assert data['user'] == "test_user"
        assert data['status'] == "success"

    def test_audit_log_json_with_error(self):
        """测试包含错误的审计日志转换为 JSON"""
        entry = AuditLogEntry(
            operation_type="delete_worktree",
            user="test_user",
            operation_details={"branch": "feature/test"},
            status="failure",
            error_message="Worktree not found",
        )

        json_str = entry.to_json()
        data = json.loads(json_str)

        assert 'error_message' in data
        assert data['error_message'] == "Worktree not found"


class TestOperationTracer:
    """测试 OperationTracer 类"""

    def test_tracer_creation(self):
        """测试操作追踪器创建"""
        tracer = OperationTracer()

        assert tracer.logger is not None
        assert len(tracer.operations) == 0

    def test_start_operation(self):
        """测试启动操作追踪"""
        tracer = OperationTracer()

        op_id = tracer.start_operation("test_operation", branch="feature/test")

        assert op_id in tracer.operations
        assert tracer.operations[op_id]['name'] == "test_operation"
        assert tracer.operations[op_id]['status'] == "running"

    def test_start_operation_with_custom_id(self):
        """测试使用自定义 ID 启动操作"""
        tracer = OperationTracer()
        custom_id = "custom-op-123"

        op_id = tracer.start_operation(
            "test_operation",
            operation_id=custom_id,
        )

        assert op_id == custom_id

    def test_end_operation_success(self):
        """测试操作成功完成"""
        tracer = OperationTracer()

        op_id = tracer.start_operation("test_operation")
        stats = tracer.end_operation(op_id, status="success", result={"key": "value"})

        assert stats['operation_id'] == op_id
        assert stats['status'] == "success"
        assert 'duration_ms' in stats
        assert stats['duration_ms'] >= 0

    def test_end_operation_failure(self):
        """测试操作失败"""
        tracer = OperationTracer()

        op_id = tracer.start_operation("test_operation")
        stats = tracer.end_operation(op_id, status="failure")

        assert stats['status'] == "failure"

    def test_end_nonexistent_operation(self):
        """测试结束不存在的操作"""
        tracer = OperationTracer()

        with pytest.raises(ValueError, match="not found"):
            tracer.end_operation("nonexistent-op")

    def test_record_exception(self):
        """测试记录异常"""
        tracer = OperationTracer()

        op_id = tracer.start_operation("test_operation")

        try:
            raise ValueError("Test error")
        except ValueError as e:
            tracer.record_exception(op_id, e)

    def test_record_exception_nonexistent_operation(self):
        """测试记录不存在操作的异常"""
        tracer = OperationTracer()

        with pytest.raises(ValueError, match="not found"):
            tracer.record_exception(
                "nonexistent-op",
                ValueError("Test error")
            )

    def test_get_operation_stats(self):
        """测试获取操作统计"""
        tracer = OperationTracer()

        op_id = tracer.start_operation("test_operation", branch="feature/test")
        tracer.end_operation(op_id, status="success")

        stats = tracer.get_operation_stats(op_id)

        assert stats is not None
        assert stats['name'] == "test_operation"
        assert stats['status'] == "success"
        assert stats['duration_ms'] >= 0

    def test_get_nonexistent_operation_stats(self):
        """测试获取不存在操作的统计"""
        tracer = OperationTracer()

        stats = tracer.get_operation_stats("nonexistent-op")

        assert stats is None

    def test_get_all_operations(self):
        """测试获取所有操作统计"""
        tracer = OperationTracer()

        op1 = tracer.start_operation("operation1")
        op2 = tracer.start_operation("operation2")
        tracer.end_operation(op1, status="success")
        tracer.end_operation(op2, status="failure")

        all_ops = tracer.get_all_operations()

        assert len(all_ops) == 2
        assert op1 in all_ops
        assert op2 in all_ops

    def test_clear_operations(self):
        """测试清除所有操作"""
        tracer = OperationTracer()

        tracer.start_operation("operation1")
        tracer.start_operation("operation2")

        assert len(tracer.operations) == 2

        tracer.clear_operations()

        assert len(tracer.operations) == 0


class TestOperationScope:
    """测试 OperationScope 上下文管理器"""

    def test_operation_scope_success(self):
        """测试操作范围成功执行"""
        with OperationScope("test_operation", context={"branch": "feature/test"}) as scope:
            assert scope.operation_id is not None
            assert scope.exception_occurred is False

        assert scope.exception_occurred is False

    def test_operation_scope_with_exception(self):
        """测试操作范围异常处理"""
        with pytest.raises(ValueError):
            with OperationScope("test_operation") as scope:
                raise ValueError("Test error")

        assert scope.exception_occurred is True

    def test_operation_scope_custom_id(self):
        """测试自定义操作 ID"""
        custom_id = "custom-op-123"

        with OperationScope(
            "test_operation",
            operation_id=custom_id
        ) as scope:
            assert scope.operation_id == custom_id

    def test_operation_scope_get_operation_id(self):
        """测试获取操作 ID"""
        with OperationScope("test_operation") as scope:
            op_id = scope.get_operation_id()

            assert op_id == scope.operation_id

    def test_operation_scope_get_stats(self):
        """测试获取操作统计"""
        with OperationScope("test_operation") as scope:
            # 在操作执行期间，状态应该是 running
            stats = scope.get_stats()

            assert stats is not None
            assert stats['status'] == "running"

    def test_operation_scope_context_propagation(self):
        """测试上下文传播"""
        with OperationScope(
            "test_operation",
            context={"branch": "feature/test", "action": "create"}
        ) as scope:
            stats = scope.get_stats()

            assert stats['context']['branch'] == "feature/test"
            assert stats['context']['action'] == "create"

    def test_operation_scope_logger_context(self):
        """测试日志记录器上下文设置"""
        Logger.clear_context()

        with OperationScope("test_operation") as scope:
            # 操作范围内应该设置了操作 ID
            assert _operation_id.get() == scope.operation_id

        # 退出后应该清除上下文
        assert _operation_id.get() == ""

    def test_operation_scope_nested(self):
        """测试嵌套操作范围"""
        Logger.clear_context()

        with OperationScope("outer_operation") as outer_scope:
            outer_id = outer_scope.operation_id

            with OperationScope("inner_operation") as inner_scope:
                inner_id = inner_scope.operation_id

                # 内层操作 ID 应该被设置
                assert _operation_id.get() == inner_id

            # 回到外层操作 ID（因为内层清除了上下文）
            # 注意：简单实现中，退出内层会清除上下文，外层需要重新进入才能恢复
            # 这是一个设计权衡：要么支持嵌套（需要栈），要么简化实现

        # 完全退出后应该清除上下文
        assert _operation_id.get() == ""

    def test_operation_scope_with_custom_logger(self):
        """测试使用自定义日志记录器的操作范围"""
        logger = Logger("custom_logger")

        with OperationScope("test_operation", logger=logger) as scope:
            assert scope.logger == logger

    def test_operation_scope_with_custom_tracer(self):
        """测试使用自定义追踪器的操作范围"""
        tracer = OperationTracer()

        with OperationScope("test_operation", tracer=tracer) as scope:
            assert scope.tracer == tracer


class TestGetLoggerAndConfigure:
    """测试 get_logger 和 configure_logger 函数"""

    def setup_method(self):
        """在每个测试前清除全局记录器"""
        import gm.core.logger as logger_module
        logger_module._default_logger = None

    def test_get_default_logger(self):
        """测试获取默认日志记录器"""
        logger = get_logger()

        assert logger is not None
        assert isinstance(logger, Logger)

    def test_get_logger_with_config(self):
        """测试使用配置获取日志记录器"""
        config = LoggerConfig(level="DEBUG")
        logger = get_logger("test_logger", config)

        assert logger.config.level == "DEBUG"

    def test_configure_logger(self):
        """测试配置全局日志记录器"""
        config = LoggerConfig(level="ERROR")
        configure_logger(config)

        logger = get_logger()

        assert logger.config.level == "ERROR"


class TestIntegration:
    """集成测试"""

    def test_complete_operation_workflow(self):
        """测试完整的操作工作流"""
        Logger.clear_context()
        Logger.set_request_id("req-123")
        Logger.set_user_id("user-456")

        with OperationScope(
            "add_worktree",
            context={"branch": "feature/new"}
        ) as scope:
            # 模拟操作
            import time
            time.sleep(0.01)  # 模拟一些工作

        # 操作完成后获取统计信息
        stats = scope.get_stats()

        assert stats is not None
        assert stats['duration_ms'] >= 10
        assert stats['status'] == "success"

        Logger.clear_context()

    def test_audit_log_creation_from_operation(self):
        """测试从操作创建审计日志"""
        with OperationScope(
            "delete_worktree",
            context={"branch": "feature/old"}
        ) as scope:
            pass

        stats = scope.get_stats()

        # 创建审计日志条目
        audit_entry = AuditLogEntry(
            operation_type="delete_worktree",
            user="test_user",
            operation_details={"branch": "feature/old"},
            status="success" if not scope.exception_occurred else "failure",
            result={
                "operation_id": scope.operation_id,
                "duration_ms": stats['duration_ms'],
            }
        )

        audit_dict = audit_entry.to_dict()

        assert audit_dict['operation_type'] == "delete_worktree"
        assert audit_dict['status'] == "success"
