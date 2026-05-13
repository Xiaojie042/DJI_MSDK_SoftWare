"""Pydantic request/response schemas for REST APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.runtime_config import RuntimeConfigState


class HealthResponse(BaseModel):
    status: str = "ok"
    tcp_server: str = "running"
    tcp_clients: int = 0
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
    device_type: Optional[str] = None
    parsed_data: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)
    raw_payload: Optional[dict[str, Any]] = None


class RawHistoryResponse(BaseModel):
    total: int
    records: list[RawHistoryRecordResponse]


class FlightSessionDeviceResponse(BaseModel):
    payload_index: str
    device_type: str


class FlightSessionSummaryMetricsResponse(BaseModel):
    total_distance_m: float = 0.0
    max_altitude_m: float = 0.0
    max_speed_ms: float = 0.0
    point_count: int = 0


class FlightSessionSummaryResponse(BaseModel):
    flight_id: str
    file_name: str
    drone_id: Optional[str] = None
    takeoff_time: float
    landing_time: Optional[float] = None
    total_distance_m: float = 0.0
    max_altitude_m: float = 0.0
    attached_weather_devices: list[FlightSessionDeviceResponse] = Field(default_factory=list)


class FlightSessionsResponse(BaseModel):
    total: int
    records: list[FlightSessionSummaryResponse]


class FlightSessionDetailResponse(BaseModel):
    flight_id: str
    file_name: str
    drone_id: Optional[str] = None
    status: str = "completed"
    takeoff_time: float
    landing_time: Optional[float] = None
    summary: FlightSessionSummaryMetricsResponse
    attached_weather_devices: list[FlightSessionDeviceResponse] = Field(default_factory=list)
    telemetry_records: list[dict[str, Any]] = Field(default_factory=list)
    psdk_records: list[dict[str, Any]] = Field(default_factory=list)


class DeleteFlightSessionResponse(BaseModel):
    flight_id: str
    deleted: bool = True


class MqttTargetStatusResponse(BaseModel):
    enabled: bool = False
    connected: bool = False
    broker: str = ""
    client_id: str = ""
    topic: str = ""
    tls: bool = False
    last_error: str = ""


class SystemStatusResponse(BaseModel):
    status: str = "ok"
    tcp_server_port: int
    tcp_clients: int = 0
    mqtt_broker: str
    mqtt_connected: bool
    mqtt_targets: dict[str, MqttTargetStatusResponse] = Field(default_factory=dict)
    websocket_clients: int
    database: str
    raw_history_path: str
    flight_sessions_path: str
    runtime_config_path: str
    uptime_seconds: Optional[float] = None


class LogEntryRequest(BaseModel):
    time: str
    level: str = "INFO"
    message: str
    data: Optional[str] = None


class LogBatchRequest(BaseModel):
    entries: list[LogEntryRequest]


class LogResponse(BaseModel):
    received: int
    saved: bool = True


RuntimeConfigRequest = RuntimeConfigState
RuntimeConfigResponse = RuntimeConfigState
