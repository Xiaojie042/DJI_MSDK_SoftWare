"""
Persistent storage service.

Responsibilities:
1. Store normalized telemetry into SQLite.
2. Persist raw telemetry snapshots into local JSONL for debugging/replay.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.drone import Base, DroneState, FlightRecord
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """Asynchronous persistence service for telemetry data."""

    def __init__(self):
        self._engine = create_async_engine(
            settings.database_url,
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._raw_history_path = Path(settings.raw_history_path)

    async def init_db(self) -> None:
        """Initialize database and ensure raw-history local file exists."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await asyncio.to_thread(self._ensure_raw_history_file)
        logger.info(
            "Storage initialized",
            database_url=settings.database_url,
            raw_history_path=str(self._raw_history_path),
        )

    def _ensure_raw_history_file(self) -> None:
        self._raw_history_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._raw_history_path.exists():
            self._raw_history_path.touch()

    async def save_telemetry(self, state: DroneState) -> None:
        """
        Persist one telemetry message into SQLite and local JSONL history.
        """
        record = FlightRecord(
            drone_id=state.drone_id,
            timestamp=state.timestamp,
            latitude=state.position.latitude,
            longitude=state.position.longitude,
            altitude=state.position.altitude,
            heading=state.heading,
            horizontal_speed=state.velocity.horizontal,
            vertical_speed=state.velocity.vertical,
            battery_percent=state.battery.percent,
            battery_voltage=state.battery.voltage,
            battery_temperature=state.battery.temperature,
            gps_signal=state.gps_signal,
            flight_mode=state.flight_mode,
            is_flying=1 if state.is_flying else 0,  # SQLite does not have native bool
            home_distance=state.home_distance,
            gimbal_pitch=state.gimbal_pitch,
            rc_signal=state.rc_signal,
            raw_data=state.model_dump_json(),
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

        await asyncio.to_thread(self._append_raw_history, state)
        logger.debug("Telemetry persisted", drone_id=state.drone_id)

    def _append_raw_history(self, state: DroneState) -> None:
        payload = {
            "stored_at": time.time(),
            "drone_id": state.drone_id,
            "telemetry": state.model_dump(mode="json"),
        }
        with self._raw_history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    async def get_flight_history(
        self,
        drone_id: str = "DJI-001",
        limit: int = 1000,
    ) -> list[dict]:
        """Fetch latest normalized telemetry history from SQLite."""
        async with self._session_factory() as session:
            stmt = (
                select(FlightRecord)
                .where(FlightRecord.drone_id == drone_id)
                .order_by(FlightRecord.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

        return [
            {
                "id": r.id,
                "drone_id": r.drone_id,
                "timestamp": r.timestamp,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "altitude": r.altitude,
                "heading": r.heading,
                "horizontal_speed": r.horizontal_speed,
                "vertical_speed": r.vertical_speed,
                "battery_percent": r.battery_percent,
                "battery_voltage": r.battery_voltage,
                "battery_temperature": r.battery_temperature,
                "gps_signal": r.gps_signal,
                "flight_mode": r.flight_mode,
                "is_flying": bool(r.is_flying),
                "home_distance": r.home_distance,
                "gimbal_pitch": r.gimbal_pitch,
                "rc_signal": r.rc_signal,
            }
            for r in records
        ]

    async def get_raw_history(self, limit: int = 200) -> list[dict[str, Any]]:
        """Fetch recent raw telemetry snapshots from local JSONL file."""
        safe_limit = max(1, min(limit, 10_000))
        return await asyncio.to_thread(self._read_recent_raw_history, safe_limit)

    def _read_recent_raw_history(self, limit: int) -> list[dict[str, Any]]:
        if not self._raw_history_path.exists():
            return []

        tail: deque[str] = deque(maxlen=limit)
        with self._raw_history_path.open("r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if text:
                    tail.append(text)

        records: list[dict[str, Any]] = []
        for line in tail:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping invalid JSONL raw line", preview=line[:200])

        return records

    async def close(self) -> None:
        """Close database resources."""
        await self._engine.dispose()
        logger.info("Storage closed")
