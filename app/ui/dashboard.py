from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QGroupBox
from PySide6.QtCore import Qt

class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        
        # 状态
        status_grp = QGroupBox("系统状态")
        status_layout = QVBoxLayout()
        self.lbl_mode = QLabel("模式: 未连接")
        self.lbl_volt = QLabel("电压: 0.0 V")
        self.lbl_temp = QLabel("温度: 0.0 C")
        
        status_layout.addWidget(self.lbl_mode)
        status_layout.addWidget(self.lbl_volt)
        status_layout.addWidget(self.lbl_temp)
        status_grp.setLayout(status_layout)
        
        layout.addWidget(status_grp, 0, 0)
        
        # 大指示器
        self.lbl_big_status = QLabel("安全")
        self.lbl_big_status.setAlignment(Qt.AlignCenter)
        self.lbl_big_status.setStyleSheet("font-size: 48px; color: green; border: 2px solid green;")
        layout.addWidget(self.lbl_big_status, 0, 1)
        
    def update_voltage(self, v):
        self.lbl_volt.setText(f"电压: {v:.2f} V")
