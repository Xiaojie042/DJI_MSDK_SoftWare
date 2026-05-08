"""FastAPI entrypoint for the DJI monitor backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.config import settings
from app.mqtt.client import MqttClient
from app.runtime_config import RuntimeConfigService
from app.services.dispatcher import DataDispatcher
from app.services.live_gateway import LiveGatewayService
from app.services.storage import StorageService
from app.tcp_server.server import DroneTcpServer
from app.utils.logger import get_logger, setup_logging
from app.websocket.handlers import websocket_endpoint
from app.websocket.manager import WebSocketManager

tcp_server = DroneTcpServer()
mqtt_client = MqttClient()
ws_manager = WebSocketManager()
storage_service = StorageService()
runtime_config_service = RuntimeConfigService(tcp_server=tcp_server, mqtt_client=mqtt_client)
live_gateway_service = LiveGatewayService()
dispatcher: Optional[DataDispatcher] = None

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dispatcher

    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting DJI drone monitor backend")
    logger.info("=" * 60)

    await storage_service.init_db()
    logger.info("Storage initialized")

    await runtime_config_service.initialize()
    mqtt_client.connect()
    logger.info("MQTT targets initialized")

    await live_gateway_service.initialize()
    logger.info("Live gateway initialized")

    dispatcher = DataDispatcher(
        mqtt_client=mqtt_client,
        ws_manager=ws_manager,
        storage=storage_service,
    )

    tcp_server.register_callback(dispatcher.dispatch)
    await tcp_server.start()

    runtime_config = runtime_config_service.get_config()
    logger.info(
        "Backend ready",
        api=f"http://{settings.api_host}:{settings.api_port}",
        tcp=f"{settings.tcp_server_host}:{runtime_config.connection.device_listen_port}",
        websocket=f"ws://{settings.api_host}:{settings.api_port}/ws",
    )

    yield

    logger.info("Stopping DJI drone monitor backend")
    await live_gateway_service.shutdown()
    await tcp_server.stop()
    mqtt_client.disconnect()
    await storage_service.close()
    logger.info("Backend stopped cleanly")


app = FastAPI(
    title="DJI Drone Monitor Backend",
    description="Receives DJI MSDK telemetry, forwards data to MQTT, and streams updates to the frontend.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket, ws_manager)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
