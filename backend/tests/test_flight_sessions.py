"""Tests for local flight-session storage and management."""

import asyncio
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

from app.models.drone import BatteryInfo, DroneState, GpsPosition, PsdkDataMessage, Velocity
from app.services.storage import StorageService


def _make_state(
    timestamp: float,
    latitude: float,
    longitude: float,
    altitude: float,
    is_flying: bool,
    battery_percent: int = 80,
) -> DroneState:
    return DroneState(
        drone_id="M400-001",
        timestamp=timestamp,
        position=GpsPosition(latitude=latitude, longitude=longitude, altitude=altitude),
        heading=92.5,
        velocity=Velocity(horizontal=8.5, vertical=1.2 if is_flying else -0.8),
        battery=BatteryInfo(percent=battery_percent, voltage=52.2, temperature=31.5),
        gps_signal=4,
        flight_mode="P-GPS",
        is_flying=is_flying,
        home_distance=128.0,
        gimbal_pitch=-12.0,
        rc_signal=88,
        raw_payload={
            "timestamp": timestamp,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "attitude": {
                "pitch": 1.5,
                "roll": -2.2,
                "yaw": 92.5,
            },
            "battery_status": {
                "main_battery": {
                    "percentage": battery_percent,
                }
            },
        },
    )


def test_flight_session_storage_lifecycle():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            await storage.init_db()

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                await storage.save_psdk_data(
                    PsdkDataMessage(
                        timestamp=1713252600.5,
                        payload_index="PORT_3",
                        data=":01,16,0.00,24.0,63.7,1003.9,44,,,,,0,0.00,0,0.000000,0.000000,,,,,,,0.0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,1F\r\n",
                        device_type="weather",
                        parsed_data={"temperature_c": 24.0},
                        raw_payload={"type": "psdk_data", "payload_index": "PORT_3"},
                    )
                )
                await storage.save_psdk_data(
                    PsdkDataMessage(
                        timestamp=1713252601.0,
                        payload_index="PORT_3",
                        data="VTF-01820-01872-01872-///-0001-000.0-11.5-1.25-04\r\n",
                        device_type="visibility",
                        parsed_data={"visibility_10s_m": 1820},
                        raw_payload={"type": "psdk_data", "payload_index": "PORT_3"},
                    )
                )
                await storage.save_telemetry(_make_state(1713252601.0, 31.23090, 121.47430, 32.0, True, 72))
                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))

                sessions = await storage.get_flight_sessions()
                assert len(sessions) == 1

                summary = sessions[0]
                assert summary["flight_id"]
                assert summary["file_name"].endswith(".json")
                assert summary["takeoff_time"] == pytest.approx(1713252600.0)
                assert summary["landing_time"] == pytest.approx(1713252602.0)
                assert summary["max_altitude_m"] == pytest.approx(32.0)
                assert summary["total_distance_m"] > 0
                assert {device["device_type"] for device in summary["attached_weather_devices"]} == {
                    "visibility",
                    "weather",
                }

                detail = await storage.get_flight_session(summary["flight_id"])
                assert detail is not None
                assert detail["summary"]["point_count"] == 3
                assert len(detail["telemetry_records"]) == 3
                assert len(detail["psdk_records"]) == 2
                assert detail["telemetry_records"][0]["raw_payload"]["attitude"]["pitch"] == pytest.approx(1.5)
                assert detail["psdk_records"][0]["device_type"] == "weather"

                db_history = await storage.get_flight_history(drone_id="M400-001", limit=10)
                assert len(db_history) == 3

                raw_history = await storage.get_raw_history(limit=20)
                assert len(raw_history) == 5

                deleted = await storage.delete_flight_session(summary["flight_id"])
                assert deleted is True
                assert await storage.get_flight_session(summary["flight_id"]) is None
                assert await storage.get_flight_sessions() == []
                assert await storage.get_flight_history(drone_id="M400-001", limit=10) == []
                assert await storage.get_raw_history(limit=20) == []
            finally:
                await storage.close()

    asyncio.run(scenario())


