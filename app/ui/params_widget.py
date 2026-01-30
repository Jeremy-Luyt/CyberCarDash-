from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton, QHBoxLayout, QDoubleSpinBox
from app.core.parameters import ParameterManager
from app.core.dispatcher import Dispatcher, MsgType

class ParametersWidget(QWidget):
    def __init__(self, param_mgr: ParameterManager, dispatcher: Dispatcher):
        super().__init__()
        self.param_mgr = param_mgr
        self.dispatcher = dispatcher
        
        layout = QVBoxLayout(self)
        
        # 控制
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新字典")
        refresh_btn.clicked.connect(self.request_dict)
        save_btn = QPushButton("保存到 Flash")
        save_btn.clicked.connect(self.save_params)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 树形视图
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["参数", "值", "单位", "类型"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)
        
    def request_dict(self):
        self.dispatcher.send(MsgType.DICT_REQ, b'')

    def save_params(self):
        self.dispatcher.send(MsgType.PARAM_SAVE, b'', need_ack=True)

    def rebuild_tree(self):
        self.tree.clear()
        
        for group_name, param_names in self.param_mgr.groups.items():
            group_item = QTreeWidgetItem(self.tree)
            group_item.setText(0, group_name)
            group_item.setExpanded(True)
            
            for name in param_names:
                p = self.param_mgr.params[name]
                item = QTreeWidgetItem(group_item)
                item.setText(0, p.name)
                item.setText(1, str(p.value))
                item.setText(2, p.unit)
                item.setText(3, p.type)
                # 理想情况下，添加 QSpinBox/QLineEdit 作为编辑的项小部件
                
        # 目前仅为简单实现
