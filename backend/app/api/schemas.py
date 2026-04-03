"""
Pydantic 请求/响应模型
供 REST API 使用
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    tcp_server: str = "running"
    mqtt_connected: bool = False
    websocket_clients: int = 0


class FlightHistoryQuery(BaseModel):
    """飞行历史查询参数"""
    drone_id: str = Field(default="DJI-001", description="无人机 ID")
    limit: int = Field(default=1000, ge=1, le=10000, description="返回记录数上限")


class FlightRecordResponse(BaseModel):
    """飞行记录响应"""
    id: int
    drone_id: str
    timestamp: float
    latitude: float
    longitude: float
    altitude: float
    heading: float
    horizontal_speed: float
    vertical_speed: float
    battery_percent: int
    flight_mode: str
    is_flying: bool


class FlightHistoryResponse(BaseModel):
    """飞行历史列表响应"""
    total: int
    records: list[FlightRecordResponse]


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    status: str = "ok"
    tcp_server_port: int
    mqtt_broker: str
    mqtt_connected: bool
    websocket_clients: int
    database: str
    uptime_seconds: Optional[float] = None
