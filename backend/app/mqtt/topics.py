"""
MQTT Topic 常量定义
"""

from app.config import settings

# Topic 前缀
PREFIX = settings.mqtt_topic_prefix

# 遥测数据 Topic
TELEMETRY = f"{PREFIX}/data"

# 电池告警 Topic
BATTERY_ALERT = f"{PREFIX}/alert/battery"

# GPS 丢失告警 Topic
GPS_LOST_ALERT = f"{PREFIX}/alert/gps"

# 飞行状态变更
FLIGHT_STATUS = f"{PREFIX}/status"

# 系统心跳
HEARTBEAT = f"{PREFIX}/heartbeat"
