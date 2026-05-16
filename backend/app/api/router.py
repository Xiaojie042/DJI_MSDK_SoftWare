"""REST API routes for system status, runtime config, and flight history."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    DeleteFlightSessionResponse,
    FlightHistoryResponse,
    FlightRecordResponse,
    FlightSessionDetailResponse,
    FlightSessionSummaryResponse,
    FlightSessionsResponse,
    HealthResponse,
    LogBatchRequest,
    LogResponse,
    RawHistoryRecordResponse,
    RawHistoryResponse,
    RuntimeConfigRequest,
    RuntimeConfigResponse,
    SystemStatusResponse,
)
from app.config import settings
from app.services.live_gateway import (
    Gb28181StatusResponse,
    LiveConfigResponse,
    LiveGatewayError,
    LiveLogsResponse,
    LiveRestartResponse,
    RtmpStatusResponse,
)

router = APIRouter(prefix="/api", tags=["API"])
_start_time = time.time()


def get_storage():
    from app.main import storage_service

    return storage_service


def get_mqtt():
    from app.main import mqtt_client

    return mqtt_client


def get_tcp_server():
    from app.main import tcp_server

    return tcp_server


def get_runtime_config_service():
    from app.main import runtime_config_service

    return runtime_config_service


def get_live_gateway_service():
    from app.main import live_gateway_service

    return live_gateway_service


def get_ws_manager():
    from app.main import ws_manager

    return ws_manager


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    mqtt = get_mqtt()
    ws = get_ws_manager()
    tcp = get_tcp_server()
    return HealthResponse(
        status="ok",
        tcp_server="running" if tcp.is_running else "stopped",
        tcp_clients=tcp.client_count,
        mqtt_connected=mqtt.is_connected,
        websocket_clients=ws.connection_count,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    mqtt = get_mqtt()
    ws = get_ws_manager()
    tcp = get_tcp_server()
    runtime_config = get_runtime_config_service().get_config()
    return SystemStatusResponse(
        status="ok",
        tcp_server_port=runtime_config.connection.device_listen_port,
        tcp_clients=tcp.client_count,
        mqtt_broker=mqtt.primary_broker,
        mqtt_connected=mqtt.is_connected,
        mqtt_targets=mqtt.status_snapshot,
        websocket_clients=ws.connection_count,
        database=settings.database_url,
        raw_history_path=settings.raw_history_path,
        flight_sessions_path=settings.flight_sessions_path,
        runtime_config_path=settings.runtime_config_path,
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get("/runtime-config", response_model=RuntimeConfigResponse)
async def get_runtime_config() -> RuntimeConfigResponse:
    return get_runtime_config_service().get_config()


@router.put("/runtime-config", response_model=RuntimeConfigResponse)
async def update_runtime_config(payload: RuntimeConfigRequest) -> RuntimeConfigResponse:
    runtime_config_service = get_runtime_config_service()
    try:
        return await runtime_config_service.update(payload)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to restart TCP listener: {exc}") from exc


@router.get("/history", response_model=FlightHistoryResponse)
async def get_flight_history(
    drone_id: Optional[str] = Query(default=None, description="Drone ID"),
    limit: int = Query(default=1000, ge=1, le=10000, description="Max records"),
    latest_session_only: bool = Query(
        default=False,
        description="Limit records to the latest detected flight session",
    ),
) -> FlightHistoryResponse:
    storage = get_storage()
    records = await storage.get_flight_history(
        drone_id=drone_id,
        limit=limit,
        latest_session_only=latest_session_only,
    )
    return FlightHistoryResponse(
        total=len(records),
        records=[FlightRecordResponse(**record) for record in records],
    )


@router.get("/history/raw", response_model=RawHistoryResponse)
async def get_raw_history(
    limit: int = Query(default=200, ge=1, le=10000, description="Max raw records"),
) -> RawHistoryResponse:
    storage = get_storage()
    records = await storage.get_raw_history(limit=limit)

    normalized: list[RawHistoryRecordResponse] = []
    for record in records:
        try:
            normalized.append(RawHistoryRecordResponse(**record))
        except Exception:
            continue

    return RawHistoryResponse(total=len(normalized), records=normalized)


@router.get("/flights", response_model=FlightSessionsResponse)
async def get_flights(
    limit: int = Query(default=100, ge=1, le=1000, description="Max flight sessions"),
) -> FlightSessionsResponse:
    storage = get_storage()
    records = await storage.get_flight_sessions(limit=limit)
    return FlightSessionsResponse(
        total=len(records),
        records=[FlightSessionSummaryResponse(**record) for record in records],
    )


@router.get("/flights/{flight_id}", response_model=FlightSessionDetailResponse)
async def get_flight_detail(flight_id: str) -> FlightSessionDetailResponse:
    storage = get_storage()
    session = await storage.get_flight_session(flight_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Flight session '{flight_id}' not found")

    return FlightSessionDetailResponse(**session)


@router.delete("/flights/{flight_id}", response_model=DeleteFlightSessionResponse)
async def delete_flight(flight_id: str) -> DeleteFlightSessionResponse:
    storage = get_storage()
    deleted = await storage.delete_flight_session(flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Flight session '{flight_id}' not found")

    return DeleteFlightSessionResponse(flight_id=flight_id, deleted=True)


@router.get("/live/config", response_model=LiveConfigResponse)
async def get_live_config() -> LiveConfigResponse:
    return get_live_gateway_service().get_config_response()


@router.post("/live/config", response_model=LiveConfigResponse)
async def update_live_config(payload: dict[str, Any]) -> LiveConfigResponse:
    try:
        return await get_live_gateway_service().update_config(payload)
    except LiveGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live/rtmp/start", response_model=RtmpStatusResponse)
async def start_rtmp_service() -> RtmpStatusResponse:
    try:
        return await get_live_gateway_service().start_rtmp()
    except LiveGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live/rtmp/stop", response_model=RtmpStatusResponse)
async def stop_rtmp_service() -> RtmpStatusResponse:
    return await get_live_gateway_service().stop_rtmp()


@router.get("/live/rtmp/status", response_model=RtmpStatusResponse)
async def get_rtmp_status() -> RtmpStatusResponse:
    return get_live_gateway_service().get_rtmp_status()


@router.post("/live/restart", response_model=LiveRestartResponse)
async def restart_live_services() -> LiveRestartResponse:
    try:
        return await get_live_gateway_service().restart_related_services()
    except LiveGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live/gb28181/start", response_model=Gb28181StatusResponse)
async def start_gb28181_forwarding() -> Gb28181StatusResponse:
    try:
        return await get_live_gateway_service().start_gb28181()
    except LiveGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live/gb28181/stop", response_model=Gb28181StatusResponse)
async def stop_gb28181_forwarding() -> Gb28181StatusResponse:
    return await get_live_gateway_service().stop_gb28181()


@router.get("/live/gb28181/status", response_model=Gb28181StatusResponse)
async def get_gb28181_status() -> Gb28181StatusResponse:
    return get_live_gateway_service().get_gb28181_status()


@router.get("/live/logs", response_model=LiveLogsResponse)
async def get_live_logs(
    limit: int = Query(default=200, ge=1, le=500, description="Max live gateway log lines"),
) -> LiveLogsResponse:
    return get_live_gateway_service().get_logs(limit=limit)


@router.post("/logs", response_model=LogResponse)
async def save_frontend_logs(payload: LogBatchRequest) -> LogResponse:
    """Receive frontend debug logs and save to the log/ directory."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "log")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"frontend-debug-{time.strftime('%Y%m%d')}.log")

    try:
        with open(log_file, "a", encoding="utf-8", newline="") as fh:
            for entry in payload.entries:
                line = f"[{entry.level}] {entry.time} {entry.message}"
                if entry.data:
                    line += f" | {entry.data}"
                fh.write(line + "\n")
        return LogResponse(received=len(payload.entries), saved=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write log file: {exc}") from exc
