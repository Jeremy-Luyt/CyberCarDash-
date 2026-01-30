import sys
import os
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def main():
    # 设置插件目录路径，确保在打包后也能找到
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        base_path = sys._MEIPASS
    else:
        # 如果是源代码运行
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 可以在这里做一些路径初始化的工作，如果需要的话
    # 例如将 base_path 加入 sys.path 或设置环境变量
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
