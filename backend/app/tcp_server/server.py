"""Async TCP server for incoming telemetry streams."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from app.config import settings
from app.models.drone import StreamMessage
from app.tcp_server.parser import TcpDataParser
from app.utils.logger import get_logger

logger = get_logger(__name__)

DataCallback = Callable[[StreamMessage], Awaitable[None]]


class DroneTcpServer:
    def __init__(
        self,
        host: str = settings.tcp_server_host,
        port: int = settings.tcp_server_port,
    ) -> None:
        self.host = host
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._callbacks: list[DataCallback] = []
        self._client_count = 0

    def register_callback(self, callback: DataCallback) -> None:
        self._callbacks.append(callback)
        logger.info("TCP callback registered", callback=callback.__qualname__)

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def client_count(self) -> int:
        return self._client_count

    async def start(self) -> None:
        if self._server is not None:
            return

        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        address = self._server.sockets[0].getsockname()
        logger.info("TCP server started", host=address[0], port=address[1])

    async def stop(self) -> None:
        if self._server is None:
            return

        server = self._server
        self._server = None
        server.close()
        await server.wait_closed()
        logger.info("TCP server stopped", port=self.port)

    async def restart(self, *, host: Optional[str] = None, port: Optional[int] = None) -> None:
        await self.stop()
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        await self.start()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        parser = TcpDataParser()
        self._client_count += 1
        logger.info("TCP client connected", peer=peer, total_clients=self._client_count)

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break

                logger.debug("TCP payload received", peer=peer, size=len(data))
                messages = parser.feed(data)
                for message in messages:
                    for callback in self._callbacks:
                        try:
                            await callback(message)
                        except Exception as exc:
                            logger.error(
                                "TCP callback failed",
                                callback=callback.__qualname__,
                                error=str(exc),
                            )
        except asyncio.CancelledError:
            logger.info("TCP client cancelled", peer=peer)
        except ConnectionResetError:
            logger.warning("TCP client connection reset", peer=peer)
        except Exception as exc:
            logger.error("TCP client failed", peer=peer, error=str(exc))
        finally:
            self._client_count = max(0, self._client_count - 1)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("TCP client disconnected", peer=peer, total_clients=self._client_count)
