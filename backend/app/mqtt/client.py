"""
MQTT 客户端封装
基于 paho-mqtt，负责将无人机遥测数据发布到本地 EMQX Broker
"""

from __future__ import annotations

import json
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from app.config import settings
from app.models.drone import DroneState
from app.mqtt import topics
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MqttClient:
    """
    MQTT 客户端

    在独立线程中运行 MQTT 事件循环，主线程通过 publish() 发布消息。
    连接到本地 EMQX Broker。
    """

    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._connected: bool = False
        self._lock = threading.Lock()

    def connect(self) -> None:
        """建立 MQTT 连接"""
        self._client = mqtt.Client(
            client_id=settings.mqtt_client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # 设置回调
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish = self._on_publish

        # 认证 (如果配置了用户名密码)
        if settings.mqtt_username:
            self._client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password,
            )

        # 遗嘱消息 (连接异常断开时发布)
        self._client.will_set(
            topic=topics.HEARTBEAT,
            payload=json.dumps({"status": "offline", "client_id": settings.mqtt_client_id}),
            qos=1,
            retain=True,
        )

        try:
            self._client.connect(
                host=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
                keepalive=60,
            )
            # 启动后台网络循环线程
            self._client.loop_start()
            logger.info(
                "MQTT 客户端连接中",
                broker=f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
            )
        except Exception as e:
            logger.error("MQTT 连接失败", error=str(e))
            raise

    def disconnect(self) -> None:
        """断开 MQTT 连接"""
        if self._client:
            # 发送离线消息
            self._client.publish(
                topic=topics.HEARTBEAT,
                payload=json.dumps({"status": "offline", "client_id": settings.mqtt_client_id}),
                qos=1,
                retain=True,
            )
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("MQTT 客户端已断开")

    async def publish_telemetry(self, state: DroneState) -> None:
        """
        发布遥测数据到 MQTT

        Args:
            state: 无人机状态数据
        """
        if not self._connected:
            logger.warning("MQTT 未连接，跳过发布")
            return

        payload = state.model_dump_json()

        with self._lock:
            result = self._client.publish(
                topic=topics.TELEMETRY,
                payload=payload,
                qos=0,  # 遥测数据使用 QoS 0 (最多一次)
            )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.debug("MQTT 遥测数据已发布", drone_id=state.drone_id)
        else:
            logger.warning("MQTT 发布失败", rc=result.rc)

    async def publish_alert(self, topic: str, message: dict) -> None:
        """发布告警消息"""
        if not self._connected:
            return

        with self._lock:
            self._client.publish(
                topic=topic,
                payload=json.dumps(message),
                qos=1,  # 告警使用 QoS 1 (至少一次)
            )

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ─── 回调 ──────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            # 发送上线消息
            client.publish(
                topic=topics.HEARTBEAT,
                payload=json.dumps({"status": "online", "client_id": settings.mqtt_client_id}),
                qos=1,
                retain=True,
            )
            logger.info("MQTT 已连接到 Broker")
        else:
            self._connected = False
            logger.error("MQTT 连接失败", rc=rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning("MQTT 意外断开，将自动重连", rc=rc)
        else:
            logger.info("MQTT 已正常断开")

    def _on_publish(self, client, userdata, mid, rc=None, properties=None):
        logger.debug("MQTT 消息已发布", mid=mid)
