"""Tests for runtime config persistence and dual MQTT routing."""

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - direct-script fallback
    from tests import _pytest_compat as pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.mqtt.client import MqttClient
from app.models.drone import BatteryInfo, DroneState, GpsPosition, Velocity
from app.runtime_config import (
    RuntimeConfigService,
    RuntimeConfigState,
    RuntimeConnectionConfig,
    RuntimeMqttTargetConfig,
)


class _FakePublishResult:
    def __init__(self, rc: int = 0) -> None:
        self.rc = rc


class _FakePahoClient:
    instances: list["_FakePahoClient"] = []

    def __init__(self, client_id: str = "", callback_api_version=None) -> None:
        self.client_id = client_id
        self.callback_api_version = callback_api_version
        self.on_connect = None
        self.on_disconnect = None
        self.on_publish = None
        self.published: list[dict[str, object]] = []
        self.tls_enabled = False
        self.loop_started = False
        _FakePahoClient.instances.append(self)

    def reconnect_delay_set(self, min_delay: int, max_delay: int) -> None:
        self.reconnect_delay = (min_delay, max_delay)

    def username_pw_set(self, username: str, password: Optional[str] = None) -> None:
        self.username = username
        self.password = password

    def tls_set(self) -> None:
        self.tls_enabled = True

    def will_set(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        self.will_message = {
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
        }

    def connect(self, host: str, port: int, keepalive: int = 60) -> int:
        self.host = host
        self.port = port
        self.keepalive = keepalive
        if self.on_connect:
            self.on_connect(self, None, None, 0, None)
        return 0

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> _FakePublishResult:
        self.published.append(
            {
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
            }
        )
        if self.on_publish:
            self.on_publish(self, None, len(self.published), 0, None)
        return _FakePublishResult(0)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def disconnect(self) -> None:
        if self.on_disconnect:
            self.on_disconnect(self, None, None, 0, None)


class _StubTcpServer:
    def __init__(self) -> None:
        self.host = "0.0.0.0"
        self.port = 9001
        self.is_running = False
        self.restart_calls: list[int] = []

    async def restart(self, *, host: Optional[str] = None, port: Optional[int] = None) -> None:
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
            self.restart_calls.append(port)
        self.is_running = True


class _StubMqttService:
    def __init__(self) -> None:
        self.configure_calls: list[tuple[dict[str, object], dict[str, object]]] = []

    def configure(self, local_config: RuntimeMqttTargetConfig, cloud_config: RuntimeMqttTargetConfig) -> None:
        self.configure_calls.append((local_config.model_dump(), cloud_config.model_dump()))


def _make_state() -> DroneState:
    return DroneState(
        drone_id="M400-001",
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


def test_dual_mqtt_targets_publish_independently():
    async def scenario() -> None:
        _FakePahoClient.instances.clear()
        client = MqttClient(client_factory=_FakePahoClient)
        client.configure(
            RuntimeMqttTargetConfig(
                enabled=True,
                host="127.0.0.1",
                port=1883,
                client_id="local-client",
                topic="drone/local",
            ),
            RuntimeMqttTargetConfig(
                enabled=True,
                host="mqtt.example.com",
                port=8883,
                client_id="cloud-client",
                topic="drone/cloud",
                tls=True,
            ),
        )

        client.connect()
        await client.publish_telemetry(_make_state())
        await client.publish_alert("battery", {"level": "WARNING"})

        instances = {item.client_id: item for item in _FakePahoClient.instances}
        local_topics = [message["topic"] for message in instances["local-client"].published]
        cloud_topics = [message["topic"] for message in instances["cloud-client"].published]

        assert "drone/local/data" in local_topics
        assert "drone/local/alert/battery" in local_topics
        assert "drone/cloud/data" in cloud_topics
        assert "drone/cloud/alert/battery" in cloud_topics
        assert instances["cloud-client"].tls_enabled is True
        assert client.status_snapshot["local"]["connected"] is True
        assert client.status_snapshot["cloud"]["connected"] is True

        client.disconnect()

    asyncio.run(scenario())


def test_runtime_config_service_persists_and_restarts_tcp_listener():
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "runtime_config.json"
            tcp_server = _StubTcpServer()
            mqtt_service = _StubMqttService()
            service = RuntimeConfigService(
                tcp_server=tcp_server,
                mqtt_client=mqtt_service,
                config_path=config_path,
            )

            initial = await service.initialize()
            assert tcp_server.port == initial.connection.device_listen_port
            assert len(mqtt_service.configure_calls) == 1

            tcp_server.is_running = True
            updated = RuntimeConfigState(
                connection=RuntimeConnectionConfig(
                    api_host=initial.connection.api_host,
                    api_port=initial.connection.api_port,
                    device_listen_port=9105,
                ),
                mqtt_local=RuntimeMqttTargetConfig(
                    enabled=True,
                    host="127.0.0.1",
                    port=1883,
                    client_id="local-client",
                    topic="drone/local",
                ),
                mqtt_cloud=RuntimeMqttTargetConfig(
                    enabled=True,
                    host="mqtt.example.com",
                    port=8883,
                    client_id="cloud-client",
                    topic="drone/cloud",
                    tls=True,
                ),
            )

            result = await service.update(updated)

            assert result.connection.device_listen_port == 9105
            assert tcp_server.restart_calls == [9105]
            assert len(mqtt_service.configure_calls) == 2
            assert config_path.exists() is True

            reloaded_tcp_server = _StubTcpServer()
            reloaded_mqtt_service = _StubMqttService()
            reloaded_service = RuntimeConfigService(
                tcp_server=reloaded_tcp_server,
                mqtt_client=reloaded_mqtt_service,
                config_path=config_path,
            )
            reloaded = await reloaded_service.initialize()

            assert reloaded.connection.device_listen_port == 9105
            assert reloaded.mqtt_cloud.enabled is True
            assert reloaded.mqtt_cloud.host == "mqtt.example.com"
            assert reloaded_tcp_server.port == 9105

    asyncio.run(scenario())


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
