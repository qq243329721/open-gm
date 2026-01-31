"""结构化日志系统

支持链路追踪和性能监控的结构化日志记录器。使用 structlog 库提供 JSON 输出格式。"""

import logging
import json
import time
import traceback
import contextvars
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union
from pathlib import Path
from contextlib import contextmanager

import structlog


# 全局链路上下文变量
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'request_id', default=""
)
_operation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'operation_id', default=""
)
_user_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'user_id', default=""
)


class LoggerConfig:
    """日志配置类"""

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        level: str = "INFO",
        json_output: bool = False,
        console_output: bool = False,
    ):
        """初始化日志配置
        Args:
            log_dir: 日志目录，如果为 None 则不写入文件
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
            json_output: 是否输出 JSON 格式
            console_output: 是否输出到控制台
        """
        self.log_dir = log_dir
        self.level = level
        self.json_output = json_output
        self.console_output = console_output


class Logger:
    """结构化日志记录器

    提供 JSON 格式的结构化日志记录，支持链路追踪。
    """

    def __init__(self, name: str = "gm", config: Optional[LoggerConfig] = None):
        """初始化日志记录器

        Args:
            name: 日志记录器名称
            config: 日志配置对象
        """
        self.name = name
        self.config = config or LoggerConfig()
        self._setup_structlog()
        self.logger = structlog.get_logger(name)

    def _setup_structlog(self) -> None:
        """配置 structlog"""
        handlers = []

        # 添加控制台处理器
        if self.config.console_output:
            console_handler = logging.StreamHandler()
            handlers.append(console_handler)

        # 添加文件处理器
        if self.config.log_dir:
            log_dir = Path(self.config.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "gm.log"
            file_handler = logging.FileHandler(log_file)
            handlers.append(file_handler)

        # 配置 basicConfig
        if handlers:
            logging.basicConfig(
                handlers=handlers,
                level=getattr(logging, self.config.level, logging.INFO),
                format="%(message)s",
            )

        # 配置 structlog 的处理器
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
                if self.config.json_output
                else structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    def debug(self, event: str, **kwargs) -> None:
        """记录 DEBUG 级别日志"""
        self._log("debug", event, **kwargs)

    def info(self, event: str, **kwargs) -> None:
        """记录 INFO 级别日志"""
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        """记录 WARNING 级别日志"""
        self._log("warning", event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        """记录 ERROR 级别日志"""
        self._log("error", event, **kwargs)

    def bind(self, **kwargs) -> 'Logger':
        """绑定上下文信息到日志记录器
        
        Args:
            **kwargs: 要绑定的上下文信息
            
        Returns:
            新的日志记录器实例，绑定了指定的上下文
        """
        # 创建一个新的日志记录器实例
        new_logger = Logger(self.name, self.config)
        # 绑定上下文到structlog logger
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger

    def _log(self, level: str, event: str, **kwargs) -> None:
        """内部日志记录方法

        Args:
            level: 日志级别
            event: 日志事件描述
            **kwargs: 其他日志属性
        """
        context = self._build_context(**kwargs)

        log_method = getattr(self.logger, level)
        log_method(event, **context)

    def _build_context(self, **kwargs) -> Dict[str, Any]:
        """构建日志上下文

        Args:
            **kwargs: 额外的上下文信息

        Returns:
            包含链路信息和其他上下文的字典
        """
        context = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }

        # 添加链路追踪信息
        request_id = _request_id.get()
        if request_id:
            context['request_id'] = request_id

        operation_id = _operation_id.get()
        if operation_id:
            context['operation_id'] = operation_id

        user_id = _user_id.get()
        if user_id:
            context['user_id'] = user_id

        # 添加用户提供的上下文
        context.update(kwargs)

        return context

    @staticmethod
    def set_request_id(request_id: str) -> None:
        """设置请求 ID

        Args:
            request_id: 请求标识符
        """
        _request_id.set(request_id)

    @staticmethod
    def set_operation_id(operation_id: str) -> None:
        """设置操作 ID

        Args:
            operation_id: 操作标识符
        """
        _operation_id.set(operation_id)

    @staticmethod
    def set_user_id(user_id: str) -> None:
        """设置用户 ID

        Args:
            user_id: 用户标识符
        """
        _user_id.set(user_id)

    @staticmethod
    def clear_context() -> None:
        """清除所有链路上下文"""
        _request_id.set("")
        _operation_id.set("")
        _user_id.set("")


class AuditLogEntry:
    """审计日志条目

    记录系统中的操作，用于审计和安全追踪。
    """

    def __init__(
        self,
        operation_type: str,
        user: str,
        operation_details: Dict[str, Any],
        status: str = "success",
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        """初始化审计日志条目
        Args:
            operation_type: 操作类型 (e.g., "add_worktree", "delete_worktree")
            user: 执行操作的用户
            operation_details: 操作详情字典
            status: 操作状态 ("success", "failure")
            result: 操作结果
            error_message: 错误消息（仅在失败时）
            timestamp: 时间戳，默认为当前时间
        """
        self.operation_type = operation_type
        self.user = user
        self.operation_details = operation_details
        self.status = status
        self.result = result or {}
        self.error_message = error_message
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含审计日志信息的字典
        """
        entry = {
            'timestamp': self.timestamp.isoformat().replace('+00:00', 'Z'),
            'operation_type': self.operation_type,
            'user': self.user,
            'status': self.status,
            'details': self.operation_details,
            'result': self.result,
        }

        if self.error_message:
            entry['error_message'] = self.error_message

        return entry

    def to_json(self) -> str:
        """转换为 JSON 字符串

        Returns:
            JSON 格式的审计日志
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class OperationTracer:
    """操作追踪器

    用于追踪操作的执行过程，包括开始、结束、异常等事件。
    """

    def __init__(self, logger: Optional[Logger] = None):
        """初始化操作追踪器

        Args:
            logger: 日志记录器实例，如果为 None 则创建默认实例
        """
        self.logger = logger or Logger()
        self.operations: Dict[str, Dict[str, Any]] = {}

    def start_operation(
        self,
        operation_name: str,
        operation_id: Optional[str] = None,
        **context
    ) -> str:
        """记录操作开始
        Args:
            operation_name: 操作名称
            operation_id: 操作 ID，如果为 None 则自动生成
            **context: 操作上下文信息

        Returns:
            生成或提供的操作 ID
        """
        op_id = operation_id or str(uuid.uuid4())

        self.operations[op_id] = {
            'name': operation_name,
            'start_time': time.time(),
            'context': context,
            'status': 'running',
        }

        self.logger.info(
            f'{operation_name}_started',
            operation_id=op_id,
            **context,
        )

        return op_id

    def end_operation(
        self,
        operation_id: str,
        status: str = "success",
        result: Optional[Dict[str, Any]] = None,
        **context
    ) -> Dict[str, Any]:
        """记录操作结束

        Args:
            operation_id: 操作 ID
            status: 操作状态 ("success", "failure")
            result: 操作结果
            **context: 额外的上下文信息

        Returns:
            包含操作统计的字典
        """
        if operation_id not in self.operations:
            raise ValueError(f"Operation {operation_id} not found")

        op_data = self.operations[operation_id]
        duration_ms = int((time.time() - op_data['start_time']) * 1000)

        op_data['status'] = status
        op_data['duration_ms'] = duration_ms
        op_data['result'] = result or {}

        event_name = f"{op_data['name']}_{'succeeded' if status == 'success' else 'failed'}"

        self.logger.info(
            event_name,
            operation_id=operation_id,
            duration_ms=duration_ms,
            status=status,
            **context,
        )

        return {
            'operation_id': operation_id,
            'duration_ms': duration_ms,
            'status': status,
        }

    def record_exception(
        self,
        operation_id: str,
        exception: Exception,
        **context
    ) -> None:
        """记录操作中的异常

        Args:
            operation_id: 操作 ID
            exception: 异常对象
            **context: 额外的上下文信息
        """
        if operation_id not in self.operations:
            raise ValueError(f"Operation {operation_id} not found")

        op_data = self.operations[operation_id]

        self.logger.error(
            f"{op_data['name']}_error",
            operation_id=operation_id,
            error_type=type(exception).__name__,
            error_message=str(exception),
            traceback=traceback.format_exc(),
            **context,
        )

    def get_operation_stats(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """获取操作统计信息

        Args:
            operation_id: 操作 ID

        Returns:
            操作统计信息，如果操作不存在返回 None
        """
        return self.operations.get(operation_id)

    def get_all_operations(self) -> Dict[str, Dict[str, Any]]:
        """获取所有操作的统计信息

        Returns:
            所有操作的统计信息字典
        """
        return self.operations.copy()

    def clear_operations(self) -> None:
        """清除所有操作记录"""
        self.operations.clear()


class OperationScope:
    """操作范围上下文管理器

    提供 with 语句支持的操作追踪上下文。
    自动处理操作的开始、结束和异常记录。
    """

    def __init__(
        self,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
        logger: Optional[Logger] = None,
        tracer: Optional[OperationTracer] = None,
        operation_id: Optional[str] = None,
    ):
        """初始化操作范围
        Args:
            operation_name: 操作名称
            context: 操作上下文信息
            logger: 日志记录器实例
            tracer: 操作追踪器实例
            operation_id: 操作 ID，如果为 None 则自动生成
        """
        self.operation_name = operation_name
        self.context = context or {}
        self.logger = logger or Logger()
        self.tracer = tracer or OperationTracer(self.logger)
        self.operation_id = operation_id or str(uuid.uuid4())
        self.exception_occurred = False

    def __enter__(self) -> 'OperationScope':
        """进入操作范围"""
        Logger.set_operation_id(self.operation_id)
        self.tracer.start_operation(
            self.operation_name,
            operation_id=self.operation_id,
            **self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出操作范围
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯

        Returns:
            False，表示异常将继续传播
        """
        if exc_type is not None:
            self.exception_occurred = True
            self.tracer.record_exception(
                self.operation_id,
                exc_val,
                **self.context
            )
            self.tracer.end_operation(
                self.operation_id,
                status="failure",
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.context
            )
        else:
            self.tracer.end_operation(
                self.operation_id,
                status="success",
                **self.context
            )

        # 仅清除当前操作的 ID，不影响外层操作
        if _operation_id.get() == self.operation_id:
            Logger.clear_context()
        return False

    def get_operation_id(self) -> str:
        """获取操作 ID

        Returns:
            操作 ID
        """
        return self.operation_id

    def get_stats(self) -> Optional[Dict[str, Any]]:
        """获取操作统计信息

        Returns:
            操作统计信息
        """
        return self.tracer.get_operation_stats(self.operation_id)


# 全局默认记录器实例
_default_logger: Optional[Logger] = None


def get_logger(
    name: str = "gm",
    config: Optional[LoggerConfig] = None,
) -> Logger:
    """获取日志记录器实例
    Args:
        name: 日志记录器名称
        config: 日志配置对象

    Returns:
        日志记录器实例
    """
    global _default_logger

    # 如果已经有全局记录器，直接返回（不会被新配置覆盖）
    if _default_logger is not None:
        return _default_logger

    _default_logger = Logger(name, config)

    return _default_logger


def configure_logger(config: LoggerConfig) -> None:
    """配置全局日志记录器
    Args:
        config: 日志配置对象
    """
    global _default_logger
    _default_logger = Logger("gm", config)
