"""MQTT client service with independent local and cloud targets."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

from app.models.drone import DroneState, PsdkDataMessage
from app.mqtt import topics
from app.runtime_config import RuntimeMqttTargetConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)
WEATHER_AGGREGATE_DEVICE_TYPES = {"weather", "visibility"}


def _reason_code_value(reason_code: Any) -> int:
    if reason_code is None:
        return 0

    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


class _ManagedMqttTarget:
    def __init__(
        self,
        name: str,
        config: RuntimeMqttTargetConfig,
        *,
        client_factory: Callable[..., mqtt.Client],
    ) -> None:
        self.name = name
        self._config = config.model_copy(deep=True)
        self._client_factory = client_factory
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._lock = threading.Lock()
        self._last_error = ""

    @property
    def config(self) -> RuntimeMqttTargetConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def broker(self) -> str:
        if not self._config.host:
            return ""
        return f"{self._config.host}:{self._config.port}"

    def set_config(self, config: RuntimeMqttTargetConfig) -> bool:
        changed = self._config.model_dump() != config.model_dump()
        self._config = config.model_copy(deep=True)
        if not self._config.enabled:
            self._last_error = ""
        return changed

    def connect(self) -> None:
        self.disconnect()

        if not self._config.enabled:
            return

        if not self._config.host:
            self._last_error = f"{self.name} target is enabled but host is empty"
            logger.warning("MQTT target skipped because host is empty", target=self.name)
            return

        client = self._client_factory(
            client_id=self._config.client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_publish = self._on_publish
        client.reconnect_delay_set(min_delay=1, max_delay=30)

        if self._config.username:
            client.username_pw_set(self._config.username, self._config.password)

        if self._config.tls:
            client.tls_set()

        client.will_set(
            topic=topics.heartbeat(self._config.topic),
            payload=self._heartbeat_payload("offline"),
            qos=1,
            retain=True,
        )

        try:
            client.connect(self._config.host, self._config.port, keepalive=60)
            client.loop_start()
            self._client = client
            self._last_error = ""
            logger.info(
                "MQTT target connecting",
                target=self.name,
                broker=self.broker,
                topic=self._config.topic,
            )
        except Exception as exc:
            self._client = None
            self._connected = False
            self._last_error = str(exc)
            logger.warning("MQTT target connection failed", target=self.name, error=str(exc))

    def disconnect(self) -> None:
        client = self._client
        if client is None:
            self._connected = False
            return

        self._client = None
        was_connected = self._connected
        self._connected = False

        try:
            if was_connected:
                client.publish(
                    topic=topics.heartbeat(self._config.topic),
                    payload=self._heartbeat_payload("offline"),
                    qos=1,
                    retain=True,
                )
        except Exception:
            pass

        try:
            client.loop_stop()
        except Exception:
            pass

        try:
            client.disconnect()
        except Exception:
            pass

    def publish_json(self, topic: str, payload: str, *, qos: int = 0, retain: bool = False) -> bool:
        if not self._config.enabled or not self._connected or self._client is None:
            return False

        with self._lock:
            result = self._client.publish(topic=topic, payload=payload, qos=qos, retain=retain)

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self._last_error = f"publish rc={result.rc}"
            logger.warning("MQTT publish failed", target=self.name, rc=result.rc, topic=topic)
            return False

        return True

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "connected": self._connected,
            "broker": self.broker,
            "client_id": self._config.client_id,
            "topic": self._config.topic,
            "tls": self._config.tls,
            "last_error": self._last_error,
        }

    def _heartbeat_payload(self, status: str) -> str:
        return json.dumps(
            {
                "target": self.name,
                "status": status,
                "client_id": self._config.client_id,
            },
            ensure_ascii=False,
        )

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        code = _reason_code_value(reason_code)
        if code == 0:
            self._connected = True
            self._last_error = ""
            client.publish(
                topic=topics.heartbeat(self._config.topic),
                payload=self._heartbeat_payload("online"),
                qos=1,
                retain=True,
            )
            logger.info("MQTT target connected", target=self.name, broker=self.broker)
            return

        self._connected = False
        self._last_error = f"connect rc={code}"
        logger.warning("MQTT target connect rejected", target=self.name, rc=code)

    def _on_disconnect(self, client, userdata, disconnect_flags=None, reason_code=None, properties=None) -> None:
        code = _reason_code_value(reason_code)
        self._connected = False
        if code not in (0, mqtt.MQTT_ERR_SUCCESS):
            self._last_error = f"disconnect rc={code}"
            logger.warning("MQTT target disconnected unexpectedly", target=self.name, rc=code)
        else:
            logger.info("MQTT target disconnected", target=self.name)

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None) -> None:
        logger.debug("MQTT message published", target=self.name, mid=mid)


class MqttClient:
    """Publish telemetry to independent local and cloud MQTT targets."""

    def __init__(self, *, client_factory: Callable[..., mqtt.Client] = mqtt.Client) -> None:
        self._client_factory = client_factory
        self._started = False
        self._psdk_lock = threading.Lock()
        self._latest_weather_payload: Optional[dict[str, Any]] = None
        self._latest_visibility_payload: Optional[dict[str, Any]] = None
        self._targets = {
            "local": _ManagedMqttTarget(
                "local",
                RuntimeMqttTargetConfig(
                    enabled=False,
                    client_id="drone-monitor-local",
                    topic="drone/telemetry",
                ),
                client_factory=self._client_factory,
            ),
            "cloud": _ManagedMqttTarget(
                "cloud",
                RuntimeMqttTargetConfig(
                    enabled=False,
                    client_id="drone-monitor-cloud",
                    topic="drone/telemetry/cloud",
                ),
                client_factory=self._client_factory,
            ),
        }

    def configure(
        self,
        local_config: RuntimeMqttTargetConfig,
        cloud_config: RuntimeMqttTargetConfig,
    ) -> None:
        next_configs = {
            "local": local_config,
            "cloud": cloud_config,
        }

        for name, config in next_configs.items():
            changed = self._targets[name].set_config(config)
            if self._started and changed:
                self._targets[name].connect()

    def connect(self) -> None:
        self._started = True
        for target in self._targets.values():
            target.connect()

    def disconnect(self) -> None:
        self._started = False
        for target in self._targets.values():
            target.disconnect()

    async def publish_telemetry(self, state: DroneState) -> None:
        payload = state.model_dump_json()
        for target in self._targets.values():
            target.publish_json(topics.telemetry(target.config.topic), payload, qos=0)

    async def publish_alert(self, category: str, message: dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False)
        for target in self._targets.values():
            target.publish_json(topics.alert(target.config.topic, category), payload, qos=1)

    async def publish_psdk_data(self, message: PsdkDataMessage) -> None:
        normalized_device_type = self._normalize_device_type(message.device_type)

        if normalized_device_type in WEATHER_AGGREGATE_DEVICE_TYPES:
            payload = self._build_weather_aggregate_payload(message, normalized_device_type)
            topic_builder = topics.psdk_weather
        else:
            payload = message.model_dump_json()
            topic_builder = lambda prefix: topics.psdk(prefix, message.device_type)

        for target in self._targets.values():
            target.publish_json(topic_builder(target.config.topic), payload, qos=0)

    @property
    def is_connected(self) -> bool:
        return any(target.is_connected for target in self._targets.values())

    @property
    def primary_broker(self) -> str:
        for name in ("local", "cloud"):
            broker = self._targets[name].broker
            if broker:
                return broker
        return ""

    @property
    def status_snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            name: target.status_snapshot()
            for name, target in self._targets.items()
        }

    def _build_weather_aggregate_payload(self, message: PsdkDataMessage, normalized_device_type: str) -> str:
        current_payload = message.model_dump(mode="json")

        with self._psdk_lock:
            if normalized_device_type == "weather":
                self._latest_weather_payload = current_payload
            elif normalized_device_type == "visibility":
                self._latest_visibility_payload = current_payload

            weather_payload = deepcopy(self._latest_weather_payload)
            visibility_payload = deepcopy(self._latest_visibility_payload)

        merged_payload = weather_payload or self._create_weather_fallback_payload(current_payload)
        merged_payload["device_type"] = "weather"
        merged_payload["trigger_device_type"] = normalized_device_type
        merged_payload["visibility_payload"] = visibility_payload
        merged_payload["raw_payload"] = self._merge_raw_payload(
            merged_payload.get("raw_payload"),
            visibility_payload,
        )
        return json.dumps(merged_payload, ensure_ascii=False)

    def _create_weather_fallback_payload(self, current_payload: dict[str, Any]) -> dict[str, Any]:
        fallback = deepcopy(current_payload)
        fallback["device_type"] = "weather"
        fallback["data"] = ""
        fallback["parsed_data"] = None
        fallback["warnings"] = []

        raw_payload = dict(fallback.get("raw_payload") or {})
        raw_payload["device_type"] = "weather"
        fallback["raw_payload"] = raw_payload or None
        return fallback

    def _merge_raw_payload(
        self,
        raw_payload: Optional[dict[str, Any]],
        visibility_payload: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        merged = dict(raw_payload or {})
        merged["visibility_payload"] = (
            deepcopy(visibility_payload.get("raw_payload"))
            if visibility_payload and visibility_payload.get("raw_payload") is not None
            else None
        )
        return merged or None

    def _normalize_device_type(self, device_type: Any) -> str:
        return str(device_type or "").strip().lower() or "unknown"
