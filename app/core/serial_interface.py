import serial
import threading
import time
import collections
import logging
from typing import Optional, Callable, Deque
from .protocol import Packet, MsgType, ProtocolError

logger = logging.getLogger(__name__)

class SerialInterface:
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.running = False
        self.rx_thread: Optional[threading.Thread] = None
        self.tx_thread: Optional[threading.Thread] = None
        
        self.tx_queue = collections.deque() # 发送队列
        self.rx_callback: Optional[Callable[[Packet], None]] = None
        
        self.connected = False
        self.error_count = 0
        self.rx_buffer = bytearray()
        
        # 统计信息
        self.stats = {
            'tx_packets': 0,
            'rx_packets': 0,
            'rx_errors': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }

    def open(self) -> bool:
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            
            self.running = True
            self.connected = True
            
            self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True, name="SerialRx")
            self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True, name="SerialTx")
            
            self.rx_thread.start()
            self.tx_thread.start()
            
            logger.info(f"已连接到 {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            logger.error(f"打开串口 {self.port} 失败: {e}")
            self.connected = False
            return False

    def close(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False
        logger.info("串口已关闭")

    def send(self, packet: Packet):
        self.tx_queue.append(packet)

    def set_callback(self, callback: Callable[[Packet], None]):
        self.rx_callback = callback

    def _tx_loop(self):
        while self.running:
            if not self.tx_queue:
                time.sleep(0.001)
                continue
            
            try:
                packet = self.tx_queue.popleft()
                data = packet.serialize()
                if self.serial and self.serial.is_open:
                    self.serial.write(data)
                    self.stats['tx_packets'] += 1
                    self.stats['bytes_sent'] += len(data)
            except Exception as e:
                logger.error(f"TX 错误: {e}")
                self.connected = False
                # 可选：在此处或上层尝试重连逻辑

    def _rx_loop(self):
        while self.running:
            try:
                if not self.serial or not self.serial.is_open:
                    time.sleep(0.1)
                    continue
                
                # 读取可用字节
                data = self.serial.read(self.serial.in_waiting or 1)
                if data:
                    self.stats['bytes_received'] += len(data)
                    self.rx_buffer.extend(data)
                    self._process_buffer()
                    
            except Exception as e:
                logger.error(f"RX 错误: {e}")
                self.connected = False
                time.sleep(1)

    def _process_buffer(self):
        # 帧以 0x00 分隔
        while b'\x00' in self.rx_buffer:
            # 找到第一个分隔符
            idx = self.rx_buffer.index(b'\x00')
            
            # 提取帧（解码逻辑如果需要的话排除分隔符，
            # 但我们的协议解析器期望 COBS 数据，从技术上讲，该数据块中不包含分隔符）
            # cobs_decode 函数期望零之前的块。
            frame_data = self.rx_buffer[:idx]
            
            # 从缓冲区移除帧 + 分隔符
            del self.rx_buffer[:idx+1]
            
            if len(frame_data) > 0:
                try:
                    packet = Packet.parse(frame_data)
                    self.stats['rx_packets'] += 1
                    if self.rx_callback:
                        self.rx_callback(packet)
                except ProtocolError as pe:
                    self.stats['rx_errors'] += 1
                    logger.warning(f"协议错误: {pe}")
                except Exception as e:
                    self.stats['rx_errors'] += 1
                    logger.error(f"解析错误: {e}")
