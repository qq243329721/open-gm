"""依赖注入系统实现"""

from typing import Dict, Any, Type, Optional

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
