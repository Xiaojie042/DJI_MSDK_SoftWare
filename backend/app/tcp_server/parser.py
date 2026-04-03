"""
TCP 数据解析器
支持两种模式:
  1. JSON 模式 (当前默认): MSDK v5 Android 端通过网络接口发送 JSON 数据
  2. 二进制帧模式 (预留): 自定义二进制协议帧解析

JSON 模式下，每条消息以换行符 '\\n' 分隔，格式为 JSON 字符串。
"""

from __future__ import annotations

import json
import time
from typing import Optional

from app.models.drone import DroneState, GpsPosition, Velocity, BatteryInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TcpDataParser:
    """
    TCP 数据流解析器

    处理粘包/拆包问题，从字节流中提取完整消息。
    当前使用 JSON + 换行符分隔模式。
    """

    def __init__(self):
        self._buffer: bytes = b""

    def feed(self, data: bytes) -> list[DroneState]:
        """
        喂入原始字节数据，返回解析出的 DroneState 列表

        Args:
            data: 从 TCP socket 读取的原始字节

        Returns:
            解析成功的 DroneState 对象列表
        """
        self._buffer += data
        results: list[DroneState] = []

        # JSON 模式: 按换行符分割
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue

            state = self._parse_json(line)
            if state:
                results.append(state)

        return results

    def _parse_json(self, data: bytes) -> Optional[DroneState]:
        """
        解析 JSON 格式的遥测数据

        支持多种 JSON 结构，尽可能兼容 MSDK v5 的默认数据格式。
        """
        try:
            payload = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("JSON 解析失败", error=str(e), raw=data[:100])
            return None

        try:
            # 提取位置信息
            position = GpsPosition(
                latitude=self._extract_float(payload, [
                    "latitude", "lat", "gps.latitude",
                    "location.latitude", "position.latitude"
                ]),
                longitude=self._extract_float(payload, [
                    "longitude", "lng", "lon", "gps.longitude",
                    "location.longitude", "position.longitude"
                ]),
                altitude=self._extract_float(payload, [
                    "altitude", "alt", "height",
                    "gps.altitude", "location.altitude"
                ]),
            )

            # 提取速度信息
            velocity = Velocity(
                horizontal=self._extract_float(payload, [
                    "horizontalSpeed", "horizontal_speed", "hSpeed",
                    "speed.horizontal", "velocity.horizontal"
                ]),
                vertical=self._extract_float(payload, [
                    "verticalSpeed", "vertical_speed", "vSpeed",
                    "speed.vertical", "velocity.vertical"
                ]),
            )

            # 提取电池信息
            battery = BatteryInfo(
                percent=int(self._extract_float(payload, [
                    "batteryPercent", "battery_percent", "battery.percent",
                    "batteryLevel", "battery_level"
                ])),
                voltage=self._extract_float(payload, [
                    "batteryVoltage", "battery_voltage", "battery.voltage"
                ]),
                temperature=self._extract_float(payload, [
                    "batteryTemperature", "battery_temperature", "battery.temperature"
                ]),
            )

            state = DroneState(
                drone_id=payload.get("droneId", payload.get("drone_id", "DJI-001")),
                timestamp=payload.get("timestamp", time.time()),
                position=position,
                heading=self._extract_float(payload, ["heading", "yaw", "compassHeading"]),
                velocity=velocity,
                battery=battery,
                gps_signal=int(self._extract_float(payload, [
                    "gpsSignal", "gps_signal", "gpsLevel", "satelliteCount"
                ])),
                flight_mode=payload.get("flightMode", payload.get("flight_mode", "UNKNOWN")),
                is_flying=payload.get("isFlying", payload.get("is_flying", False)),
                home_distance=self._extract_float(payload, [
                    "homeDistance", "home_distance", "distanceToHome"
                ]),
                gimbal_pitch=self._extract_float(payload, [
                    "gimbalPitch", "gimbal_pitch", "gimbal.pitch"
                ]),
                rc_signal=payload.get("rcSignal", payload.get("rc_signal")),
            )

            logger.debug(
                "遥测数据解析成功",
                drone_id=state.drone_id,
                lat=state.position.latitude,
                lng=state.position.longitude,
                alt=state.position.altitude,
            )
            return state

        except Exception as e:
            logger.error("DroneState 构建失败", error=str(e))
            return None

    @staticmethod
    def _extract_float(payload: dict, keys: list[str], default: float = 0.0) -> float:
        """
        从嵌套 JSON 中按多个可能的 key 提取浮点数值

        支持点分路径 (如 "gps.latitude") 进行嵌套查找。
        """
        for key in keys:
            if "." in key:
                # 嵌套路径
                parts = key.split(".")
                val = payload
                for part in parts:
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = None
                        break
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
            else:
                val = payload.get(key)
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        return default

    def reset(self):
        """重置解析器缓冲区"""
        self._buffer = b""