def test_get_flight_history_can_limit_to_latest_session():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            await storage.init_db()

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                await storage.save_telemetry(_make_state(1713252601.0, 31.23090, 121.47430, 32.0, True, 72))
                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))

                await storage.save_telemetry(_make_state(1713252620.0, 31.24040, 121.48370, 10.0, True, 77))
                await storage.save_telemetry(_make_state(1713252621.0, 31.24090, 121.48430, 24.0, True, 71))
                await storage.save_telemetry(_make_state(1713252622.0, 31.24110, 121.48460, 3.0, False, 68))

                all_records = await storage.get_flight_history(drone_id="M400-001", limit=10)
                latest_records = await storage.get_flight_history(
                    drone_id="M400-001",
                    limit=10,
                    latest_session_only=True,
                )

                assert len(all_records) == 6
                assert len(latest_records) == 3
                assert sorted(record["timestamp"] for record in latest_records) == [
                    pytest.approx(1713252620.0),
                    pytest.approx(1713252621.0),
                    pytest.approx(1713252622.0),
                ]
            finally:
                await storage.close()

    asyncio.run(scenario())


def test_weather_devices_do_not_leak_between_flights():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            await storage.init_db()

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                await storage.save_psdk_data(
                    PsdkDataMessage(
                        timestamp=1713252600.5,
                        payload_index="PORT_3",
                        data="weather-frame",
                        device_type="weather",
                        parsed_data={"temperature_c": 24.0},
                        raw_payload={"type": "psdk_data", "payload_index": "PORT_3"},
                    )
                )
                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))

                await storage.save_telemetry(_make_state(1713252620.0, 31.24040, 121.48370, 10.0, True, 77))
                await storage.save_telemetry(_make_state(1713252622.0, 31.24110, 121.48460, 3.0, False, 68))

                sessions = await storage.get_flight_sessions(limit=10)
                assert len(sessions) == 2

                sessions_by_takeoff = {
                    round(float(session["takeoff_time"])): session
                    for session in sessions
                }
                first_session = sessions_by_takeoff[1713252600]
                second_session = sessions_by_takeoff[1713252620]

                assert first_session["attached_weather_devices"] == [
                    {"payload_index": "PORT_3", "device_type": "weather"}
                ]
                assert second_session["attached_weather_devices"] == []
            finally:
                await storage.close()

    asyncio.run(scenario())


def test_active_flight_session_persist_is_throttled_but_readable():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            storage._active_session_flush_interval_seconds = 60.0
            storage._active_session_max_pending_changes = 100
            await storage.init_db()

            write_count = 0
            original_write_json_file = storage._write_json_file

            def tracked_write_json_file(path: Path, payload: dict[str, object]) -> None:
                nonlocal write_count
                write_count += 1
                original_write_json_file(path, payload)

            storage._write_json_file = tracked_write_json_file

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                assert write_count == 2
                flight_id = storage._active_flight_id
                assert flight_id

                await storage.save_psdk_data(
                    PsdkDataMessage(
                        timestamp=1713252600.5,
                        payload_index="PORT_3",
                        data="weather-frame",
                        device_type="weather",
                        parsed_data={"temperature_c": 24.0},
                        raw_payload={"type": "psdk_data", "payload_index": "PORT_3"},
                    )
                )
                await storage.save_telemetry(_make_state(1713252601.0, 31.23090, 121.47430, 32.0, True, 72))
                assert write_count == 2

                sessions = await storage.get_flight_sessions(limit=10)
                assert write_count == 3
                assert len(sessions) == 1
                assert sessions[0]["flight_id"] == flight_id
                assert sessions[0]["attached_weather_devices"] == [
                    {"payload_index": "PORT_3", "device_type": "weather"}
                ]

                detail = await storage.get_flight_session(flight_id)
                assert detail is not None
                assert write_count == 3
                assert len(detail["telemetry_records"]) == 2
                assert len(detail["psdk_records"]) == 1
                assert detail["summary"]["point_count"] == 2

                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))
                assert write_count == 4

                final_detail = await storage.get_flight_session(flight_id)
                assert final_detail is not None
                assert write_count == 4
                assert final_detail["status"] == "completed"
                assert final_detail["landing_time"] == pytest.approx(1713252602.0)
                assert len(final_detail["telemetry_records"]) == 3
            finally:
                await storage.close()

    asyncio.run(scenario())


