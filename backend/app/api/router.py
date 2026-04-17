"""REST API routes for system status, telemetry history, and flight sessions."""

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
    return SystemStatusResponse(
        status="ok",
        tcp_server_port=settings.tcp_server_port,
        mqtt_broker=f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
        mqtt_connected=mqtt.is_connected,
        websocket_clients=ws.connection_count,
        database=settings.database_url,
        raw_history_path=settings.raw_history_path,
        flight_sessions_path=settings.flight_sessions_path,
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get("/history", response_model=FlightHistoryResponse)
async def get_flight_history(
    drone_id: Optional[str] = Query(default=None, description="Drone ID"),
    limit: int = Query(default=1000, ge=1, le=10000, description="Max records"),
) -> FlightHistoryResponse:
    storage = get_storage()
    records = await storage.get_flight_history(drone_id=drone_id, limit=limit)
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
