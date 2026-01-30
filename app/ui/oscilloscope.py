from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox
import pyqtgraph as pg
import numpy as np
from collections import deque

class OscilloscopeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        # 控制
        ctrl_layout = QHBoxLayout()
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setCheckable(True)
        ctrl_layout.addWidget(self.btn_pause)
        ctrl_layout.addStretch()
        self.layout.addLayout(ctrl_layout)
        
        # 绘图
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        self.layout.addWidget(self.plot_widget)
        
        # 数据
        self.history_size = 1000
        self.curves = []
        self.data_buffers = []
        
        # 设置初始通道（实际应用中将是动态的）
        colors = ['r', 'g', 'b', 'c', 'm', 'y']
        for i in range(6):
            curve = self.plot_widget.plot(pen=colors[i], name=f"通道{i}")
            self.curves.append(curve)
            self.data_buffers.append(deque(maxlen=self.history_size))
            
    def add_data(self, values):
        if self.btn_pause.isChecked():
            return
            
        for i, val in enumerate(values):
            if i < len(self.data_buffers):
                self.data_buffers[i].append(val)
                
    def update_plot(self):
        if self.btn_pause.isChecked():
            return
            
        for i, curve in enumerate(self.curves):
            if i < len(self.data_buffers) and len(self.data_buffers[i]) > 0:
                curve.setData(list(self.data_buffers[i]))
