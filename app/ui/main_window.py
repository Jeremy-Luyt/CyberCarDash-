import sys
import os
import json
import time
import struct
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QTabWidget, QPushButton, QLabel, 
                               QComboBox, QStatusBar, QMessageBox,
                               QLineEdit, QFormLayout, QDoubleSpinBox,
                               QTextEdit, QTableWidget, QTableWidgetItem)
from PySide6.QtCore import QTimer, Slot, Signal, QObject

from app.core.serial_interface import SerialInterface
from app.core.dispatcher import Dispatcher, MsgType
from app.core.parameters import ParameterManager
from app.core.protocol import Packet
from app.core.plugin_manager import PluginManager
from app.core.algo_sdk import ControlCompiler

from .oscilloscope import OscilloscopeWidget
from .params_widget import ParametersWidget
from .dashboard import DashboardWidget

class SignalBridge(QObject):
    telemetry_received = Signal(object) # 载荷数据（元组/列表）
    watchdog_timeout = Signal()
    export_log_received = Signal(object)

class ControlCompilerWidget(QWidget):
    def __init__(self, dispatcher: Dispatcher, compiler: ControlCompiler):
        super().__init__()
        self.dispatcher = dispatcher
        self.compiler = compiler
        self.baseline_metrics = None
        self.last_tuned_pid = None

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_experiment_tab()
        self._build_model_tab()
        self._build_tuning_tab()
        self._build_feedforward_tab()
        self._build_compile_tab()
        self._build_report_tab()

    def _build_experiment_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.exp_type = QComboBox()
        self.exp_type.addItems(["step", "chirp", "prbs", "brake"])
        self.exp_duration = QDoubleSpinBox()
        self.exp_duration.setRange(0.5, 60.0)
        self.exp_duration.setValue(5.0)
        self.exp_max_pwm = QDoubleSpinBox()
        self.exp_max_pwm.setRange(0, 1000)
        self.exp_max_pwm.setValue(200)
        self.exp_max_accel = QDoubleSpinBox()
        self.exp_max_accel.setRange(0, 500)
        self.exp_max_accel.setValue(50)
        self.exp_max_yaw = QDoubleSpinBox()
        self.exp_max_yaw.setRange(0, 500)
        self.exp_max_yaw.setValue(50)
        self.exp_max_dev = QDoubleSpinBox()
        self.exp_max_dev.setRange(0, 1000)
        self.exp_max_dev.setValue(100)

        form.addRow("试验类型", self.exp_type)
        form.addRow("持续时间(s)", self.exp_duration)
        form.addRow("最大PWM", self.exp_max_pwm)
        form.addRow("最大加速度", self.exp_max_accel)
        form.addRow("最大角速度", self.exp_max_yaw)
        form.addRow("最大偏离", self.exp_max_dev)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.exp_start_btn = QPushButton("开始试验")
        self.exp_stop_btn = QPushButton("安全停止")
        self.exp_export_btn = QPushButton("导出日志")
        self.exp_start_btn.clicked.connect(self.start_experiment)
        self.exp_stop_btn.clicked.connect(self.stop_experiment)
        self.exp_export_btn.clicked.connect(self.request_log)
        btn_row.addWidget(self.exp_start_btn)
        btn_row.addWidget(self.exp_stop_btn)
        btn_row.addWidget(self.exp_export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.exp_status = QLabel("状态: 待命")
        layout.addWidget(self.exp_status)
        self.tabs.addTab(tab, "自动试验")

    def _build_model_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.model_speed_bin = QDoubleSpinBox()
        self.model_speed_bin.setRange(1, 500)
        self.model_speed_bin.setValue(50)
        self.model_voltage_bin = QDoubleSpinBox()
        self.model_voltage_bin.setRange(0.5, 20)
        self.model_voltage_bin.setValue(2)

        form.addRow("速度分箱", self.model_speed_bin)
        form.addRow("电压分箱", self.model_voltage_bin)
        layout.addLayout(form)

        self.model_build_btn = QPushButton("生成模型表")
        self.model_build_btn.clicked.connect(self.build_model_table)
        layout.addWidget(self.model_build_btn)

        self.model_table = QTableWidget(0, 5)
        self.model_table.setHorizontalHeaderLabels(["速度段", "电压段", "时间常数", "延迟", "死区"])
        layout.addWidget(self.model_table)
        self.tabs.addTab(tab, "模型学习")

    def _build_tuning_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.pid_kp = QDoubleSpinBox()
        self.pid_kp.setRange(0, 50)
        self.pid_kp.setValue(1.2)
        self.pid_ki = QDoubleSpinBox()
        self.pid_ki.setRange(0, 10)
        self.pid_ki.setValue(0.05)
        self.pid_kd = QDoubleSpinBox()
        self.pid_kd.setRange(0, 10)
        self.pid_kd.setValue(0.1)

        self.w_rms = QDoubleSpinBox()
        self.w_rms.setRange(0, 10)
        self.w_rms.setValue(1)
        self.w_overshoot = QDoubleSpinBox()
        self.w_overshoot.setRange(0, 10)
        self.w_overshoot.setValue(1)
        self.w_settle = QDoubleSpinBox()
        self.w_settle.setRange(0, 10)
        self.w_settle.setValue(1)
        self.w_sat = QDoubleSpinBox()
        self.w_sat.setRange(0, 10)
        self.w_sat.setValue(1)
        self.w_energy = QDoubleSpinBox()
        self.w_energy.setRange(0, 10)
        self.w_energy.setValue(1)
        self.w_jitter = QDoubleSpinBox()
        self.w_jitter.setRange(0, 10)
        self.w_jitter.setValue(1)

        form.addRow("Kp", self.pid_kp)
        form.addRow("Ki", self.pid_ki)
        form.addRow("Kd", self.pid_kd)
        form.addRow("RMS权重", self.w_rms)
        form.addRow("超调权重", self.w_overshoot)
        form.addRow("稳定时间权重", self.w_settle)
        form.addRow("饱和权重", self.w_sat)
        form.addRow("能耗权重", self.w_energy)
        form.addRow("抖动权重", self.w_jitter)
        layout.addLayout(form)

        self.tune_btn = QPushButton("搜索最优")
        self.tune_btn.clicked.connect(self.run_tuning)
        layout.addWidget(self.tune_btn)

        self.tune_result = QTextEdit()
        self.tune_result.setReadOnly(True)
        layout.addWidget(self.tune_result)
        self.tabs.addTab(tab, "自动调参")

    def _build_feedforward_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.ff_alpha = QDoubleSpinBox()
        self.ff_alpha.setRange(0.0, 1.0)
        self.ff_alpha.setSingleStep(0.05)
        self.ff_alpha.setValue(0.2)
        form.addRow("学习率", self.ff_alpha)
        layout.addLayout(form)
        self.ff_btn = QPushButton("更新前馈")
        self.ff_btn.clicked.connect(self.update_feedforward)
        layout.addWidget(self.ff_btn)
        self.ff_view = QTextEdit()
        self.ff_view.setReadOnly(True)
        layout.addWidget(self.ff_view)
        self.tabs.addTab(tab, "学习前馈")

    def _build_compile_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.profile_id = QLineEdit("profile_001")
        form.addRow("策略ID", self.profile_id)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.compile_btn = QPushButton("编译策略")
        self.apply_btn = QPushButton("应用策略")
        self.export_btn = QPushButton("导出策略文件")
        self.compile_btn.clicked.connect(self.compile_profile)
        self.apply_btn.clicked.connect(self.apply_profile)
        self.export_btn.clicked.connect(self.export_profile)
        btn_row.addWidget(self.compile_btn)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.compile_view = QTextEdit()
        self.compile_view.setReadOnly(True)
        layout.addWidget(self.compile_view)
        self.tabs.addTab(tab, "策略编译")

    def _build_report_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        btn_row = QHBoxLayout()
        self.report_baseline_btn = QPushButton("保存基线")
        self.report_compare_btn = QPushButton("生成对比")
        self.report_baseline_btn.clicked.connect(self.save_baseline)
        self.report_compare_btn.clicked.connect(self.generate_report)
        btn_row.addWidget(self.report_baseline_btn)
        btn_row.addWidget(self.report_compare_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        layout.addWidget(self.report_view)
        self.tabs.addTab(tab, "对比与报告")

    def start_experiment(self):
        payload = {
            "type": self.exp_type.currentText(),
            "duration": self.exp_duration.value(),
            "limits": {
                "max_pwm": self.exp_max_pwm.value(),
                "max_accel": self.exp_max_accel.value(),
                "max_yaw": self.exp_max_yaw.value(),
                "max_dev": self.exp_max_dev.value()
            }
        }
        data = json.dumps(payload).encode("utf-8")
        self.dispatcher.send(MsgType.RUN_EXPERIMENT, data)
        self.exp_status.setText("状态: 已发送试验指令")

    def stop_experiment(self):
        payload = {"action": "stop"}
        data = json.dumps(payload).encode("utf-8")
        self.dispatcher.send(MsgType.RUN_EXPERIMENT, data)
        self.exp_status.setText("状态: 已发送安全停止")

    def request_log(self):
        payload = {"start": 0, "count": 2000}
        data = json.dumps(payload).encode("utf-8")
        self.dispatcher.send(MsgType.EXPORT_LOG, data)
        self.exp_status.setText("状态: 已请求日志")

    def load_log_records(self, records):
        self.compiler.logs = records
        self.exp_status.setText(f"状态: 已载入日志 {len(records)} 条")

    def build_model_table(self):
        table = self.compiler.build_model_table(self.model_speed_bin.value(), self.model_voltage_bin.value())
        self.model_table.setRowCount(len(table))
        for row, item in enumerate(table):
            self.model_table.setItem(row, 0, QTableWidgetItem(f"{item['speed_bin'][0]}-{item['speed_bin'][1]}"))
            self.model_table.setItem(row, 1, QTableWidgetItem(f"{item['voltage_bin'][0]}-{item['voltage_bin'][1]}"))
            self.model_table.setItem(row, 2, QTableWidgetItem(f"{item['tau']:.3f}"))
            self.model_table.setItem(row, 3, QTableWidgetItem(f"{item['delay']:.3f}"))
            self.model_table.setItem(row, 4, QTableWidgetItem(f"{item['deadzone']:.3f}"))

    def run_tuning(self):
        base_pid = {"kp": self.pid_kp.value(), "ki": self.pid_ki.value(), "kd": self.pid_kd.value()}
        weight = {
            "rms": self.w_rms.value(),
            "overshoot": self.w_overshoot.value(),
            "settle": self.w_settle.value(),
            "sat": self.w_sat.value(),
            "energy": self.w_energy.value(),
            "jitter": self.w_jitter.value()
        }
        best = self.compiler.auto_tune(self.compiler.logs, base_pid, weight)
        if not best:
            self.tune_result.setPlainText("日志不足，无法调参")
            return
        self.last_tuned_pid = best["pid"]
        metrics = best.get("metrics", {})
        text = {
            "pid": best["pid"],
            "metrics": metrics,
            "cost": best.get("cost", 0.0)
        }
        self.tune_result.setPlainText(json.dumps(text, ensure_ascii=False, indent=2))

    def update_feedforward(self):
        table = self.compiler.update_feedforward(self.compiler.logs, self.ff_alpha.value())
        preview = table[:50]
        self.ff_view.setPlainText(json.dumps({"size": len(table), "preview": preview}, ensure_ascii=False, indent=2))

    def compile_profile(self):
        pid = self.last_tuned_pid or {"kp": self.pid_kp.value(), "ki": self.pid_ki.value(), "kd": self.pid_kd.value()}
        profile = self.compiler.compile_profile(self.profile_id.text().strip(), pid)
        self.compile_view.setPlainText(json.dumps(profile, ensure_ascii=False, indent=2))

    def apply_profile(self):
        if not self.compiler.profile:
            self.compile_profile()
        payload = {"profile": self.compiler.profile}
        data = json.dumps(payload).encode("utf-8")
        self.dispatcher.send(MsgType.APPLY_PROFILE, data)

    def export_profile(self):
        if not self.compiler.profile:
            self.compile_profile()
        profile = self.compiler.profile
        if not profile:
            self.compile_view.setPlainText("没有可导出的策略")
            return
        export_dir = os.path.join(os.getcwd(), "export")
        os.makedirs(export_dir, exist_ok=True)
        params_path = os.path.join(export_dir, "params.bin")
        table_path = os.path.join(export_dir, "control_table.h")
        pid = profile.get("pid", {})
        ff = profile.get("feedforward_table", [])
        with open(params_path, "wb") as f:
            f.write(struct.pack("<3f", float(pid.get("kp", 0.0)), float(pid.get("ki", 0.0)), float(pid.get("kd", 0.0))))
            f.write(struct.pack("<I", len(ff)))
            for v in ff:
                f.write(struct.pack("<f", float(v)))
        ff_values = ", ".join([f"{float(v):.6f}" for v in ff])
        header = "const float control_pid[3] = {" + f"{float(pid.get('kp', 0.0)):.6f}, {float(pid.get('ki', 0.0)):.6f}, {float(pid.get('kd', 0.0)):.6f}" + "};\n"
        header += "const float control_ff[] = {" + ff_values + "};\n"
        with open(table_path, "w", encoding="utf-8") as f:
            f.write(header)
        self.compile_view.setPlainText(f"导出完成: {params_path} , {table_path}")

    def save_baseline(self):
        metrics = self.compiler.compute_metrics(self.compiler.logs)
        self.baseline_metrics = metrics
        self.report_view.setPlainText(json.dumps({"baseline": metrics}, ensure_ascii=False, indent=2))

    def generate_report(self):
        metrics = self.compiler.compute_metrics(self.compiler.logs)
        report = {"current": metrics}
        if self.baseline_metrics:
            report["baseline"] = self.baseline_metrics
        self.report_view.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyberCarDash Pro - 工业控制主机")
        self.resize(1280, 800)
        
        # 信号桥接器（用于线程安全）
        self.signals = SignalBridge()
        self.signals.telemetry_received.connect(self.process_telemetry)
        self.signals.watchdog_timeout.connect(self.handle_watchdog)
        self.signals.export_log_received.connect(self.process_export_log)
        
        # 核心系统
        self.serial = SerialInterface("COM3")
        self.dispatcher = Dispatcher(self.serial)
        self.param_mgr = ParameterManager()
        self.plugin_mgr = PluginManager()
        self.plugin_mgr.discover_plugins()
        self.compiler = ControlCompiler()
        
        self.dispatcher.register_telemetry_handler(self.on_telemetry)
        self.dispatcher.set_watchdog_callback(self.on_watchdog_timeout)
        self.dispatcher.register_handler(MsgType.EXPORT_LOG, self.on_export_log)
        
        # UI 设置
        self.setup_ui()
        
        # 定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(33) # 约 30Hz
        
        # 自动连接逻辑（可选，或手动）
        # self.connect_device() 

    def setup_ui(self):
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 工具栏 / 顶部栏
        top_bar = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4"])
        self.port_combo.setEditable(True)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        top_bar.addWidget(QLabel("端口:"))
        top_bar.addWidget(self.port_combo)
        top_bar.addWidget(self.connect_btn)
        top_bar.addStretch()
        
        main_layout.addLayout(top_bar)
        
        # 标签页
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # 1. 仪表盘标签页
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.dashboard, "仪表盘")
        
        # 2. 示波器标签页
        self.scope = OscilloscopeWidget()
        self.tabs.addTab(self.scope, "示波器")
        
        # 3. 参数标签页
        self.params_widget = ParametersWidget(self.param_mgr, self.dispatcher)
        self.tabs.addTab(self.params_widget, "参数")

        self.compiler_widget = ControlCompilerWidget(self.dispatcher, self.compiler)
        self.tabs.addTab(self.compiler_widget, "Control Compiler")
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
    def toggle_connection(self):
        if self.serial.connected:
            self.serial.close()
            self.connect_btn.setText("连接")
            self.status_bar.showMessage("已断开连接")
        else:
            port = self.port_combo.currentText()
            self.serial.port = port
            if self.serial.open():
                self.connect_btn.setText("断开连接")
                self.status_bar.showMessage(f"已连接到 {port}")
                # 开始握手
                self.start_handshake()
            else:
                QMessageBox.critical(self, "错误", "无法打开串口")

    def start_handshake(self):
        # 发送 HELLO
        self.dispatcher.send(MsgType.HELLO_REQ, b'')
        # 调度字典请求
        QTimer.singleShot(500, lambda: self.dispatcher.send(MsgType.DICT_REQ, b''))

    def on_telemetry(self, packet: Packet):
        # 线程: 串口接收线程
        # 发送信号到主线程
        try:
            # 假设载荷为浮点数组
            count = len(packet.payload) // 4
            values = struct.unpack(f'<{count}f', packet.payload)
            self.signals.telemetry_received.emit(values)
        except Exception:
            pass

    def on_export_log(self, packet: Packet):
        try:
            data = json.loads(packet.payload.decode("utf-8"))
            records = data.get("records", [])
            self.signals.export_log_received.emit(records)
        except Exception:
            pass

    def on_watchdog_timeout(self):
        # 线程: 调度器线程
        self.signals.watchdog_timeout.emit()

    @Slot(object)
    def process_telemetry(self, values):
        # 线程: 主线程
        
        # 1. 为插件准备数据字典
        # 假设演示的固定顺序: [电压, 电流, 俯仰角, 陀螺仪Y轴, 速度]
        telemetry_dict = {}
        if len(values) >= 5:
            telemetry_dict = {
                "voltage": values[0],
                "current": values[1],
                "pitch": values[2],
                "gyro_y": values[3],
                "speed": values[4]
            }
            target_value = None
            if "target_spd" in self.param_mgr.params:
                target_value = self.param_mgr.params["target_spd"].value
            elif "target_vel" in self.param_mgr.params:
                target_value = self.param_mgr.params["target_vel"].value
            context = {"target_spd": float(target_value)} if target_value is not None else None
            self.compiler.ingest(telemetry_dict, time.time(), context)
            
        # 2. 运行插件
        for plugin in self.plugin_mgr.get_all_plugins():
            if plugin.enabled:
                outputs = plugin.update(telemetry_dict, 0.05) # 假设 dt=50ms
                # 可选：可视化输出？
                # 目前仅将 GFG 输出打印到控制台以证明其工作正常
                if "gfg_output" in outputs:
                    # 将其追加到值中以便示波器显示？
                    # 让我们扩展元组以进行可视化（如果示波器支持）
                    pass
        
        # 传递给示波器
        self.scope.add_data(values)
        
        # 传递给仪表盘 (例如第一个值是电压)
        if len(values) > 0:
            self.dashboard.update_voltage(values[0])

    @Slot(object)
    def process_export_log(self, records):
        self.compiler_widget.load_log_records(records)

    @Slot()
    def handle_watchdog(self):
        # 线程: 主线程
        self.status_bar.showMessage("看门狗超时 - 连接丢失？", 5000)
        # 在此处理安全逻辑

    def update_ui(self):
        self.scope.update_plot()
        # 更新连接统计信息
        stats = self.serial.stats
        self.status_bar.showMessage(f"TX: {stats['tx_packets']} | RX: {stats['rx_packets']} | ERR: {stats['rx_errors']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
