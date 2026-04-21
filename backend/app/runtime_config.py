"""Runtime configuration models and service."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.mqtt.client import MqttClient
    from app.tcp_server.server import DroneTcpServer

logger = get_logger(__name__)


def _clean_text(value: Any, fallback: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or fallback


def _clean_topic(value: Any, fallback: str) -> str:
    normalized = _clean_text(value, fallback).strip("/")
    return normalized or fallback


def _read_timestamp(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class RuntimeConnectionConfig(BaseModel):
    api_host: str = Field(default=settings.api_host)
    api_port: int = Field(default=settings.api_port, ge=1, le=65535)
    device_listen_port: int = Field(default=settings.tcp_server_port, ge=1, le=65535)

    @field_validator("api_host", mode="before")
    @classmethod
    def _normalize_api_host(cls, value: Any) -> str:
        return _clean_text(value, settings.api_host)


class RuntimeMqttTargetConfig(BaseModel):
    enabled: bool = False
    host: str = ""
    port: int = Field(default=1883, ge=1, le=65535)
    client_id: str = "drone-monitor"
    username: str = ""
    password: str = ""
    topic: str = "drone/telemetry"
    tls: bool = False

    @field_validator("host", "client_id", "username", "password", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, value: Any) -> str:
        return _clean_topic(value, "drone/telemetry")


class RuntimeConfigState(BaseModel):
    connection: RuntimeConnectionConfig = Field(default_factory=RuntimeConnectionConfig)
    mqtt_local: RuntimeMqttTargetConfig
    mqtt_cloud: RuntimeMqttTargetConfig
    updated_at: Optional[float] = None


def create_default_runtime_config() -> RuntimeConfigState:
    local_client_id = _clean_text(settings.mqtt_client_id, "drone-monitor-local")
    topic_prefix = _clean_topic(settings.mqtt_topic_prefix, "drone/telemetry")

    return RuntimeConfigState(
        connection=RuntimeConnectionConfig(),
        mqtt_local=RuntimeMqttTargetConfig(
            enabled=True,
            host=_clean_text(settings.mqtt_broker_host, "127.0.0.1"),
            port=settings.mqtt_broker_port,
            client_id=local_client_id,
            username=_clean_text(settings.mqtt_username),
            password=_clean_text(settings.mqtt_password),
            topic=topic_prefix,
            tls=False,
        ),
        mqtt_cloud=RuntimeMqttTargetConfig(
            enabled=False,
            host="",
            port=8883,
            client_id=f"{local_client_id}-cloud",
            username="",
            password="",
            topic=f"{topic_prefix}/cloud",
            tls=True,
        ),
        updated_at=None,
    )


class RuntimeConfigService:
    """Load, persist, and apply backend runtime configuration."""

    def __init__(
        self,
        *,
        tcp_server: "DroneTcpServer",
        mqtt_client: "MqttClient",
        config_path: Union[str, Path] = settings.runtime_config_path,
    ) -> None:
        self.tcp_server = tcp_server
        self.mqtt_client = mqtt_client
        self.config_path = Path(config_path)
        self._lock = asyncio.Lock()
        self._config = create_default_runtime_config()

    async def initialize(self) -> RuntimeConfigState:
        async with self._lock:
            self._config = self._load()
            self.tcp_server.port = self._config.connection.device_listen_port
            self.mqtt_client.configure(self._config.mqtt_local, self._config.mqtt_cloud)
            self._persist(self._config)
            logger.info(
                "Runtime configuration initialized",
                tcp_port=self._config.connection.device_listen_port,
                runtime_config_path=str(self.config_path),
            )
            return self.get_config()

    def get_config(self) -> RuntimeConfigState:
        return self._config.model_copy(deep=True)

    async def update(self, payload: Union[RuntimeConfigState, dict[str, Any]]) -> RuntimeConfigState:
        next_config = (
            payload.model_copy(deep=True)
            if isinstance(payload, RuntimeConfigState)
            else self._coerce_payload(payload)
        )
        next_config.updated_at = time.time()

        async with self._lock:
            current_config = self._config

            if next_config.connection.device_listen_port != current_config.connection.device_listen_port:
                if self.tcp_server.is_running:
                    await self.tcp_server.restart(port=next_config.connection.device_listen_port)
                else:
                    self.tcp_server.port = next_config.connection.device_listen_port

            self.mqtt_client.configure(next_config.mqtt_local, next_config.mqtt_cloud)
            self._persist(next_config)
            self._config = next_config

            logger.info(
                "Runtime configuration updated",
                tcp_port=next_config.connection.device_listen_port,
                local_broker=next_config.mqtt_local.host,
                cloud_broker=next_config.mqtt_cloud.host,
            )
            return self.get_config()

    def _load(self) -> RuntimeConfigState:
        if not self.config_path.exists():
            return create_default_runtime_config()

        try:
            raw = self.config_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            return self._coerce_payload(payload)
        except Exception as exc:
            logger.warning("Failed to load runtime configuration, using defaults", error=str(exc))
            return create_default_runtime_config()

    def _persist(self, config: RuntimeConfigState) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _coerce_payload(self, payload: Any) -> RuntimeConfigState:
        defaults = create_default_runtime_config()
        data = payload if isinstance(payload, dict) else {}

        return RuntimeConfigState(
            connection=RuntimeConnectionConfig.model_validate(
                data.get("connection") or defaults.connection.model_dump()
            ),
            mqtt_local=RuntimeMqttTargetConfig.model_validate(
                data.get("mqtt_local") or data.get("mqttLocal") or defaults.mqtt_local.model_dump()
            ),
            mqtt_cloud=RuntimeMqttTargetConfig.model_validate(
                data.get("mqtt_cloud") or data.get("mqttCloud") or defaults.mqtt_cloud.model_dump()
            ),
            updated_at=_read_timestamp(data.get("updated_at") or data.get("updatedAt") or defaults.updated_at),
        )
