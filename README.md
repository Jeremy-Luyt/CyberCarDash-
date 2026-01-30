# CyberCarDash Pro

工业级通用电赛控制类上位机（非飞行器） + STM32F407 通信参考实现

## 1. 快速开始

### 1.1 环境搭建 (Windows)

1.  运行 `scripts/setup_venv.bat` 自动创建虚拟环境并安装依赖。
2.  或者手动执行：
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    ```

### 1.2 运行

1.  **启动上位机**：
    ```bash
    .venv\Scripts\python app/main.py
    ```
2.  在上位机界面中，Port 选择你的串口并点击 `Connect`。

### 1.3 打包 EXE

运行 `scripts/build_exe.bat`，生成的 exe 位于 `dist/CyberCarDash.exe`。

## 2. 核心特性

*   **Python venv 隔离**: 纯净依赖管理，不依赖 conda。
*   **自描述协议**: 上位机不硬编码参数，完全依赖 MCU 下发的字典。
*   **算法插件 SDK**: 支持 `app/plugins` 下放置自定义算法 (见 `app/plugins/fusion_guard.py`)。
*   **高性能波形**: 基于 pyqtgraph，支持 200Hz+ 遥测。

## 3. 目录结构

*   `app/`: 上位机源码
    *   `core/`: 协议、串口、调度、参数管理
    *   `ui/`: PySide6 界面
    *   `plugins/`: 算法插件
*   `firmware_ref/`: STM32F4 C语言参考实现
*   `tools/`: 工具
*   `scripts/`: 批处理脚本

## 4. 算法示例 (FusionGuard)

内置于 `app/plugins/fusion_guard.py`，实现了：
*   异常检测 (基于统计方差)
*   自适应低通滤波 (基于输入动态调整 alpha)
*   安全系数输出

## 5. 协议说明

详见 `docs/assumptions_cn.md` 与 `app/core/protocol.py`。
