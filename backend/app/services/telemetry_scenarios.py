"""Deterministic telemetry scenarios for local testing and replay."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional


@dataclass(frozen=True)
class ScenarioStep:
    """One named telemetry frame in a synthetic scenario."""

    name: str
    payload: dict[str, Any]


def build_m400_mission_scenario(start_time: Optional[datetime] = None) -> list[ScenarioStep]:
    """
    Build a deterministic M400 mission profile for parser/integration tests.

    The scenario covers:
    1. preflight on ground
    2. auto takeoff
    3. climb
    4. acceleration
    5. cruise
    6. low-battery prepare-to-return
    7. go home
    8. final approach and landing
    """
    home_lat = 31.2304
    home_lng = 121.4737
    start = start_time or datetime(2026, 4, 16, 10, 0, 0)

    phase_specs = [
        {
            "name": "preflight_ready",
            "seconds": 0,
            "east_m": 0.0,
            "north_m": 0.0,
            "altitude_m": 0.0,
            "horizontal_speed": 0.0,
            "vertical_speed": 0.0,
            "heading": 92.0,
            "battery_percent": 100,
            "battery_temp_c": 28.5,
            "gps_satellite_count": 18,
            "gps_signal_level": "LEVEL_5",
            "flight_mode": "TAKE_OFF_READY",
            "flight_mode_string": "TAKE_OFF_READY",
            "fc_flight_mode": "TAKEOFF",
            "is_flying": False,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 1,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 91,
            "link_quality": 100,
        },
        {
            "name": "auto_takeoff",
            "seconds": 10,
            "east_m": 2.0,
            "north_m": 0.0,
            "altitude_m": 4.5,
            "horizontal_speed": 1.2,
            "vertical_speed": 2.4,
            "heading": 94.0,
            "battery_percent": 98,
            "battery_temp_c": 29.0,
            "gps_satellite_count": 18,
            "gps_signal_level": "LEVEL_5",
            "flight_mode": "AUTO_TAKE_OFF",
            "flight_mode_string": "AUTO_TAKE_OFF",
            "fc_flight_mode": "AUTO_TAKE_OFF",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 1,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 90,
            "link_quality": 100,
        },
        {
            "name": "climb_departure",
            "seconds": 20,
            "east_m": 32.0,
            "north_m": 5.0,
            "altitude_m": 24.0,
            "horizontal_speed": 4.8,
            "vertical_speed": 3.6,
            "heading": 96.0,
            "battery_percent": 95,
            "battery_temp_c": 30.2,
            "gps_satellite_count": 19,
            "gps_signal_level": "LEVEL_5",
            "flight_mode": "GPS_NORMAL",
            "flight_mode_string": "P-GPS",
            "fc_flight_mode": "GPS_ATTI",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 2,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 89,
            "link_quality": 99,
        },
        {
            "name": "acceleration_outbound",
            "seconds": 30,
            "east_m": 105.0,
            "north_m": 10.0,
            "altitude_m": 56.0,
            "horizontal_speed": 9.6,
            "vertical_speed": 2.8,
            "heading": 98.0,
            "battery_percent": 90,
            "battery_temp_c": 31.6,
            "gps_satellite_count": 20,
            "gps_signal_level": "LEVEL_5",
            "flight_mode": "GPS_NORMAL",
            "flight_mode_string": "P-GPS",
            "fc_flight_mode": "GPS_ATTI",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 3,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 88,
            "link_quality": 98,
        },
        {
            "name": "cruise_outbound",
            "seconds": 40,
            "east_m": 220.0,
            "north_m": 14.0,
            "altitude_m": 88.0,
            "horizontal_speed": 14.4,
            "vertical_speed": 1.2,
            "heading": 100.0,
            "battery_percent": 82,
            "battery_temp_c": 32.1,
            "gps_satellite_count": 20,
            "gps_signal_level": "LEVEL_5",
            "flight_mode": "GPS_NORMAL",
            "flight_mode_string": "P-GPS",
            "fc_flight_mode": "GPS_ATTI",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 4,
            "wind_warning": "LEVEL_1",
            "rc_battery_percentage": 87,
            "link_quality": 96,
        },
        {
            "name": "mission_hold",
            "seconds": 50,
            "east_m": 340.0,
            "north_m": 16.0,
            "altitude_m": 118.0,
            "horizontal_speed": 11.2,
            "vertical_speed": 0.2,
            "heading": 101.0,
            "battery_percent": 66,
            "battery_temp_c": 32.8,
            "gps_satellite_count": 19,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "GPS_NORMAL",
            "flight_mode_string": "P-GPS",
            "fc_flight_mode": "GPS_ATTI",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "FLY_NORMALLY",
            "auto_rth_reason": "NONE",
            "wind_speed": 5,
            "wind_warning": "LEVEL_1",
            "rc_battery_percentage": 85,
            "link_quality": 93,
        },
        {
            "name": "low_battery_warning",
            "seconds": 60,
            "east_m": 355.0,
            "north_m": 18.0,
            "altitude_m": 116.0,
            "horizontal_speed": 6.4,
            "vertical_speed": -0.2,
            "heading": 258.0,
            "battery_percent": 24,
            "battery_temp_c": 33.1,
            "gps_satellite_count": 18,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "GPS_NORMAL",
            "flight_mode_string": "LOW_BATTERY_PREPARE_RTH",
            "fc_flight_mode": "GPS_ATTI",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "GO_HOME",
            "auto_rth_reason": "WARNING_POWER_GOHOME",
            "wind_speed": 5,
            "wind_warning": "LEVEL_1",
            "rc_battery_percentage": 84,
            "link_quality": 92,
        },
        {
            "name": "go_home_active",
            "seconds": 70,
            "east_m": 215.0,
            "north_m": 12.0,
            "altitude_m": 100.0,
            "horizontal_speed": 12.8,
            "vertical_speed": -0.8,
            "heading": 270.0,
            "battery_percent": 20,
            "battery_temp_c": 32.2,
            "gps_satellite_count": 18,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "GO_HOME",
            "flight_mode_string": "GO_HOME",
            "fc_flight_mode": "GO_HOME",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "GO_HOME",
            "auto_rth_reason": "WARNING_POWER_GOHOME",
            "wind_speed": 4,
            "wind_warning": "LEVEL_1",
            "rc_battery_percentage": 83,
            "link_quality": 95,
        },
        {
            "name": "final_approach",
            "seconds": 80,
            "east_m": 58.0,
            "north_m": 4.0,
            "altitude_m": 34.0,
            "horizontal_speed": 5.2,
            "vertical_speed": -2.6,
            "heading": 274.0,
            "battery_percent": 17,
            "battery_temp_c": 31.8,
            "gps_satellite_count": 17,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "GO_HOME",
            "flight_mode_string": "GO_HOME",
            "fc_flight_mode": "GO_HOME",
            "is_flying": True,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": True,
            "battery_threshold_behavior": "GO_HOME",
            "auto_rth_reason": "WARNING_POWER_GOHOME",
            "wind_speed": 3,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 82,
            "link_quality": 98,
        },
        {
            "name": "auto_landing",
            "seconds": 90,
            "east_m": 6.0,
            "north_m": 1.0,
            "altitude_m": 8.0,
            "horizontal_speed": 1.4,
            "vertical_speed": -1.9,
            "heading": 279.0,
            "battery_percent": 14,
            "battery_temp_c": 31.0,
            "gps_satellite_count": 17,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "AUTO_LANDING",
            "flight_mode_string": "AUTO_LANDING",
            "fc_flight_mode": "AUTO_LANDING",
            "is_flying": True,
            "is_in_landing_mode": True,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "LAND_IMMEDIATELY",
            "auto_rth_reason": "WARNING_POWER_GOHOME",
            "wind_speed": 2,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 81,
            "link_quality": 99,
        },
        {
            "name": "landed_shutdown",
            "seconds": 100,
            "east_m": 0.0,
            "north_m": 0.0,
            "altitude_m": 0.0,
            "horizontal_speed": 0.0,
            "vertical_speed": 0.0,
            "heading": 280.0,
            "battery_percent": 12,
            "battery_temp_c": 29.6,
            "gps_satellite_count": 17,
            "gps_signal_level": "LEVEL_4",
            "flight_mode": "TAKE_OFF_READY",
            "flight_mode_string": "TAKE_OFF_READY",
            "fc_flight_mode": "ATTI_LANDING",
            "is_flying": False,
            "is_in_landing_mode": False,
            "is_landing_confirmation_needed": False,
            "battery_threshold_behavior": "LAND_IMMEDIATELY",
            "auto_rth_reason": "WARNING_POWER_GOHOME",
            "wind_speed": 1,
            "wind_warning": "LEVEL_0",
            "rc_battery_percentage": 80,
            "link_quality": 100,
        },
    ]

    steps: list[ScenarioStep] = []
    base_payload = _build_base_payload(home_lat, home_lng)

    for phase in phase_specs:
        altitude_m = float(phase["altitude_m"])
        horizontal_speed = float(phase["horizontal_speed"])
        vertical_speed = float(phase["vertical_speed"])
        latitude, longitude = _offset_coordinates(
            home_lat,
            home_lng,
            east_m=float(phase["east_m"]),
            north_m=float(phase["north_m"]),
        )
        home_distance = _distance_meters(home_lat, home_lng, latitude, longitude)
        payload = copy.deepcopy(base_payload)
        payload.update(
            {
                "timestamp": _format_timestamp(start + timedelta(seconds=int(phase["seconds"]))),
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
                    "x": round(horizontal_speed if float(phase["east_m"]) >= 0 else -horizontal_speed, 1),
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
                "is_in_landing_mode": bool(phase["is_in_landing_mode"]),
                "is_landing_confirmation_needed": bool(phase["is_landing_confirmation_needed"]),
                "flight_time_in_seconds": int(phase["seconds"]),
                "battery_percent_needed_to_go_home": 26,
                "battery_threshold_behavior": phase["battery_threshold_behavior"],
                "auto_rth_reason": phase["auto_rth_reason"],
                "wind": {
                    "speed": int(phase["wind_speed"]),
                    "direction": "EAST" if float(phase["east_m"]) >= 0 else "WEST",
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
                ),
                "air_link_status": _build_air_link_status(int(phase["link_quality"])),
                "remote_controller_status": {
                    "connected": True,
                    "mode": "CHANNEL_A",
                    "serial_number": "7CACN880010UE1",
                    "battery_percentage": int(phase["rc_battery_percentage"]),
                },
                "failsafe_action": "GOHOME",
            }
        )
        steps.append(ScenarioStep(name=str(phase["name"]), payload=payload))

    return steps


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


def _build_battery_status(aggregate_percent: int, temperature_c: float) -> dict[str, Any]:
    main_percent = max(0, min(100, aggregate_percent))
    secondary_percent = max(0, min(100, aggregate_percent - 1))
    main_voltage_mv = int(48000 + main_percent * 42)
    secondary_voltage_mv = int(47800 + secondary_percent * 41)

    return {
        "aggregate_percentage": aggregate_percent,
        "connected_count": 2,
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
            "cell_voltages_mv": [int(main_voltage_mv / 13)] * 13,
        },
        "secondary_battery": {
            "index": 1,
            "connected": True,
            "percentage": secondary_percent,
            "temperature_celsius": round(temperature_c - 0.4, 1),
            "voltage_mv": secondary_voltage_mv,
            "serial_number": "M400SECBAT0001",
            "cell_voltages_mv": [int(secondary_voltage_mv / 13)] * 13,
        },
    }


def _build_air_link_status(link_quality: int) -> dict[str, Any]:
    return {
        "connected": True,
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