def test_get_flight_sessions_reuses_cached_summaries_for_unchanged_files():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            await storage.init_db()

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                await storage.save_telemetry(_make_state(1713252601.0, 31.23090, 121.47430, 32.0, True, 72))
                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))

                await storage.save_telemetry(_make_state(1713252620.0, 31.24040, 121.48370, 10.0, True, 77))
                await storage.save_telemetry(_make_state(1713252621.0, 31.24090, 121.48430, 24.0, True, 71))
                await storage.save_telemetry(_make_state(1713252622.0, 31.24110, 121.48460, 3.0, False, 68))

                expected_sessions = await storage.get_flight_sessions(limit=10)
                assert len(expected_sessions) == 2

                read_count = 0
                original_read_json_file = storage._read_json_file

                def tracked_read_json_file(path: Path) -> dict[str, object]:
                    nonlocal read_count
                    read_count += 1
                    return original_read_json_file(path)

                storage._read_json_file = tracked_read_json_file

                cached_sessions = await storage.get_flight_sessions(limit=10)
                repeated_sessions = await storage.get_flight_sessions(limit=10)

                assert cached_sessions == expected_sessions
                assert repeated_sessions == expected_sessions
                assert read_count == 0
            finally:
                await storage.close()

    asyncio.run(scenario())


def test_get_flight_sessions_refreshes_cache_when_file_changes():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db_path = base / "flight_sessions.db"
            raw_history_path = base / "telemetry_raw.jsonl"
            flight_sessions_path = base / "flights"

            storage = StorageService(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                raw_history_path=str(raw_history_path),
                flight_sessions_path=str(flight_sessions_path),
            )
            await storage.init_db()

            try:
                await storage.save_telemetry(_make_state(1713252600.0, 31.23040, 121.47370, 12.0, True, 78))
                await storage.save_telemetry(_make_state(1713252601.0, 31.23090, 121.47430, 32.0, True, 72))
                await storage.save_telemetry(_make_state(1713252602.0, 31.23110, 121.47460, 4.0, False, 69))

                sessions = await storage.get_flight_sessions(limit=10)
                assert len(sessions) == 1

                flight_id = sessions[0]["flight_id"]
                path = storage._resolve_flight_session_path(flight_id)
                session_data = storage._read_json_file(path)
                session_data["summary"]["max_altitude_m"] = 256.0
                session_data["attached_weather_devices"] = [
                    {"payload_index": "PORT_9", "device_type": "weather"},
                    {"payload_index": "PORT_10", "device_type": "visibility"},
                ]
                storage._write_json_file(path, session_data)

                read_count = 0
                original_read_json_file = storage._read_json_file

                def tracked_read_json_file(changed_path: Path) -> dict[str, object]:
                    nonlocal read_count
                    read_count += 1
                    return original_read_json_file(changed_path)

                storage._read_json_file = tracked_read_json_file

                refreshed_sessions = await storage.get_flight_sessions(limit=10)

                assert refreshed_sessions[0]["flight_id"] == flight_id
                assert refreshed_sessions[0]["max_altitude_m"] == pytest.approx(256.0)
                assert refreshed_sessions[0]["attached_weather_devices"] == [
                    {"payload_index": "PORT_9", "device_type": "weather"},
                    {"payload_index": "PORT_10", "device_type": "visibility"},
                ]
                assert read_count == 1
            finally:
                await storage.close()

    asyncio.run(scenario())


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
