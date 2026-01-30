from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import struct
import json

class ParameterDef(BaseModel):
    name: str
    type: str # int, float, bool
    min_val: float = 0
    max_val: float = 0
    step: float = 1
    unit: str = ""
    group: str = "Default"
    rw: bool = True
    description: str = ""
    value: Any = 0
    fmt: str = "f" # struct 格式字符
    
class TelemetryDef(BaseModel):
    name: str
    type: str
    unit: str
    group: str
    index: int # 遥测数组中的索引

class ParameterManager:
    def __init__(self):
        self.params: Dict[str, ParameterDef] = {}
        self.telemetry: Dict[str, TelemetryDef] = {}
        self.groups: Dict[str, List[str]] = {}
        
    def load_dictionary(self, json_data: str):
        """从 MCU 响应加载字典"""
        try:
            data = json.loads(json_data)
            
            # 加载参数
            for p_data in data.get('params', []):
                p = ParameterDef(**p_data)
                self.params[p.name] = p
                if p.group not in self.groups:
                    self.groups[p.group] = []
                self.groups[p.group].append(p.name)
                
            # 加载遥测
            for idx, t_data in enumerate(data.get('telemetry', [])):
                t = TelemetryDef(**t_data, index=idx)
                self.telemetry[t.name] = t
                
        except Exception as e:
            print(f"Failed to load dictionary: {e}")

    def update_param(self, name: str, value: Any):
        if name in self.params:
            self.params[name].value = value
            
    def get_param_bytes(self, name: str, value: Any) -> bytes:
        p = self.params.get(name)
        if not p:
            return b''
            
        if p.type == 'float':
            return struct.pack('<f', float(value))
        elif p.type == 'int':
            return struct.pack('<i', int(value))
        elif p.type == 'uint':
            return struct.pack('<I', int(value))
        return b''
