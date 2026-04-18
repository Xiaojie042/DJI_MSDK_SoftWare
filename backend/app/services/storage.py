"""
Persistent storage service.

Responsibilities:
1. Store normalized telemetry into SQLite.
2. Persist raw telemetry snapshots into local JSONL for debugging/replay.
3. Persist each detected flight as an independent local JSON session file.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.drone import Base, DroneState, FlightRecord, PsdkDataMessage
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _to_radians(degrees: float) -> float:
    return degrees * math.pi / 180.0


def _has_valid_position(latitude: float, longitude: float) -> bool:
    return math.isfinite(latitude) and math.isfinite(longitude) and (latitude != 0.0 or longitude != 0.0)


def _haversine_distance_meters(point_a: dict[str, float], point_b: dict[str, float]) -> float:
    earth_radius = 6371000.0
    lat_delta = _to_radians(point_b["lat"] - point_a["lat"])
    lng_delta = _to_radians(point_b["lng"] - point_a["lng"])
    start_lat = _to_radians(point_a["lat"])
    end_lat = _to_radians(point_b["lat"])

    haversine = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(start_lat) * math.cos(end_lat) * math.sin(lng_delta / 2) ** 2
    )
    return 2 * earth_radius * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


class StorageService:
    """Asynchronous persistence service for telemetry and flight sessions."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        raw_history_path: Optional[str] = None,
        flight_sessions_path: Optional[str] = None,
    ):
        self._database_url = database_url or settings.database_url
        self._engine = create_async_engine(
            self._database_url,
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._raw_history_path = Path(raw_history_path or settings.raw_history_path)
        self._flight_sessions_path = Path(flight_sessions_path or settings.flight_sessions_path)
        self._session_lock = asyncio.Lock()
        self._active_flight_id: Optional[str] = None
        self._active_flight_path: Optional[Path] = None
        self._active_flight_session: Optional[dict[str, Any]] = None
        self._known_weather_devices: dict[str, dict[str, str]] = {}

    async def init_db(self) -> None:
        """Initialize database and ensure local persistence paths exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await asyncio.to_thread(self._ensure_local_paths)
        logger.info(
            "Storage initialized",
            database_url=self._database_url,
            raw_history_path=str(self._raw_history_path),
            flight_sessions_path=str(self._flight_sessions_path),
        )

    def _ensure_local_paths(self) -> None:
        self._raw_history_path.parent.mkdir(parents=True, exist_ok=True)
        self._flight_sessions_path.mkdir(parents=True, exist_ok=True)
        if not self._raw_history_path.exists():
            self._raw_history_path.touch()

    async def save_telemetry(self, state: DroneState) -> None:
        """Persist one telemetry message into SQLite, JSONL history, and flight session JSON."""
        normalized_payload = self._build_normalized_payload(state)
        raw_payload = self._build_raw_payload(state)

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
            is_flying=1 if state.is_flying else 0,
            home_distance=state.home_distance,
            gimbal_pitch=state.gimbal_pitch,
            rc_signal=state.rc_signal,
            raw_data=json.dumps(raw_payload, ensure_ascii=False),
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

        await asyncio.to_thread(self._append_raw_history, state, normalized_payload, raw_payload)
        await self._sync_flight_session_with_telemetry(state, normalized_payload, raw_payload)
        logger.debug("Telemetry persisted", drone_id=state.drone_id)

    async def save_psdk_data(self, message: PsdkDataMessage) -> None:
        """Persist PSDK raw message into local JSONL history and active flight session."""
        await asyncio.to_thread(self._append_psdk_history, message)
        await self._sync_flight_session_with_psdk(message)
        logger.debug("PSDK raw data persisted", payload_index=message.payload_index)

    def _append_raw_history(
        self,
        state: DroneState,
        normalized_payload: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        payload = {
            "stored_at": time.time(),
            "type": "flight_data",
            "drone_id": state.drone_id,
            "telemetry": normalized_payload,
            "raw_payload": raw_payload,
        }
        with self._raw_history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _append_psdk_history(self, message: PsdkDataMessage) -> None:
        payload = {
            "stored_at": time.time(),
            "type": "psdk_data",
            "timestamp": message.timestamp,
            "payload_index": message.payload_index,
            "data": message.data,
            "device_type": message.device_type,
            "parsed_data": message.parsed_data,
            "warnings": message.warnings,
            "raw_payload": message.raw_payload or {},
        }
        with self._raw_history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def _build_normalized_payload(state: DroneState) -> dict[str, Any]:
        return state.model_dump(mode="json", exclude={"raw_payload"})

    @staticmethod
    def _build_raw_payload(state: DroneState) -> dict[str, Any]:
        return state.raw_payload or state.model_dump(mode="json", exclude={"raw_payload"})

    async def _sync_flight_session_with_telemetry(
        self,
        state: DroneState,
        normalized_payload: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        async with self._session_lock:
            if self._should_rotate_active_session(state):
                await self._finalize_active_flight_session(state.timestamp)

            if state.is_flying and self._active_flight_session is None:
                await self._start_flight_session(state)

            if self._active_flight_session is None:
                return

            telemetry_record = {
                "timestamp": state.timestamp,
                "telemetry": normalized_payload,
                "raw_payload": raw_payload,
            }
            self._active_flight_session["telemetry_records"].append(telemetry_record)
            self._update_flight_summary_with_state(self._active_flight_session, state)
            await self._persist_active_flight_session()

            if not state.is_flying:
                await self._finalize_active_flight_session(state.timestamp)

    async def _sync_flight_session_with_psdk(self, message: PsdkDataMessage) -> None:
        async with self._session_lock:
            device = {
                "payload_index": message.payload_index,
                "device_type": message.device_type,
            }
            self._register_weather_device(device)

            if self._active_flight_session is None:
                return

            self._merge_weather_devices(self._active_flight_session, [device])
            self._active_flight_session["psdk_records"].append(
                {
                    "timestamp": message.timestamp,
                    "payload_index": message.payload_index,
                    "device_type": message.device_type,
                    "data": message.data,
                    "parsed_data": message.parsed_data,
                    "warnings": message.warnings,
                    "raw_payload": message.raw_payload or {},
                }
            )
            await self._persist_active_flight_session()

    def _should_rotate_active_session(self, state: DroneState) -> bool:
        if not self._active_flight_session:
            return False
        active_drone_id = self._active_flight_session.get("drone_id")
        return bool(active_drone_id and active_drone_id != state.drone_id)

    async def _start_flight_session(self, state: DroneState) -> None:
        flight_id = await asyncio.to_thread(self._generate_flight_id, state.timestamp)
        file_path = self._flight_sessions_path / f"{flight_id}.json"
        session_data = {
            "flight_id": flight_id,
            "file_name": file_path.name,
            "drone_id": state.drone_id,
            "status": "active",
            "takeoff_time": state.timestamp,
            "landing_time": None,
            "summary": {
                "total_distance_m": 0.0,
                "max_altitude_m": max(float(state.position.altitude), 0.0),
                "max_speed_ms": max(float(state.velocity.horizontal), 0.0),
                "point_count": 0,
            },
            "attached_weather_devices": self._list_known_weather_devices(),
            "telemetry_records": [],
            "psdk_records": [],
        }

        self._active_flight_id = flight_id
        self._active_flight_path = file_path
        self._active_flight_session = session_data
        await self._persist_active_flight_session()

    async def _finalize_active_flight_session(self, landing_time: Optional[float] = None) -> None:
        if not self._active_flight_session:
            return

        telemetry_records = self._active_flight_session.get("telemetry_records", [])
        resolved_landing_time = landing_time
        if resolved_landing_time is None and telemetry_records:
            resolved_landing_time = telemetry_records[-1].get("timestamp")

        self._active_flight_session["status"] = "completed"
        self._active_flight_session["landing_time"] = resolved_landing_time
        await self._persist_active_flight_session()

        self._active_flight_id = None
        self._active_flight_path = None
        self._active_flight_session = None

    async def _persist_active_flight_session(self) -> None:
        if not self._active_flight_path or not self._active_flight_session:
            return
        payload = json.loads(json.dumps(self._active_flight_session, ensure_ascii=False))
        await asyncio.to_thread(self._write_json_file, self._active_flight_path, payload)

    def _update_flight_summary_with_state(self, flight_session: dict[str, Any], state: DroneState) -> None:
        summary = flight_session.setdefault(
            "summary",
            {
                "total_distance_m": 0.0,
                "max_altitude_m": 0.0,
                "max_speed_ms": 0.0,
                "point_count": 0,
            },
        )
        telemetry_records = flight_session.get("telemetry_records", [])
        summary["point_count"] = len(telemetry_records)
        summary["max_altitude_m"] = max(summary.get("max_altitude_m", 0.0), float(state.position.altitude))
        summary["max_speed_ms"] = max(summary.get("max_speed_ms", 0.0), float(state.velocity.horizontal))

        if len(telemetry_records) < 2:
            return

        previous_state = telemetry_records[-2].get("telemetry", {})
        previous_position = previous_state.get("position", {})
        current_position = {
            "latitude": float(state.position.latitude),
            "longitude": float(state.position.longitude),
        }

        prev_lat = float(previous_position.get("latitude", 0.0))
        prev_lng = float(previous_position.get("longitude", 0.0))
        cur_lat = current_position["latitude"]
        cur_lng = current_position["longitude"]

        if not (_has_valid_position(prev_lat, prev_lng) and _has_valid_position(cur_lat, cur_lng)):
            return

        distance = _haversine_distance_meters(
            {"lat": prev_lat, "lng": prev_lng},
            {"lat": cur_lat, "lng": cur_lng},
        )
        summary["total_distance_m"] = round(summary.get("total_distance_m", 0.0) + distance, 3)

    def _register_weather_device(self, device: dict[str, str]) -> None:
        key = f"{device['payload_index']}::{device['device_type']}"
        self._known_weather_devices[key] = device

    def _list_known_weather_devices(self) -> list[dict[str, str]]:
        return sorted(self._known_weather_devices.values(), key=lambda item: (item["payload_index"], item["device_type"]))

    def _merge_weather_devices(
        self,
        flight_session: dict[str, Any],
        devices: list[dict[str, str]],
    ) -> None:
        merged = {
            f"{item['payload_index']}::{item['device_type']}": item
            for item in flight_session.get("attached_weather_devices", [])
        }
        for item in devices:
            merged[f"{item['payload_index']}::{item['device_type']}"] = item
        flight_session["attached_weather_devices"] = sorted(
            merged.values(),
            key=lambda entry: (entry["payload_index"], entry["device_type"]),
        )

    def _generate_flight_id(self, timestamp: float) -> str:
        base_name = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
        candidate = base_name
        index = 1
        while (self._flight_sessions_path / f"{candidate}.json").exists():
            candidate = f"{base_name}_{index}"
            index += 1
        return candidate

    def _write_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _read_json_file(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _resolve_flight_session_path(self, flight_id: str) -> Path:
        safe_name = Path(flight_id).name
        if safe_name.endswith(".json"):
            candidate = self._flight_sessions_path / safe_name
        else:
            candidate = self._flight_sessions_path / f"{safe_name}.json"
        return candidate

    def _build_flight_session_summary(self, session_data: dict[str, Any]) -> dict[str, Any]:
        summary = session_data.get("summary", {})
        return {
            "flight_id": session_data.get("flight_id"),
            "file_name": session_data.get("file_name"),
            "drone_id": session_data.get("drone_id"),
            "takeoff_time": session_data.get("takeoff_time"),
            "landing_time": session_data.get("landing_time"),
            "total_distance_m": float(summary.get("total_distance_m", 0.0)),
            "max_altitude_m": float(summary.get("max_altitude_m", 0.0)),
            "attached_weather_devices": session_data.get("attached_weather_devices", []),
        }

    async def get_flight_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        return await asyncio.to_thread(self._list_flight_sessions_sync, safe_limit)

    def _list_flight_sessions_sync(self, limit: int) -> list[dict[str, Any]]:
        if not self._flight_sessions_path.exists():
            return []

        sessions: list[dict[str, Any]] = []
        for path in self._flight_sessions_path.glob("*.json"):
            try:
                session_data = self._read_json_file(path)
                sessions.append(self._build_flight_session_summary(session_data))
            except Exception as exc:
                logger.warning("Skipping invalid flight session file", path=str(path), error=str(exc))

        sessions.sort(key=lambda item: item.get("takeoff_time") or 0.0, reverse=True)
        return sessions[:limit]

    async def get_flight_session(self, flight_id: str) -> Optional[dict[str, Any]]:
        path = self._resolve_flight_session_path(flight_id)
        return await asyncio.to_thread(self._read_flight_session_sync, path)

    def _read_flight_session_sync(self, path: Path) -> Optional[dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return self._read_json_file(path)
        except Exception as exc:
            logger.error("Failed to read flight session file", path=str(path), error=str(exc))
            return None

    async def delete_flight_session(self, flight_id: str) -> bool:
        async with self._session_lock:
            path = self._resolve_flight_session_path(flight_id)
            session_data = await asyncio.to_thread(self._read_flight_session_sync, path)
            if not session_data:
                return False

            if self._active_flight_id == session_data.get("flight_id"):
                self._active_flight_id = None
                self._active_flight_path = None
                self._active_flight_session = None

            await self._delete_session_related_records(session_data)
            await asyncio.to_thread(self._delete_flight_session_file, path)
            return True

    async def _delete_session_related_records(self, session_data: dict[str, Any]) -> None:
        await asyncio.gather(
            self._delete_session_db_records(session_data),
            asyncio.to_thread(self._prune_raw_history_for_session, session_data),
        )

    async def _delete_session_db_records(self, session_data: dict[str, Any]) -> None:
        drone_id = session_data.get("drone_id")
        start_time = self._coerce_timestamp(session_data.get("takeoff_time"))
        end_time = self._resolve_session_end_time(session_data)

        if not drone_id or start_time is None or end_time is None:
            return

        async with self._session_factory() as session:
            stmt = delete(FlightRecord).where(
                FlightRecord.drone_id == drone_id,
                FlightRecord.timestamp >= start_time,
                FlightRecord.timestamp <= end_time,
            )
            await session.execute(stmt)
            await session.commit()

    def _delete_flight_session_file(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def _prune_raw_history_for_session(self, session_data: dict[str, Any]) -> None:
        if not self._raw_history_path.exists():
            return

        start_time = self._coerce_timestamp(session_data.get("takeoff_time"))
        end_time = self._resolve_session_end_time(session_data)
        drone_id = session_data.get("drone_id")

        if start_time is None or end_time is None:
            return

        retained_lines: list[str] = []
        with self._raw_history_path.open("r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue

                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    retained_lines.append(line)
                    continue

                if not self._belongs_to_session(payload, drone_id, start_time, end_time):
                    retained_lines.append(line)

        with self._raw_history_path.open("w", encoding="utf-8") as f:
            f.writelines(retained_lines)

    def _belongs_to_session(
        self,
        payload: dict[str, Any],
        drone_id: Optional[str],
        start_time: float,
        end_time: float,
    ) -> bool:
        payload_type = payload.get("type")

        if payload_type == "flight_data":
            payload_drone_id = payload.get("drone_id")
            telemetry = payload.get("telemetry", {})
            payload_time = self._coerce_timestamp(telemetry.get("timestamp"))
            return bool(
                payload_drone_id == drone_id
                and payload_time is not None
                and start_time <= payload_time <= end_time
            )

        if payload_type == "psdk_data":
            payload_time = self._coerce_timestamp(payload.get("timestamp"))
            return bool(payload_time is not None and start_time <= payload_time <= end_time)

        return False

    def _resolve_session_end_time(self, session_data: dict[str, Any]) -> Optional[float]:
        landing_time = self._coerce_timestamp(session_data.get("landing_time"))
        if landing_time is not None:
            return landing_time

        telemetry_records = session_data.get("telemetry_records", [])
        if telemetry_records:
            return self._coerce_timestamp(telemetry_records[-1].get("timestamp"))
        return None

    def _coerce_timestamp(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                try:
                    return datetime.fromisoformat(value).timestamp()
                except ValueError:
                    return None
        return None

    async def get_flight_history(
        self,
        drone_id: Optional[str] = None,
        limit: int = 1000,
        latest_session_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch latest normalized telemetry history from SQLite."""
        session_window: tuple[Optional[float], Optional[float]] = (None, None)

        async with self._session_factory() as session:
            target_drone_id = drone_id or await self._get_latest_drone_id(session)
            if not target_drone_id:
                return []

            if latest_session_only:
                session_window = await asyncio.to_thread(
                    self._get_latest_session_window_sync,
                    target_drone_id,
                )

            stmt = select(FlightRecord).where(FlightRecord.drone_id == target_drone_id)
            start_time, end_time = session_window
            if start_time is not None:
                stmt = stmt.where(FlightRecord.timestamp >= start_time)
            if end_time is not None:
                stmt = stmt.where(FlightRecord.timestamp <= end_time)

            stmt = stmt.order_by(FlightRecord.id.desc()).limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()

        return [
            {
                "id": record.id,
                "drone_id": record.drone_id,
                "timestamp": record.timestamp,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "altitude": record.altitude,
                "heading": record.heading,
                "horizontal_speed": record.horizontal_speed,
                "vertical_speed": record.vertical_speed,
                "battery_percent": record.battery_percent,
                "battery_voltage": record.battery_voltage,
                "battery_temperature": record.battery_temperature,
                "gps_signal": record.gps_signal,
                "flight_mode": record.flight_mode,
                "is_flying": bool(record.is_flying),
                "home_distance": record.home_distance,
                "gimbal_pitch": record.gimbal_pitch,
                "rc_signal": record.rc_signal,
            }
            for record in records
        ]

    async def _get_latest_drone_id(self, session: AsyncSession) -> Optional[str]:
        stmt = select(FlightRecord.drone_id).order_by(FlightRecord.id.desc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _get_latest_session_window_sync(self, drone_id: str) -> tuple[Optional[float], Optional[float]]:
        for session_data in self._list_flight_sessions_sync(limit=500):
            if session_data.get("drone_id") != drone_id:
                continue

            start_time = self._coerce_timestamp(session_data.get("takeoff_time"))
            end_time = self._coerce_timestamp(session_data.get("landing_time"))
            if start_time is not None:
                return start_time, end_time

        return None, None

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
        async with self._session_lock:
            if self._active_flight_session:
                await self._finalize_active_flight_session()
        await self._engine.dispose()
        logger.info("Storage closed")
