"""Pydantic request/response schemas for REST APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    tcp_server: str = "running"
    mqtt_connected: bool = False
    websocket_clients: int = 0


class FlightHistoryQuery(BaseModel):
    drone_id: str = Field(default="DJI-001", description="Drone ID")
    limit: int = Field(default=1000, ge=1, le=10000, description="Max records")


class FlightRecordResponse(BaseModel):
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
    battery_voltage: float = 0.0
    battery_temperature: float = 0.0
    gps_signal: int = 0
    flight_mode: str
    is_flying: bool
    home_distance: float = 0.0
    gimbal_pitch: float = 0.0
    rc_signal: Optional[int] = None


class FlightHistoryResponse(BaseModel):
    total: int
    records: list[FlightRecordResponse]


class RawHistoryRecordResponse(BaseModel):
    stored_at: float
    drone_id: Optional[str] = None
    type: Optional[str] = None
    telemetry: Optional[dict[str, Any]] = None
    timestamp: Optional[float] = None
    payload_index: Optional[str] = None
    data: Optional[str] = None
    raw_payload: Optional[dict[str, Any]] = None


class RawHistoryResponse(BaseModel):
    total: int
    records: list[RawHistoryRecordResponse]


class SystemStatusResponse(BaseModel):
    status: str = "ok"
    tcp_server_port: int
    mqtt_broker: str
    mqtt_connected: bool
    websocket_clients: int
    database: str
    raw_history_path: str
    uptime_seconds: Optional[float] = None
