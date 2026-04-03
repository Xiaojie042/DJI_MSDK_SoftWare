"""
TCP 解析器单元测试
"""

import json
import time

import pytest

from app.tcp_server.parser import TcpDataParser


class TestTcpDataParser:
    """测试 JSON 模式的解析"""

    def setup_method(self):
        self.parser = TcpDataParser()

    def _make_json_line(self, data: dict) -> bytes:
        """构造 JSON 行数据"""
        return json.dumps(data).encode("utf-8") + b"\n"

    def test_parse_complete_json(self):
        """测试完整 JSON 数据解析"""
        data = {
            "droneId": "DJI-001",
            "timestamp": time.time(),
            "latitude": 31.2304,
            "longitude": 121.4737,
            "altitude": 100.0,
            "horizontalSpeed": 5.0,
            "verticalSpeed": 1.0,
            "batteryPercent": 80,
            "batteryVoltage": 22.8,
            "gpsSignal": 5,
            "flightMode": "GPS",
            "isFlying": True,
            "heading": 180.0,
            "homeDistance": 50.0,
        }

        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1

        state = results[0]
        assert state.drone_id == "DJI-001"
        assert state.position.latitude == 31.2304
        assert state.position.longitude == 121.4737
        assert state.position.altitude == 100.0
        assert state.velocity.horizontal == 5.0
        assert state.battery.percent == 80
        assert state.flight_mode == "GPS"
        assert state.is_flying is True

    def test_parse_partial_data(self):
        """测试部分数据 (粘包模拟)"""
        data = {"latitude": 31.0, "longitude": 121.0}
        line = json.dumps(data).encode("utf-8") + b"\n"

        # 分两次喂入
        part1 = line[:10]
        part2 = line[10:]

        results1 = self.parser.feed(part1)
        assert len(results1) == 0  # 不完整，不应返回

        results2 = self.parser.feed(part2)
        assert len(results2) == 1  # 完整了

    def test_parse_multiple_messages(self):
        """测试多条消息"""
        data1 = {"latitude": 31.0, "longitude": 121.0}
        data2 = {"latitude": 32.0, "longitude": 122.0}

        combined = self._make_json_line(data1) + self._make_json_line(data2)
        results = self.parser.feed(combined)
        assert len(results) == 2

    def test_invalid_json(self):
        """测试无效 JSON"""
        results = self.parser.feed(b"not valid json\n")
        assert len(results) == 0

    def test_empty_line(self):
        """测试空行"""
        results = self.parser.feed(b"\n\n\n")
        assert len(results) == 0

    def test_nested_json_extraction(self):
        """测试嵌套 JSON 字段提取"""
        data = {
            "droneId": "DJI-002",
            "gps": {
                "latitude": 39.9042,
                "longitude": 116.4074,
                "altitude": 200.0,
            },
            "battery": {
                "percent": 65,
                "voltage": 21.5,
            },
        }

        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1

        state = results[0]
        assert state.drone_id == "DJI-002"
        # 嵌套路径 gps.latitude 应被正确提取
        assert state.position.latitude == 39.9042

    def test_reset(self):
        """测试重置解析器"""
        self.parser.feed(b"partial data")  # 不完整
        self.parser.reset()

        # 重置后应从新数据开始
        data = {"latitude": 31.0, "longitude": 121.0}
        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1
