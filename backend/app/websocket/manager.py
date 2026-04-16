"""
WebSocket 连接池管理器
管理所有前端 WebSocket 连接，支持广播推送
"""

from __future__ import annotations

import json
from typing import Set

from fastapi import WebSocket

from app.models.drone import StreamMessage
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """
    WebSocket 连接池管理器

    维护所有已连接的前端 WebSocket 客户端，
    提供广播功能将无人机数据实时推送给所有客户端。
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WebSocket 客户端已连接", total=len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除断开的 WebSocket 连接"""
        self._connections.discard(websocket)
        logger.info("WebSocket 客户端已断开", total=len(self._connections))

    async def broadcast(self, message: StreamMessage) -> None:
        """
        向所有已连接的 WebSocket 客户端广播无人机状态

        Args:
            message: 解析后的实时消息
        """
        if not self._connections:
            return

        # 序列化一次，广播给所有客户端
        payload = message.model_dump_json()

        disconnected: list[WebSocket] = []

        for ws in self._connections.copy():
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning("WebSocket 发送失败，标记断开", error=str(e))
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self._connections.discard(ws)

    async def broadcast_json(self, data: dict) -> None:
        """广播任意 JSON 数据"""
        if not self._connections:
            return

        payload = json.dumps(data)
        disconnected: list[WebSocket] = []

        for ws in self._connections.copy():
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._connections)
