"""Deterministic telemetry scenarios for local testing and replay."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from app.services.psdk_data_parser import calculate_weather_lrc


@dataclass(frozen=True)
class ScenarioStep:
    """One named telemetry frame in a synthetic scenario."""

    name: str
    payload: dict[str, Any]


HUNAN_LAT_RANGE = (26.9, 29.4)
HUNAN_LNG_RANGE = (109.8, 113.8)
BASE_DISTANCE_SCALE = 0.43
PSDK_PORT = "PORT_3"


def _create_rng(seed: Optional[int]) -> random.Random:
    return random.Random(seed)


def _derive_seed(seed: Optional[int], offset: int) -> Optional[int]:
    return None if seed is None else seed + offset


def _select_hunan_home(rng: random.Random) -> tuple[float, float]:
    latitude = round(rng.uniform(*HUNAN_LAT_RANGE), 7)
    longitude = round(rng.uniform(*HUNAN_LNG_RANGE), 7)
    return latitude, longitude


def _clamp_int(value: float, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _randomize_phase_specs(
    phase_specs: list[dict[str, Any]],
    cycle_seconds: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    scale = max(0.18, (cycle_seconds / 30.0) * BASE_DISTANCE_SCALE * rng.uniform(0.94, 1.06))
    heading_bias = rng.uniform(-4.0, 4.0)
    lateral_bias = rng.uniform(-6.0, 6.0)
    altitude_bias = rng.uniform(0.95, 1.06)
    wind_bias = rng.uniform(-1.0, 1.5)

    randomized_specs: list[dict[str, Any]] = []
    for phase in phase_specs:
        item = dict(phase)
        progress = float(item["progress"])
        wave = math.sin(progress * math.pi)

        item["east_m"] = round(float(item["east_m"]) * scale + wave * rng.uniform(-5.0, 5.0), 3)
        item["north_m"] = round(float(item["north_m"]) * scale + wave * lateral_bias, 3)
        item["heading"] = round(float(item["heading"]) + heading_bias + rng.uniform(-2.0, 2.0), 1)
        item["wind_speed"] = max(1, int(round(float(item["wind_speed"]) + wind_bias + rng.uniform(-1.0, 1.0))))
        item["battery_temp_c"] = round(float(item["battery_temp_c"]) + rng.uniform(-0.4, 0.8), 1)
        item["gps_satellite_count"] = _clamp_int(float(item["gps_satellite_count"]) + rng.uniform(-1.0, 1.0), 5, 20)
        item["link_quality"] = _clamp_int(float(item["link_quality"]) + rng.uniform(-2.0, 2.0), 10, 100)

        altitude = float(item["altitude_m"])
        if altitude > 0:
            item["altitude_m"] = round(max(altitude * altitude_bias + rng.uniform(-2.0, 2.0), 1.5), 2)
        else:
            item["altitude_m"] = 0.0

        if not bool(item["is_flying"]):
            item["east_m"] = 0.0
            item["north_m"] = 0.0
            item["altitude_m"] = 0.0

        randomized_specs.append(item)

    return randomized_specs


def build_m400_mission_scenario(
    start_time: Optional[datetime] = None,
    cycle_seconds: float = 30.0,
    seed: Optional[int] = None,
) -> list[ScenarioStep]:
    """Build the baseline M400 mission profile."""
    return _build_flight_scenario(
        phase_specs=_base_mission_phase_specs(),
        start_time=start_time,
        cycle_seconds=cycle_seconds,
        seed=seed,
    )


def build_m400_fault_scenario(
    start_time: Optional[datetime] = None,
    cycle_seconds: float = 30.0,
    seed: Optional[int] = None,
) -> list[ScenarioStep]:
    """Build an M400 mission profile with realistic operational degradations."""
    return _build_flight_scenario(
        phase_specs=_fault_mission_phase_specs(),
        start_time=start_time,
        cycle_seconds=cycle_seconds,
        seed=seed,
    )


def build_m400_mixed_stream_scenario(
    start_time: Optional[datetime] = None,
    cycle_seconds: float = 30.0,
    seed: Optional[int] = None,
) -> list[ScenarioStep]:
    """
    Build a mixed stream that interleaves flight telemetry with PSDK weather
    and visibility payloads.
    """
    flight_steps = build_m400_fault_scenario(start_time=start_time, cycle_seconds=cycle_seconds, seed=seed)
    rng = _create_rng(_derive_seed(seed, 101))
    mixed_steps: list[ScenarioStep] = []

    for step in flight_steps:
        mixed_steps.append(step)

        timestamp = datetime.strptime(step.payload["timestamp"], "%Y-%m-%d %H:%M:%S.%f")
        if step.name == "cruise_outbound":
            mixed_steps.extend(
                [
                    _build_weather_step("weather_snapshot_cruise", timestamp + timedelta(milliseconds=150)),
                    _build_visibility_step("visibility_snapshot_cruise", timestamp + timedelta(milliseconds=300)),
                ]
            )
        elif step.name == "gps_signal_degraded":
            mixed_steps.append(
                    _build_weather_step(
                        "weather_snapshot_gps_degraded",
                        timestamp + timedelta(milliseconds=150),
                        relative_wind_direction=str(_clamp_int(72 + rng.uniform(-12.0, 14.0), 0, 359)),
                        relative_wind_speed=f"{max(1.6, 4.8 + rng.uniform(-0.6, 0.9)):.2f}",
                        temperature=f"{27.4 + rng.uniform(-1.0, 1.1):.1f}",
                        humidity=f"{58.3 + rng.uniform(-4.0, 4.5):.1f}",
                        pressure=f"{931.5 + rng.uniform(-3.0, 2.0):.1f}",
                        compass_heading=str(_clamp_int(18 + rng.uniform(-10.0, 12.0), 0, 359)),
                        true_wind_direction=f"{74.2 + rng.uniform(-8.0, 8.0):.1f}",
                        true_wind_speed=f"{max(2.2, 5.36 + rng.uniform(-0.7, 0.9)):.2f}",
                    )
                )
        elif step.name == "battery_anomaly_detected":
            mixed_steps.append(
                _build_visibility_step(
                    "visibility_snapshot_battery_anomaly",
                    timestamp + timedelta(milliseconds=150),
                    visibility_10s=f"{_clamp_int(1580 + rng.uniform(-120.0, 80.0), 600, 9000):05d}",
                    visibility_1min=f"{_clamp_int(1620 + rng.uniform(-110.0, 90.0), 650, 9000):05d}",
                    visibility_10min=f"{_clamp_int(1650 + rng.uniform(-100.0, 120.0), 700, 9000):05d}",
                    voltage=f"{max(10.6, 11.2 + rng.uniform(-0.3, 0.2)):.2f}",
                )
            )

    return mixed_steps


def build_m400_weather_device_scenario(
    start_time: Optional[datetime] = None,
    cycle_seconds: float = 30.0,
    seed: Optional[int] = None,
) -> list[ScenarioStep]:
    """Build a weather-device-only stream for PSDK weather and visibility testing."""
    start = start_time or datetime.now().replace(microsecond=0)
    safe_cycle_seconds = max(5, int(round(float(cycle_seconds))))
    rng = _create_rng(seed)
    direction_base = rng.uniform(32.0, 118.0)
    relative_speed_base = rng.uniform(0.25, 1.25)
    temperature_base = rng.uniform(18.5, 29.5)
    humidity_base = rng.uniform(46.0, 74.0)
    pressure_base = rng.uniform(990.0, 1008.0)
    compass_base = rng.uniform(12.0, 92.0)
    true_direction_base = direction_base + rng.uniform(-16.0, 18.0)
    true_speed_base = relative_speed_base + rng.uniform(0.9, 2.2)
    visibility_base = rng.uniform(1500.0, 4200.0)
    voltage_base = rng.uniform(11.1, 12.2)
    steps: list[ScenarioStep] = []

    for second in range(safe_cycle_seconds + 1):
        base_time = start + timedelta(seconds=second)
        progress = second / max(1, safe_cycle_seconds)
        gust_wave = math.sin(progress * math.pi * 2.2 + rng.uniform(-0.08, 0.08))
        weather_drift = math.sin(progress * math.pi * 1.4)
        temperature = temperature_base + weather_drift * 2.4 + rng.uniform(-0.35, 0.35)
        humidity = humidity_base - weather_drift * 5.0 + rng.uniform(-1.0, 1.0)
        pressure = pressure_base + math.cos(progress * math.pi * 1.1) * 2.8 + rng.uniform(-0.4, 0.4)
        rel_direction = (direction_base + second * rng.uniform(3.4, 5.8) + gust_wave * 22.0) % 360.0
        rel_speed = max(0.0, relative_speed_base + gust_wave * 0.9 + rng.uniform(-0.08, 0.08))
        compass_heading = (compass_base + second * rng.uniform(2.6, 4.2)) % 360.0
        true_direction = (true_direction_base + second * rng.uniform(3.8, 6.5) + gust_wave * 18.0) % 360.0
        true_speed = max(0.2, true_speed_base + gust_wave * 0.85 + rng.uniform(-0.08, 0.08))

        steps.append(
            _build_weather_step(
                name=f"weather_device_{second:02d}",
                timestamp=base_time,
                relative_wind_direction=str(int(round(rel_direction)) % 360),
                relative_wind_speed=f"{rel_speed:.2f}",
                temperature=f"{temperature:.1f}",
                humidity=f"{max(18.0, min(95.0, humidity)):.1f}",
                pressure=f"{max(940.0, min(1045.0, pressure)):.1f}",
                compass_heading=str(int(round(compass_heading)) % 360),
                true_wind_direction=f"{true_direction:.1f}",
                true_wind_speed=f"{true_speed:.2f}",
            )
        )

        if second < safe_cycle_seconds:
            visibility_wave = math.sin(progress * math.pi * 1.6 + 0.6)
            visibility_10s = _clamp_int(visibility_base + visibility_wave * 420.0 + rng.uniform(-80.0, 80.0), 600, 9000)
            visibility_1min = _clamp_int(visibility_base + visibility_wave * 360.0 + rng.uniform(-60.0, 60.0), 650, 9000)
            visibility_10min = _clamp_int(visibility_base + visibility_wave * 300.0 + rng.uniform(-40.0, 40.0), 700, 9000)
            voltage = max(10.8, voltage_base - progress * 0.5 + rng.uniform(-0.05, 0.05))
            steps.append(
                _build_visibility_step(
                    name=f"visibility_device_{second:02d}",
                    timestamp=base_time + timedelta(milliseconds=500),
                    visibility_10s=f"{visibility_10s:05d}",
                    visibility_1min=f"{visibility_1min:05d}",
                    visibility_10min=f"{visibility_10min:05d}",
                    voltage=f"{voltage:.2f}",
                )
            )

    return steps


def _build_flight_scenario(
    phase_specs: list[dict[str, Any]],
    start_time: Optional[datetime],
    cycle_seconds: float,
    seed: Optional[int] = None,
) -> list[ScenarioStep]:
    rng = _create_rng(seed)
    home_lat, home_lng = _select_hunan_home(rng)
    start = start_time or datetime.now().replace(microsecond=0)
    safe_cycle_seconds = max(5, int(round(float(cycle_seconds))))
    base_payload = _build_base_payload(home_lat, home_lng)
    randomized_phase_specs = _randomize_phase_specs(phase_specs, safe_cycle_seconds, rng)
    phase_timeline = _build_phase_timeline(randomized_phase_specs, safe_cycle_seconds)

    steps: list[ScenarioStep] = []
    previous_position: Optional[dict[str, float]] = None
    previous_timestamp: Optional[datetime] = None
    for second in range(safe_cycle_seconds + 1):
        phase, phase_name = _resolve_phase_for_second(phase_timeline, second)
        current_timestamp = start + timedelta(seconds=second)
        payload = _build_flight_payload(
            base_payload=base_payload,
            phase=phase,
            timestamp=current_timestamp,
            elapsed_seconds=second,
            home_lat=home_lat,
            home_lng=home_lng,
            previous_position=previous_position,
            previous_timestamp=previous_timestamp,
        )
        step_name = phase_name or f"sample_{second:02d}"
        steps.append(ScenarioStep(name=step_name, payload=payload))
        previous_position = {
            "latitude": payload["location"]["latitude"],
            "longitude": payload["location"]["longitude"],
            "altitude": payload["relative_altitude"],
            "east_m": float(phase["east_m"]),
            "north_m": float(phase["north_m"]),
        }
        previous_timestamp = current_timestamp

    return steps


def _build_phase_timeline(phase_specs: list[dict[str, Any]], total_seconds: int) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for phase in phase_specs:
        phase_copy = dict(phase)
        phase_copy["time_second"] = max(0, min(total_seconds, int(round(float(phase["progress"]) * total_seconds))))
        timeline.append(phase_copy)
    timeline.sort(key=lambda item: item["time_second"])
    return timeline


def _resolve_phase_for_second(
    phase_timeline: list[dict[str, Any]],
    second: int,
) -> tuple[dict[str, Any], Optional[str]]:
    if not phase_timeline:
        raise ValueError("Phase timeline cannot be empty")

    first_phase = phase_timeline[0]
    if second <= int(first_phase["time_second"]):
        return dict(first_phase), str(first_phase["name"])

    for index in range(len(phase_timeline) - 1):
        current_phase = phase_timeline[index]
        next_phase = phase_timeline[index + 1]
        current_second = int(current_phase["time_second"])
        next_second = int(next_phase["time_second"])

        if second == current_second:
            return dict(current_phase), str(current_phase["name"])
        if second == next_second:
            return dict(next_phase), str(next_phase["name"])
        if second < next_second:
            return _interpolate_phase_between(current_phase, next_phase, second), None

    last_phase = phase_timeline[-1]
    return dict(last_phase), str(last_phase["name"])


def _interpolate_phase_between(
    current_phase: dict[str, Any],
    next_phase: dict[str, Any],
    second: int,
) -> dict[str, Any]:
    current_second = int(current_phase["time_second"])
    next_second = int(next_phase["time_second"])
    if next_second <= current_second:
        return dict(next_phase)

    factor = (second - current_second) / float(next_second - current_second)
    phase = dict(current_phase)
    phase.update(
        {
            "east_m": _interpolate_float(current_phase["east_m"], next_phase["east_m"], factor),
            "north_m": _interpolate_float(current_phase["north_m"], next_phase["north_m"], factor),
            "altitude_m": _interpolate_float(current_phase["altitude_m"], next_phase["altitude_m"], factor),
            "horizontal_speed": _interpolate_float(
                current_phase["horizontal_speed"], next_phase["horizontal_speed"], factor
            ),
            "vertical_speed": _interpolate_float(current_phase["vertical_speed"], next_phase["vertical_speed"], factor),
            "heading": _interpolate_float(current_phase["heading"], next_phase["heading"], factor),
            "battery_percent": _interpolate_int(current_phase["battery_percent"], next_phase["battery_percent"], factor),
            "battery_temp_c": _interpolate_float(current_phase["battery_temp_c"], next_phase["battery_temp_c"], factor),
            "gps_satellite_count": _interpolate_int(
                current_phase["gps_satellite_count"], next_phase["gps_satellite_count"], factor
            ),
            "link_quality": _interpolate_int(current_phase["link_quality"], next_phase["link_quality"], factor),
            "rc_battery_percentage": _interpolate_int(
                current_phase["rc_battery_percentage"], next_phase["rc_battery_percentage"], factor
            ),
            "wind_speed": _interpolate_int(current_phase["wind_speed"], next_phase["wind_speed"], factor),
        }
    )
    return phase


def _build_flight_payload(
    base_payload: dict[str, Any],
    phase: dict[str, Any],
    timestamp: datetime,
    elapsed_seconds: int,
    home_lat: float,
    home_lng: float,
    previous_position: Optional[dict[str, float]] = None,
    previous_timestamp: Optional[datetime] = None,
) -> dict[str, Any]:
    altitude_m = float(phase["altitude_m"])
    latitude, longitude = _offset_coordinates(
        home_lat,
        home_lng,
        east_m=float(phase["east_m"]),
        north_m=float(phase["north_m"]),
    )
    home_distance = _distance_meters(home_lat, home_lng, latitude, longitude)

    if previous_position and previous_timestamp:
        delta_seconds = max((timestamp - previous_timestamp).total_seconds(), 1e-6)
        horizontal_speed = round(
            _distance_meters(
                previous_position["latitude"],
                previous_position["longitude"],
                latitude,
                longitude,
            )
            / delta_seconds,
            1,
        )
        vertical_speed = round((altitude_m - float(previous_position["altitude"])) / delta_seconds, 1)
        east_delta = float(phase["east_m"]) - float(previous_position.get("east_m", phase["east_m"]))
    else:
        horizontal_speed = round(float(phase.get("horizontal_speed", 0.0)), 1)
        vertical_speed = round(float(phase.get("vertical_speed", 0.0)), 1)
        east_delta = float(phase["east_m"])

    if not bool(phase["is_flying"]):
        horizontal_speed = 0.0
        vertical_speed = 0.0

    east_direction = 1 if east_delta >= 0 else -1

    payload = copy.deepcopy(base_payload)
    payload.update(
        {
            "timestamp": _format_timestamp(timestamp),
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude_m,
            },
            "aircraft_status": {
                "aircraft_location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "altitude": altitude_m,
                },
                "home_location": {
                    "latitude": home_lat,
                    "longitude": home_lng,
                },
                "distance_to_home": round(home_distance, 1),
            },
            "altitude": altitude_m,
            "relative_altitude": altitude_m,
            "attitude": {
                "pitch": round(min(12.0, horizontal_speed * 0.8), 1),
                "roll": round(max(-6.0, min(6.0, vertical_speed * -1.2)), 1),
                "yaw": float(phase["heading"]),
            },
            "velocity": {
                "x": round(horizontal_speed * east_direction, 1),
                "y": 0.0,
                "z": vertical_speed,
                "horizontal_speed": horizontal_speed,
                "total_speed": round(math.sqrt(horizontal_speed**2 + vertical_speed**2), 1),
            },
            "horizontal_speed": horizontal_speed,
            "speed_total": round(math.sqrt(horizontal_speed**2 + vertical_speed**2), 1),
            "flight_mode": phase["flight_mode"],
            "flight_mode_string": phase["flight_mode_string"],
            "fc_flight_mode": phase["fc_flight_mode"],
            "is_flying": bool(phase["is_flying"]),
            "aircraft_heading": float(phase["heading"]),
            "gps_satellite_count": int(phase["gps_satellite_count"]),
            "gps_signal_level": str(phase["gps_signal_level"]),
            "are_motors_on": bool(phase["is_flying"]),
            "is_in_landing_mode": bool(phase.get("is_in_landing_mode", False)),
            "is_landing_confirmation_needed": bool(phase.get("is_landing_confirmation_needed", False)),
            "flight_time_in_seconds": elapsed_seconds,
            "battery_percent_needed_to_go_home": 26,
            "battery_threshold_behavior": phase["battery_threshold_behavior"],
            "auto_rth_reason": phase["auto_rth_reason"],
            "wind": {
                "speed": int(phase["wind_speed"]),
                "direction": phase.get(
                    "wind_direction",
                    "EAST" if float(phase["east_m"]) >= 0 else "WEST",
                ),
                "warning": phase["wind_warning"],
            },
            "vps_status": {
                "vision_positioning_enabled": True,
                "ultrasonic_used": altitude_m <= 10.0,
                "ultrasonic_height_cm": int(max(0.0, min(1000.0, altitude_m * 100.0))),
            },
            "battery_status": _build_battery_status(
                int(phase["battery_percent"]),
                float(phase["battery_temp_c"]),
                anomaly_flags=phase.get("battery_flags"),
            ),
            "air_link_status": _build_air_link_status(
                int(phase["link_quality"]),
                connected=bool(phase.get("air_link_connected", True)),
            ),
            "remote_controller_status": {
                "connected": bool(phase.get("remote_controller_connected", True)),
                "mode": "CHANNEL_A",
                "serial_number": "7CACN880010UE1",
                "battery_percentage": int(phase["rc_battery_percentage"]),
            },
            "failsafe_action": phase.get("failsafe_action", "GOHOME"),
        }
    )
    return payload


def _interpolate_float(start: Any, end: Any, factor: float) -> float:
    return round(float(start) + (float(end) - float(start)) * factor, 3)


def _interpolate_int(start: Any, end: Any, factor: float) -> int:
    return int(round(float(start) + (float(end) - float(start)) * factor))


def _base_mission_phase_specs() -> list[dict[str, Any]]:
    return [
        _phase(
            name="preflight_ready",
            progress=0.00,
            east_m=0.0,
            north_m=0.0,
            altitude_m=0.0,
            horizontal_speed=0.0,
            vertical_speed=0.0,
            heading=92.0,
            battery_percent=100,
            battery_temp_c=28.5,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_5",
            flight_mode="TAKE_OFF_READY",
            flight_mode_string="TAKE_OFF_READY",
            fc_flight_mode="TAKEOFF",
            is_flying=False,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=91,
            link_quality=100,
        ),
        _phase(
            name="auto_takeoff",
            progress=0.08,
            east_m=2.0,
            north_m=0.0,
            altitude_m=4.5,
            horizontal_speed=1.2,
            vertical_speed=2.4,
            heading=94.0,
            battery_percent=98,
            battery_temp_c=29.0,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_5",
            flight_mode="AUTO_TAKE_OFF",
            flight_mode_string="AUTO_TAKE_OFF",
            fc_flight_mode="AUTO_TAKE_OFF",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=90,
            link_quality=100,
        ),
        _phase(
            name="climb_departure",
            progress=0.18,
            east_m=32.0,
            north_m=5.0,
            altitude_m=24.0,
            horizontal_speed=4.8,
            vertical_speed=3.6,
            heading=96.0,
            battery_percent=95,
            battery_temp_c=30.2,
            gps_satellite_count=19,
            gps_signal_level="LEVEL_5",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=2,
            wind_warning="LEVEL_0",
            rc_battery_percentage=89,
            link_quality=99,
        ),
        _phase(
            name="acceleration_outbound",
            progress=0.30,
            east_m=105.0,
            north_m=10.0,
            altitude_m=56.0,
            horizontal_speed=9.6,
            vertical_speed=2.8,
            heading=98.0,
            battery_percent=90,
            battery_temp_c=31.6,
            gps_satellite_count=20,
            gps_signal_level="LEVEL_5",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=3,
            wind_warning="LEVEL_0",
            rc_battery_percentage=88,
            link_quality=98,
        ),
        _phase(
            name="cruise_outbound",
            progress=0.44,
            east_m=220.0,
            north_m=14.0,
            altitude_m=88.0,
            horizontal_speed=14.4,
            vertical_speed=1.2,
            heading=100.0,
            battery_percent=82,
            battery_temp_c=32.1,
            gps_satellite_count=20,
            gps_signal_level="LEVEL_5",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=4,
            wind_warning="LEVEL_1",
            rc_battery_percentage=87,
            link_quality=96,
        ),
        _phase(
            name="mission_hold",
            progress=0.58,
            east_m=340.0,
            north_m=16.0,
            altitude_m=118.0,
            horizontal_speed=11.2,
            vertical_speed=0.2,
            heading=101.0,
            battery_percent=66,
            battery_temp_c=32.8,
            gps_satellite_count=19,
            gps_signal_level="LEVEL_4",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=5,
            wind_warning="LEVEL_1",
            rc_battery_percentage=85,
            link_quality=93,
        ),
        _phase(
            name="low_battery_warning",
            progress=0.70,
            east_m=355.0,
            north_m=18.0,
            altitude_m=116.0,
            horizontal_speed=6.4,
            vertical_speed=-0.2,
            heading=258.0,
            battery_percent=24,
            battery_temp_c=33.1,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_4",
            flight_mode="GPS_NORMAL",
            flight_mode_string="LOW_BATTERY_PREPARE_RTH",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=5,
            wind_warning="LEVEL_1",
            rc_battery_percentage=84,
            link_quality=92,
        ),
        _phase(
            name="go_home_active",
            progress=0.82,
            east_m=215.0,
            north_m=12.0,
            altitude_m=100.0,
            horizontal_speed=12.8,
            vertical_speed=-0.8,
            heading=270.0,
            battery_percent=20,
            battery_temp_c=32.2,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_4",
            flight_mode="GO_HOME",
            flight_mode_string="GO_HOME",
            fc_flight_mode="GO_HOME",
            is_flying=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=4,
            wind_warning="LEVEL_1",
            rc_battery_percentage=83,
            link_quality=95,
        ),
        _phase(
            name="final_approach",
            progress=0.92,
            east_m=58.0,
            north_m=4.0,
            altitude_m=34.0,
            horizontal_speed=5.2,
            vertical_speed=-2.6,
            heading=274.0,
            battery_percent=17,
            battery_temp_c=31.8,
            gps_satellite_count=17,
            gps_signal_level="LEVEL_4",
            flight_mode="GO_HOME",
            flight_mode_string="GO_HOME",
            fc_flight_mode="GO_HOME",
            is_flying=True,
            is_landing_confirmation_needed=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=3,
            wind_warning="LEVEL_0",
            rc_battery_percentage=82,
            link_quality=98,
        ),
        _phase(
            name="auto_landing",
            progress=0.97,
            east_m=6.0,
            north_m=1.0,
            altitude_m=8.0,
            horizontal_speed=1.4,
            vertical_speed=-1.9,
            heading=279.0,
            battery_percent=14,
            battery_temp_c=31.0,
            gps_satellite_count=17,
            gps_signal_level="LEVEL_4",
            flight_mode="AUTO_LANDING",
            flight_mode_string="AUTO_LANDING",
            fc_flight_mode="AUTO_LANDING",
            is_flying=True,
            is_in_landing_mode=True,
            battery_threshold_behavior="LAND_IMMEDIATELY",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=2,
            wind_warning="LEVEL_0",
            rc_battery_percentage=81,
            link_quality=99,
        ),
        _phase(
            name="landed_shutdown",
            progress=1.00,
            east_m=0.0,
            north_m=0.0,
            altitude_m=0.0,
            horizontal_speed=0.0,
            vertical_speed=0.0,
            heading=280.0,
            battery_percent=12,
            battery_temp_c=29.6,
            gps_satellite_count=17,
            gps_signal_level="LEVEL_4",
            flight_mode="TAKE_OFF_READY",
            flight_mode_string="TAKE_OFF_READY",
            fc_flight_mode="ATTI_LANDING",
            is_flying=False,
            battery_threshold_behavior="LAND_IMMEDIATELY",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=80,
            link_quality=100,
        ),
    ]


def _fault_mission_phase_specs() -> list[dict[str, Any]]:
    return [
        _phase(
            name="preflight_ready",
            progress=0.00,
            east_m=0.0,
            north_m=0.0,
            altitude_m=0.0,
            horizontal_speed=0.0,
            vertical_speed=0.0,
            heading=92.0,
            battery_percent=100,
            battery_temp_c=28.5,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_5",
            flight_mode="TAKE_OFF_READY",
            flight_mode_string="TAKE_OFF_READY",
            fc_flight_mode="TAKEOFF",
            is_flying=False,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=91,
            link_quality=100,
        ),
        _phase(
            name="auto_takeoff",
            progress=0.07,
            east_m=3.0,
            north_m=1.0,
            altitude_m=6.0,
            horizontal_speed=1.5,
            vertical_speed=2.8,
            heading=95.0,
            battery_percent=98,
            battery_temp_c=29.1,
            gps_satellite_count=18,
            gps_signal_level="LEVEL_5",
            flight_mode="AUTO_TAKE_OFF",
            flight_mode_string="AUTO_TAKE_OFF",
            fc_flight_mode="AUTO_TAKE_OFF",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=90,
            link_quality=100,
        ),
        _phase(
            name="climb_departure",
            progress=0.15,
            east_m=44.0,
            north_m=6.0,
            altitude_m=28.0,
            horizontal_speed=5.2,
            vertical_speed=3.2,
            heading=97.0,
            battery_percent=95,
            battery_temp_c=30.4,
            gps_satellite_count=19,
            gps_signal_level="LEVEL_5",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=2,
            wind_warning="LEVEL_0",
            rc_battery_percentage=89,
            link_quality=99,
        ),
        _phase(
            name="acceleration_outbound",
            progress=0.26,
            east_m=128.0,
            north_m=9.0,
            altitude_m=62.0,
            horizontal_speed=10.2,
            vertical_speed=2.1,
            heading=100.0,
            battery_percent=90,
            battery_temp_c=31.8,
            gps_satellite_count=20,
            gps_signal_level="LEVEL_5",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=3,
            wind_warning="LEVEL_0",
            rc_battery_percentage=88,
            link_quality=97,
        ),
        _phase(
            name="cruise_outbound",
            progress=0.38,
            east_m=240.0,
            north_m=13.0,
            altitude_m=92.0,
            horizontal_speed=13.8,
            vertical_speed=0.8,
            heading=102.0,
            battery_percent=84,
            battery_temp_c=32.3,
            gps_satellite_count=19,
            gps_signal_level="LEVEL_4",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=4,
            wind_warning="LEVEL_1",
            rc_battery_percentage=86,
            link_quality=95,
        ),
        _phase(
            name="gps_signal_degraded",
            progress=0.50,
            east_m=272.0,
            north_m=15.0,
            altitude_m=96.0,
            horizontal_speed=10.0,
            vertical_speed=-0.1,
            heading=106.0,
            battery_percent=79,
            battery_temp_c=32.6,
            gps_satellite_count=6,
            gps_signal_level="LEVEL_1",
            flight_mode="ATTI",
            flight_mode_string="ATTI",
            fc_flight_mode="ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=5,
            wind_warning="LEVEL_1",
            rc_battery_percentage=85,
            link_quality=90,
        ),
        _phase(
            name="rc_link_degraded",
            progress=0.60,
            east_m=315.0,
            north_m=17.0,
            altitude_m=98.0,
            horizontal_speed=9.4,
            vertical_speed=-0.3,
            heading=108.0,
            battery_percent=73,
            battery_temp_c=33.0,
            gps_satellite_count=14,
            gps_signal_level="LEVEL_3",
            flight_mode="GPS_NORMAL",
            flight_mode_string="P-GPS",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="FLY_NORMALLY",
            auto_rth_reason="NONE",
            wind_speed=5,
            wind_warning="LEVEL_1",
            rc_battery_percentage=83,
            link_quality=24,
        ),
        _phase(
            name="battery_anomaly_detected",
            progress=0.70,
            east_m=332.0,
            north_m=18.0,
            altitude_m=94.0,
            horizontal_speed=7.2,
            vertical_speed=-0.6,
            heading=246.0,
            battery_percent=34,
            battery_temp_c=40.2,
            gps_satellite_count=14,
            gps_signal_level="LEVEL_3",
            flight_mode="GPS_NORMAL",
            flight_mode_string="BATTERY_DIAGNOSIS_PROTECT",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="BATTERY_DIAGNOSIS_PROTECT",
            wind_speed=4,
            wind_warning="LEVEL_1",
            rc_battery_percentage=82,
            link_quality=78,
            battery_flags={
                "cell_damaged": True,
                "voltage_difference_detected": True,
                "low_cell_voltage_detected": True,
            },
        ),
        _phase(
            name="low_battery_warning",
            progress=0.78,
            east_m=348.0,
            north_m=18.0,
            altitude_m=90.0,
            horizontal_speed=6.1,
            vertical_speed=-0.5,
            heading=258.0,
            battery_percent=22,
            battery_temp_c=37.5,
            gps_satellite_count=14,
            gps_signal_level="LEVEL_3",
            flight_mode="GPS_NORMAL",
            flight_mode_string="LOW_BATTERY_PREPARE_RTH",
            fc_flight_mode="GPS_ATTI",
            is_flying=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=4,
            wind_warning="LEVEL_1",
            rc_battery_percentage=81,
            link_quality=68,
        ),
        _phase(
            name="go_home_active",
            progress=0.86,
            east_m=210.0,
            north_m=12.0,
            altitude_m=82.0,
            horizontal_speed=11.4,
            vertical_speed=-1.0,
            heading=272.0,
            battery_percent=18,
            battery_temp_c=35.8,
            gps_satellite_count=15,
            gps_signal_level="LEVEL_4",
            flight_mode="GO_HOME",
            flight_mode_string="GO_HOME",
            fc_flight_mode="GO_HOME",
            is_flying=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=3,
            wind_warning="LEVEL_1",
            rc_battery_percentage=80,
            link_quality=76,
        ),
        _phase(
            name="final_approach",
            progress=0.93,
            east_m=64.0,
            north_m=4.0,
            altitude_m=30.0,
            horizontal_speed=4.8,
            vertical_speed=-2.8,
            heading=276.0,
            battery_percent=15,
            battery_temp_c=33.8,
            gps_satellite_count=15,
            gps_signal_level="LEVEL_4",
            flight_mode="GO_HOME",
            flight_mode_string="GO_HOME",
            fc_flight_mode="GO_HOME",
            is_flying=True,
            is_landing_confirmation_needed=True,
            battery_threshold_behavior="GO_HOME",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=3,
            wind_warning="LEVEL_0",
            rc_battery_percentage=79,
            link_quality=88,
        ),
        _phase(
            name="auto_landing",
            progress=0.98,
            east_m=8.0,
            north_m=1.0,
            altitude_m=6.0,
            horizontal_speed=1.3,
            vertical_speed=-1.7,
            heading=279.0,
            battery_percent=13,
            battery_temp_c=31.9,
            gps_satellite_count=16,
            gps_signal_level="LEVEL_4",
            flight_mode="AUTO_LANDING",
            flight_mode_string="AUTO_LANDING",
            fc_flight_mode="AUTO_LANDING",
            is_flying=True,
            is_in_landing_mode=True,
            battery_threshold_behavior="LAND_IMMEDIATELY",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=2,
            wind_warning="LEVEL_0",
            rc_battery_percentage=78,
            link_quality=95,
        ),
        _phase(
            name="landed_shutdown",
            progress=1.00,
            east_m=0.0,
            north_m=0.0,
            altitude_m=0.0,
            horizontal_speed=0.0,
            vertical_speed=0.0,
            heading=280.0,
            battery_percent=12,
            battery_temp_c=30.1,
            gps_satellite_count=16,
            gps_signal_level="LEVEL_4",
            flight_mode="TAKE_OFF_READY",
            flight_mode_string="TAKE_OFF_READY",
            fc_flight_mode="ATTI_LANDING",
            is_flying=False,
            battery_threshold_behavior="LAND_IMMEDIATELY",
            auto_rth_reason="WARNING_POWER_GOHOME",
            wind_speed=1,
            wind_warning="LEVEL_0",
            rc_battery_percentage=77,
            link_quality=100,
        ),
    ]


def _phase(**values: Any) -> dict[str, Any]:
    defaults = {
        "is_in_landing_mode": False,
        "is_landing_confirmation_needed": False,
        "battery_flags": None,
        "air_link_connected": True,
        "remote_controller_connected": True,
        "failsafe_action": "GOHOME",
    }
    defaults.update(values)
    return defaults


def _build_weather_step(
    name: str,
    timestamp: datetime,
    relative_wind_direction: str = "56",
    relative_wind_speed: str = "0.03",
    temperature: str = "28.9",
    humidity: str = "61.1",
    pressure: str = "929.0",
    compass_heading: str = "12",
    true_wind_direction: str = "12.5",
    true_wind_speed: str = "2.82",
) -> ScenarioStep:
    frame_body = (
        f":01,{relative_wind_direction},{relative_wind_speed},{temperature},{humidity},"
        f"{pressure},{compass_heading},,,,,,,,,,,,,,,{true_wind_direction},,{true_wind_speed},,"
    )
    checksum = calculate_weather_lrc(frame_body) or "00"
    payload = {
        "type": "psdk_data",
        "timestamp": _format_timestamp(timestamp),
        "payload_index": PSDK_PORT,
        "data": f"{frame_body}{checksum}\r\n",
    }
    return ScenarioStep(name=name, payload=payload)


def _build_visibility_step(
    name: str,
    timestamp: datetime,
    visibility_10s: str = "01820",
    visibility_1min: str = "01872",
    visibility_10min: str = "01872",
    voltage: str = "11.5",
) -> ScenarioStep:
    payload = {
        "type": "psdk_data",
        "timestamp": _format_timestamp(timestamp),
        "payload_index": PSDK_PORT,
        "data": f"VTF-{visibility_10s}-{visibility_1min}-{visibility_10min}-///-0001-000.0-{voltage}-1.25-04\r\n",
    }
    return ScenarioStep(name=name, payload=payload)


def _build_base_payload(home_lat: float, home_lng: float) -> dict[str, Any]:
    return {
        "type": "flight_data",
        "schema_version": 2,
        "aircraft_name": "Matrice 400 Test Rig",
        "product_type": "DJI_MATRICE_400",
        "product_firmware_version": "16.00.0813",
        "flight_controller_serial_number": "1581F8DBW256G00A2PXY",
        "flight_controller_connected": True,
        "remote_controller_connected": True,
        "home_location": {
            "latitude": home_lat,
            "longitude": home_lng,
        },
        "go_home_height": 120,
        "height_limit": 500,
        "distance_limit_enabled": False,
        "distance_limit": 5000,
        "low_battery_warning_threshold": 25,
        "serious_low_battery_warning_threshold": 15,
        "low_battery_rth_info": {
            "battery_percent_needed_to_land": 12,
            "battery_percent_needed_to_go_home": 26,
            "remaining_flight_time": 540,
        },
    }


def _build_battery_status(
    aggregate_percent: int,
    temperature_c: float,
    anomaly_flags: Optional[dict[str, bool]] = None,
) -> dict[str, Any]:
    flags = {
        "any_battery_disconnected": False,
        "cell_damaged": False,
        "firmware_difference_detected": False,
        "voltage_difference_detected": False,
        "low_cell_voltage_detected": False,
    }
    if anomaly_flags:
        flags.update(anomaly_flags)

    main_percent = max(0, min(100, aggregate_percent))
    secondary_percent = max(0, min(100, aggregate_percent - 1))
    main_voltage_mv = int(48000 + main_percent * 42)
    secondary_voltage_mv = int(47800 + secondary_percent * 41)

    return {
        "aggregate_percentage": aggregate_percent,
        "connected_count": 2,
        **flags,
        "overview": [
            {"index": 0, "is_connected": True},
            {"index": 1, "is_connected": True},
        ],
        "main_battery": {
            "index": 0,
            "connected": True,
            "percentage": main_percent,
            "temperature_celsius": round(temperature_c, 1),
            "voltage_mv": main_voltage_mv,
            "serial_number": "M400MAINBAT0001",
            "cell_voltages_mv": _build_cell_voltages(main_voltage_mv, flags),
        },
        "secondary_battery": {
            "index": 1,
            "connected": True,
            "percentage": secondary_percent,
            "temperature_celsius": round(temperature_c - 0.4, 1),
            "voltage_mv": secondary_voltage_mv,
            "serial_number": "M400SECBAT0001",
            "cell_voltages_mv": _build_cell_voltages(secondary_voltage_mv, flags),
        },
    }


def _build_cell_voltages(pack_voltage_mv: int, flags: dict[str, bool]) -> list[int]:
    base_cell_voltage = int(pack_voltage_mv / 13)
    voltages = [base_cell_voltage] * 13
    if flags.get("voltage_difference_detected"):
        voltages[0] = max(2800, base_cell_voltage - 180)
        voltages[-1] = base_cell_voltage + 95
    if flags.get("low_cell_voltage_detected"):
        voltages[3] = max(2700, base_cell_voltage - 260)
    return voltages


def _build_air_link_status(link_quality: int, connected: bool = True) -> dict[str, Any]:
    return {
        "connected": connected,
        "down_link_quality": max(0, min(100, link_quality)),
        "down_link_quality_raw": max(0, min(100, link_quality - 8)),
        "up_link_quality": max(0, min(100, link_quality - 2)),
        "up_link_quality_raw": max(0, min(100, link_quality - 10)),
        "link_signal_quality": max(0, min(5, round(link_quality / 20))),
        "dynamic_data_rate": round(12.0 + (link_quality / 10.0), 3),
        "frequency_point": 5804,
        "frequency_band": "BAND_MULTI",
    }


def _format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _offset_coordinates(
    latitude: float,
    longitude: float,
    east_m: float = 0.0,
    north_m: float = 0.0,
) -> tuple[float, float]:
    delta_lat = north_m / 111_320.0
    delta_lng = east_m / (111_320.0 * math.cos(math.radians(latitude)))
    return round(latitude + delta_lat, 7), round(longitude + delta_lng, 7)


def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
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
