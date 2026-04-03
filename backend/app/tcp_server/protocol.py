"""
DJI MSDK v5 通信协议定义
定义帧结构常量和协议相关枚举

注意：当前 TCP 数据格式尚未确定，
     MSDK v5 Android 端以 JSON 格式通过网络接口发送数据。
     此模块预留了二进制帧协议解析的框架，
     同时支持 JSON 格式直接解析。
"""

from enum import IntEnum

# ─── 二进制帧协议常量 (预留) ──────────────────────────────

# 帧头标识
FRAME_HEADER = b"\xAA\x55"
HEADER_SIZE = 2
LENGTH_SIZE = 2
CMD_ID_SIZE = 1
CRC_SIZE = 2

# 最小帧长度: Header(2) + Length(2) + CmdId(1) + CRC(2) = 7
MIN_FRAME_SIZE = HEADER_SIZE + LENGTH_SIZE + CMD_ID_SIZE + CRC_SIZE

# 最大 Payload 长度
MAX_PAYLOAD_SIZE = 1024


class CommandId(IntEnum):
    """命令 ID 枚举 (预留，待协议确定后补充)"""
    HEARTBEAT = 0x00
    TELEMETRY = 0x01       # 遥测数据
    GPS_DATA = 0x02        # GPS 数据
    BATTERY_INFO = 0x03    # 电池信息
    FLIGHT_STATUS = 0x04   # 飞行状态
    GIMBAL_DATA = 0x05     # 云台数据
    RC_SIGNAL = 0x06       # 遥控器信号


class FlightMode(IntEnum):
    """飞行模式枚举"""
    UNKNOWN = 0
    GPS = 1
    ATTI = 2
    SPORT = 3
    TRIPOD = 4
    AUTO_LANDING = 5
    AUTO_TAKEOFF = 6
    GO_HOME = 7
    WAYPOINT = 8


FLIGHT_MODE_NAMES = {
    FlightMode.UNKNOWN: "UNKNOWN",
    FlightMode.GPS: "GPS",
    FlightMode.ATTI: "ATTI",
    FlightMode.SPORT: "SPORT",
    FlightMode.TRIPOD: "TRIPOD",
    FlightMode.AUTO_LANDING: "AUTO_LANDING",
    FlightMode.AUTO_TAKEOFF: "AUTO_TAKEOFF",
    FlightMode.GO_HOME: "GO_HOME",
    FlightMode.WAYPOINT: "WAYPOINT",
}
