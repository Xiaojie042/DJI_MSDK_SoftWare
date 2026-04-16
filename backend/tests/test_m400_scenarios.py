"""Scenario-level tests for M400 flight telemetry."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.drone import DroneState
from app.services.telemetry_scenarios import build_m400_mission_scenario
from app.tcp_server.parser import TcpDataParser


SCHEMA_PATH = Path(__file__).resolve().parent / "test_data" / "flight_data_schema_v2.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _serialize_steps(steps) -> bytes:
    return b"".join(json.dumps(step.payload, ensure_ascii=False).encode("utf-8") + b"\n" for step in steps)


def _feed_in_chunks(parser: TcpDataParser, payload: bytes, chunk_sizes: list[int]) -> list[DroneState]:
    results: list[DroneState] = []
    cursor = 0
    chunk_index = 0

    while cursor < len(payload):
        size = chunk_sizes[chunk_index % len(chunk_sizes)]
        part = payload[cursor : cursor + size]
        results.extend(parser.feed(part))
        cursor += size
        chunk_index += 1

    return results


class TestM400MissionScenario:
    def test_generated_m400_scenario_matches_schema_enums(self):
        schema = _load_schema()
        enum_sets = schema["enum_sets"]
        steps = build_m400_mission_scenario()

        assert len(steps) >= 10

        timestamps = []
        for step in steps:
            payload = step.payload
            timestamps.append(datetime.strptime(payload["timestamp"], "%Y-%m-%d %H:%M:%S.%f"))

            assert payload["type"] == "flight_data"
            assert payload["schema_version"] == 2
            assert payload["product_type"] == "DJI_MATRICE_400"
            assert payload["product_type"] in enum_sets["ProductType"]
            assert payload["flight_mode"] in enum_sets["FlightMode"]
            assert payload["fc_flight_mode"] in enum_sets["FCFlightMode"]
            assert payload["gps_signal_level"] in enum_sets["GPSSignalLevel"]
            assert payload["battery_threshold_behavior"] in enum_sets["BatteryThresholdBehavior"]
            assert payload["failsafe_action"] in enum_sets["FailsafeAction"]
            assert payload["auto_rth_reason"] in enum_sets["FCAutoRTHReason"]

        assert timestamps == sorted(timestamps)

    def test_parser_handles_full_m400_mission_sequence(self):
        parser = TcpDataParser()
        steps = build_m400_mission_scenario()
        results = parser.feed(_serialize_steps(steps))

        assert len(results) == len(steps)
        assert all(isinstance(item, DroneState) for item in results)

        names_to_states = {step.name: state for step, state in zip(steps, results)}

        assert results[0].drone_id == "1581F8DBW256G00A2PXY"
        assert results[0].is_flying is False
        assert results[0].position.altitude == pytest.approx(0.0)

        assert names_to_states["auto_takeoff"].is_flying is True
        assert names_to_states["climb_departure"].position.altitude > names_to_states["auto_takeoff"].position.altitude
        assert (
            names_to_states["acceleration_outbound"].velocity.horizontal
            > names_to_states["climb_departure"].velocity.horizontal
        )
        assert names_to_states["cruise_outbound"].home_distance > names_to_states["climb_departure"].home_distance

        assert names_to_states["low_battery_warning"].battery.percent == 24
        assert names_to_states["low_battery_warning"].flight_mode == "LOW_BATTERY_PREPARE_RTH"
        assert names_to_states["go_home_active"].flight_mode == "GO_HOME"
        assert names_to_states["go_home_active"].home_distance < names_to_states["low_battery_warning"].home_distance
        assert names_to_states["auto_landing"].flight_mode == "AUTO_LANDING"
        assert names_to_states["landed_shutdown"].is_flying is False
        assert names_to_states["landed_shutdown"].position.altitude == pytest.approx(0.0)
        assert names_to_states["landed_shutdown"].home_distance == pytest.approx(0.0, abs=1.5)

    def test_parser_handles_chunked_m400_stream(self):
        parser = TcpDataParser()
        steps = build_m400_mission_scenario()
        payload = _serialize_steps(steps)
        results = _feed_in_chunks(parser, payload, [7, 13, 29, 5, 41])

        assert len(results) == len(steps)
        assert results[-1].battery.percent == 12
        assert results[-1].is_flying is False
        assert max(item.velocity.horizontal for item in results) >= 14.0

    def test_low_battery_phase_preserves_rth_metadata_in_raw_payload(self):
        parser = TcpDataParser()
        steps = build_m400_mission_scenario()
        results = parser.feed(_serialize_steps(steps))
        names_to_states = {step.name: state for step, state in zip(steps, results)}
        low_battery_state = names_to_states["low_battery_warning"]
        go_home_state = names_to_states["go_home_active"]

        assert low_battery_state.raw_payload["battery_threshold_behavior"] == "GO_HOME"
        assert low_battery_state.raw_payload["auto_rth_reason"] == "WARNING_POWER_GOHOME"
        assert low_battery_state.raw_payload["low_battery_warning_threshold"] == 25
        assert low_battery_state.raw_payload["serious_low_battery_warning_threshold"] == 15
        assert go_home_state.raw_payload["flight_mode"] == "GO_HOME"
        assert go_home_state.raw_payload["failsafe_action"] == "GOHOME"


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
