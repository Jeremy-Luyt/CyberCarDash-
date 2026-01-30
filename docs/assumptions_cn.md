# Assumptions and Engineering Decisions (CN)

## 1. 通信协议假设
- **帧头帧尾**: 使用 COBS (Consistent Overhead Byte Stuffing) 编码，以 `0x00` 作为帧分隔符。
- **字节序**: 所有多字节数据（uint16, uint32, float等）均采用 **Little Endian (小端)** 格式。
- **CRC**: 使用 CRC-16/CCITT-FALSE (Poly: 0x1021, Init: 0xFFFF, RefIn: False, RefOut: False, XorOut: 0x0000)。
- **握手超时**: 默认 1秒，重试 3次。

## 2. UI 渲染
- 使用 PySide6 + PyQtGraph。
- 刷新率限制在 30Hz 以保证 UI 响应。
- 数据接收在后台线程，通过 Signal/Slot 或 共享队列传递给 UI。

## 3. 算法插件
- 插件位于 `app/plugins/` 目录。
- 必须继承自 `app.core.algo_sdk.AlgorithmBase`。
- 系统启动时自动扫描并加载。

## 4. 打包
- PyInstaller 打包时包含 `assets` 文件夹。
- 启动脚本会自动处理 `sys._MEIPASS` 路径问题。
