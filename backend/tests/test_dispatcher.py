"""Dispatcher tests for telemetry and PSDK fan-out."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

from app.models.drone import BatteryInfo, DroneState, GpsPosition, PsdkDataMessage, Velocity
from app.services.dispatcher import DataDispatcher


class _StubMqttService:
    def __init__(self) -> None:
        self.telemetry_states: list[DroneState] = []
        self.psdk_messages: list[PsdkDataMessage] = []
        self.alerts: list[tuple[str, dict]] = []

    async def publish_telemetry(self, state: DroneState) -> None:
        self.telemetry_states.append(state)

    async def publish_psdk_data(self, message: PsdkDataMessage) -> None:
        self.psdk_messages.append(message)

    async def publish_alert(self, category: str, message: dict) -> None:
        self.alerts.append((category, message))


class _StubWebSocketManager:
    def __init__(self) -> None:
        self.connection_count = 0
        self.broadcast_states: list[DroneState] = []
        self.broadcast_payloads: list[dict] = []

    async def broadcast(self, state: DroneState) -> None:
        self.broadcast_states.append(state)

    async def broadcast_json(self, payload: dict) -> None:
        self.broadcast_payloads.append(payload)


class _StubStorageService:
    def __init__(self) -> None:
        self.saved_states: list[DroneState] = []
        self.saved_psdk_messages: list[PsdkDataMessage] = []

    async def save_telemetry(self, state: DroneState) -> None:
        self.saved_states.append(state)

    async def save_psdk_data(self, message: PsdkDataMessage) -> None:
        self.saved_psdk_messages.append(message)


class _SlowStorageService(_StubStorageService):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def save_telemetry(self, state: DroneState) -> None:
        self.started.set()
        await self.release.wait()
        await super().save_telemetry(state)


class _FailingStorageService(_StubStorageService):
    async def save_telemetry(self, state: DroneState) -> None:
        raise RuntimeError("disk unavailable")


class _FailingPsdkStorageService(_StubStorageService):
    async def save_psdk_data(self, message: PsdkDataMessage) -> None:
        raise RuntimeError("raw history unavailable")


def _make_state(drone_id: str = "M400-001") -> DroneState:
    return DroneState(
        drone_id=drone_id,
        timestamp=1713252600.0,
        position=GpsPosition(latitude=31.2304, longitude=121.4737, altitude=128.5),
        heading=92.5,
        velocity=Velocity(horizontal=8.5, vertical=1.2),
        battery=BatteryInfo(percent=74, voltage=52.1, temperature=31.4),
        gps_signal=4,
        flight_mode="P-GPS",
        is_flying=True,
        home_distance=180.0,
        gimbal_pitch=-10.0,
        rc_signal=88,
        raw_payload={"source": "test"},
    )


def _make_psdk_message(device_type: str = "weather") -> PsdkDataMessage:
    return PsdkDataMessage(
        timestamp=1713252600.0,
        payload_index="PORT_3",
        data="test-frame",
        device_type=device_type,
        parsed_data={"source": device_type},
        raw_payload={"type": "psdk_data", "device_type": device_type},
    )


def test_dispatcher_forwards_telemetry_to_mqtt_and_websocket_before_slow_storage_finishes():
    async def scenario() -> None:
        mqtt_service = _StubMqttService()
        ws_manager = _StubWebSocketManager()
        storage_service = _SlowStorageService()
        dispatcher = DataDispatcher(mqtt_service, ws_manager, storage_service)

        message = _make_state("1581F8DBW257200A2R21")

        await asyncio.wait_for(dispatcher.dispatch(message), timeout=0.2)
        await asyncio.wait_for(storage_service.started.wait(), timeout=0.2)

        assert len(mqtt_service.telemetry_states) == 1
        assert mqtt_service.telemetry_states[0].drone_id == "1581F8DBW257200A2R21"
        assert len(ws_manager.broadcast_states) == 1
        assert storage_service.saved_states == []

        storage_service.release.set()
        await dispatcher.close()
        assert len(storage_service.saved_states) == 1

    asyncio.run(scenario())


def test_dispatcher_storage_failure_does_not_block_telemetry_upload():
    async def scenario() -> None:
        mqtt_service = _StubMqttService()
        ws_manager = _StubWebSocketManager()
        storage_service = _FailingStorageService()
        dispatcher = DataDispatcher(mqtt_service, ws_manager, storage_service)

        message = _make_state()

        await dispatcher.dispatch(message)
        await dispatcher.drain_storage()
        await dispatcher.close()

        assert len(mqtt_service.telemetry_states) == 1
        assert len(ws_manager.broadcast_states) == 1

    asyncio.run(scenario())


def test_dispatcher_forwards_psdk_messages_to_mqtt_websocket_and_storage():
    async def scenario() -> None:
        mqtt_service = _StubMqttService()
        ws_manager = _StubWebSocketManager()
        storage_service = _StubStorageService()
        dispatcher = DataDispatcher(mqtt_service, ws_manager, storage_service)

        message = _make_psdk_message("visibility")

        await dispatcher.dispatch(message)
        await dispatcher.close()

        assert len(mqtt_service.psdk_messages) == 1
        assert mqtt_service.psdk_messages[0].device_type == "visibility"
        assert len(ws_manager.broadcast_payloads) == 1
        assert ws_manager.broadcast_payloads[0]["device_type"] == "visibility"
        assert len(storage_service.saved_psdk_messages) == 1
        assert storage_service.saved_psdk_messages[0].payload_index == "PORT_3"

    asyncio.run(scenario())


def test_dispatcher_psdk_storage_failure_does_not_block_mqtt_or_websocket():
    async def scenario() -> None:
        mqtt_service = _StubMqttService()
        ws_manager = _StubWebSocketManager()
        storage_service = _FailingPsdkStorageService()
        dispatcher = DataDispatcher(mqtt_service, ws_manager, storage_service)

        message = _make_psdk_message("weather")

        await dispatcher.dispatch(message)
        await dispatcher.drain_storage()
        await dispatcher.close()

        assert len(mqtt_service.psdk_messages) == 1
        assert len(ws_manager.broadcast_payloads) == 1

    asyncio.run(scenario())


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
