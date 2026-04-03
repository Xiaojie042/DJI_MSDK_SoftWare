"""
TCP Server 实现
基于 asyncio 的异步 TCP 服务器，接收 DJI 遥控器数据流
"""

from __future__ import annotations

import asyncio
from typing import Optional, Callable, Awaitable

from app.config import settings
from app.tcp_server.parser import TcpDataParser
from app.models.drone import DroneState
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 数据回调类型: 接收 DroneState 后的处理函数
DataCallback = Callable[[DroneState], Awaitable[None]]


class DroneTcpServer:
    """
    异步 TCP 服务器

    接收 DJI MSDK Android 端通过网络接口发送的数据，
    解析后通过回调分发给 MQTT / WebSocket / DB。
    """

    def __init__(
        self,
        host: str = settings.tcp_server_host,
        port: int = settings.tcp_server_port,
    ):
        self.host = host
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._callbacks: list[DataCallback] = []
        self._client_count: int = 0

    def register_callback(self, callback: DataCallback) -> None:
        """注册数据处理回调函数"""
        self._callbacks.append(callback)
        logger.info("注册数据回调", callback=callback.__qualname__)

    async def start(self) -> None:
        """启动 TCP 服务器"""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        addr = self._server.sockets[0].getsockname()
        logger.info("TCP Server 已启动", host=addr[0], port=addr[1])

    async def stop(self) -> None:
        """停止 TCP 服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("TCP Server 已停止")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理单个 TCP 客户端连接"""
        peer = writer.get_extra_info("peername")
        self._client_count += 1
        logger.info("TCP 客户端已连接", peer=peer, total_clients=self._client_count)

        parser = TcpDataParser()

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    # 连接关闭
                    break

                logger.debug("收到 TCP 数据", size=len(data), peer=peer)

                # 解析数据
                states = parser.feed(data)
                for state in states:
                    # 分发给所有回调
                    for callback in self._callbacks:
                        try:
                            await callback(state)
                        except Exception as e:
                            logger.error(
                                "数据回调执行失败",
                                callback=callback.__qualname__,
                                error=str(e),
                            )

        except asyncio.CancelledError:
            logger.info("TCP 客户端连接被取消", peer=peer)
        except ConnectionResetError:
            logger.warning("TCP 客户端连接重置", peer=peer)
        except Exception as e:
            logger.error("TCP 客户端处理异常", peer=peer, error=str(e))
        finally:
            self._client_count -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("TCP 客户端已断开", peer=peer, total_clients=self._client_count)
