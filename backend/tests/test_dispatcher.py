"""Dispatcher tests for telemetry and PSDK fan-out."""

import asyncio
import sys
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.drone import PsdkDataMessage
from app.services.dispatcher import DataDispatcher


class _StubMqttService:
    def __init__(self) -> None:
        self.psdk_messages: list[PsdkDataMessage] = []

    async def publish_psdk_data(self, message: PsdkDataMessage) -> None:
        self.psdk_messages.append(message)


class _StubWebSocketManager:
    def __init__(self) -> None:
        self.connection_count = 0
        self.broadcast_payloads: list[dict] = []

    async def broadcast_json(self, payload: dict) -> None:
        self.broadcast_payloads.append(payload)


class _StubStorageService:
    def __init__(self) -> None:
        self.saved_psdk_messages: list[PsdkDataMessage] = []

    async def save_psdk_data(self, message: PsdkDataMessage) -> None:
        self.saved_psdk_messages.append(message)


def _make_psdk_message(device_type: str = "weather") -> PsdkDataMessage:
    return PsdkDataMessage(
        timestamp=1713252600.0,
        payload_index="PORT_3",
        data="test-frame",
        device_type=device_type,
        parsed_data={"source": device_type},
        raw_payload={"type": "psdk_data", "device_type": device_type},
    )


def test_dispatcher_forwards_psdk_messages_to_mqtt_websocket_and_storage():
    async def scenario() -> None:
        mqtt_service = _StubMqttService()
        ws_manager = _StubWebSocketManager()
        storage_service = _StubStorageService()
        dispatcher = DataDispatcher(mqtt_service, ws_manager, storage_service)

        message = _make_psdk_message("visibility")

        await dispatcher.dispatch(message)

        assert len(mqtt_service.psdk_messages) == 1
        assert mqtt_service.psdk_messages[0].device_type == "visibility"
        assert len(ws_manager.broadcast_payloads) == 1
        assert ws_manager.broadcast_payloads[0]["device_type"] == "visibility"
        assert len(storage_service.saved_psdk_messages) == 1
        assert storage_service.saved_psdk_messages[0].payload_index == "PORT_3"

    asyncio.run(scenario())


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
