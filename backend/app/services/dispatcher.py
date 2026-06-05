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
DEFAULT_STORAGE_QUEUE_SIZE = 1000


class DataDispatcher:
    def __init__(
        self,
        mqtt_client: MqttClient,
        ws_manager: WebSocketManager,
        storage: StorageService,
        *,
        storage_queue_size: int = DEFAULT_STORAGE_QUEUE_SIZE,
    ) -> None:
        self.mqtt = mqtt_client
        self.ws = ws_manager
        self.storage = storage
        self._last_alert_time = 0.0
        self._storage_queue: asyncio.Queue[StreamMessage] = asyncio.Queue(
            maxsize=max(1, int(storage_queue_size))
        )
        self._storage_worker_task: asyncio.Task[None] | None = None

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

        self._enqueue_storage(state, label="Database")

        results = await asyncio.gather(
            self._publish_mqtt(state),
            self._broadcast_ws(state),
            return_exceptions=True,
        )

        for name, result in zip(("MQTT", "WebSocket"), results):
            if isinstance(result, Exception):
                logger.error(f"{name} dispatch failed", error=str(result))

        await self._check_alerts(state)

    async def _publish_mqtt(self, state: DroneState) -> None:
        await self.mqtt.publish_telemetry(state)

    async def _broadcast_ws(self, state: DroneState) -> None:
        await self.ws.broadcast(state)

    async def _save_db(self, state: DroneState) -> None:
        await self.storage.save_telemetry(state)

    def _enqueue_storage(self, message: StreamMessage, *, label: str) -> None:
        self._ensure_storage_worker()
        try:
            self._storage_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.error(
                f"{label} dispatch dropped because storage queue is full",
                queue_size=self._storage_queue.qsize(),
            )

    def _ensure_storage_worker(self) -> None:
        if self._storage_worker_task is None or self._storage_worker_task.done():
            self._storage_worker_task = asyncio.create_task(
                self._storage_worker(),
                name="drone-storage-dispatcher",
            )

    async def _storage_worker(self) -> None:
        while True:
            message = await self._storage_queue.get()
            try:
                if isinstance(message, PsdkDataMessage):
                    await self.storage.save_psdk_data(message)
                else:
                    await self._save_db(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "Storage background dispatch failed",
                    message_type=type(message).__name__,
                    error=str(exc),
                )
            finally:
                self._storage_queue.task_done()

    async def drain_storage(self) -> None:
        """Wait until all queued storage work has been processed."""
        await self._storage_queue.join()

    async def close(self) -> None:
        """Flush queued storage work and stop the background storage worker."""
        await self.drain_storage()
        if self._storage_worker_task is None:
            return

        self._storage_worker_task.cancel()
        try:
            await self._storage_worker_task
        except asyncio.CancelledError:
            pass
        self._storage_worker_task = None

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

        self._enqueue_storage(message, label="RawHistory")

        results = await asyncio.gather(
            self.mqtt.publish_psdk_data(message),
            self.ws.broadcast_json(message.model_dump(mode="json")),
            return_exceptions=True,
        )

        for name, result in zip(("MQTT", "WebSocket"), results):
            if isinstance(result, Exception):
                logger.error(f"{name} PSDK dispatch failed", error=str(result))
