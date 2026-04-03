"""
REST API 路由
提供系统状态查询和历史数据接口
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from app.api.schemas import (
    HealthResponse,
    FlightHistoryResponse,
    FlightRecordResponse,
    SystemStatusResponse,
)
from app.config import settings

router = APIRouter(prefix="/api", tags=["API"])

# 启动时间 (用于计算 uptime)
_start_time = time.time()


def get_storage():
    """获取 StorageService 依赖 (在 main.py 中注入)"""
    from app.main import storage_service
    return storage_service


def get_mqtt():
    """获取 MqttClient 依赖"""
    from app.main import mqtt_client
    return mqtt_client


def get_ws_manager():
    """获取 WebSocketManager 依赖"""
    from app.main import ws_manager
    return ws_manager


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    mqtt = get_mqtt()
    ws = get_ws_manager()
    return HealthResponse(
        status="ok",
        tcp_server="running",
        mqtt_connected=mqtt.is_connected,
        websocket_clients=ws.connection_count,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """系统详细状态"""
    mqtt = get_mqtt()
    ws = get_ws_manager()
    return SystemStatusResponse(
        status="ok",
        tcp_server_port=settings.tcp_server_port,
        mqtt_broker=f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
        mqtt_connected=mqtt.is_connected,
        websocket_clients=ws.connection_count,
        database=settings.database_url,
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get("/history", response_model=FlightHistoryResponse)
async def get_flight_history(
    drone_id: str = Query(default="DJI-001", description="无人机 ID"),
    limit: int = Query(default=1000, ge=1, le=10000, description="返回记录数"),
):
    """查询飞行历史记录"""
    storage = get_storage()
    records = await storage.get_flight_history(drone_id=drone_id, limit=limit)
    return FlightHistoryResponse(
        total=len(records),
        records=[FlightRecordResponse(**r) for r in records],
    )
