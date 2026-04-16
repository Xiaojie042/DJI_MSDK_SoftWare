"""Unit tests for TCP telemetry parser."""

import json
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.drone import PsdkDataMessage
from app.tcp_server.parser import TcpDataParser


class TestTcpDataParser:
    """Test JSON parsing and stream handling."""

    def setup_method(self):
        self.parser = TcpDataParser()

    @staticmethod
    def _make_json_line(data: dict) -> bytes:
        return json.dumps(data).encode("utf-8") + b"\n"

    def test_parse_complete_json(self):
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
        assert state.position.latitude == pytest.approx(31.2304)
        assert state.position.longitude == pytest.approx(121.4737)
        assert state.position.altitude == pytest.approx(100.0)
        assert state.velocity.horizontal == pytest.approx(5.0)
        assert state.battery.percent == 80
        assert state.flight_mode == "GPS"
        assert state.is_flying is True
        assert state.raw_payload == data

    def test_parse_partial_data(self):
        data = {"latitude": 31.0, "longitude": 121.0}
        line = self._make_json_line(data)

        results1 = self.parser.feed(line[:10])
        assert len(results1) == 0

        results2 = self.parser.feed(line[10:])
        assert len(results2) == 1

    def test_parse_multiple_messages(self):
        data1 = {"latitude": 31.0, "longitude": 121.0}
        data2 = {"latitude": 32.0, "longitude": 122.0}
        combined = self._make_json_line(data1) + self._make_json_line(data2)

        results = self.parser.feed(combined)
        assert len(results) == 2

    def test_invalid_json(self):
        results = self.parser.feed(b"not valid json\n")
        assert len(results) == 0

    def test_empty_line(self):
        results = self.parser.feed(b"\n\n\n")
        assert len(results) == 0

    def test_nested_json_extraction(self):
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
        assert results[0].drone_id == "DJI-002"
        assert results[0].position.latitude == pytest.approx(39.9042)

    def test_reset(self):
        self.parser.feed(b"partial data")
        self.parser.reset()

        data = {"latitude": 31.0, "longitude": 121.0}
        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1

    def test_parse_msdk_v2_payload(self):
        data = {
            "type": "flight_data",
            "schema_version": 2,
            "timestamp": "2026-04-13 16:01:52.538",
            "relative_altitude": 12.5,
            "flight_mode_string": "P-GPS",
            "is_flying": True,
            "aircraft_heading": -15.1,
            "gps_satellite_count": 17,
            "gps_signal_level": "LEVEL_4",
            "home_location": {
                "latitude": 4.583662361046586e7,
                "longitude": 4.583662361046586e7,
            },
            "battery_status": {
                "main_battery": {
                    "percentage": 78,
                    "temperature_celsius": 29.3,
                    "voltage_mv": 52306,
                }
            },
            "air_link_status": {
                "down_link_quality": 100,
                "up_link_quality": 96,
                "link_signal_quality": 5,
            },
            "flight_controller_serial_number": "1581F8DBW256G00A2PXY",
        }

        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1

        state = results[0]
        assert state.drone_id == "1581F8DBW256G00A2PXY"
        assert state.flight_mode == "P-GPS"
        assert state.is_flying is True
        assert state.heading == pytest.approx(-15.1)
        assert state.gps_signal == 4
        assert state.battery.percent == 78
        assert state.battery.voltage == pytest.approx(52.306, rel=1e-3)
        assert state.battery.temperature == pytest.approx(29.3)
        assert state.rc_signal == 100
        assert state.position.altitude == pytest.approx(12.5)
        assert 0 < abs(state.position.latitude) <= 90
        assert 0 < abs(state.position.longitude) <= 180

    def test_parse_json_stream_without_newline(self):
        data1 = {"latitude": 31.0, "longitude": 121.0, "batteryPercent": 60}
        data2 = {"latitude": 31.1, "longitude": 121.1, "batteryPercent": 59}
        stream = json.dumps(data1).encode("utf-8") + json.dumps(data2).encode("utf-8")

        results = self.parser.feed(stream)
        assert len(results) == 2
        assert results[0].battery.percent == 60
        assert results[1].battery.percent == 59

    def test_parse_psdk_payload(self):
        data = {
            "type": "psdk_data",
            "timestamp": "2026-04-15 17:31:21",
            "payload_index": "PORT_3",
            "data": ":01,16,0.00,24.0,63.7,1003.9,44,,,,,0,0.00,0,0.000000,0.000000,,,,,,,0.0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,1F\r\n",
        }

        results = self.parser.feed(self._make_json_line(data))
        assert len(results) == 1
        assert isinstance(results[0], PsdkDataMessage)
        assert results[0].payload_index == "PORT_3"
        assert results[0].data == data["data"]
        assert results[0].raw_payload == data


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
