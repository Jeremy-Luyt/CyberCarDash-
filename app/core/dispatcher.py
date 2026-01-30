import threading
import time
import logging
from collections import deque
from typing import Dict, Callable, Any, Optional
from .protocol import Packet, MsgType
from .serial_interface import SerialInterface

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    处理消息分发、ACK 管理以及请求/响应匹配。
    """
    def __init__(self, serial_interface: SerialInterface):
        self.serial = serial_interface
        self.serial.set_callback(self._on_packet_received)
        
        self.handlers: Dict[MsgType, Callable[[Packet], None]] = {}
        self.telemetry_handlers = []
        
        # ACK 管理
        self.pending_acks: Dict[int, Dict] = {} # seq -> {timestamp, callback, retry_count, packet}
        self.ack_lock = threading.Lock()
        
        self.seq_counter = 0
        self.running = True
        
        # 看门狗
        self.last_heartbeat = time.time()
        self.watchdog_callback: Optional[Callable[[], None]] = None
        
        threading.Thread(target=self._maintenance_loop, daemon=True, name="DispatcherMaintenance").start()

    def register_handler(self, msg_type: MsgType, handler: Callable[[Packet], None]):
        self.handlers[msg_type] = handler

    def register_telemetry_handler(self, handler: Callable[[Packet], None]):
        self.telemetry_handlers.append(handler)

    def set_watchdog_callback(self, callback: Callable[[], None]):
        self.watchdog_callback = callback

    def send(self, msg_type: MsgType, payload: bytes = b'', need_ack: bool = False, callback: Callable[[bool], None] = None) -> int:
        seq = self._next_seq()
        packet = Packet(msg_type, payload, seq=seq)
        
        if need_ack:
            with self.ack_lock:
                self.pending_acks[seq] = {
                    'ts': time.time(),
                    'cb': callback,
                    'retry': 3,
                    'pkt': packet
                }
        
        self.serial.send(packet)
        return seq

    def _next_seq(self) -> int:
        self.seq_counter = (self.seq_counter + 1) & 0xFFFF
        return self.seq_counter

    def _on_packet_received(self, packet: Packet):
        self.last_heartbeat = time.time()
        
        # 处理 ACK
        if packet.msg_type == MsgType.ACK:
            self._handle_ack(packet)
            return
            
        # 分发
        if packet.msg_type == MsgType.TELEMETRY:
            for h in self.telemetry_handlers:
                h(packet)
        elif packet.msg_type in self.handlers:
            self.handlers[packet.msg_type](packet)
        else:
            logger.debug(f"未处理的数据包类型: {packet.msg_type}")

    def _handle_ack(self, packet: Packet):
        # ACK 载荷通常包含被确认的序列号 (uint16)
        if len(packet.payload) >= 2:
            import struct
            acked_seq = struct.unpack('<H', packet.payload[:2])[0]
            with self.ack_lock:
                if acked_seq in self.pending_acks:
                    req = self.pending_acks.pop(acked_seq)
                    if req['cb']:
                        req['cb'](True)

    def _maintenance_loop(self):
        while self.running:
            now = time.time()
            
            # 检查 ACK
            to_retry = []
            to_fail = []
            
            with self.ack_lock:
                for seq, req in list(self.pending_acks.items()):
                    if now - req['ts'] > 0.2: # 200ms 超时
                        if req['retry'] > 0:
                            req['retry'] -= 1
                            req['ts'] = now
                            to_retry.append(req['pkt'])
                        else:
                            to_fail.append(seq)
                            
                for seq in to_fail:
                    req = self.pending_acks.pop(seq)
                    if req['cb']:
                        req['cb'](False)
                        
            for pkt in to_retry:
                logger.warning(f"重试数据包 {pkt.seq} 类型 {pkt.msg_type}")
                self.serial.send(pkt)
            
            # 看门狗检查
            if now - self.last_heartbeat > 1.0: # 1s 超时
                if self.watchdog_callback:
                    self.watchdog_callback()
            
            time.sleep(0.05)

