import pkgutil
import importlib
import inspect
import os
import sys
from app.core.algo_sdk import AlgorithmBase

class PluginManager:
    def __init__(self, plugin_dir="app/plugins"):
        self.plugin_dir = plugin_dir
        self.plugins = {}

    def discover_plugins(self):
        """
        从插件目录动态加载插件。
        """
        # 确保插件目录在路径中
        if self.plugin_dir not in sys.path:
            sys.path.append(self.plugin_dir)
            
        # 遍历包
        # 假设 app.plugins 是一个包
        import app.plugins
        
        for loader, name, is_pkg in pkgutil.iter_modules(app.plugins.__path__):
            try:
                module = importlib.import_module(f"app.plugins.{name}")
                # 查找继承自 AlgorithmBase 的类
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (isinstance(attribute, type) and 
                        issubclass(attribute, AlgorithmBase) and 
                        attribute is not AlgorithmBase):
                        
                        # 实例化
                        instance = attribute()
                        self.plugins[instance.name] = instance
                        print(f"[PluginManager] 加载插件: {instance.name}")
                        
            except Exception as e:
                print(f"[PluginManager] 加载 {name} 失败: {e}")

    def get_plugin(self, name):
        return self.plugins.get(name)

    def get_all_plugins(self):
        return self.plugins.values()
