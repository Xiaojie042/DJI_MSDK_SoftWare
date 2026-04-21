"""Dispatch telemetry to MQTT, WebSocket, and storage."""

from __future__ import annotations

import asyncio
import time

from app.models.drone import DroneState, PsdkDataMessage, StreamMessage
from app.mqtt.client import MqttClient
from app.services.storage import StorageService
from app.utils.logger import get_logger
from app.websocket.manager import WebSocketManager

logger = get_logger(__name__)

BATTERY_LOW_THRESHOLD = 20
GPS_WEAK_THRESHOLD = 2


class DataDispatcher:
    def __init__(
        self,
        mqtt_client: MqttClient,
        ws_manager: WebSocketManager,
        storage: StorageService,
    ) -> None:
        self.mqtt = mqtt_client
        self.ws = ws_manager
        self.storage = storage
        self._last_alert_time = 0.0

    async def dispatch(self, message: StreamMessage) -> None:
        if isinstance(message, PsdkDataMessage):
            await self._dispatch_psdk_data(message)
            return

        state = message
        logger.info(
            "Dispatching telemetry",
            drone_id=state.drone_id,
            lat=state.position.latitude,
            lng=state.position.longitude,
            alt=state.position.altitude,
            ws_clients=self.ws.connection_count,
        )

        results = await asyncio.gather(
            self._publish_mqtt(state),
            self._broadcast_ws(state),
            self._save_db(state),
            return_exceptions=True,
        )

        for name, result in zip(("MQTT", "WebSocket", "Database"), results):
            if isinstance(result, Exception):
                logger.error(f"{name} dispatch failed", error=str(result))

        await self._check_alerts(state)

    async def _publish_mqtt(self, state: DroneState) -> None:
        await self.mqtt.publish_telemetry(state)

    async def _broadcast_ws(self, state: DroneState) -> None:
        await self.ws.broadcast(state)

    async def _save_db(self, state: DroneState) -> None:
        await self.storage.save_telemetry(state)

    async def _check_alerts(self, state: DroneState) -> None:
        now = time.time()
        if now - self._last_alert_time < 10:
            return

        alerts: list[dict[str, object]] = []

        if 0 < state.battery.percent <= BATTERY_LOW_THRESHOLD:
            alert = {
                "type": "BATTERY_LOW",
                "level": "WARNING" if state.battery.percent > 10 else "CRITICAL",
                "message": f"Battery is low: {state.battery.percent}%",
                "drone_id": state.drone_id,
                "timestamp": now,
                "value": state.battery.percent,
            }
            alerts.append(alert)
            await self.mqtt.publish_alert("battery", alert)

        if state.gps_signal <= GPS_WEAK_THRESHOLD and state.is_flying:
            alert = {
                "type": "GPS_WEAK",
                "level": "WARNING",
                "message": f"GPS signal is weak: {state.gps_signal}",
                "drone_id": state.drone_id,
                "timestamp": now,
                "value": state.gps_signal,
            }
            alerts.append(alert)
            await self.mqtt.publish_alert("gps", alert)

        if alerts:
            self._last_alert_time = now
            for alert in alerts:
                await self.ws.broadcast_json({"type": "alert", "data": alert})
                logger.warning("Alert broadcast", alert_type=alert["type"], message=alert["message"])

    async def _dispatch_psdk_data(self, message: PsdkDataMessage) -> None:
        logger.info(
            "Dispatching PSDK payload",
            payload_index=message.payload_index,
            ws_clients=self.ws.connection_count,
        )

        results = await asyncio.gather(
            self.ws.broadcast_json(message.model_dump(mode="json")),
            self.storage.save_psdk_data(message),
            return_exceptions=True,
        )

        for name, result in zip(("WebSocket", "RawHistory"), results):
            if isinstance(result, Exception):
                logger.error(f"{name} PSDK dispatch failed", error=str(result))
