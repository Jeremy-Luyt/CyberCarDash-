import struct
import time
from enum import Enum, auto
from typing import List, Optional, Tuple, Any

class MsgType(Enum):
    HELLO_REQ = 0x01
    HELLO_RSP = 0x02
    DICT_REQ  = 0x03
    DICT_RSP  = 0x04
    PARAM_SET = 0x05
    PARAM_GET = 0x06
    PARAM_VAL = 0x07 # GET 或 SET 确认的响应
    TELEMETRY = 0x08
    CMD       = 0x09
    ACK       = 0x0A
    ERROR     = 0x0B
    TIME_SYNC = 0x0C
    RUN_EXPERIMENT = 0x0D
    EXPORT_LOG = 0x0E
    APPLY_PROFILE = 0x0F

class ProtocolError(Exception):
    pass

def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: 多项式 0x1021, 初始值 0xFFFF"""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc

def cobs_encode(data: bytes) -> bytes:
    """COBS 编码"""
    out = bytearray()
    idx = 0
    code_idx = 0
    code = 1
    out.append(0) # 代码占位符
    
    for byte in data:
        if byte == 0:
            out[code_idx] = code
            code = 1
            code_idx = len(out)
            out.append(0)
        else:
            out.append(byte)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code = 1
                code_idx = len(out)
                out.append(0)
                
    out[code_idx] = code
    return bytes(out)

def cobs_decode(data: bytes) -> bytes:
    """COBS 解码"""
    out = bytearray()
    idx = 0
    while idx < len(data):
        code = data[idx]
        idx += 1
        if code == 0:
            break # 帧结束或错误
            
        for i in range(code - 1):
            if idx >= len(data):
                break # 错误
            out.append(data[idx])
            idx += 1
            
        if code < 0xFF and idx < len(data):
            # 隐式零，除非我们到了末尾
            # 注意：标准 COBS 如果 code < 0xFF 则添加零，但是
            # 如果我们在缓冲区的最末端，我们不追加零。
            # 然而，通常 COBS 帧由 0x00 分隔，所以内部的 0x00 被恢复。
            # 在块解码中，如果我们没有到达末尾，我们追加 0。
            # 这里我们假设 'data' 是完整的 COBS 块（不包括分隔符 0x00）
            if idx < len(data) or code < 0xFF: # 逻辑检查：标准 COBS 在 code < 0xFF 时恢复 0
                 out.append(0)
                 
    # 移除错误添加的尾随零（最后一个块逻辑）
    # 实际上，标准 COBS 逻辑：
    # 如果 code < 0xFF，意味着后面有一个 0。
    # 如果 code == 0xFF，后面没有 0。
    # 最后一个代码字节指向末尾。
    # 为了安全起见，让我们使用更简单的实现逻辑。
    return _cobs_decode_simple(data)

def _cobs_decode_simple(data: bytes) -> bytes:
    res = bytearray()
    i = 0
    while i < len(data):
        code = data[i]
        i += 1
        if code == 0: 
            # 除非是分隔符，否则不应出现在编码块中
            break
        
        # 复制 code-1 字节
        chunk = data[i:i+code-1]
        res.extend(chunk)
        i += len(chunk)
        
        if code < 0xFF and i < len(data):
            res.append(0)
            
    return bytes(res)

class Packet:
    def __init__(self, msg_type: MsgType, payload: bytes = b'', seq: int = 0, flags: int = 0):
        self.version = 1
        self.msg_type = msg_type
        self.seq = seq
        self.flags = flags
        self.payload = payload
        self.timestamp = time.time()
        
    def serialize(self) -> bytes:
        # 头部: 版本(1) | 消息类型(1) | 序列号(2) | 标志(1) | 载荷长度(2)
        # 头部总长: 7 字节
        header = struct.pack('<BBHBH', 
                             self.version, 
                             self.msg_type.value, 
                             self.seq, 
                             self.flags, 
                             len(self.payload))
        
        # 主体: 载荷 | CRC16
        body = self.payload
        checksum_data = header + body
        crc = crc16_ccitt_false(checksum_data)
        
        raw_frame = header + body + struct.pack('<H', crc)
        encoded = cobs_encode(raw_frame)
        return encoded + b'\x00' # 分隔符

    @classmethod
    def parse(cls, data: bytes) -> 'Packet':
        # 1. 移除分隔符（如果存在）（通常由调用者处理，但检查一下）
        if data.endswith(b'\x00'):
            data = data[:-1]
            
        # 2. COBS 解码
        try:
            decoded = cobs_decode(data)
        except Exception as e:
            raise ProtocolError(f"COBS 解码失败: {e}")
            
        if len(decoded) < 9: # 头部(7) + CRC(2)
            raise ProtocolError("帧太短")
            
        # 3. 检查 CRC
        content = decoded[:-2]
        received_crc = struct.unpack('<H', decoded[-2:])[0]
        calc_crc = crc16_ccitt_false(content)
        
        if received_crc != calc_crc:
            raise ProtocolError(f"CRC 不匹配: rx={received_crc:04X} calc={calc_crc:04X}")
            
        # 4. 解析头部
        # <BBHBH
        ver, mtype_val, seq, flags, plen = struct.unpack('<BBHBH', decoded[:7])
        
        if ver != 1:
            raise ProtocolError(f"不支持的版本: {ver}")
            
        if len(decoded) - 9 != plen:
             # 有时如果存在 bug，载荷长度可能不匹配，但相信长度字段还是实际数据？
             # 为了鲁棒性，相信实际数据，或进行严格检查。
             # 严格检查：
             if len(decoded) - 9 < plen:
                 raise ProtocolError("载荷被截断")
        
        payload = decoded[7:7+plen]
        
        try:
            msg_type = MsgType(mtype_val)
        except ValueError:
            # 优雅地处理未知的消息类型，或者引发异常
            # 目前映射到 ERROR 或引发异常
            raise ProtocolError(f"未知的消息类型: {mtype_val}")
            
        return cls(msg_type, payload, seq, flags)
