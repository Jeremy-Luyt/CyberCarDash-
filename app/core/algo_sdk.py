from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import time
import numpy as np

class AlgorithmBase(ABC):
    """
    算法插件的抽象基类。
    """
    def __init__(self):
        self.name = "Unknown Algo"
        self.description = "No description"
        self.inputs = [] # 所需的遥测键列表
        self.outputs = [] # 生成的输出键列表
        self.enabled = True

    @abstractmethod
    def init(self):
        """初始化内部状态"""
        pass

    @abstractmethod
    def update(self, telemetry_data: Dict[str, float], dt: float) -> Dict[str, float]:
        """
        处理新的遥测数据。
        Args:
            telemetry_data: 最新遥测值的字典
            dt: 自上次更新以来的时间（秒）
        Returns:
            计算输出的字典（虚拟遥测）
        """
        pass

    @abstractmethod
    def reset(self):
        """重置状态"""
        pass

    def get_config(self) -> Dict[str, Any]:
        return {}

    def set_config(self, config: Dict[str, Any]):
        pass

class ControlCompiler:
    def __init__(self):
        self.logs = []
        self.experiments = []
        self.model_table = []
        self.tuning_table = []
        self.feedforward_table = []
        self.last_report = {}
        self.profile = {}
        self.session_id = 0

    def reset(self):
        self.logs = []
        self.experiments = []
        self.model_table = []
        self.tuning_table = []
        self.feedforward_table = []
        self.last_report = {}
        self.profile = {}
        self.session_id += 1

    def ingest(self, telemetry: Dict[str, float], timestamp: Optional[float] = None, context: Optional[Dict[str, Any]] = None):
        t = timestamp if timestamp is not None else time.time()
        entry = {"t": t}
        entry.update(telemetry)
        if context:
            entry.update(context)
        self.logs.append(entry)

    def slice_logs(self, start: Optional[float] = None, end: Optional[float] = None):
        if not self.logs:
            return []
        if start is None and end is None:
            return list(self.logs)
        return [x for x in self.logs if (start is None or x["t"] >= start) and (end is None or x["t"] <= end)]

    def compute_metrics(self, samples, target_key="target_spd", output_key="speed"):
        if not samples:
            return {}
        times = np.array([s["t"] for s in samples], dtype=float)
        y = np.array([s.get(output_key, 0.0) for s in samples], dtype=float)
        r = np.array([s.get(target_key, y[-1] if len(y) > 0 else 0.0) for s in samples], dtype=float)
        err = r - y
        rms = float(np.sqrt(np.mean(err ** 2))) if len(err) > 0 else 0.0
        overshoot = float(np.max(y - r)) if len(y) > 0 else 0.0
        settle_time = 0.0
        if len(y) > 0:
            band = np.maximum(0.02 * np.abs(r), 0.5)
            within = np.abs(err) <= band
            settle_time = float(times[-1] - times[0])
            for i in range(len(within)):
                if np.all(within[i:]):
                    settle_time = float(times[i] - times[0])
                    break
        energy = float(np.mean(np.abs(err)))
        jitter = float(np.std(err))
        return {
            "rms_error": rms,
            "overshoot": overshoot,
            "settle_time": settle_time,
            "energy": energy,
            "jitter": jitter
        }

    def estimate_model(self, samples, target_key="target_spd", output_key="speed"):
        if len(samples) < 5:
            return {}
        times = np.array([s["t"] for s in samples], dtype=float)
        y = np.array([s.get(output_key, 0.0) for s in samples], dtype=float)
        r = np.array([s.get(target_key, y[-1]) for s in samples], dtype=float)
        start = y[0]
        final = y[-1]
        total = final - start
        if abs(total) < 1e-6:
            return {"tau": 0.0, "delay": 0.0, "deadzone": 0.0}
        y63 = start + 0.632 * total
        idx63 = np.argmax((y - y63) * np.sign(total) >= 0)
        tau = float(times[idx63] - times[0]) if idx63 > 0 else 0.0
        y05 = start + 0.05 * total
        idx05 = np.argmax((y - y05) * np.sign(total) >= 0)
        delay = float(times[idx05] - times[0]) if idx05 > 0 else 0.0
        err = np.abs(r - y)
        deadzone = float(np.percentile(err, 10)) if len(err) > 0 else 0.0
        return {"tau": tau, "delay": delay, "deadzone": deadzone}

    def build_model_table(self, speed_bin=50.0, voltage_bin=2.0):
        table = {}
        for s in self.logs:
            spd = float(s.get("speed", 0.0))
            volt = float(s.get("voltage", 0.0))
            key = (int(spd // speed_bin), int(volt // voltage_bin))
            table.setdefault(key, []).append(s)
        result = []
        for (sp_bin, v_bin), samples in table.items():
            model = self.estimate_model(samples)
            if model:
                result.append({
                    "speed_bin": [sp_bin * speed_bin, (sp_bin + 1) * speed_bin],
                    "voltage_bin": [v_bin * voltage_bin, (v_bin + 1) * voltage_bin],
                    "tau": model.get("tau", 0.0),
                    "delay": model.get("delay", 0.0),
                    "deadzone": model.get("deadzone", 0.0)
                })
        self.model_table = result
        return result

    def _simulate_pid(self, r, tau, dt, pid, u_limit):
        if len(r) == 0 or dt <= 0:
            return [], []
        y = float(r[0])
        integral = 0.0
        prev_err = r[0] - y
        ys = []
        us = []
        for ref in r:
            err = ref - y
            integral += err * dt
            deriv = (err - prev_err) / dt
            u = pid["kp"] * err + pid["ki"] * integral + pid["kd"] * deriv
            u = max(-u_limit, min(u_limit, u))
            y += dt * (u - y) / max(tau, 1e-3)
            ys.append(y)
            us.append(u)
            prev_err = err
        return ys, us

    def auto_tune(self, samples, base_pid, weight, u_limit=100.0):
        if not samples:
            return {}
        times = np.array([s["t"] for s in samples], dtype=float)
        r = np.array([s.get("target_spd", 0.0) for s in samples], dtype=float)
        dt = float(np.median(np.diff(times))) if len(times) > 1 else 0.05
        model = self.estimate_model(samples)
        tau = model.get("tau", 0.5) if model else 0.5
        factors = [0.6, 0.8, 1.0, 1.2, 1.5]
        candidates = []
        for kp in factors:
            for ki in factors:
                for kd in factors:
                    pid = {
                        "kp": base_pid["kp"] * kp,
                        "ki": base_pid["ki"] * ki,
                        "kd": base_pid["kd"] * kd
                    }
                    ys, us = self._simulate_pid(r, tau, dt, pid, u_limit)
                    if not ys:
                        continue
                    sim_samples = [{"t": float(times[i]), "speed": ys[i], "target_spd": float(r[i])} for i in range(len(ys))]
                    metrics = self.compute_metrics(sim_samples)
                    saturation = float(np.mean(np.abs(us) >= 0.98 * u_limit))
                    cost = (
                        weight["rms"] * metrics.get("rms_error", 0.0) +
                        weight["overshoot"] * max(0.0, metrics.get("overshoot", 0.0)) +
                        weight["settle"] * metrics.get("settle_time", 0.0) +
                        weight["sat"] * saturation +
                        weight["energy"] * metrics.get("energy", 0.0) +
                        weight["jitter"] * metrics.get("jitter", 0.0)
                    )
                    candidates.append({"pid": pid, "cost": cost, "metrics": metrics})
        best = min(candidates, key=lambda x: x["cost"]) if candidates else {}
        self.tuning_table = candidates
        return best

    def update_feedforward(self, samples, alpha=0.2):
        if not samples:
            return []
        n = len(samples)
        if len(self.feedforward_table) < n:
            self.feedforward_table.extend([0.0] * (n - len(self.feedforward_table)))
        for i in range(n):
            r = float(samples[i].get("target_spd", 0.0))
            y = float(samples[i].get("speed", 0.0))
            err = r - y
            self.feedforward_table[i] = self.feedforward_table[i] + alpha * err
        return self.feedforward_table

    def compile_profile(self, profile_id: str, pid: Dict[str, float]):
        profile = {
            "profile_id": profile_id,
            "pid": pid,
            "model_table": self.model_table,
            "feedforward_table": self.feedforward_table
        }
        self.profile = profile
        return profile
