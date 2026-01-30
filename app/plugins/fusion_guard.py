import numpy as np
from app.core.algo_sdk import AlgorithmBase
from typing import Dict, Deque
from collections import deque

class FusionGuardAlgo(AlgorithmBase):
    """
    工业自稳融合 (FusionGuard) - 旗舰示例算法
    
    原理：
    1. 异常检测：监控输入信号的方差与突变，检测传感器故障或剧烈震荡。
    2. 自适应滤波：根据信号噪声水平动态调整低通滤波器截止频率。
    3. 软限幅与保护：输出经过平滑处理，并提供建议的安全增益系数。
    """
    def __init__(self):
        super().__init__()
        self.name = "FusionGuard Industrial Stabilizer"
        self.description = "Combines anomaly detection, adaptive filtering, and safety limiting."
        self.inputs = ["pitch", "gyro_y"] # Example inputs
        self.outputs = ["pitch_fused", "safety_factor", "anomaly_score"]
        
        # Internal state
        self.history_len = 50
        self.pitch_buffer = deque(maxlen=self.history_len)
        self.gyro_buffer = deque(maxlen=self.history_len)
        self.last_val = 0.0
        self.alpha = 0.1 # Default filter coefficient
        
    def init(self):
        self.pitch_buffer.clear()
        self.gyro_buffer.clear()
        self.last_val = 0.0
        
    def update(self, telemetry_data: Dict[str, float], dt: float) -> Dict[str, float]:
        # Get inputs (handle missing keys gracefully)
        raw_pitch = telemetry_data.get("pitch", 0.0)
        raw_gyro = telemetry_data.get("gyro_y", 0.0)
        
        self.pitch_buffer.append(raw_pitch)
        self.gyro_buffer.append(raw_gyro)
        
        # 1. Anomaly Detection (Statistical)
        anomaly_score = 0.0
        if len(self.pitch_buffer) > 10:
            std_dev = np.std(list(self.pitch_buffer))
            if std_dev > 10.0: # High vibration threshold
                anomaly_score = 1.0
            elif std_dev > 5.0:
                anomaly_score = 0.5
                
        # 2. Adaptive Filtering
        # If high motion (high gyro), increase bandwidth (higher alpha) to reduce lag
        # If static (low gyro), decrease bandwidth (lower alpha) to reduce noise
        gyro_mag = abs(raw_gyro)
        target_alpha = 0.05 + min(gyro_mag / 200.0, 0.9) # map 0-200 deg/s to 0.05-0.95
        
        # Smooth alpha transition
        self.alpha = self.alpha * 0.9 + target_alpha * 0.1
        
        # Apply LPF
        fused_pitch = self.last_val * (1 - self.alpha) + raw_pitch * self.alpha
        self.last_val = fused_pitch
        
        # 3. Safety Factor
        # If anomaly detected, reduce control authority recommendation
        safety_factor = 1.0 - anomaly_score
        
        return {
            "pitch_fused": fused_pitch,
            "safety_factor": safety_factor,
            "anomaly_score": anomaly_score
        }

    def reset(self):
        self.init()
