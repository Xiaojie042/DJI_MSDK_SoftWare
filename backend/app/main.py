"""
DJI 无人机实时监控系统 - FastAPI 入口
负责启动所有服务组件的生命周期管理
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import setup_logging, get_logger
from app.tcp_server.server import DroneTcpServer
from app.mqtt.client import MqttClient
from app.websocket.manager import WebSocketManager
from app.websocket.handlers import websocket_endpoint
from app.services.dispatcher import DataDispatcher
from app.services.storage import StorageService
from app.api.router import router as api_router

# ─── 全局服务实例 ──────────────────────────────────────

tcp_server = DroneTcpServer()
mqtt_client = MqttClient()
ws_manager = WebSocketManager()
storage_service = StorageService()
dispatcher: Optional[DataDispatcher] = None

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时: 初始化日志 → 初始化数据库 → 连接 MQTT → 启动 TCP Server
    关闭时: 停止 TCP Server → 断开 MQTT → 关闭数据库
    """
    global dispatcher

    # ── 启动 ──
    setup_logging()
    logger.info("=" * 60)
    logger.info("DJI 无人机实时监控系统启动中...")
    logger.info("=" * 60)

    # 1. 初始化数据库
    await storage_service.init_db()
    logger.info("✓ 数据库初始化完成")

    # 2. 连接 MQTT Broker
    try:
        mqtt_client.connect()
        logger.info("✓ MQTT 客户端已启动")
    except Exception as e:
        logger.warning(f"⚠ MQTT 连接失败 (将继续运行): {e}")

    # 3. 创建数据分发器
    dispatcher = DataDispatcher(
        mqtt_client=mqtt_client,
        ws_manager=ws_manager,
        storage=storage_service,
    )

    # 4. 启动 TCP Server 并注册回调
    tcp_server.register_callback(dispatcher.dispatch)
    await tcp_server.start()
    logger.info("✓ TCP Server 已启动")

    logger.info("=" * 60)
    logger.info(f"✓ 系统就绪 | API: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"✓ TCP Server 监听: {settings.tcp_server_host}:{settings.tcp_server_port}")
    logger.info(f"✓ WebSocket 端点: ws://{settings.api_host}:{settings.api_port}/ws")
    logger.info("=" * 60)

    yield

    # ── 关闭 ──
    logger.info("系统关闭中...")
    await tcp_server.stop()
    mqtt_client.disconnect()
    await storage_service.close()
    logger.info("系统已安全关闭")


# ─── 创建 FastAPI 应用 ────────────────────────────────

app = FastAPI(
    title="DJI 无人机实时监控系统",
    description="接收 DJI MSDK v5 遥测数据，通过 MQTT 上传云端，WebSocket 推送前端",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件 (允许 Vue 前端跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 REST API 路由
app.include_router(api_router)


# ─── WebSocket 端点 ───────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """前端 WebSocket 连接端点"""
    await websocket_endpoint(websocket, ws_manager)


# ─── 启动入口 ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
