"""REST API routes for system status, runtime config, and flight history."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    DeleteFlightSessionResponse,
    FlightHistoryResponse,
    FlightRecordResponse,
    FlightSessionDetailResponse,
    FlightSessionSummaryResponse,
    FlightSessionsResponse,
    HealthResponse,
    RawHistoryRecordResponse,
    RawHistoryResponse,
    RuntimeConfigRequest,
    RuntimeConfigResponse,
    SystemStatusResponse,
)
from app.config import settings

router = APIRouter(prefix="/api", tags=["API"])
_start_time = time.time()


def get_storage():
    from app.main import storage_service

    return storage_service


def get_mqtt():
    from app.main import mqtt_client

    return mqtt_client


def get_runtime_config_service():
    from app.main import runtime_config_service

    return runtime_config_service


def get_ws_manager():
    from app.main import ws_manager

    return ws_manager


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    mqtt = get_mqtt()
    ws = get_ws_manager()
    return HealthResponse(
        status="ok",
        tcp_server="running",
        mqtt_connected=mqtt.is_connected,
        websocket_clients=ws.connection_count,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    mqtt = get_mqtt()
    ws = get_ws_manager()
    runtime_config = get_runtime_config_service().get_config()
    return SystemStatusResponse(
        status="ok",
        tcp_server_port=runtime_config.connection.device_listen_port,
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
