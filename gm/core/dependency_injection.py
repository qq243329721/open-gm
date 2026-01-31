"""依赖注入系统实现"""

from typing import Dict, Any, Type, Optional, Callable
import inspect
from gm.core.exceptions import CircularDependencyError, ResolutionError

class ServiceRegistry:
    """服务注册中心"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register(self, name: str, service_class: Type, singleton: bool = True) -> None:
        """注册服务"""
        self._services[name] = {
            'class': service_class,
            'singleton': singleton
        }
    
    def resolve(self, name: str) -> Any:
        """解析并实例化服务"""
        if name in self._singletons:
            return self._singletons[name]
        
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        service_info = self._services[name]
        instance = service_info['class']()
        
        if service_info['singleton']:
            self._singletons[name] = instance
        
        return instance

_service_registry = ServiceRegistry()

def register_service(name: str, service_class: Type, singleton: bool = True) -> None:
    _service_registry.register(name, service_class, singleton)

def resolve_service(name: str) -> Any:
    return _service_registry.resolve(name)

def register_instance(name: str, instance: Any) -> None:
    _service_registry._singletons[name] = instance


class DIContainer:
    """简单的依赖注入容器，支持基于类型的自动注入"""
    def __init__(self):
        self._services: Dict[Type, tuple] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolution_stack: list = []

    def register(self, interface: Type, implementation, singleton: bool = False) -> None:
        self._services[interface] = (implementation, singleton)

    def resolve(self, interface: Type) -> Any:
        if interface in self._singletons:
            return self._singletons[interface]
        if interface not in self._services:
            raise KeyError(f"Unregistered service: {interface}")
        if interface in self._resolution_stack:
            raise CircularDependencyError(f"Circular dependency detected: {' -> '.join(str(i) for i in self._resolution_stack)} -> {interface}")
        self._resolution_stack.append(interface)
        implementation, is_singleton = self._services[interface]
        try:
            if callable(implementation):
                sig = inspect.signature(implementation.__init__)
                kwargs: Dict[str, Any] = {}
            for name, param in sig.parameters.items():
                # 跳过可变参数，避免对隐藏的 *args/**kwargs 进行注入
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                if name == 'self':
                    continue
                    if param.annotation != inspect.Parameter.empty and param.annotation in self._services:
                        kwargs[name] = self.resolve(param.annotation)
                    elif param.default != inspect.Parameter.empty:
                        kwargs[name] = param.default
                    else:
                        raise ResolutionError(f"Cannot resolve parameter '{name}' for {implementation}")
                instance = implementation(**kwargs)
            else:
                instance = implementation
        finally:
            self._resolution_stack.pop()

        if is_singleton:
            self._singletons[interface] = instance
        return instance

    def clear(self) -> None:
        self._services.clear()
        self._singletons.clear()


# 简单全局容器实例（用于向后兼容性轻量用例）
_container = DIContainer()

def get_container() -> DIContainer:
    return _container
