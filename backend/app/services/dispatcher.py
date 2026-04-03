"""
数据分发服务
将解析后的 DroneState 同时分发到:
  1. MQTT Broker (云端上传)
  2. WebSocket (前端实时推送)
  3. SQLite (本地持久化)
"""

from __future__ import annotations

import asyncio

from app.models.drone import DroneState
from app.mqtt.client import MqttClient
from app.mqtt import topics
from app.websocket.manager import WebSocketManager
from app.services.storage import StorageService
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 电池低电量告警阈值
BATTERY_LOW_THRESHOLD = 20
# GPS 信号弱告警阈值
GPS_WEAK_THRESHOLD = 2


class DataDispatcher:
    """
    数据分发器

    核心中枢：接收 TCP Server 解析后的 DroneState，
    并行分发到 MQTT / WebSocket / 数据库。
    同时检测告警条件。
    """

    def __init__(
        self,
        mqtt_client: MqttClient,
        ws_manager: WebSocketManager,
        storage: StorageService,
    ):
        self.mqtt = mqtt_client
        self.ws = ws_manager
        self.storage = storage
        self._last_alert_time: float = 0

    async def dispatch(self, state: DroneState) -> None:
        """
        分发无人机状态数据

        并行执行三个任务：
        1. 发布到 MQTT
        2. 广播到 WebSocket
        3. 存储到数据库

        Args:
            state: 解析后的无人机状态
        """
        logger.info(
            "分发遥测数据",
            drone_id=state.drone_id,
            lat=state.position.latitude,
            lng=state.position.longitude,
            alt=state.position.altitude,
            battery=state.battery.percent,
            ws_clients=self.ws.connection_count,
        )

        # 并行分发
        results = await asyncio.gather(
            self._publish_mqtt(state),
            self._broadcast_ws(state),
            self._save_db(state),
            return_exceptions=True,
        )

        # 记录失败
        task_names = ["MQTT", "WebSocket", "Database"]
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.error(f"{name} 分发失败", error=str(result))

        # 检查告警
        await self._check_alerts(state)

    async def _publish_mqtt(self, state: DroneState) -> None:
        """发布到 MQTT"""
        await self.mqtt.publish_telemetry(state)

    async def _broadcast_ws(self, state: DroneState) -> None:
        """广播到 WebSocket"""
        await self.ws.broadcast(state)

    async def _save_db(self, state: DroneState) -> None:
        """存储到数据库"""
        await self.storage.save_telemetry(state)

    async def _check_alerts(self, state: DroneState) -> None:
        """检查告警条件"""
        import time
        now = time.time()

        # 限制告警频率 (最频繁每 10 秒一次)
        if now - self._last_alert_time < 10:
            return

        alerts = []

        # 电池低电量告警
        if state.battery.percent <= BATTERY_LOW_THRESHOLD and state.battery.percent > 0:
            alert = {
                "type": "BATTERY_LOW",
                "level": "WARNING" if state.battery.percent > 10 else "CRITICAL",
                "message": f"电池电量过低: {state.battery.percent}%",
                "drone_id": state.drone_id,
                "timestamp": now,
                "value": state.battery.percent,
            }
            alerts.append(alert)
            await self.mqtt.publish_alert(topics.BATTERY_ALERT, alert)

        # GPS 信号弱告警
        if state.gps_signal <= GPS_WEAK_THRESHOLD and state.is_flying:
            alert = {
                "type": "GPS_WEAK",
                "level": "WARNING",
                "message": f"GPS 信号弱: {state.gps_signal}",
                "drone_id": state.drone_id,
                "timestamp": now,
                "value": state.gps_signal,
            }
            alerts.append(alert)
            await self.mqtt.publish_alert(topics.GPS_LOST_ALERT, alert)

        # 通过 WebSocket 推送告警给前端
        if alerts:
            self._last_alert_time = now
            for alert in alerts:
                await self.ws.broadcast_json({"type": "alert", "data": alert})
                logger.warning("告警触发", alert_type=alert["type"], message=alert["message"])
