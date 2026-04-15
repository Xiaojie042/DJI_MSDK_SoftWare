"""
TCP telemetry parser.

Supports:
1. newline-delimited JSON messages
2. plain JSON object streams without trailing newline
3. nested DJI MSDK-style payloads
"""

from __future__ import annotations

import codecs
import json
import math
import time
from datetime import datetime
from typing import Any, Optional

from app.models.drone import BatteryInfo, DroneState, GpsPosition, Velocity
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MISSING = object()


class TcpDataParser:
    """Parse TCP byte streams into ``DroneState`` objects."""

    def __init__(self):
        self._buffer = ""
        self._json_decoder = json.JSONDecoder()
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")()

    def feed(self, data: bytes) -> list[DroneState]:
        """
        Feed raw TCP bytes and return parsed telemetry messages.

        The parser tolerates sticky packets and split packets. It first tries to
        decode complete JSON objects from the stream, and falls back to
        newline-delimited handling when the current buffer contains malformed
        lines.
        """
        try:
            self._buffer += self._utf8_decoder.decode(data)
        except UnicodeDecodeError as exc:
            logger.warning("TCP payload is not valid UTF-8", error=str(exc))
            return []

        results: list[DroneState] = []

        while True:
            chunk = self._buffer.lstrip()
            if not chunk:
                self._buffer = ""
                break

            try:
                payload, end = self._json_decoder.raw_decode(chunk)
            except json.JSONDecodeError as exc:
                newline_index = chunk.find("\n")
                if newline_index == -1:
                    # Most likely an incomplete JSON object, keep buffering.
                    break

                line = chunk[:newline_index].strip()
                self._buffer = chunk[newline_index + 1 :]

                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid JSON line", error=str(exc), raw=line[:200])
                    continue

                state = self._build_state(payload)
                if state:
                    results.append(state)
                continue

            self._buffer = chunk[end:]
            state = self._build_state(payload)
            if state:
                results.append(state)

        return results

    def _build_state(self, payload: Any) -> Optional[DroneState]:
        """Convert a decoded JSON payload into a normalized ``DroneState``."""
        if not isinstance(payload, dict):
            logger.warning("Ignoring non-object JSON payload", payload_type=type(payload).__name__)
            return None

        try:
            position = GpsPosition(
                latitude=self._extract_latitude(payload),
                longitude=self._extract_longitude(payload),
                altitude=self._extract_altitude(payload),
            )

            velocity = Velocity(
                horizontal=self._extract_horizontal_speed(payload),
                vertical=self._extract_vertical_speed(payload),
            )

            battery = BatteryInfo(
                percent=int(
                    self._extract_float(
                        payload,
                        [
                            "batteryPercent",
                            "battery_percent",
                            "battery.percent",
                            "batteryLevel",
                            "battery_level",
                            "battery_status.main_battery.percentage",
                        ],
                    )
                ),
                voltage=self._extract_voltage(payload),
                temperature=self._extract_float(
                    payload,
                    [
                        "batteryTemperature",
                        "battery_temperature",
                        "battery.temperature",
                        "battery_status.main_battery.temperature_celsius",
                    ],
                ),
            )

            state = DroneState(
                drone_id=self._extract_string(
                    payload,
                    [
                        "droneId",
                        "drone_id",
                        "flight_controller_serial_number",
                        "aircraft_serial_number",
                        "serial_number",
                    ],
                    default="DJI-001",
                ),
                timestamp=self._extract_timestamp(payload),
                position=position,
                heading=self._extract_float(
                    payload,
                    ["aircraft_heading", "heading", "compassHeading", "attitude.yaw", "yaw"],
                ),
                velocity=velocity,
                battery=battery,
                gps_signal=self._extract_gps_signal(payload),
                flight_mode=self._extract_string(
                    payload,
                    ["flight_mode_string", "flightMode", "flight_mode", "fc_flight_mode"],
                    default="UNKNOWN",
                ),
                is_flying=self._extract_bool(
                    payload,
                    ["isFlying", "is_flying", "are_motors_on"],
                    default=False,
                ),
                home_distance=self._extract_home_distance(payload, position),
                gimbal_pitch=self._extract_float(
                    payload,
                    ["gimbalPitch", "gimbal_pitch", "gimbal.pitch"],
                ),
                rc_signal=self._extract_rc_signal(payload),
            )

            logger.debug(
                "Telemetry parsed successfully",
                drone_id=state.drone_id,
                lat=state.position.latitude,
                lng=state.position.longitude,
                alt=state.position.altitude,
                flight_mode=state.flight_mode,
            )
            return state
        except Exception as exc:
            logger.error("Failed to build DroneState", error=str(exc))
            return None

    def _extract_latitude(self, payload: dict) -> float:
        value = self._extract_float(
            payload,
            [
                "latitude",
                "lat",
                "gps.latitude",
                "location.latitude",
                "position.latitude",
                "home_location.latitude",
                "aircraft_status.location.latitude",
                "aircraft_status.latitude",
            ],
        )
        return self._normalize_coordinate(value, 90.0)

    def _extract_longitude(self, payload: dict) -> float:
        value = self._extract_float(
            payload,
            [
                "longitude",
                "lng",
                "lon",
                "gps.longitude",
                "location.longitude",
                "position.longitude",
                "home_location.longitude",
                "aircraft_status.location.longitude",
                "aircraft_status.longitude",
            ],
        )
        return self._normalize_coordinate(value, 180.0)

    def _extract_altitude(self, payload: dict) -> float:
        return self._extract_float(
            payload,
            [
                "relative_altitude",
                "altitude",
                "alt",
                "height",
                "gps.altitude",
                "location.altitude",
                "position.altitude",
                "vps_status.ultrasonic_height_cm",
            ],
        ) / (
            100.0
            if self._extract_value(payload, ["vps_status.ultrasonic_height_cm"]) is not _MISSING
            and self._extract_float(payload, ["relative_altitude", "altitude", "alt", "height"]) == 0.0
            else 1.0
        )

    def _extract_horizontal_speed(self, payload: dict) -> float:
        direct = self._extract_float(
            payload,
            [
                "horizontal_speed",
                "horizontalSpeed",
                "hSpeed",
                "speed.horizontal",
                "velocity.horizontal",
                "velocity.horizontal_speed",
            ],
        )
        if direct > 0:
            return direct

        velocity_x = self._extract_float(payload, ["velocity.x"])
        velocity_y = self._extract_float(payload, ["velocity.y"])
        if velocity_x or velocity_y:
            return math.sqrt(velocity_x**2 + velocity_y**2)

        return self._extract_float(payload, ["speed_total", "total_speed", "velocity.total_speed"])

    def _extract_vertical_speed(self, payload: dict) -> float:
        direct = self._extract_float(
            payload,
            [
                "verticalSpeed",
                "vertical_speed",
                "vSpeed",
                "speed.vertical",
                "velocity.vertical",
            ],
        )
        if direct:
            return direct

        return self._extract_float(payload, ["velocity.z"])

    def _extract_voltage(self, payload: dict) -> float:
        voltage = self._extract_float(
            payload,
            [
                "batteryVoltage",
                "battery_voltage",
                "battery.voltage",
                "battery_status.main_battery.voltage_mv",
            ],
        )

        if voltage > 200:
            return round(voltage / 1000.0, 3)
        return voltage

    def _extract_timestamp(self, payload: dict) -> float:
        raw_value = self._extract_value(payload, ["timestamp"])
        if raw_value is _MISSING:
            return time.time()

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        if isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                return time.time()

            try:
                return float(text)
            except ValueError:
                pass

            iso_candidate = text.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(iso_candidate).timestamp()
            except ValueError:
                logger.warning("Unsupported timestamp format, falling back to now", timestamp=text)

        return time.time()

    def _extract_gps_signal(self, payload: dict) -> int:
        level = self._extract_string(payload, ["gps_signal_level"], default="")
        if level:
            suffix = level.split("_")[-1]
            if suffix.isdigit():
                return max(0, min(5, int(suffix)))

        numeric = int(
            self._extract_float(
                payload,
                ["gpsSignal", "gps_signal", "gpsLevel", "signal_level"],
            )
        )
        if numeric:
            return max(0, min(5, numeric))

        satellites = int(
            self._extract_float(payload, ["gps_satellite_count", "satelliteCount", "satellite_count"])
        )
        if satellites >= 16:
            return 5
        if satellites >= 12:
            return 4
        if satellites >= 8:
            return 3
        if satellites >= 5:
            return 2
        if satellites >= 1:
            return 1
        return 0

    def _extract_home_distance(self, payload: dict, position: GpsPosition) -> float:
        direct = self._extract_float(
            payload,
            ["homeDistance", "home_distance", "distanceToHome"],
        )
        if direct:
            return direct

        home_lat = self._normalize_coordinate(
            self._extract_float(
                payload,
                ["home_location.latitude", "aircraft_status.home_location.latitude"],
            ),
            90.0,
        )
        home_lng = self._normalize_coordinate(
            self._extract_float(
                payload,
                ["home_location.longitude", "aircraft_status.home_location.longitude"],
            ),
            180.0,
        )

        if not self._has_valid_position(position.latitude, position.longitude):
            return 0.0

        if not self._has_valid_position(home_lat, home_lng):
            return 0.0

        return self._haversine_distance_meters(
            position.latitude,
            position.longitude,
            home_lat,
            home_lng,
        )

    def _extract_rc_signal(self, payload: dict) -> Optional[int]:
        direct = self._extract_value(
            payload,
            ["rcSignal", "rc_signal", "air_link_status.down_link_quality", "air_link_status.up_link_quality"],
        )

        if direct is not _MISSING:
            try:
                return int(float(direct))
            except (TypeError, ValueError):
                pass

        link_quality_level = self._extract_value(payload, ["air_link_status.link_signal_quality"])
        if link_quality_level is not _MISSING:
            try:
                return int(float(link_quality_level) * 20)
            except (TypeError, ValueError):
                return None

        return None

    @staticmethod
    def _normalize_coordinate(value: float, limit: float) -> float:
        if not value:
            return 0.0

        normalized = float(value)
        while abs(normalized) > limit:
            normalized /= 10.0

        return normalized

    @staticmethod
    def _has_valid_position(latitude: float, longitude: float) -> bool:
        return bool(
            (latitude != 0.0 or longitude != 0.0)
            and (-90.0 <= latitude <= 90.0)
            and (-180.0 <= longitude <= 180.0)
        )

    @staticmethod
    def _haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Compute great-circle distance between two points on Earth in meters.
        """
        earth_radius_m = 6_371_000.0

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return earth_radius_m * c

    @staticmethod
    def _extract_value(payload: dict, keys: list[str]) -> Any:
        for key in keys:
            value: Any = payload
            for part in key.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = _MISSING
                    break

            if value is not _MISSING and value is not None:
                return value

        return _MISSING

    @classmethod
    def _extract_float(cls, payload: dict, keys: list[str], default: float = 0.0) -> float:
        value = cls._extract_value(payload, keys)
        if value is _MISSING:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _extract_string(cls, payload: dict, keys: list[str], default: str = "") -> str:
        value = cls._extract_value(payload, keys)
        if value is _MISSING:
            return default
        return str(value)

    @classmethod
    def _extract_bool(cls, payload: dict, keys: list[str], default: bool = False) -> bool:
        value = cls._extract_value(payload, keys)
        if value is _MISSING:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False

        return default

    def reset(self):
        """Reset parser state."""
        self._buffer = ""
        self._utf8_decoder.reset()
