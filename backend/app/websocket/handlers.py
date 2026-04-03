"""
WebSocket 请求处理器
处理前端 WebSocket 连接的消息（如命令下发等）
"""

from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.manager import WebSocketManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def websocket_endpoint(websocket: WebSocket, ws_manager: WebSocketManager):
    """
    WebSocket 端点处理函数

    前端连接后持续接收遥测数据推送。
    同时监听前端发来的消息（预留，如命令下发）。
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # 等待前端发来的消息 (预留功能)
            data = await websocket.receive_text()
            logger.debug("收到 WebSocket 消息", data=data[:200])

            # TODO: 处理前端命令，如请求历史数据、设置告警阈值等

    except WebSocketDisconnect:
        logger.info("WebSocket 客户端主动断开")
    except Exception as e:
        logger.error("WebSocket 处理异常", error=str(e))
    finally:
        await ws_manager.disconnect(websocket)
